import time
import uuid
from typing import TypedDict, Optional
from langgraph.graph import END, START, StateGraph

try:
    from backend.guardrails import InputGuardian, OutputGuardian
    from backend.redis_streams import RedisEventStream
    from backend.neo4j_client import Neo4jProductGraph
    from backend.vector_ingestion import DocumentVectorIngester
    from backend.database import DatabaseManager
    from backend.dpdp_engine import DPDPEngine
    from backend.decision_policy import DeterministicDecisionPolicy
    from backend.customer_context import SyntheticCustomerContextProvider
    from backend.signal_detection import VersionedRuleSignalDetector
except ImportError:
    from guardrails import InputGuardian, OutputGuardian
    from redis_streams import RedisEventStream
    from neo4j_client import Neo4jProductGraph
    from vector_ingestion import DocumentVectorIngester
    from database import DatabaseManager
    from dpdp_engine import DPDPEngine
    from decision_policy import DeterministicDecisionPolicy
    from customer_context import SyntheticCustomerContextProvider
    from signal_detection import VersionedRuleSignalDetector

# Define the State Machine context payload structure
class GraphState(TypedDict):
    raw_signal: str
    raw_details: str
    masked_details: Optional[str]
    signal_category: Optional[str]
    signal_evidence: Optional[dict]
    recommended_product_id: Optional[str]
    interest_rate: Optional[float]
    risk_tier: Optional[str]
    compliance_approved: bool
    compliance_logs: Optional[str]
    nudge_output: Optional[str]
    execution_timings: dict
    decision_token: Optional[str]
    recommendation_id: Optional[str]
    delivery_mode: Optional[str] # 'auto_fire' | 'decision_token_required' | 'support_mode' | 'budget_exceeded' | 'consent_required'
    rag_context: Optional[str]
    neo4j_query: Optional[dict]
    nudge_budget: Optional[dict]
    event_id: Optional[str]
    policy_evidence: Optional[dict]
    review_id: Optional[str]
    decision_outcome: Optional[str]
    reason_codes: list[str]
    policy_checks: list[dict]
    decision_context: Optional[dict]
    customer_context: Optional[dict]
    customer_segment: Optional[str]
    rollout_mode: Optional[str]
    customer_presentation: Optional[dict]

class SignalDetectionAgent:
    def __init__(self, detector=None):
        self.detector = detector or VersionedRuleSignalDetector()

    def detect(self, state: GraphState) -> GraphState:
        """Classifies a masked signal through a versioned detector contract."""
        start_time = time.time()
        print("[Agent: SignalDetection] Analyzing behavioral signal...")
        evidence = self.detector.classify(state["raw_signal"])
        state["signal_category"] = evidence["category"]
        state["signal_evidence"] = evidence
        state.setdefault("execution_timings", {})["node_signal_detection"] = time.time() - start_time
        return state

class RecommendationAgent:
    def __init__(self, product_catalog=None, policy_retriever=None):
        self.neo4j_client = product_catalog or Neo4jProductGraph()
        self.vector_ingester = policy_retriever or DocumentVectorIngester()

    def recommend(self, state: GraphState, customer_segment: str) -> GraphState:
        """Matches graph-governed products and retrieves approved policy evidence."""
        start_time = time.time()
        print("[Agent: Recommendation] Resolving eligible banking products...")

        category = state["signal_category"]
        neo4j_result = self.neo4j_client.query_eligibility(category, customer_segment)
        state["neo4j_query"] = neo4j_result

        evidence = self.vector_ingester.retrieve_policy(state["raw_signal"])
        state["policy_evidence"] = evidence
        state["rag_context"] = evidence["excerpt"]

        if neo4j_result:
            state["recommended_product_id"] = neo4j_result["product_id"]
            state["interest_rate"] = neo4j_result["rate"]
            state["risk_tier"] = neo4j_result["risk_tier"]
            # Rates remain decision evidence in the synthetic catalog but are not
            # customer-presented until a live, versioned SBI pricing feed exists.
            state["nudge_output"] = neo4j_result["product"]
        else:
            state["recommended_product_id"] = "NO_PRODUCT"
            state["interest_rate"] = 0.0
            state["risk_tier"] = "support"
            state["nudge_output"] = "No eligible product found."

        state.setdefault("execution_timings", {})["node_neo4j_recommendation"] = time.time() - start_time
        return state

class ComplianceAgent:
    def __init__(self, high_risk_review_required=False):
        self.policy = DeterministicDecisionPolicy()
        self.high_risk_review_required = high_risk_review_required

    def validate(self, state: GraphState) -> GraphState:
        """Checks the recommendation against active prototype decision policies."""
        start_time = time.time()
        print("[Agent: Compliance] Running internal policy checks...")
        decision = self.policy.evaluate(state, self.high_risk_review_required)
        state["decision_outcome"] = decision["outcome"]
        state["reason_codes"] = decision["reason_codes"]
        state["policy_checks"] = decision["checks"]
        state["decision_context"] = decision["context_summary"]
        state["compliance_approved"] = decision["outcome"] != "rejected"
        state["compliance_logs"] = f"{decision['policy_version']}: {decision['outcome']}"

        state.setdefault("execution_timings", {})["node_compliance_gate"] = time.time() - start_time
        return state

class SaarthiAgentOrchestrator:
    def __init__(self, db=None, event_stream=None, product_catalog=None, policy_retriever=None, audit_ledger=None, high_risk_review_required=False, customer_context_provider=None, rollout_control=None, signal_detector=None):
        self.redis_stream = event_stream or RedisEventStream()
        self.input_guardian = InputGuardian()
        self.signal_agent = SignalDetectionAgent(signal_detector)
        self.recommendation_agent = RecommendationAgent(product_catalog, policy_retriever)
        self.compliance_agent = ComplianceAgent(high_risk_review_required)
        self.output_guardian = OutputGuardian()
        self.db = db if db is not None else DatabaseManager()
        self.dpdp_engine = DPDPEngine(self.db, audit_ledger=audit_ledger)
        self.audit_ledger = audit_ledger
        self.high_risk_review_required = high_risk_review_required
        self.customer_context_provider = customer_context_provider or SyntheticCustomerContextProvider()
        self.rollout_control = rollout_control
        self.workflow_version = "saarthi-decision-graph-2026.08.3"
        self.graph = self._compile_graph()

    @staticmethod
    def _build_action_presentation(state: GraphState) -> dict:
        product = state.get("neo4j_query") or {}
        product_id = state.get("recommended_product_id")
        product_name = product.get("product") or "SBI service"
        body = state.get("nudge_output") or f"Review the available terms for {product_name}."
        return {
            "schema_version": "customer-presentation-v1",
            "product_id": product_id,
            "title": product_name,
            "body": (
                f"{body} Demo catalogue terms are not a live SBI offer; "
                "approved eligibility, pricing and disclosures must be checked before execution."
            ),
            "action_label": "Review & Continue",
            "consent_text": (
                f"Authorize this one-time action for {product_name}. "
                "Review the applicable SBI terms and disclosures before proceeding."
            ),
            "success_text": f"The configured fulfilment adapter recorded the action for {product_name}.",
            "support_only": False,
        }

    @staticmethod
    def _build_support_presentation() -> dict:
        return {
            "schema_version": "customer-presentation-v1",
            "product_id": None,
            "title": "Saarthi Support Mode",
            "body": (
                "This situation is being handled as support-only. No promotional product or "
                "financial execution is available from this recommendation. An SBI representative "
                "can review the appropriate next step."
            ),
            "action_label": None,
            "consent_text": None,
            "success_text": None,
            "support_only": True,
        }

    def _compile_graph(self):
        workflow = StateGraph(GraphState)
        workflow.add_node("input_guardian", self._input_guardian_node)
        workflow.add_node("signal_detection", self.signal_agent.detect)
        workflow.add_node("recommendation", self._recommendation_node)
        workflow.add_node("deterministic_compliance", self.compliance_agent.validate)
        workflow.add_edge(START, "input_guardian")
        workflow.add_edge("input_guardian", "signal_detection")
        workflow.add_edge("signal_detection", "recommendation")
        workflow.add_edge("recommendation", "deterministic_compliance")
        workflow.add_edge("deterministic_compliance", END)
        return workflow.compile()

    def _input_guardian_node(self, state: GraphState) -> GraphState:
        started = time.time()
        state["masked_details"] = self.input_guardian.mask_pii(state["raw_details"])
        state.setdefault("execution_timings", {})["node_input_guardian"] = time.time() - started
        return state

    def _recommendation_node(self, state: GraphState) -> GraphState:
        return self.recommendation_agent.recommend(state, state["customer_segment"])

    @staticmethod
    def _public_result(state: GraphState) -> GraphState:
        """Never return the inbound unmasked payload across the API boundary."""
        state.pop("raw_details", None)
        state.pop("customer_context", None)
        # Synthetic catalogue pricing is decision/reviewer evidence only.  It
        # must not cross the customer API boundary until an approved, live SBI
        # pricing feed is connected.
        state["interest_rate"] = None
        if state.get("neo4j_query"):
            state["neo4j_query"] = {
                key: value
                for key, value in state["neo4j_query"].items()
                if key != "rate"
            }
        if state.get("delivery_mode") == "human_review_required":
            state["recommended_product_id"] = None
            state["nudge_output"] = "A potential recommendation is pending independent review."
            state["neo4j_query"] = None
            state["customer_presentation"] = None
        if state.get("delivery_mode") == "support_mode":
            state["recommended_product_id"] = None
            state["nudge_output"] = None
            state["neo4j_query"] = None
            state["rag_context"] = None
            state["policy_evidence"] = None
        if state.get("delivery_mode") == "shadow_mode":
            state["recommended_product_id"] = None
            state["nudge_output"] = None
            state["neo4j_query"] = None
            state["rag_context"] = None
            state["policy_evidence"] = None
            state["customer_presentation"] = None
        return state

    def _blocked_state(self, signal: str, mode: str, message: str, budget=None, event_id=None) -> GraphState:
        return self._public_result({
            "raw_signal": signal,
            "masked_details": None,
            "signal_category": None,
            "signal_evidence": None,
            "recommended_product_id": None,
            "interest_rate": None,
            "risk_tier": None,
            "compliance_approved": False,
            "compliance_logs": message,
            "nudge_output": None,
            "execution_timings": {},
            "decision_token": None,
            "recommendation_id": None,
            "delivery_mode": mode,
            "rag_context": None,
            "neo4j_query": None,
            "nudge_budget": budget,
            "event_id": event_id,
            "policy_evidence": None,
            "review_id": None,
            "decision_outcome": "rejected",
            "reason_codes": [],
            "policy_checks": [],
            "decision_context": None,
            "customer_context": None,
            "customer_segment": None,
            "rollout_mode": mode if mode in {"rollout_blocked", "shadow_mode"} else None,
            "customer_presentation": None,
        })

    @staticmethod
    def _combine_rollout_mode(current, evaluation):
        if current == "disabled" or evaluation["mode"] == "disabled":
            return "disabled"
        if current == "shadow" or evaluation["mode"] == "shadow":
            return "shadow"
        return "live"

    def _audit_rollout_suppression(self, customer_id, evaluation, stage, event_id=None):
        if self.audit_ledger:
            self.audit_ledger.append(customer_id, "rollout_decision_suppressed", {
                "stage": stage,
                "mode": evaluation["mode"],
                "control_ids": evaluation["control_ids"],
                "event_id": event_id,
            })

    def run_trace(
        self,
        signal: str,
        details: str,
        customer_segment: str = 'corporate',
        customer_id: str = None,
        idempotency_key: str = None,
    ) -> GraphState:
        """Runs the sequential LangGraph DAG nodes."""
        safe_signal = self.input_guardian.mask_pii(signal)
        customer_id = customer_id or "unknown"
        print(f"\n--- Starting Saarthi Orchestrator Pipeline ---\nSignal: {safe_signal}\nSegment: {customer_segment}")

        rollout_mode = "live"
        if self.rollout_control:
            initial_rollout = self.rollout_control.evaluate(customer_id, channel="in_app")
            rollout_mode = self._combine_rollout_mode(rollout_mode, initial_rollout)
            if rollout_mode == "disabled":
                self._audit_rollout_suppression(customer_id, initial_rollout, "pre_profile")
                blocked = self._blocked_state(
                    safe_signal, "rollout_blocked", "Customer engagement is disabled by an active rollout control.",
                    self.db.get_nudge_budget_status(customer_id),
                )
                blocked["reason_codes"] = initial_rollout["reason_codes"]
                blocked["decision_outcome"] = "rollout_blocked"
                return blocked

        if not self.dpdp_engine.verify_purpose_consent(customer_id, "personalization"):
            return self._blocked_state(
                safe_signal,
                "consent_required",
                "Active personalization consent is required before behavioral profiling.",
                self.db.get_nudge_budget_status(customer_id),
            )

        try:
            customer_context = self.customer_context_provider.get_context(customer_id, customer_segment)
            trusted_segment = customer_context["customer_segment"]
        except Exception as error:
            return self._blocked_state(
                safe_signal,
                "dependency_unavailable",
                f"Customer context unavailable: {type(error).__name__}",
                self.db.get_nudge_budget_status(customer_id),
            )

        if self.rollout_control:
            segment_rollout = self.rollout_control.evaluate(
                customer_id, channel="in_app", segment=trusted_segment,
            )
            rollout_mode = self._combine_rollout_mode(rollout_mode, segment_rollout)
            if rollout_mode == "disabled":
                self._audit_rollout_suppression(customer_id, segment_rollout, "trusted_segment")
                blocked = self._blocked_state(
                    safe_signal, "rollout_blocked", "Customer engagement is disabled for this trusted segment.",
                    self.db.get_nudge_budget_status(customer_id),
                )
                blocked["reason_codes"] = segment_rollout["reason_codes"]
                blocked["decision_outcome"] = "rollout_blocked"
                return blocked

        # Initialize state
        state: GraphState = {
            "raw_signal": safe_signal,
            "raw_details": details,
            "masked_details": self.input_guardian.mask_pii(details),
            "signal_category": None,
            "signal_evidence": None,
            "recommended_product_id": None,
            "interest_rate": None,
            "risk_tier": None,
            "compliance_approved": False,
            "compliance_logs": None,
            "nudge_output": None,
            "execution_timings": {},
            "decision_token": None,
            "recommendation_id": None,
            "delivery_mode": None,
            "rag_context": None,
            "neo4j_query": None,
            "nudge_budget": None,
            "event_id": None,
            "policy_evidence": None,
            "review_id": None,
            "decision_outcome": None,
            "reason_codes": [],
            "policy_checks": [],
            "decision_context": None,
            "customer_context": customer_context,
            "customer_segment": trusted_segment,
            "rollout_mode": rollout_mode,
            "customer_presentation": None,
        }

        try:
            event = self.redis_stream.publish_event(
                'ORCHESTRATOR_TRACE',
                customer_id,
                {'signal': safe_signal, 'segment': trusted_segment},
                idempotency_key=idempotency_key,
            )
            state["event_id"] = event["event_id"]
        except Exception as error:
            return self._blocked_state(
                safe_signal,
                "dependency_unavailable",
                f"Event stream unavailable: {type(error).__name__}",
                self.db.get_nudge_budget_status(customer_id),
            )

        start_time = time.time()
        try:
            state = self.graph.invoke(state)
        except Exception as error:
            return self._blocked_state(
                safe_signal,
                "dependency_unavailable",
                f"Decision workflow unavailable: {type(error).__name__}",
                self.db.get_nudge_budget_status(customer_id),
                state["event_id"],
            )

        rollout_evaluation = {"mode": rollout_mode, "reason_codes": ["ROLLOUT_LIVE"], "control_ids": []}
        if self.rollout_control:
            rollout_evaluation = self.rollout_control.evaluate(
                customer_id,
                channel="in_app",
                segment=trusted_segment,
                signal=state["signal_category"],
                product=state["recommended_product_id"],
                model=(
                    f"{state['signal_evidence']['model_id']}:{state['signal_evidence']['model_version']}"
                    if state.get("signal_evidence") else None
                ),
            )
            rollout_mode = self._combine_rollout_mode(rollout_mode, rollout_evaluation)
            state["rollout_mode"] = rollout_mode
            state["reason_codes"] = list(dict.fromkeys(state["reason_codes"] + rollout_evaluation["reason_codes"]))
            if rollout_mode == "disabled":
                self._audit_rollout_suppression(
                    customer_id, rollout_evaluation, "post_decision", state["event_id"],
                )
                blocked = self._blocked_state(
                    safe_signal, "rollout_blocked", "The selected engagement is disabled by an active rollout control.",
                    self.db.get_nudge_budget_status(customer_id), state["event_id"],
                )
                blocked["reason_codes"] = state["reason_codes"]
                blocked["decision_outcome"] = "rollout_blocked"
                return blocked

        # Reserve promotional capacity only after dependencies and policy evaluation succeed.
        if rollout_mode == "shadow":
            state["nudge_budget"] = self.db.get_nudge_budget_status(customer_id)
        elif not state["compliance_approved"]:
            state["nudge_budget"] = self.db.get_nudge_budget_status(customer_id)
        elif state["decision_outcome"] in {"support_only", "review_required"}:
            state["nudge_budget"] = self.db.get_nudge_budget_status(customer_id)
        else:
            state["nudge_budget"] = self.db.consume_nudge_budget(customer_id)
            if not state["nudge_budget"]["allowed"]:
                print(f"[Orchestrator] Nudge budget exceeded for {customer_id}")
                return self._blocked_state(
                    safe_signal,
                    "budget_exceeded",
                    "Nudge budget exceeded",
                    state["nudge_budget"],
                    state["event_id"],
                )

        # Output Guardian screening and routing
        start_time_out = time.time()
        print("[Node: output_guardian] Screening nudge output...")
        action_presentation = self._build_action_presentation(state)
        text_to_test = " | ".join((
            f"Product: {state['nudge_output']}",
            f"rate: {state['interest_rate']}%",
            action_presentation["title"],
            action_presentation["body"],
            action_presentation["action_label"],
            action_presentation["consent_text"],
            action_presentation["success_text"],
            "Refer to KFS.",
        ))

        has_consent = self.dpdp_engine.verify_purpose_consent(customer_id, "personalization")
        is_ok, msg = self.output_guardian.verify_compliance(text_to_test, has_consent, state["risk_tier"])

        if not state["compliance_approved"]:
            is_ok = False
            msg = state["compliance_logs"]

        state["compliance_approved"] = is_ok
        state["compliance_logs"] = msg

        if is_ok and rollout_mode == "shadow":
            state["delivery_mode"] = "shadow_mode"
            state["decision_outcome"] = "shadow_only"
        elif is_ok:
            if state["decision_outcome"] == "support_only":
                state["delivery_mode"] = 'support_mode'
            elif state["decision_outcome"] == "review_required":
                state["delivery_mode"] = 'human_review_required'
            elif state["risk_tier"] == 'low':
                state["delivery_mode"] = 'auto_fire'
            elif state["risk_tier"] == 'high':
                state["delivery_mode"] = 'decision_token_required'
            else:
                state["delivery_mode"] = 'support_mode'
        else:
            state["delivery_mode"] = 'support_mode'

        if state["delivery_mode"] == "support_mode":
            state["customer_presentation"] = self._build_support_presentation()
        elif state["delivery_mode"] in {"auto_fire", "decision_token_required", "human_review_required"}:
            state["customer_presentation"] = action_presentation
        else:
            state["customer_presentation"] = None

        if is_ok and state["delivery_mode"] not in {"support_mode", "shadow_mode"}:
            state["recommendation_id"] = str(uuid.uuid4())
            initial_status = "pending_review" if state["delivery_mode"] == "human_review_required" else "presented"
            recommendation_evidence = {
                "product_name": state["neo4j_query"]["product"] if state.get("neo4j_query") else None,
                "nudge_output": state["nudge_output"],
                "policy": state["policy_evidence"],
                "decision_context": state["decision_context"],
                "reason_codes": state["reason_codes"],
                "policy_checks": state["policy_checks"],
                "customer_segment": trusted_segment,
                "signal_category": state["signal_category"],
                "signal_detection": state["signal_evidence"],
                "rollout_control_ids": rollout_evaluation["control_ids"],
                "workflow_version": self.workflow_version,
                "presentation": state["customer_presentation"],
            }
            self.db.create_recommendation_with_status(
                recommendation_id=state["recommendation_id"],
                customer_id=customer_id,
                product_id=state["recommended_product_id"],
                interest_rate=state["interest_rate"],
                risk_tier=state["risk_tier"],
                initial_status=initial_status,
                evidence=recommendation_evidence,
            )
            if initial_status == "pending_review":
                state["review_id"] = str(uuid.uuid4())
                self.db.create_human_review(
                    state["review_id"], state["recommendation_id"], customer_id,
                    "High-risk recommendation requires independent human review",
                    evidence={
                        "product_id": state["recommended_product_id"],
                        "interest_rate": state["interest_rate"],
                        "risk_tier": state["risk_tier"],
                        **recommendation_evidence,
                        "compliance_logs": state["compliance_logs"],
                    },
                )

        print(f"[Router] Delivery Mode: {state['delivery_mode']}")
        state.setdefault("execution_timings", {})["node_output_guardian"] = time.time() - start_time_out

        # Log to DB
        exec_time_ms = int((time.time() - start_time) * 1000)
        self.db.log_audit_event(
            customer_id=customer_id,
            signal=safe_signal,
            recommended_product_id=state["recommended_product_id"],
            decision_token=state.get("decision_token"),
            risk_tier=state["risk_tier"],
            delivery_mode=state["delivery_mode"],
            compliance_status=1 if state["compliance_approved"] else 0,
            execution_time_ms=exec_time_ms
        )
        if self.audit_ledger:
            self.audit_ledger.append(customer_id, "recommendation_evaluated", {
                "recommendation_id": state["recommendation_id"],
                "product_id": state["recommended_product_id"],
                "risk_tier": state["risk_tier"],
                "delivery_mode": state["delivery_mode"],
                "compliance_approved": state["compliance_approved"],
                "policy_id": state["policy_evidence"]["policy_id"] if state.get("policy_evidence") else None,
                "policy_hash": state["policy_evidence"]["content_sha256"] if state.get("policy_evidence") else None,
                "decision_outcome": state["decision_outcome"],
                "reason_codes": state["reason_codes"],
                "context_version": state["decision_context"]["context_version"] if state.get("decision_context") else None,
                "signal_model_id": state["signal_evidence"]["model_id"] if state.get("signal_evidence") else None,
                "signal_model_version": state["signal_evidence"]["model_version"] if state.get("signal_evidence") else None,
                "signal_input_digest": state["signal_evidence"]["input_digest"] if state.get("signal_evidence") else None,
                "workflow_version": self.workflow_version,
            })

        print("\n--- Pipeline Completed ---")
        return self._public_result(state)

if __name__ == "__main__":
    orchestrator = SaarthiAgentOrchestrator()
    orchestrator.dpdp_engine.grant_consent("SBI-123456", "personalization")
    result = orchestrator.run_trace(
        signal="Recurring credit card payment outflow pattern of INR 4,200/mo across external card balances",
        details="User ID: SBI-123456 | User Email: priya.sharma@example.com | Card: 4321-XXXX-XXXX-9901 | PAN: ABCDE1234F",
        customer_segment="stressed",
        customer_id="SBI-123456",
    )
    print(f"PII Sanitized Details: {result['masked_details']}")
    print(f"Product Matched: {result['recommended_product_id']} ({result['nudge_output']})")
    print(f"Compliance Audit: {result['compliance_logs']}")
    print(f"Delivery Mode: {result['delivery_mode']}")
