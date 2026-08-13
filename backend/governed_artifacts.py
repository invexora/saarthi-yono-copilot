import base64
import hashlib
import json
import re
import uuid
from datetime import datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


class GovernedArtifactError(ValueError):
    pass


class ArtifactMaterializationError(RuntimeError):
    pass


class GovernedArtifactService:
    ARTIFACT_TYPES = {"product_catalog", "policy_registry"}
    VERSION_PATTERN = re.compile(r"^[A-Za-z0-9_.:+\-/]{1,100}$")
    PUBLIC_FIELDS = (
        "artifact_id", "artifact_type", "version", "content_digest", "signing_key_id",
        "status", "requested_at", "decided_at", "effective_at",
    )
    PRODUCT_KEYS = {
        "rule_id", "trigger", "segment", "product_id", "product", "rate", "risk_tier",
        "catalog_version", "effective_from", "effective_to", "active", "product_type",
        "monthly_commitment", "max_dsti",
    }
    POLICY_KEYS = {
        "policy_id", "title", "version", "category", "source_system",
        "approval_status", "approved_by", "effective_from", "effective_to",
        "content_sha256", "content",
    }

    def __init__(
        self,
        database,
        public_key_base64=None,
        signing_key_id=None,
        audit_ledger=None,
        required=False,
    ):
        self.database = database
        self.signing_key_id = signing_key_id
        self.audit_ledger = audit_ledger
        self.required = required
        self.product_catalog = None
        self.policy_catalog = None
        self.public_key = None
        if public_key_base64:
            try:
                key_bytes = base64.b64decode(public_key_base64, validate=True)
                self.public_key = Ed25519PublicKey.from_public_bytes(key_bytes)
            except (ValueError, TypeError) as error:
                raise RuntimeError("Invalid governed-artifact Ed25519 public key") from error
        if self.public_key and not self.signing_key_id:
            raise RuntimeError("Governed-artifact signing key ID is required with a trust anchor")

    @staticmethod
    def canonical_envelope(artifact_type, version, payload):
        return json.dumps(
            {"artifactType": artifact_type, "version": version, "payload": payload},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()

    @staticmethod
    def _parse_time(value, field):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError
            return parsed
        except (AttributeError, TypeError, ValueError) as error:
            raise GovernedArtifactError(f"invalid_{field}") from error

    def _verify_signature(self, artifact_type, version, payload, signature, signing_key_id):
        if not self.public_key:
            raise GovernedArtifactError("artifact_trust_anchor_not_configured")
        if signing_key_id != self.signing_key_id:
            raise GovernedArtifactError("artifact_signing_key_not_trusted")
        try:
            signature_bytes = base64.b64decode(signature, validate=True)
            self.public_key.verify(
                signature_bytes,
                self.canonical_envelope(artifact_type, version, payload),
            )
        except (ValueError, TypeError, InvalidSignature) as error:
            raise GovernedArtifactError("artifact_signature_invalid") from error

    def _validate_product_catalog(self, version, payload):
        if set(payload) != {"catalog_version", "rules"} or payload["catalog_version"] != version:
            raise GovernedArtifactError("product_catalog_envelope_invalid")
        rules = payload["rules"]
        if not isinstance(rules, list) or not 1 <= len(rules) <= 5000:
            raise GovernedArtifactError("product_catalog_rules_invalid")
        rule_ids, eligibility_keys = set(), set()
        for rule in rules:
            if not isinstance(rule, dict) or set(rule) != self.PRODUCT_KEYS:
                raise GovernedArtifactError("product_rule_schema_invalid")
            if rule["catalog_version"] != version:
                raise GovernedArtifactError("product_rule_version_mismatch")
            if rule["trigger"] not in {"friction", "opportunity", "lifeevent", "stress"}:
                raise GovernedArtifactError("product_rule_trigger_invalid")
            if rule["segment"] not in {"corporate", "pensioner", "sme", "stressed", "student"}:
                raise GovernedArtifactError("product_rule_segment_invalid")
            if rule["risk_tier"] not in {"low", "high", "support"}:
                raise GovernedArtifactError("product_rule_risk_invalid")
            if rule["product_type"] not in {"credit", "savings", "investment", "service"}:
                raise GovernedArtifactError("product_rule_type_invalid")
            if not isinstance(rule["active"], bool):
                raise GovernedArtifactError("product_rule_active_invalid")
            numeric = (rule["rate"], rule["monthly_commitment"], rule["max_dsti"])
            if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in numeric):
                raise GovernedArtifactError("product_rule_numeric_invalid")
            if not 0 <= rule["rate"] <= 100 or rule["monthly_commitment"] < 0 or not 0 < rule["max_dsti"] <= 1:
                raise GovernedArtifactError("product_rule_limits_invalid")
            start = self._parse_time(rule["effective_from"], "effective_from")
            if rule["effective_to"] is not None and self._parse_time(rule["effective_to"], "effective_to") <= start:
                raise GovernedArtifactError("product_rule_effective_window_invalid")
            for field in ("rule_id", "product_id", "product"):
                if not isinstance(rule[field], str) or not 1 <= len(rule[field]) <= 200:
                    raise GovernedArtifactError(f"product_rule_{field}_invalid")
            eligibility_key = (rule["trigger"], rule["segment"], rule["effective_from"])
            if rule["rule_id"] in rule_ids or eligibility_key in eligibility_keys:
                raise GovernedArtifactError("product_rule_duplicate")
            rule_ids.add(rule["rule_id"])
            eligibility_keys.add(eligibility_key)
        return len(rules)

    def _validate_policy_registry(self, version, payload):
        if set(payload) != {"manifest_version", "policies"} or payload["manifest_version"] != version:
            raise GovernedArtifactError("policy_registry_envelope_invalid")
        policies = payload["policies"]
        if not isinstance(policies, list) or not 1 <= len(policies) <= 1000:
            raise GovernedArtifactError("policy_registry_documents_invalid")
        identities = set()
        for policy in policies:
            if not isinstance(policy, dict) or set(policy) != self.POLICY_KEYS:
                raise GovernedArtifactError("policy_document_schema_invalid")
            if policy["approval_status"] != "approved" or not policy["approved_by"]:
                raise GovernedArtifactError("policy_document_not_approved")
            if not isinstance(policy["content"], str) or not policy["content"]:
                raise GovernedArtifactError("policy_document_content_invalid")
            digest = hashlib.sha256(policy["content"].encode()).hexdigest()
            if digest != policy["content_sha256"]:
                raise GovernedArtifactError("policy_document_digest_invalid")
            start = self._parse_time(policy["effective_from"], "effective_from")
            if policy["effective_to"] is not None and self._parse_time(policy["effective_to"], "effective_to") <= start:
                raise GovernedArtifactError("policy_document_effective_window_invalid")
            for field in ("policy_id", "title", "version", "category", "source_system", "approved_by"):
                if not isinstance(policy[field], str) or not 1 <= len(policy[field]) <= 300:
                    raise GovernedArtifactError(f"policy_document_{field}_invalid")
            identity = (policy["policy_id"], policy["version"])
            if identity in identities:
                raise GovernedArtifactError("policy_document_duplicate")
            identities.add(identity)
        return len(policies)

    def validate_payload(self, artifact_type, version, payload):
        if artifact_type not in self.ARTIFACT_TYPES:
            raise GovernedArtifactError("artifact_type_invalid")
        if not self.VERSION_PATTERN.fullmatch(version or ""):
            raise GovernedArtifactError("artifact_version_invalid")
        if not isinstance(payload, dict):
            raise GovernedArtifactError("artifact_payload_invalid")
        canonical = self.canonical_envelope(artifact_type, version, payload)
        if len(canonical) > 2_000_000:
            raise GovernedArtifactError("artifact_payload_too_large")
        item_count = (
            self._validate_product_catalog(version, payload)
            if artifact_type == "product_catalog"
            else self._validate_policy_registry(version, payload)
        )
        return canonical, item_count

    def request(
        self, artifact_type, version, payload, signature, signing_key_id, requester_ref,
    ):
        canonical, item_count = self.validate_payload(artifact_type, version, payload)
        self._verify_signature(artifact_type, version, payload, signature, signing_key_id)
        digest = hashlib.sha256(canonical).hexdigest()
        envelope = {"artifactType": artifact_type, "version": version, "payload": payload}
        row, request_status = self.database.request_governed_artifact(
            str(uuid.uuid4()), artifact_type, version, digest, envelope,
            signature, signing_key_id, requester_ref,
        )
        if request_status == "already_exists":
            request_status = "already_requested" if row["content_digest"] == digest else "version_conflict"
        if self.audit_ledger and request_status == "requested":
            self.audit_ledger.append("system:governed-artifact", "governed_artifact_requested", {
                "artifact_id": row["artifact_id"],
                "artifact_type": artifact_type,
                "version": version,
                "content_digest": digest,
                "signing_key_id": signing_key_id,
                "requester_ref": requester_ref,
            })
        return {"status": request_status, "artifact": self._public(row, item_count)}

    @staticmethod
    def _envelope(row):
        envelope = row["envelope_json"]
        return json.loads(envelope) if isinstance(envelope, str) else envelope

    def _item_count(self, row):
        envelope = self._envelope(row)
        payload = envelope["payload"]
        return len(payload["rules"] if row["artifact_type"] == "product_catalog" else payload["policies"])

    def _public(self, row, item_count=None):
        if not row:
            return None
        result = {field: row.get(field) for field in self.PUBLIC_FIELDS}
        result["item_count"] = self._item_count(row) if item_count is None else item_count
        return result

    def configure_materializers(self, product_catalog, policy_catalog):
        self.product_catalog = product_catalog
        self.policy_catalog = policy_catalog

    def _materialize(self, row):
        envelope = self._envelope(row)
        canonical, _ = self.validate_payload(row["artifact_type"], row["version"], envelope["payload"])
        if hashlib.sha256(canonical).hexdigest() != row["content_digest"]:
            raise ArtifactMaterializationError("stored_artifact_digest_mismatch")
        self._verify_signature(
            row["artifact_type"], row["version"], envelope["payload"],
            row["signature"], row["signing_key_id"],
        )
        try:
            if row["artifact_type"] == "product_catalog":
                if not self.product_catalog:
                    raise RuntimeError("product catalog materializer unavailable")
                self.product_catalog.apply_governed_feed(envelope["payload"])
            else:
                if not self.policy_catalog:
                    raise RuntimeError("policy catalog materializer unavailable")
                self.policy_catalog.apply_governed_feed(envelope["payload"])
        except Exception as error:
            raise ArtifactMaterializationError(type(error).__name__) from error

    def _materializer(self, artifact_type):
        return self.product_catalog if artifact_type == "product_catalog" else self.policy_catalog

    def decide(self, artifact_id, decision, decider_ref):
        if decision not in {"approved", "rejected"}:
            raise GovernedArtifactError("artifact_decision_invalid")
        if decision == "approved":
            claimed, claim_status = self.database.claim_governed_artifact_activation(
                artifact_id, decider_ref,
            )
            if claim_status != "claimed":
                return {"status": claim_status, "artifact": self._public(claimed)}
            previous_active = self.database.get_active_governed_artifact(
                claimed["artifact_type"]
            )
            materializer = self._materializer(claimed["artifact_type"])
            runtime_snapshot = (
                materializer.snapshot_governed_feed()
                if materializer and hasattr(materializer, "snapshot_governed_feed")
                else None
            )
            try:
                self._materialize(claimed)
            except Exception:
                self.database.abandon_governed_artifact_activation(artifact_id, decider_ref)
                raise
            try:
                decided, outcome = self.database.complete_governed_artifact_activation(
                    artifact_id, decider_ref,
                )
                if outcome == "claim_lost":
                    raise ArtifactMaterializationError("artifact_activation_claim_lost")
            except Exception as error:
                if previous_active:
                    self._materialize(previous_active)
                elif runtime_snapshot is not None:
                    materializer.apply_governed_feed(runtime_snapshot)
                self.database.abandon_governed_artifact_activation(artifact_id, decider_ref)
                if isinstance(error, ArtifactMaterializationError):
                    raise
                raise ArtifactMaterializationError("artifact_activation_commit_failed") from error
            row = claimed
        else:
            decided, outcome = self.database.decide_governed_artifact(
                artifact_id, decider_ref, decision,
            )
            row = decided
        if self.audit_ledger and outcome in {"approved", "rejected"}:
            self.audit_ledger.append("system:governed-artifact", f"governed_artifact_{outcome}", {
                "artifact_id": artifact_id,
                "artifact_type": row["artifact_type"],
                "version": row["version"],
                "content_digest": row["content_digest"],
                "decider_ref": decider_ref,
            })
        return {"status": outcome, "artifact": self._public(decided)}

    def materialize_active(self):
        materialized = []
        for artifact_type in sorted(self.ARTIFACT_TYPES):
            row = self.database.get_active_governed_artifact(artifact_type)
            if row:
                self._materialize(row)
                materialized.append(artifact_type)
        return materialized

    def list(self, artifact_status=None, artifact_type=None, limit=200):
        return [
            self._public(row)
            for row in self.database.list_governed_artifacts(
                artifact_status, artifact_type, limit,
            )
        ]

    def health(self):
        active = {
            artifact_type: bool(self.database.get_active_governed_artifact(artifact_type))
            for artifact_type in self.ARTIFACT_TYPES
        }
        ready = bool(self.public_key) and all(active.values()) if self.required else True
        return {
            "name": "governed_artifacts",
            "mode": "signed" if self.public_key else "local-fallback",
            "ready": ready,
            "detail": ";".join(f"{key}={'active' if value else 'fallback'}" for key, value in sorted(active.items())),
        }
