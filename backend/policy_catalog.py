import hashlib
import copy
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


APPROVAL_RANK = {"draft": 0, "demo": 1, "approved": 2}


class PolicyCatalog:
    """Manifest-backed policy retrieval with provenance and integrity validation."""

    def __init__(self, manifest_path=None, minimum_approval="approved", now=None, manifest_data=None):
        self.manifest_path = Path(manifest_path or Path(__file__).with_name("policies") / "manifest.json")
        self.minimum_approval = minimum_approval
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.manifest_version = None
        self.policies = []
        self._vectors = []
        self._idf = {}
        self._load(manifest_data)

    @staticmethod
    def _tokenize(text):
        return re.findall(r"[a-z0-9]+", text.lower())

    @staticmethod
    def _parse_time(value):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def _load(self, manifest_data=None):
        data = manifest_data if manifest_data is not None else json.loads(self.manifest_path.read_text())
        self.manifest_version = data["manifest_version"]
        current = self.now()
        minimum = APPROVAL_RANK[self.minimum_approval]
        for policy in data["policies"]:
            actual_hash = hashlib.sha256(policy["content"].encode()).hexdigest()
            if actual_hash != policy["content_sha256"]:
                raise RuntimeError(f"Policy integrity check failed: {policy['policy_id']}")
            if APPROVAL_RANK.get(policy["approval_status"], -1) < minimum:
                continue
            if not policy.get("approved_by"):
                raise RuntimeError(f"Policy approval owner missing: {policy['policy_id']}")
            if self._parse_time(policy["effective_from"]) > current:
                continue
            if policy.get("effective_to") and self._parse_time(policy["effective_to"]) <= current:
                continue
            self.policies.append(policy)
        if not self.policies:
            raise RuntimeError("No eligible policy documents are available")
        self._index()

    def _index(self):
        self._vectors = []
        doc_frequency = Counter()
        for policy in self.policies:
            doc_frequency.update(set(self._tokenize(policy["content"])))
        count = len(self.policies)
        self._idf = {word: math.log((count + 1) / (frequency + 1)) + 1 for word, frequency in doc_frequency.items()}
        for policy in self.policies:
            words = self._tokenize(policy["content"])
            tf = Counter(words)
            self._vectors.append((policy, {word: amount / len(words) * self._idf[word] for word, amount in tf.items()}))

    def apply_governed_feed(self, payload):
        candidate = PolicyCatalog(
            manifest_path=self.manifest_path,
            minimum_approval=self.minimum_approval,
            now=self.now,
            manifest_data=payload,
        )
        self.manifest_version = candidate.manifest_version
        self.policies = candidate.policies
        self._vectors = candidate._vectors
        self._idf = candidate._idf

    def snapshot_governed_feed(self):
        return {
            "manifest_version": self.manifest_version,
            "policies": copy.deepcopy(self.policies),
        }

    def retrieve_policy(self, query):
        words = self._tokenize(query)
        tf = Counter(words)
        query_vector = {word: amount / max(1, len(words)) * self._idf.get(word, 0) for word, amount in tf.items()}

        def cosine(left, right):
            numerator = sum(left[word] * right[word] for word in set(left) & set(right))
            denominator = math.sqrt(sum(value * value for value in left.values())) * math.sqrt(sum(value * value for value in right.values()))
            return numerator / denominator if denominator else 0.0

        policy, score = max(((policy, cosine(query_vector, vector)) for policy, vector in self._vectors), key=lambda item: item[1])
        return {
            "policy_id": policy["policy_id"],
            "title": policy["title"],
            "version": policy["version"],
            "category": policy["category"],
            "source_system": policy["source_system"],
            "approval_status": policy["approval_status"],
            "approved_by": policy["approved_by"],
            "effective_from": policy["effective_from"],
            "effective_to": policy.get("effective_to"),
            "content_sha256": policy["content_sha256"],
            "excerpt": policy["content"],
            "relevance_score": round(score, 6),
            "retrieved_at": self.now().isoformat(),
            "manifest_version": self.manifest_version,
        }

    def retrieve_context(self, query):
        return self.retrieve_policy(query)["excerpt"]

    def list_policies(self):
        return [{key: value for key, value in policy.items() if key != "content"} for policy in self.policies]

    def health(self):
        return {
            "name": "policy_retriever",
            "mode": "manifest-tfidf",
            "ready": bool(self.policies),
            "detail": f"{len(self.policies)} validated policies; manifest {self.manifest_version}",
        }
