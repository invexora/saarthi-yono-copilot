from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from backend.auth import Identity, identity_dependency
from backend.audit_ledger import AuditLedger
from backend.customer_context import create_customer_context_provider
from backend.data_synthesis import CustomerDataSynthesizer
from backend.dpdp_engine import DPDPEngine
from backend.fulfillment import create_fulfillment_client
from backend.fulfillment_service import FulfillmentService
from backend.governed_artifacts import (
    ArtifactMaterializationError,
    GovernedArtifactError,
    GovernedArtifactService,
)
from backend.reconciliation_service import FulfillmentReconciliationService
from backend.case_management import create_case_management_client
from backend.operations_case_service import OperationsCaseService
from backend.outcome_monitoring import OutcomeMonitoringError, OutcomeMonitoringService
from backend.neo4j_client import Neo4jProductGraph
from backend.orchestrator import SaarthiAgentOrchestrator
from backend.persistence import create_database
from backend.redis_streams import RedisEventStream
from backend.rollout import RolloutControlError, RolloutControlService
from backend.signal_detection import SignalDetectionError, create_signal_detector
from backend.policy_catalog import PolicyCatalog
from backend.schemas import (
    AuthorizationRequest,
    AuthorizationResponse,
    AuditRecord,
    ConsentArtifact,
    ConsentRecord,
    ConsentRequest,
    ConsentRevocationResponse,
    CustomerDataExport,
    ErasureResponse,
    HealthResponse,
    OrchestrationRequest,
    OrchestrationResponse,
    ProductResponse,
    ReadinessResponse,
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    HumanReview,
    LedgerVerificationResponse,
    RecommendationPresentationResponse,
    ActionExecutionRequest,
    ActionExecutionResponse,
    EventStreamStatus,
    DeadLetterRecord,
    DeadLetterReplayResponse,
    FulfillmentReconciliationRecord,
    FulfillmentReconciliationResponse,
    ReconciliationAcknowledgementRequest,
    OperationsCaseRequest,
    OperationsCaseRecord,
    OperationsCaseResponse,
    RolloutControlRequest,
    RolloutControlDecisionRequest,
    EmergencyDisableRequest,
    RolloutControlRecord,
    RolloutControlResponse,
    OutcomeObservationRequest,
    OutcomeObservationResponse,
    OutcomeMonitoringReport,
    SignalModelEvaluationReport,
    GovernedArtifactRequest,
    GovernedArtifactDecisionRequest,
    GovernedArtifactRecord,
    GovernedArtifactResponse,
)
from backend.settings import Settings


def create_app(settings=None, database=None, event_stream=None, product_catalog=None, policy_retriever=None, customer_context_provider=None, fulfillment_client=None, case_management_client=None, signal_detector=None, artifact_service=None):
    settings = settings or Settings.from_env()
    settings.validate()
    db = database or create_database(settings)
    audit_ledger = AuditLedger(db, settings.audit_secret or settings.decision_secret, settings.audit_key_version)
    artifact_service = artifact_service or GovernedArtifactService(
        db,
        settings.artifact_signing_public_key,
        settings.artifact_signing_key_id,
        audit_ledger,
        required=settings.artifact_feed_mode == "signed",
    )
    rollout_control = RolloutControlService(
        db, settings.audit_secret or settings.decision_secret, audit_ledger,
    )
    outcome_monitoring = OutcomeMonitoringService(
        db,
        settings.audit_secret or settings.decision_secret,
        audit_ledger,
        policy_id=settings.monitoring_policy_id,
        policy_status=settings.monitoring_policy_status,
        minimum_sample_size=settings.monitoring_minimum_sample_size,
        maximum_complaint_rate=settings.monitoring_maximum_complaint_rate,
        maximum_harm_rate=settings.monitoring_maximum_harm_rate,
        minimum_conversion_ratio=settings.monitoring_minimum_conversion_ratio,
    )
    dpdp = DPDPEngine(
        db,
        decision_secret=settings.decision_secret,
        audit_ledger=audit_ledger,
        rollout_control=rollout_control,
    )
    event_stream = event_stream or RedisEventStream(
        mode=settings.event_stream_mode,
        redis_url=settings.redis_url,
    )
    event_stream.ensure_consumer_group(settings.event_consumer_group)
    product_graph = product_catalog or Neo4jProductGraph(
        mode=settings.product_catalog_mode,
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
        database=settings.neo4j_database,
    )
    policy_catalog = policy_retriever or PolicyCatalog(
        manifest_path=settings.policy_manifest_path,
        minimum_approval=settings.policy_minimum_approval,
    )
    artifact_service.configure_materializers(product_graph, policy_catalog)
    artifact_service.materialize_active()
    signal_detector = signal_detector or create_signal_detector(settings)
    customer_context = customer_context_provider or create_customer_context_provider(settings)
    fulfillment = fulfillment_client or create_fulfillment_client(settings)
    fulfillment_service = FulfillmentService(
        db, fulfillment, audit_ledger, dpdp, rollout_control,
    )
    reconciliation_service = FulfillmentReconciliationService(
        db, fulfillment, audit_ledger,
        settings.fulfillment_reconciliation_retry_seconds,
    )
    case_management = case_management_client or create_case_management_client(settings)
    operations_case_service = OperationsCaseService(
        db,
        case_management,
        audit_ledger,
        settings.case_retry_seconds,
        settings.case_sync_interval_seconds,
    )
    orchestrator = SaarthiAgentOrchestrator(
        db,
        event_stream=event_stream,
        product_catalog=product_graph,
        policy_retriever=policy_catalog,
        audit_ledger=audit_ledger,
        high_risk_review_required=settings.high_risk_review_mode == "required",
        customer_context_provider=customer_context,
        rollout_control=rollout_control,
        signal_detector=signal_detector,
    )
    orchestrator.dpdp_engine = dpdp
    synth = CustomerDataSynthesizer()
    authenticate = identity_dependency(settings)

    @asynccontextmanager
    async def lifespan(_app):
        try:
            yield
        finally:
            product_graph.close()

    app = FastAPI(
        title="Saarthi YONO Co-Pilot API",
        version="0.16-governed-artifacts",
        description="Typed decisioning and consent API for the Saarthi SBI reference implementation.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Saarthi-Demo-Customer", "X-Saarthi-Demo-Role"],
    )
    def event_consumer_health():
        current = event_stream.get_consumer_group_info(
            settings.event_consumer_group,
            settings.event_worker_heartbeat_timeout_seconds,
        )
        required = settings.event_stream_mode == "redis"
        active = current["active_consumers"]
        return {
            "name": "event_consumer",
            "mode": settings.event_stream_mode,
            "ready": active > 0 if required else True,
            "detail": f"active_consumers={active}",
        }

    def dependency_statuses():
        return [
            db.health(),
            event_stream.health(),
            event_consumer_health(),
            product_graph.health(),
            policy_catalog.health(),
            artifact_service.health(),
            signal_detector.health(),
            customer_context.health(),
            fulfillment.health(),
            case_management.health(),
        ]

    @app.get("/api/v1/health", response_model=HealthResponse, tags=["operations"])
    def health():
        return {
            "status": "ok",
            "system": "State Bank of India — Saarthi YONO Co-Pilot",
            "version": "0.16-governed-artifacts",
            "deployment_mode": settings.deployment_mode,
            "auth_mode": settings.auth_mode,
            "data_residency": settings.data_residency,
            "controls": ["authenticated-identity", "purpose-consent-gate", "pii-masking", "nudge-budget", "ed25519-artifact-verification", "four-eyes-artifact-activation", "restart-safe-artifact-materialization", "versioned-signal-detection", "signal-input-binding", "evaluated-signal-provenance", "minimum-signal-confidence", "hierarchical-rollout-controls", "four-eyes-rollout-activation", "emergency-kill-switch", "shadow-mode", "deterministic-cohorts", "idempotent-outcome-observations", "aggregate-disparity-monitoring", "minimum-sample-alerting", "single-use-authorization", "hashed-decision-tokens", "idempotent-fulfillment", "downstream-status-reconciliation", "four-eyes-operations-case-escalation", "redis-consumer-groups", "worker-heartbeat-readiness", "bounded-retry-dead-letter-replay", "data-minimized-processing-receipts", "approved-policy-provenance", "tamper-evident-audit-ledger", "compiled-langgraph-workflow", f"artifact-feed:{settings.artifact_feed_mode}", f"signal-detection:{settings.signal_detection_mode}", f"monitoring-policy:{settings.monitoring_policy_status}", f"high-risk-review:{settings.high_risk_review_mode}"],
            "simulated_components": [
                component
                for component, simulated in (
                    ("redis-stream", settings.event_stream_mode == "memory"),
                    ("neo4j-product-graph", settings.product_catalog_mode == "memory"),
                    ("local-policy-retriever", True),
                    ("versioned-rule-signal-detector", settings.signal_detection_mode == "rules"),
                    ("synthetic-customer-context", settings.customer_context_mode == "synthetic"),
                    ("synthetic-fulfillment", settings.fulfillment_mode == "synthetic"),
                    ("synthetic-case-management", settings.case_management_mode == "synthetic"),
                )
                if simulated
            ],
            "applied_migrations": db.get_applied_migrations(),
        }

    @app.get("/api/v1/ready", response_model=ReadinessResponse, tags=["operations"])
    def ready(response: Response):
        dependencies = dependency_statuses()
        is_ready = all(dependency["ready"] for dependency in dependencies)
        if not is_ready:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "ready" if is_ready else "not_ready", "dependencies": dependencies}

    @app.get("/api/v1/metrics", response_class=PlainTextResponse, tags=["operations"])
    def metrics(identity: Identity = Depends(authenticate)):
        identity.require_any_role("ops", "admin")
        current = db.get_system_metrics()
        stream_status = event_stream.get_consumer_group_info(
            settings.event_consumer_group,
            settings.event_worker_heartbeat_timeout_seconds,
        )
        monitoring = outcome_monitoring.report(window_days=30, dimension="segment")
        return (
            "# HELP saarthi_pipeline_requests_total Total requests to Saarthi agent pipeline\n"
            "# TYPE saarthi_pipeline_requests_total counter\n"
            f"saarthi_pipeline_requests_total {current['audit_records']}\n"
            "# HELP saarthi_dpdp_consents_active Total active DPDP consents\n"
            "# TYPE saarthi_dpdp_consents_active gauge\n"
            f"saarthi_dpdp_consents_active {current['active_consents']}\n"
            "# HELP saarthi_recommendations_pending Pending recommendations\n"
            "# TYPE saarthi_recommendations_pending gauge\n"
            f"saarthi_recommendations_pending {current['pending_recommendations']}\n"
            "# HELP saarthi_recommendations_authorized Authorized recommendations\n"
            "# TYPE saarthi_recommendations_authorized counter\n"
            f"saarthi_recommendations_authorized {current['authorized_recommendations']}\n"
            "# HELP saarthi_recommendations_fulfilled Confirmed downstream fulfilments\n"
            "# TYPE saarthi_recommendations_fulfilled counter\n"
            f"saarthi_recommendations_fulfilled {current['fulfilled_recommendations']}\n"
            "# HELP saarthi_event_stream_lag Undelivered events in the primary consumer group\n"
            "# TYPE saarthi_event_stream_lag gauge\n"
            f"saarthi_event_stream_lag {stream_status['lag']}\n"
            "# HELP saarthi_event_stream_pending Pending unacknowledged events\n"
            "# TYPE saarthi_event_stream_pending gauge\n"
            f"saarthi_event_stream_pending {stream_status['pending']}\n"
            "# HELP saarthi_event_dead_letters Dead-letter events awaiting operator action\n"
            "# TYPE saarthi_event_dead_letters gauge\n"
            f"saarthi_event_dead_letters {stream_status['dead_letters']}\n"
            "# HELP saarthi_event_active_consumers Consumers with a current worker heartbeat\n"
            "# TYPE saarthi_event_active_consumers gauge\n"
            f"saarthi_event_active_consumers {stream_status['active_consumers']}\n"
            "# HELP saarthi_events_processed_total Durable data-minimized processing receipts\n"
            "# TYPE saarthi_events_processed_total counter\n"
            f"saarthi_events_processed_total {current['processed_events']}\n"
            "# HELP saarthi_fulfillment_reconciliation_pending Fulfilments awaiting or retrying provider verification\n"
            "# TYPE saarthi_fulfillment_reconciliation_pending gauge\n"
            f"saarthi_fulfillment_reconciliation_pending {current['reconciliation_pending']}\n"
            "# HELP saarthi_fulfillment_reconciliation_mismatches Unresolved provider/local fulfilment discrepancies\n"
            "# TYPE saarthi_fulfillment_reconciliation_mismatches gauge\n"
            f"saarthi_fulfillment_reconciliation_mismatches {current['reconciliation_mismatches']}\n"
            "# HELP saarthi_operations_cases_pending_approval Case escalations awaiting a second approver\n"
            "# TYPE saarthi_operations_cases_pending_approval gauge\n"
            f"saarthi_operations_cases_pending_approval {current['cases_pending_approval']}\n"
            "# HELP saarthi_operations_cases_open Submitted SBI operations cases still open\n"
            "# TYPE saarthi_operations_cases_open gauge\n"
            f"saarthi_operations_cases_open {current['cases_open']}\n"
            "# HELP saarthi_operations_cases_retry Case submissions or synchronizations awaiting retry\n"
            "# TYPE saarthi_operations_cases_retry gauge\n"
            f"saarthi_operations_cases_retry {current['cases_retry']}\n"
            "# HELP saarthi_rollout_controls_pending Rollout changes awaiting independent approval\n"
            "# TYPE saarthi_rollout_controls_pending gauge\n"
            f"saarthi_rollout_controls_pending {current['rollout_pending']}\n"
            "# HELP saarthi_rollout_controls_disabled Active rollout kill switches\n"
            "# TYPE saarthi_rollout_controls_disabled gauge\n"
            f"saarthi_rollout_controls_disabled {current['rollout_disabled']}\n"
            "# HELP saarthi_rollout_controls_shadow Active shadow or partial-cohort controls\n"
            "# TYPE saarthi_rollout_controls_shadow gauge\n"
            f"saarthi_rollout_controls_shadow {current['rollout_shadow']}\n"
            "# HELP saarthi_outcome_observations Currently retained post-decision observations\n"
            "# TYPE saarthi_outcome_observations gauge\n"
            f"saarthi_outcome_observations {current['outcome_observations']}\n"
            "# HELP saarthi_outcome_harms Currently retained harm observations\n"
            "# TYPE saarthi_outcome_harms gauge\n"
            f"saarthi_outcome_harms {current['harm_outcomes']}\n"
            "# HELP saarthi_outcome_complaints Currently retained complaint observations\n"
            "# TYPE saarthi_outcome_complaints gauge\n"
            f"saarthi_outcome_complaints {current['complaint_outcomes']}\n"
            "# HELP saarthi_monitoring_alerts Current 30-day segment monitoring alerts\n"
            "# TYPE saarthi_monitoring_alerts gauge\n"
            f"saarthi_monitoring_alerts {len(monitoring['alerts'])}\n"
            "# HELP saarthi_governed_artifacts_pending Signed artifacts awaiting independent approval\n"
            "# TYPE saarthi_governed_artifacts_pending gauge\n"
            f"saarthi_governed_artifacts_pending {current['governed_artifacts_pending']}\n"
            "# HELP saarthi_governed_artifacts_active Active signed product and policy artifacts\n"
            "# TYPE saarthi_governed_artifacts_active gauge\n"
            f"saarthi_governed_artifacts_active {current['governed_artifacts_active']}\n"
        )

    @app.get("/api/v1/events/status", response_model=EventStreamStatus, tags=["operations"])
    def event_status(identity: Identity = Depends(authenticate)):
        identity.require_any_role("ops", "admin")
        current = event_stream.get_consumer_group_info(
            settings.event_consumer_group,
            settings.event_worker_heartbeat_timeout_seconds,
        )
        return {
            **current,
            "within_slo": current["active_consumers"] > 0 and current["lag"] <= settings.event_lag_slo_max and current["pending"] <= settings.event_pending_slo_max and current["dead_letters"] == 0,
        }

    @app.get("/api/v1/events/dead-letters", response_model=list[DeadLetterRecord], tags=["operations"])
    def dead_letters(
        limit: int = Query(default=50, ge=1, le=500),
        identity: Identity = Depends(authenticate),
    ):
        identity.require_any_role("ops", "admin")
        return event_stream.list_dead_letters(limit)

    @app.post("/api/v1/events/dead-letters/{dead_letter_id}/replay", response_model=DeadLetterReplayResponse, tags=["operations"])
    def replay_dead_letter(
        dead_letter_id: str,
        idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=128),
        identity: Identity = Depends(authenticate),
    ):
        identity.require_any_role("admin")
        result = event_stream.replay_dead_letter(dead_letter_id, idempotency_key)
        if not result["replayed"]:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="dead_letter_not_found")
        if not result["deduplicated"]:
            audit_ledger.append(identity.customer_id, "dead_letter_replayed", {
                "dead_letter_id": dead_letter_id,
                "event_id": result["event_id"],
                "operator_ref": audit_ledger.principal_ref(identity.subject),
            })
        return result

    @app.post("/api/v1/orchestrate", response_model=OrchestrationResponse, tags=["decisioning"])
    def orchestrate(
        request: OrchestrationRequest,
        response: Response,
        identity: Identity = Depends(authenticate),
        idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ):
        claim = db.claim_idempotency(identity.customer_id, idempotency_key)
        if claim["status"] == "replay":
            response.status_code = claim["http_status"]
            response.headers["Idempotency-Replayed"] = "true"
            return claim["response"]
        if claim["status"] == "in_progress":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="request_with_idempotency_key_in_progress")

        try:
            result = orchestrator.run_trace(
                signal=request.signal,
                details=request.details,
                customer_segment=request.segment.value,
                customer_id=identity.customer_id,
                idempotency_key=idempotency_key,
            )
            http_status = status.HTTP_200_OK
            if result.get("delivery_mode") == "consent_required":
                http_status = status.HTTP_403_FORBIDDEN
            elif result.get("delivery_mode") == "budget_exceeded":
                http_status = status.HTTP_429_TOO_MANY_REQUESTS
            elif result.get("delivery_mode") == "dependency_unavailable":
                http_status = status.HTTP_503_SERVICE_UNAVAILABLE
            if http_status == status.HTTP_503_SERVICE_UNAVAILABLE:
                db.abandon_idempotency(identity.customer_id, idempotency_key)
            else:
                db.complete_idempotency(identity.customer_id, idempotency_key, result, http_status)
            response.status_code = http_status
            return result
        except Exception:
            db.abandon_idempotency(identity.customer_id, idempotency_key)
            raise

    @app.get("/api/v1/products", response_model=list[ProductResponse], tags=["catalog"])
    def products(identity: Identity = Depends(authenticate)):
        # This route is reachable by customer identities.  The in-memory rates
        # are synthetic decision fixtures, not customer-presentable SBI terms.
        return [{**product, "rate": None} for product in product_graph.list_products()]

    @app.get("/api/v1/policies", tags=["catalog"])
    def policies(identity: Identity = Depends(authenticate)):
        identity.require_any_role("auditor", "reviewer", "ops", "admin")
        return policy_catalog.list_policies()

    @app.get("/api/v1/consent", response_model=list[ConsentRecord], tags=["privacy"])
    def consent_status(identity: Identity = Depends(authenticate)):
        return db.get_consent_status(identity.customer_id)

    @app.post("/api/v1/consent/grant", response_model=ConsentArtifact, tags=["privacy"])
    def grant_consent(request: ConsentRequest, identity: Identity = Depends(authenticate)):
        return dpdp.grant_consent(identity.customer_id, request.purpose)

    @app.post("/api/v1/consent/revoke", response_model=ConsentRevocationResponse, tags=["privacy"])
    def revoke_consent(request: ConsentRequest, identity: Identity = Depends(authenticate)):
        return dpdp.revoke_consent(identity.customer_id, request.purpose)

    @app.post("/api/v1/consent/erase", response_model=ErasureResponse, tags=["privacy"])
    def erase(identity: Identity = Depends(authenticate)):
        return dpdp.revoke_consent_and_erase(identity.customer_id)

    @app.get("/api/v1/consent/export", response_model=CustomerDataExport, tags=["privacy"])
    def export(identity: Identity = Depends(authenticate)):
        return dpdp.generate_data_portability_export(identity.customer_id)

    @app.post("/api/v1/decisions/authorize", response_model=AuthorizationResponse, tags=["decisioning"])
    def authorize(request: AuthorizationRequest, response: Response, identity: Identity = Depends(authenticate)):
        result = dpdp.authorize_recommendation(request.recommendation_id, identity.customer_id)
        response.status_code = {
            "authorized": status.HTTP_200_OK,
            "already_authorized": status.HTTP_409_CONFLICT,
            "review_required": status.HTTP_409_CONFLICT,
            "review_rejected": status.HTTP_403_FORBIDDEN,
            "offer_not_presented": status.HTTP_409_CONFLICT,
            "expired": status.HTTP_410_GONE,
            "not_found": status.HTTP_404_NOT_FOUND,
            "consent_required": status.HTTP_403_FORBIDDEN,
            "rollout_blocked": status.HTTP_423_LOCKED,
            "rollout_shadow": status.HTTP_423_LOCKED,
        }.get(result["status"], status.HTTP_400_BAD_REQUEST)
        return result

    @app.get("/api/v1/recommendations/{recommendation_id}", response_model=RecommendationPresentationResponse, tags=["decisioning"])
    def present_recommendation(recommendation_id: str, response: Response, identity: Identity = Depends(authenticate)):
        result = dpdp.present_recommendation(recommendation_id, identity.customer_id)
        response.status_code = {
            "presented": status.HTTP_200_OK,
            "already_presented": status.HTTP_200_OK,
            "already_authorized": status.HTTP_200_OK,
            "review_required": status.HTTP_409_CONFLICT,
            "review_rejected": status.HTTP_403_FORBIDDEN,
            "budget_exceeded": status.HTTP_429_TOO_MANY_REQUESTS,
            "expired": status.HTTP_410_GONE,
            "not_found": status.HTTP_404_NOT_FOUND,
            "invalid_state": status.HTTP_409_CONFLICT,
            "consent_required": status.HTTP_403_FORBIDDEN,
            "rollout_blocked": status.HTTP_423_LOCKED,
            "rollout_shadow": status.HTTP_423_LOCKED,
        }[result["status"]]
        return result

    @app.post("/api/v1/actions/execute", response_model=ActionExecutionResponse, tags=["decisioning"])
    def execute_action(request: ActionExecutionRequest, response: Response, identity: Identity = Depends(authenticate)):
        result = fulfillment_service.execute(request.recommendation_id, identity.customer_id, request.decision_token)
        response.status_code = {
            "fulfilled": status.HTTP_200_OK,
            "already_fulfilled": status.HTTP_200_OK,
            "in_progress": status.HTTP_409_CONFLICT,
            "invalid_token": status.HTTP_403_FORBIDDEN,
            "token_expired": status.HTTP_410_GONE,
            "not_authorized": status.HTTP_409_CONFLICT,
            "not_found": status.HTTP_404_NOT_FOUND,
            "dependency_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
            "consent_required": status.HTTP_403_FORBIDDEN,
            "rollout_blocked": status.HTTP_423_LOCKED,
            "rollout_shadow": status.HTTP_423_LOCKED,
        }[result["status"]]
        return result

    @app.get(
        "/api/v1/fulfillment/reconciliations",
        response_model=list[FulfillmentReconciliationRecord],
        tags=["operations"],
    )
    def fulfillment_reconciliations(
        reconciliation_status: str | None = Query(
            default=None, pattern="^(pending|checking|matched|mismatch|retry)$",
        ),
        limit: int = Query(default=100, ge=1, le=500),
        identity: Identity = Depends(authenticate),
    ):
        identity.require_any_role("ops", "admin")
        return reconciliation_service.list(reconciliation_status, limit)

    @app.post(
        "/api/v1/fulfillment/reconciliations/{recommendation_id}/run",
        response_model=FulfillmentReconciliationResponse,
        tags=["operations"],
    )
    def run_fulfillment_reconciliation(
        recommendation_id: str,
        response: Response,
        identity: Identity = Depends(authenticate),
    ):
        identity.require_any_role("ops", "admin")
        result = reconciliation_service.reconcile(recommendation_id)
        response.status_code = {
            "matched": status.HTTP_200_OK,
            "mismatch": status.HTTP_200_OK,
            "retry": status.HTTP_202_ACCEPTED,
            "already_matched": status.HTTP_200_OK,
            "in_progress": status.HTTP_409_CONFLICT,
            "not_found": status.HTTP_404_NOT_FOUND,
            "claim_lost": status.HTTP_409_CONFLICT,
            "dependency_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
        }[result["status"]]
        return result

    @app.post(
        "/api/v1/fulfillment/reconciliations/{recommendation_id}/acknowledge",
        response_model=FulfillmentReconciliationResponse,
        tags=["operations"],
    )
    def acknowledge_fulfillment_reconciliation(
        recommendation_id: str,
        request: ReconciliationAcknowledgementRequest,
        response: Response,
        identity: Identity = Depends(authenticate),
    ):
        identity.require_any_role("admin")
        result = reconciliation_service.acknowledge_mismatch(
            recommendation_id,
            audit_ledger.principal_ref(identity.subject),
            request.note,
        )
        response.status_code = (
            status.HTTP_200_OK if result["status"] == "acknowledged"
            else status.HTTP_409_CONFLICT
        )
        return result

    @app.get(
        "/api/v1/operations/cases",
        response_model=list[OperationsCaseRecord],
        tags=["operations"],
    )
    def operations_cases(
        case_status: str | None = Query(
            default=None,
            pattern="^(draft|approved|submitting|submission_retry|open|in_progress|syncing|sync_retry|resolved|closed|rejected)$",
        ),
        limit: int = Query(default=100, ge=1, le=500),
        identity: Identity = Depends(authenticate),
    ):
        identity.require_any_role("ops", "admin")
        return operations_case_service.list(case_status, limit)

    @app.post(
        "/api/v1/operations/cases",
        response_model=OperationsCaseResponse,
        tags=["operations"],
    )
    def request_operations_case(
        request: OperationsCaseRequest,
        response: Response,
        identity: Identity = Depends(authenticate),
    ):
        identity.require_any_role("ops", "admin")
        result = operations_case_service.request(
            request.recommendation_id,
            audit_ledger.principal_ref(identity.subject),
            request.summary,
        )
        response.status_code = {
            "requested": status.HTTP_201_CREATED,
            "already_requested": status.HTTP_200_OK,
            "mismatch_required": status.HTTP_409_CONFLICT,
        }[result["status"]]
        return result

    @app.post(
        "/api/v1/operations/cases/{case_id}/approve",
        response_model=OperationsCaseResponse,
        tags=["operations"],
    )
    def approve_operations_case(
        case_id: str,
        response: Response,
        identity: Identity = Depends(authenticate),
    ):
        identity.require_any_role("admin")
        result = operations_case_service.approve(
            case_id, audit_ledger.principal_ref(identity.subject),
        )
        response.status_code = {
            "approved": status.HTTP_200_OK,
            "four_eyes_required": status.HTTP_409_CONFLICT,
            "already_decided": status.HTTP_409_CONFLICT,
            "not_found": status.HTTP_404_NOT_FOUND,
        }[result["status"]]
        return result

    @app.post(
        "/api/v1/operations/cases/{case_id}/submit",
        response_model=OperationsCaseResponse,
        tags=["operations"],
    )
    def submit_operations_case(
        case_id: str,
        response: Response,
        identity: Identity = Depends(authenticate),
    ):
        identity.require_any_role("ops", "admin")
        result = operations_case_service.submit(case_id)
        response.status_code = {
            "submitted": status.HTTP_200_OK,
            "invalid_state": status.HTTP_409_CONFLICT,
            "in_progress": status.HTTP_409_CONFLICT,
            "not_found": status.HTTP_404_NOT_FOUND,
            "claim_lost": status.HTTP_409_CONFLICT,
            "dependency_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
        }[result["status"]]
        return result

    @app.post(
        "/api/v1/operations/cases/{case_id}/sync",
        response_model=OperationsCaseResponse,
        tags=["operations"],
    )
    def sync_operations_case(
        case_id: str,
        response: Response,
        identity: Identity = Depends(authenticate),
    ):
        identity.require_any_role("ops", "admin")
        result = operations_case_service.sync(case_id)
        response.status_code = {
            "synchronized": status.HTTP_200_OK,
            "invalid_state": status.HTTP_409_CONFLICT,
            "in_progress": status.HTTP_409_CONFLICT,
            "missing_reference": status.HTTP_409_CONFLICT,
            "not_found": status.HTTP_404_NOT_FOUND,
            "claim_lost": status.HTTP_409_CONFLICT,
            "dependency_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
        }[result["status"]]
        return result

    @app.post(
        "/api/v1/monitoring/outcomes",
        response_model=OutcomeObservationResponse,
        tags=["monitoring"],
    )
    def record_outcome(
        request: OutcomeObservationRequest,
        response: Response,
        identity: Identity = Depends(authenticate),
    ):
        identity.require_any_role("ops", "admin")
        try:
            result = outcome_monitoring.record(
                request.recommendation_id,
                request.source_event_id,
                request.outcome_type,
                request.source_system,
                request.evidence_digest,
                request.occurred_at,
                request.impact_score,
            )
        except OutcomeMonitoringError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error),
            )
        response.status_code = {
            "recorded": status.HTTP_201_CREATED,
            "replay": status.HTTP_200_OK,
            "idempotency_conflict": status.HTTP_409_CONFLICT,
            "not_found": status.HTTP_404_NOT_FOUND,
        }[result["status"]]
        return result

    @app.get(
        "/api/v1/monitoring/report",
        response_model=OutcomeMonitoringReport,
        tags=["monitoring"],
    )
    def monitoring_report(
        window_days: int = Query(default=30, ge=1, le=365),
        dimension: str = Query(default="segment", pattern="^(segment|signal|product)$"),
        identity: Identity = Depends(authenticate),
    ):
        identity.require_any_role("auditor", "reviewer", "ops", "admin")
        return outcome_monitoring.report(window_days, dimension)

    @app.get(
        "/api/v1/governance/artifacts",
        response_model=list[GovernedArtifactRecord],
        tags=["governance"],
    )
    def governed_artifacts(
        artifact_status: str | None = Query(
            default=None, pattern="^(pending|materializing|active|rejected|superseded)$",
        ),
        artifact_type: str | None = Query(
            default=None, pattern="^(product_catalog|policy_registry)$",
        ),
        limit: int = Query(default=200, ge=1, le=500),
        identity: Identity = Depends(authenticate),
    ):
        identity.require_any_role("auditor", "reviewer", "ops", "admin")
        return artifact_service.list(artifact_status, artifact_type, limit)

    @app.post(
        "/api/v1/governance/artifacts",
        response_model=GovernedArtifactResponse,
        tags=["governance"],
    )
    def request_governed_artifact(
        request: GovernedArtifactRequest,
        response: Response,
        identity: Identity = Depends(authenticate),
    ):
        identity.require_any_role("ops", "admin")
        try:
            result = artifact_service.request(
                request.artifact_type,
                request.version,
                request.payload,
                request.signature,
                request.signing_key_id,
                audit_ledger.principal_ref(identity.subject),
            )
        except GovernedArtifactError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error),
            )
        response.status_code = {
            "requested": status.HTTP_201_CREATED,
            "already_requested": status.HTTP_200_OK,
            "already_pending": status.HTTP_409_CONFLICT,
            "version_conflict": status.HTTP_409_CONFLICT,
        }[result["status"]]
        return result

    @app.post(
        "/api/v1/governance/artifacts/{artifact_id}/decision",
        response_model=GovernedArtifactResponse,
        tags=["governance"],
    )
    def decide_governed_artifact(
        artifact_id: str,
        request: GovernedArtifactDecisionRequest,
        response: Response,
        identity: Identity = Depends(authenticate),
    ):
        identity.require_any_role("admin")
        try:
            result = artifact_service.decide(
                artifact_id,
                request.decision,
                audit_ledger.principal_ref(identity.subject),
            )
        except (GovernedArtifactError, ArtifactMaterializationError) as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error),
            )
        response.status_code = {
            "approved": status.HTTP_200_OK,
            "rejected": status.HTTP_200_OK,
            "four_eyes_required": status.HTTP_409_CONFLICT,
            "already_decided": status.HTTP_409_CONFLICT,
            "materialization_in_progress": status.HTTP_409_CONFLICT,
            "not_found": status.HTTP_404_NOT_FOUND,
        }[result["status"]]
        return result

    @app.get(
        "/api/v1/governance/signal-model",
        response_model=SignalModelEvaluationReport,
        tags=["governance"],
    )
    def signal_model_evaluation(identity: Identity = Depends(authenticate)):
        identity.require_any_role("auditor", "reviewer", "ops", "admin")
        try:
            return signal_detector.evaluation_report()
        except SignalDetectionError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error),
            )

    @app.get(
        "/api/v1/governance/rollout-controls",
        response_model=list[RolloutControlRecord],
        tags=["governance"],
    )
    def rollout_controls(
        control_status: str | None = Query(
            default=None, pattern="^(pending|active|rejected|superseded)$",
        ),
        limit: int = Query(default=200, ge=1, le=500),
        identity: Identity = Depends(authenticate),
    ):
        identity.require_any_role("auditor", "reviewer", "ops", "admin")
        return rollout_control.list(control_status, limit)

    @app.post(
        "/api/v1/governance/rollout-controls",
        response_model=RolloutControlResponse,
        tags=["governance"],
    )
    def request_rollout_control(
        request: RolloutControlRequest,
        response: Response,
        identity: Identity = Depends(authenticate),
    ):
        identity.require_any_role("ops", "admin")
        try:
            result = rollout_control.request(
                request.scope_type,
                request.scope_value,
                request.mode,
                request.cohort_percentage,
                request.reason,
                audit_ledger.principal_ref(identity.subject),
            )
        except RolloutControlError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error),
            )
        response.status_code = {
            "requested": status.HTTP_201_CREATED,
            "already_pending": status.HTTP_409_CONFLICT,
        }[result["status"]]
        return result

    @app.post(
        "/api/v1/governance/rollout-controls/emergency-disable",
        response_model=RolloutControlResponse,
        tags=["governance"],
    )
    def emergency_disable_rollout(
        request: EmergencyDisableRequest,
        identity: Identity = Depends(authenticate),
    ):
        identity.require_any_role("admin")
        try:
            return rollout_control.emergency_disable(
                request.scope_type,
                request.scope_value,
                request.reason,
                audit_ledger.principal_ref(identity.subject),
            )
        except RolloutControlError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error),
            )

    @app.post(
        "/api/v1/governance/rollout-controls/{control_id}/decision",
        response_model=RolloutControlResponse,
        tags=["governance"],
    )
    def decide_rollout_control(
        control_id: str,
        request: RolloutControlDecisionRequest,
        response: Response,
        identity: Identity = Depends(authenticate),
    ):
        identity.require_any_role("admin")
        result = rollout_control.decide(
            control_id,
            request.decision,
            audit_ledger.principal_ref(identity.subject),
        )
        response.status_code = {
            "approved": status.HTTP_200_OK,
            "rejected": status.HTTP_200_OK,
            "four_eyes_required": status.HTTP_409_CONFLICT,
            "already_decided": status.HTTP_409_CONFLICT,
            "not_found": status.HTTP_404_NOT_FOUND,
        }[result["status"]]
        return result

    @app.get("/api/v1/reviews", response_model=list[HumanReview], tags=["governance"])
    def reviews(
        review_status: str = Query(default="pending", pattern="^(pending|approved|rejected)$"),
        limit: int = Query(default=100, ge=1, le=500),
        identity: Identity = Depends(authenticate),
    ):
        identity.require_any_role("reviewer", "admin")
        return db.list_human_reviews(review_status, limit)

    @app.post("/api/v1/reviews/{review_id}/decision", response_model=ReviewDecisionResponse, tags=["governance"])
    def decide_review(review_id: str, request: ReviewDecisionRequest, response: Response, identity: Identity = Depends(authenticate)):
        identity.require_any_role("reviewer", "admin")
        review, decision_status = dpdp.decide_human_review(review_id, request.decision, identity.subject, request.reason)
        response.status_code = {
            "decided": status.HTTP_200_OK,
            "already_decided": status.HTTP_409_CONFLICT,
            "not_found": status.HTTP_404_NOT_FOUND,
        }[decision_status]
        return {"status": decision_status, "review": review}

    @app.get("/api/v1/audit/integrity", response_model=LedgerVerificationResponse, tags=["operations"])
    def verify_audit_integrity(identity: Identity = Depends(authenticate)):
        identity.require_any_role("auditor", "ops", "admin")
        return audit_ledger.verify()

    @app.get("/api/v1/audit/logs", response_model=list[AuditRecord], tags=["operations"])
    def audit_logs(
        customer_id: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=500),
        identity: Identity = Depends(authenticate),
    ):
        identity.require_any_role("auditor", "ops", "admin")
        return db.get_audit_logs(customer_id=customer_id, limit=limit)

    @app.get("/api/v1/demo/profiles", tags=["development"])
    def demo_profiles(identity: Identity = Depends(authenticate)):
        identity.require_any_role("admin")
        if settings.auth_mode != "development":
            return Response(status_code=status.HTTP_404_NOT_FOUND)
        return [synth.generate_customer_profile() for _ in range(5)]

    return app
