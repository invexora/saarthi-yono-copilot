import os
import socket
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    host: str = "0.0.0.0"
    port: int = 5050
    db_path: str = "saarthi.db"
    database_url: str | None = None
    auth_mode: str = "jwt"
    jwt_secret: str | None = None
    jwt_issuer: str = "sbi-identity"
    jwt_audience: str = "saarthi-api"
    oidc_jwks_url: str | None = None
    oidc_algorithms: tuple[str, ...] = ("RS256",)
    decision_secret: str | None = None
    allowed_origins: tuple[str, ...] = ("http://localhost:8000",)
    deployment_mode: str = "local-prototype"
    data_residency: str = "not-configured"
    event_stream_mode: str = "memory"
    redis_url: str = "redis://localhost:6379/0"
    product_catalog_mode: str = "memory"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str | None = None
    neo4j_database: str = "neo4j"
    policy_manifest_path: str | None = None
    policy_minimum_approval: str = "approved"
    artifact_feed_mode: str = "local"
    artifact_signing_public_key: str | None = None
    artifact_signing_key_id: str | None = None
    audit_secret: str | None = None
    audit_key_version: str = "v1"
    high_risk_review_mode: str = "disabled"
    signal_detection_mode: str = "rules"
    signal_detection_url: str | None = None
    signal_detection_token: str | None = None
    signal_detection_minimum_confidence: float = 0.60
    customer_context_mode: str = "synthetic"
    customer_context_url: str | None = None
    customer_context_token: str | None = None
    fulfillment_mode: str = "synthetic"
    fulfillment_url: str | None = None
    fulfillment_token: str | None = None
    event_consumer_group: str = "saarthi-workers"
    event_lag_slo_max: int = 1000
    event_pending_slo_max: int = 100
    event_consumer_name: str = "worker-1"
    event_max_delivery_attempts: int = 3
    event_claim_idle_ms: int = 60000
    event_worker_block_ms: int = 1000
    event_worker_batch_size: int = 25
    event_worker_heartbeat_timeout_seconds: int = 30
    fulfillment_reconciliation_retry_seconds: int = 60
    fulfillment_reconciliation_batch_size: int = 25
    case_management_mode: str = "synthetic"
    case_management_url: str | None = None
    case_management_token: str | None = None
    case_retry_seconds: int = 60
    case_sync_interval_seconds: int = 300
    case_worker_batch_size: int = 25
    monitoring_policy_id: str = "draft-segment-outcomes-v1"
    monitoring_policy_status: str = "draft"
    monitoring_minimum_sample_size: int = 30
    monitoring_maximum_complaint_rate: float = 0.05
    monitoring_maximum_harm_rate: float = 0.02
    monitoring_minimum_conversion_ratio: float = 0.80

    @classmethod
    def from_env(cls):
        origins = tuple(
            origin.strip()
            for origin in os.environ.get("SAARTHI_ALLOWED_ORIGINS", os.environ.get("SAARTHI_ALLOWED_ORIGIN", "http://localhost:8000")).split(",")
            if origin.strip()
        )
        oidc_algorithms = tuple(
            algorithm.strip()
            for algorithm in os.environ.get("SAARTHI_OIDC_ALGORITHMS", "RS256").split(",")
            if algorithm.strip()
        )
        return cls(
            host=os.environ.get("HOST", "0.0.0.0"),
            port=int(os.environ.get("PORT", "5050")),
            db_path=os.environ.get("SAARTHI_DB_PATH", "saarthi.db"),
            database_url=os.environ.get("SAARTHI_DATABASE_URL"),
            auth_mode=os.environ.get("SAARTHI_AUTH_MODE", "jwt").lower(),
            jwt_secret=os.environ.get("SAARTHI_JWT_SECRET"),
            jwt_issuer=os.environ.get("SAARTHI_JWT_ISSUER", "sbi-identity"),
            jwt_audience=os.environ.get("SAARTHI_JWT_AUDIENCE", "saarthi-api"),
            oidc_jwks_url=os.environ.get("SAARTHI_OIDC_JWKS_URL"),
            oidc_algorithms=oidc_algorithms,
            decision_secret=os.environ.get("SAARTHI_DECISION_SECRET"),
            allowed_origins=origins,
            deployment_mode=os.environ.get("SAARTHI_DEPLOYMENT_MODE", "local-prototype"),
            data_residency=os.environ.get("SAARTHI_DATA_RESIDENCY", "not-configured"),
            event_stream_mode=os.environ.get("SAARTHI_EVENT_STREAM_MODE", "memory").lower(),
            redis_url=os.environ.get("SAARTHI_REDIS_URL", "redis://localhost:6379/0"),
            product_catalog_mode=os.environ.get("SAARTHI_PRODUCT_CATALOG_MODE", "memory").lower(),
            neo4j_uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            neo4j_user=os.environ.get("NEO4J_USER", "neo4j"),
            neo4j_password=os.environ.get("NEO4J_PASSWORD"),
            neo4j_database=os.environ.get("NEO4J_DATABASE", "neo4j"),
            policy_manifest_path=os.environ.get("SAARTHI_POLICY_MANIFEST_PATH"),
            policy_minimum_approval=os.environ.get("SAARTHI_POLICY_MINIMUM_APPROVAL", "approved").lower(),
            artifact_feed_mode=os.environ.get("SAARTHI_ARTIFACT_FEED_MODE", "local").lower(),
            artifact_signing_public_key=os.environ.get("SAARTHI_ARTIFACT_SIGNING_PUBLIC_KEY"),
            artifact_signing_key_id=os.environ.get("SAARTHI_ARTIFACT_SIGNING_KEY_ID"),
            audit_secret=os.environ.get("SAARTHI_AUDIT_SECRET"),
            audit_key_version=os.environ.get("SAARTHI_AUDIT_KEY_VERSION", "v1"),
            high_risk_review_mode=os.environ.get("SAARTHI_HIGH_RISK_REVIEW_MODE", "disabled").lower(),
            signal_detection_mode=os.environ.get("SAARTHI_SIGNAL_DETECTION_MODE", "rules").lower(),
            signal_detection_url=os.environ.get("SAARTHI_SIGNAL_DETECTION_URL"),
            signal_detection_token=os.environ.get("SAARTHI_SIGNAL_DETECTION_TOKEN"),
            signal_detection_minimum_confidence=float(os.environ.get("SAARTHI_SIGNAL_DETECTION_MINIMUM_CONFIDENCE", "0.60")),
            customer_context_mode=os.environ.get("SAARTHI_CUSTOMER_CONTEXT_MODE", "synthetic").lower(),
            customer_context_url=os.environ.get("SAARTHI_CUSTOMER_CONTEXT_URL"),
            customer_context_token=os.environ.get("SAARTHI_CUSTOMER_CONTEXT_TOKEN"),
            fulfillment_mode=os.environ.get("SAARTHI_FULFILLMENT_MODE", "synthetic").lower(),
            fulfillment_url=os.environ.get("SAARTHI_FULFILLMENT_URL"),
            fulfillment_token=os.environ.get("SAARTHI_FULFILLMENT_TOKEN"),
            event_consumer_group=os.environ.get("SAARTHI_EVENT_CONSUMER_GROUP", "saarthi-workers"),
            event_lag_slo_max=int(os.environ.get("SAARTHI_EVENT_LAG_SLO_MAX", "1000")),
            event_pending_slo_max=int(os.environ.get("SAARTHI_EVENT_PENDING_SLO_MAX", "100")),
            event_consumer_name=os.environ.get("SAARTHI_EVENT_CONSUMER_NAME", socket.gethostname()),
            event_max_delivery_attempts=int(os.environ.get("SAARTHI_EVENT_MAX_DELIVERY_ATTEMPTS", "3")),
            event_claim_idle_ms=int(os.environ.get("SAARTHI_EVENT_CLAIM_IDLE_MS", "60000")),
            event_worker_block_ms=int(os.environ.get("SAARTHI_EVENT_WORKER_BLOCK_MS", "1000")),
            event_worker_batch_size=int(os.environ.get("SAARTHI_EVENT_WORKER_BATCH_SIZE", "25")),
            event_worker_heartbeat_timeout_seconds=int(os.environ.get("SAARTHI_EVENT_WORKER_HEARTBEAT_TIMEOUT_SECONDS", "30")),
            fulfillment_reconciliation_retry_seconds=int(os.environ.get("SAARTHI_FULFILLMENT_RECONCILIATION_RETRY_SECONDS", "60")),
            fulfillment_reconciliation_batch_size=int(os.environ.get("SAARTHI_FULFILLMENT_RECONCILIATION_BATCH_SIZE", "25")),
            case_management_mode=os.environ.get("SAARTHI_CASE_MANAGEMENT_MODE", "synthetic").lower(),
            case_management_url=os.environ.get("SAARTHI_CASE_MANAGEMENT_URL"),
            case_management_token=os.environ.get("SAARTHI_CASE_MANAGEMENT_TOKEN"),
            case_retry_seconds=int(os.environ.get("SAARTHI_CASE_RETRY_SECONDS", "60")),
            case_sync_interval_seconds=int(os.environ.get("SAARTHI_CASE_SYNC_INTERVAL_SECONDS", "300")),
            case_worker_batch_size=int(os.environ.get("SAARTHI_CASE_WORKER_BATCH_SIZE", "25")),
            monitoring_policy_id=os.environ.get("SAARTHI_MONITORING_POLICY_ID", "draft-segment-outcomes-v1"),
            monitoring_policy_status=os.environ.get("SAARTHI_MONITORING_POLICY_STATUS", "draft").lower(),
            monitoring_minimum_sample_size=int(os.environ.get("SAARTHI_MONITORING_MINIMUM_SAMPLE_SIZE", "30")),
            monitoring_maximum_complaint_rate=float(os.environ.get("SAARTHI_MONITORING_MAXIMUM_COMPLAINT_RATE", "0.05")),
            monitoring_maximum_harm_rate=float(os.environ.get("SAARTHI_MONITORING_MAXIMUM_HARM_RATE", "0.02")),
            monitoring_minimum_conversion_ratio=float(os.environ.get("SAARTHI_MONITORING_MINIMUM_CONVERSION_RATIO", "0.80")),
        )

    def validate(self):
        if self.auth_mode not in {"jwt", "oidc", "development"}:
            raise RuntimeError("SAARTHI_AUTH_MODE must be jwt, oidc, or development")
        if self.auth_mode == "jwt" and not self.jwt_secret:
            raise RuntimeError("SAARTHI_JWT_SECRET is required when SAARTHI_AUTH_MODE=jwt")
        if self.auth_mode == "jwt" and len(self.jwt_secret) < 32:
            raise RuntimeError("SAARTHI_JWT_SECRET must be at least 32 characters")
        if self.auth_mode == "oidc" and not self.oidc_jwks_url:
            raise RuntimeError("SAARTHI_OIDC_JWKS_URL is required when SAARTHI_AUTH_MODE=oidc")
        if self.auth_mode == "oidc" and not self.oidc_jwks_url.startswith("https://"):
            raise RuntimeError("SAARTHI_OIDC_JWKS_URL must use HTTPS")
        if self.auth_mode == "oidc" and (not self.oidc_algorithms or any(algorithm.startswith("HS") or algorithm == "none" for algorithm in self.oidc_algorithms)):
            raise RuntimeError("OIDC must use an explicitly configured asymmetric signing algorithm")
        if not self.decision_secret:
            raise RuntimeError("SAARTHI_DECISION_SECRET is required")
        if len(self.decision_secret) < 32:
            raise RuntimeError("SAARTHI_DECISION_SECRET must be at least 32 characters")
        if not self.allowed_origins:
            raise RuntimeError("At least one allowed browser origin must be configured")
        if self.event_stream_mode not in {"memory", "redis"}:
            raise RuntimeError("SAARTHI_EVENT_STREAM_MODE must be 'memory' or 'redis'")
        if self.product_catalog_mode not in {"memory", "neo4j"}:
            raise RuntimeError("SAARTHI_PRODUCT_CATALOG_MODE must be 'memory' or 'neo4j'")
        if self.product_catalog_mode == "neo4j" and not self.neo4j_password:
            raise RuntimeError("NEO4J_PASSWORD is required when SAARTHI_PRODUCT_CATALOG_MODE=neo4j")
        if self.policy_minimum_approval not in {"draft", "demo", "approved"}:
            raise RuntimeError("SAARTHI_POLICY_MINIMUM_APPROVAL must be draft, demo, or approved")
        if self.artifact_feed_mode not in {"local", "signed"}:
            raise RuntimeError("SAARTHI_ARTIFACT_FEED_MODE must be local or signed")
        if self.artifact_feed_mode == "signed" and (
            not self.artifact_signing_public_key or not self.artifact_signing_key_id
        ):
            raise RuntimeError("Signed artifact feeds require a public key and key ID")
        if self.deployment_mode == "production" and self.artifact_feed_mode != "signed":
            raise RuntimeError("Production deployments require signed product and policy artifacts")
        if self.audit_secret is not None and len(self.audit_secret) < 32:
            raise RuntimeError("SAARTHI_AUDIT_SECRET must be at least 32 characters")
        if self.deployment_mode != "local-prototype" and not self.audit_secret:
            raise RuntimeError("SAARTHI_AUDIT_SECRET is required outside local-prototype mode")
        if self.high_risk_review_mode not in {"disabled", "required"}:
            raise RuntimeError("SAARTHI_HIGH_RISK_REVIEW_MODE must be disabled or required")
        if self.signal_detection_mode not in {"rules", "sbi_api"}:
            raise RuntimeError("SAARTHI_SIGNAL_DETECTION_MODE must be rules or sbi_api")
        if not 0 <= self.signal_detection_minimum_confidence <= 1:
            raise RuntimeError("SAARTHI_SIGNAL_DETECTION_MINIMUM_CONFIDENCE must be a probability")
        if self.signal_detection_mode == "sbi_api" and (
            not self.signal_detection_url or not self.signal_detection_token
        ):
            raise RuntimeError("SBI signal detection URL and service token are required in sbi_api mode")
        if self.deployment_mode == "production" and self.signal_detection_mode != "sbi_api":
            raise RuntimeError("Production deployments require the SBI signal detection service")
        if self.customer_context_mode not in {"synthetic", "sbi_api"}:
            raise RuntimeError("SAARTHI_CUSTOMER_CONTEXT_MODE must be synthetic or sbi_api")
        if self.customer_context_mode == "sbi_api" and (not self.customer_context_url or not self.customer_context_token):
            raise RuntimeError("SAARTHI_CUSTOMER_CONTEXT_URL and SAARTHI_CUSTOMER_CONTEXT_TOKEN are required in sbi_api mode")
        if self.deployment_mode == "production" and self.customer_context_mode != "sbi_api":
            raise RuntimeError("Production deployments require SAARTHI_CUSTOMER_CONTEXT_MODE=sbi_api")
        if self.deployment_mode == "production" and self.auth_mode != "oidc":
            raise RuntimeError("Production deployments require OIDC/JWKS authentication")
        if self.deployment_mode == "production" and not self.database_url:
            raise RuntimeError("Production deployments require SAARTHI_DATABASE_URL")
        if self.deployment_mode == "production" and self.event_stream_mode != "redis":
            raise RuntimeError("Production deployments require Redis event streaming")
        if self.deployment_mode == "production" and self.product_catalog_mode != "neo4j":
            raise RuntimeError("Production deployments require the Neo4j product catalog")
        if self.deployment_mode == "production" and self.high_risk_review_mode != "required":
            raise RuntimeError("Production deployments require high-risk human review")
        if self.deployment_mode == "production" and self.data_residency == "not-configured":
            raise RuntimeError("Production data residency must be explicitly configured")
        if self.fulfillment_mode not in {"synthetic", "sbi_api"}:
            raise RuntimeError("SAARTHI_FULFILLMENT_MODE must be synthetic or sbi_api")
        if self.fulfillment_mode == "sbi_api" and (not self.fulfillment_url or not self.fulfillment_token):
            raise RuntimeError("SAARTHI_FULFILLMENT_URL and SAARTHI_FULFILLMENT_TOKEN are required in sbi_api mode")
        if self.deployment_mode == "production" and self.fulfillment_mode != "sbi_api":
            raise RuntimeError("Production deployments require SAARTHI_FULFILLMENT_MODE=sbi_api")
        if not self.event_consumer_group or self.event_lag_slo_max < 0 or self.event_pending_slo_max < 0:
            raise RuntimeError("Event consumer group and non-negative SLO thresholds are required")
        if not self.event_consumer_name:
            raise RuntimeError("SAARTHI_EVENT_CONSUMER_NAME is required")
        if self.event_max_delivery_attempts < 1 or self.event_claim_idle_ms < 0:
            raise RuntimeError("Event retry and stale-claim settings are invalid")
        if self.event_worker_block_ms < 1 or self.event_worker_batch_size < 1:
            raise RuntimeError("Event worker polling settings must be positive")
        if self.event_worker_heartbeat_timeout_seconds < 1:
            raise RuntimeError("Event worker heartbeat timeout must be positive")
        if self.fulfillment_reconciliation_retry_seconds < 0 or self.fulfillment_reconciliation_batch_size < 1:
            raise RuntimeError("Fulfilment reconciliation settings are invalid")
        if self.case_management_mode not in {"synthetic", "sbi_api"}:
            raise RuntimeError("SAARTHI_CASE_MANAGEMENT_MODE must be synthetic or sbi_api")
        if self.case_management_mode == "sbi_api" and (not self.case_management_url or not self.case_management_token):
            raise RuntimeError("SAARTHI_CASE_MANAGEMENT_URL and SAARTHI_CASE_MANAGEMENT_TOKEN are required in sbi_api mode")
        if self.deployment_mode == "production" and self.case_management_mode != "sbi_api":
            raise RuntimeError("Production deployments require SAARTHI_CASE_MANAGEMENT_MODE=sbi_api")
        if self.case_retry_seconds < 0 or self.case_sync_interval_seconds < 1 or self.case_worker_batch_size < 1:
            raise RuntimeError("Case-management retry and polling settings are invalid")
        if self.monitoring_policy_status not in {"draft", "approved"} or not self.monitoring_policy_id:
            raise RuntimeError("Outcome-monitoring policy metadata is invalid")
        if self.monitoring_minimum_sample_size < 1:
            raise RuntimeError("Outcome-monitoring minimum sample size must be positive")
        if not 0 <= self.monitoring_maximum_complaint_rate <= 1 or not 0 <= self.monitoring_maximum_harm_rate <= 1:
            raise RuntimeError("Outcome-monitoring harm and complaint thresholds must be rates")
        if not 0 < self.monitoring_minimum_conversion_ratio <= 1:
            raise RuntimeError("Outcome-monitoring conversion ratio must be in (0, 1]")
        if self.deployment_mode == "production" and self.monitoring_policy_status != "approved":
            raise RuntimeError("Production deployments require an approved outcome-monitoring policy")

    def validate_worker(self):
        """Validate only dependencies used by the event/reconciliation worker."""
        if not self.decision_secret or len(self.decision_secret) < 32:
            raise RuntimeError("SAARTHI_DECISION_SECRET must be at least 32 characters")
        if self.audit_secret is not None and len(self.audit_secret) < 32:
            raise RuntimeError("SAARTHI_AUDIT_SECRET must be at least 32 characters")
        if self.deployment_mode != "local-prototype" and not self.audit_secret:
            raise RuntimeError("SAARTHI_AUDIT_SECRET is required outside local-prototype mode")
        if self.event_stream_mode not in {"memory", "redis"}:
            raise RuntimeError("SAARTHI_EVENT_STREAM_MODE must be 'memory' or 'redis'")
        if self.deployment_mode == "production" and self.event_stream_mode != "redis":
            raise RuntimeError("Production workers require Redis event streaming")
        if self.deployment_mode == "production" and not self.database_url:
            raise RuntimeError("Production workers require SAARTHI_DATABASE_URL")
        if self.deployment_mode == "production" and self.data_residency == "not-configured":
            raise RuntimeError("Production worker data residency must be explicitly configured")
        if self.fulfillment_mode not in {"synthetic", "sbi_api"}:
            raise RuntimeError("SAARTHI_FULFILLMENT_MODE must be synthetic or sbi_api")
        if self.fulfillment_mode == "sbi_api" and (not self.fulfillment_url or not self.fulfillment_token):
            raise RuntimeError("SAARTHI_FULFILLMENT_URL and SAARTHI_FULFILLMENT_TOKEN are required in sbi_api mode")
        if self.deployment_mode == "production" and self.fulfillment_mode != "sbi_api":
            raise RuntimeError("Production workers require SAARTHI_FULFILLMENT_MODE=sbi_api")
        if not self.event_consumer_group or not self.event_consumer_name:
            raise RuntimeError("Event consumer group and name are required")
        if self.event_max_delivery_attempts < 1 or self.event_claim_idle_ms < 0:
            raise RuntimeError("Event retry and stale-claim settings are invalid")
        if self.event_worker_block_ms < 1 or self.event_worker_batch_size < 1:
            raise RuntimeError("Event worker polling settings must be positive")
        if self.event_worker_heartbeat_timeout_seconds < 1:
            raise RuntimeError("Event worker heartbeat timeout must be positive")
        if self.fulfillment_reconciliation_retry_seconds < 0 or self.fulfillment_reconciliation_batch_size < 1:
            raise RuntimeError("Fulfilment reconciliation settings are invalid")
        if self.case_management_mode not in {"synthetic", "sbi_api"}:
            raise RuntimeError("SAARTHI_CASE_MANAGEMENT_MODE must be synthetic or sbi_api")
        if self.case_management_mode == "sbi_api" and (not self.case_management_url or not self.case_management_token):
            raise RuntimeError("SAARTHI_CASE_MANAGEMENT_URL and SAARTHI_CASE_MANAGEMENT_TOKEN are required in sbi_api mode")
        if self.deployment_mode == "production" and self.case_management_mode != "sbi_api":
            raise RuntimeError("Production workers require SAARTHI_CASE_MANAGEMENT_MODE=sbi_api")
        if self.case_retry_seconds < 0 or self.case_sync_interval_seconds < 1 or self.case_worker_batch_size < 1:
            raise RuntimeError("Case-management retry and polling settings are invalid")
