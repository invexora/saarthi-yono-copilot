import copy
from datetime import datetime, timezone


CATALOG_VERSION = "2026.08.2"
EFFECTIVE_FROM = "2026-01-01T00:00:00+00:00"


PRODUCT_RULES = [
    ("friction", "corporate", "SBI-TAX-DIGITAL16", "YONO Direct Tax Payment", 0.0, "low"),
    ("friction", "pensioner", "SBI-UPI-AUTOPAY04", "UPI Auto-Pay Setup", 0.0, "low"),
    ("friction", "sme", "SBI-SME-QR05", "YONO Merchant App + QR Terminal", 0.0, "low"),
    ("friction", "stressed", "SBI-KYC-VIDEO10", "YONO Video KYC", 0.0, "low"),
    ("friction", "student", "SBI-EDU-DASH13", "Digital Education Loan Dashboard", 0.0, "low"),
    ("opportunity", "corporate", "SBI-LOAN-EXP01", "SBI Express Credit Debt Consolidation", 20.0, "high"),
    ("opportunity", "pensioner", "SBI-FD-SENIOR02", "Senior Citizen Fixed Deposit", 6.75, "high"),
    ("opportunity", "sme", "SBI-SME-SWEEP06", "Current Account Auto-Sweep FD", 6.50, "high"),
    ("opportunity", "stressed", "SBI-EMI-CC08", "Credit Card Balance EMI Conversion", 12.0, "high"),
    ("opportunity", "student", "SBI-SIP-MF11", "SBI Mutual Fund SIP", 12.0, "high"),
    ("lifeevent", "corporate", "SBI-RD-FLEXI12", "Flexi Recurring Deposit", 7.10, "high"),
    ("lifeevent", "pensioner", "SBI-SCSS-GOV03", "Senior Citizen Savings Scheme", 8.20, "high"),
    ("lifeevent", "sme", "SBI-SME-PREPAY07", "Working Capital Loan Pre-Payment", 0.0, "high"),
    ("lifeevent", "stressed", "SBI-RD-MICRO09", "Emergency Micro Recurring Deposit", 6.80, "high"),
    ("lifeevent", "student", "SBI-RD-FLEXI12", "Flexi Recurring Deposit", 7.10, "high"),
    ("stress", "corporate", "SBI-RELIEF-RM15", "RM Connection + EMI Restructuring", 0.0, "support"),
    ("stress", "pensioner", "SBI-MED-AAROGYAM14", "SBI Aarogyam Medical EMI", 0.0, "support"),
    ("stress", "sme", "SBI-RELIEF-RM15", "RM Connection + EMI Restructuring", 0.0, "support"),
    ("stress", "stressed", "SBI-RELIEF-RM15", "RM Connection + EMI Restructuring", 0.0, "support"),
    ("stress", "student", "SBI-RELIEF-RM15", "RM Connection + EMI Restructuring", 0.0, "support"),
]

PRODUCT_DECISION_TERMS = {
    "SBI-LOAN-EXP01": ("credit", 9000.0, 0.50),
    "SBI-EMI-CC08": ("credit", 2550.0, 0.50),
    "SBI-SIP-MF11": ("investment", 500.0, 0.30),
    "SBI-RD-FLEXI12": ("savings", 5000.0, 0.30),
    "SBI-RD-MICRO09": ("savings", 2000.0, 0.30),
    "SBI-SCSS-GOV03": ("savings", 5000.0, 0.30),
}


def _catalog_rows():
    return [
        {
            "rule_id": f"{trigger}:{segment}:{product_id}:{CATALOG_VERSION}",
            "trigger": trigger,
            "segment": segment,
            "product_id": product_id,
            "product": product,
            "rate": rate,
            "risk_tier": risk_tier,
            "catalog_version": CATALOG_VERSION,
            "effective_from": EFFECTIVE_FROM,
            "effective_to": None,
            "active": True,
            "product_type": PRODUCT_DECISION_TERMS.get(product_id, ("service", 0.0, 1.0))[0],
            "monthly_commitment": PRODUCT_DECISION_TERMS.get(product_id, ("service", 0.0, 1.0))[1],
            "max_dsti": PRODUCT_DECISION_TERMS.get(product_id, ("service", 0.0, 1.0))[2],
        }
        for trigger, segment, product_id, product, rate, risk_tier in PRODUCT_RULES
    ]


class Neo4jProductGraph:
    """Versioned product eligibility catalog backed by memory or Neo4j."""

    def __init__(
        self,
        mode="memory",
        uri="bolt://localhost:7687",
        user="neo4j",
        password=None,
        database="neo4j",
        driver=None,
        seed_catalog=True,
    ):
        if mode not in {"memory", "neo4j"}:
            raise ValueError("product catalog mode must be 'memory' or 'neo4j'")
        self.mode = mode
        self.uri = uri
        self.database = database
        self.catalog = _catalog_rows()
        self.driver = driver

        if self.mode == "neo4j":
            if self.driver is None:
                if not password:
                    raise RuntimeError("Neo4j password is required in neo4j mode")
                from neo4j import GraphDatabase

                self.driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=5)
            self.driver.verify_connectivity()
            if seed_catalog:
                self.seed_catalog()

    @property
    def eligibility_graph(self):
        return {
            (row["trigger"], row["segment"]): {
                "product_id": row["product_id"],
                "product": row["product"],
                "rate": row["rate"],
                "risk_tier": row["risk_tier"],
            }
            for row in self.catalog
            if row["active"]
        }

    def seed_catalog(self, replace=False):
        constraint = "CREATE CONSTRAINT eligibility_rule_id IF NOT EXISTS FOR (r:EligibilityRule) REQUIRE r.rule_id IS UNIQUE"
        upsert = """
        UNWIND $rules AS rule
        MERGE (r:EligibilityRule {rule_id: rule.rule_id})
        SET r.trigger = rule.trigger,
            r.segment = rule.segment,
            r.product_id = rule.product_id,
            r.product = rule.product,
            r.rate = rule.rate,
            r.risk_tier = rule.risk_tier,
            r.catalog_version = rule.catalog_version,
            r.effective_from = datetime(rule.effective_from),
            r.effective_to = CASE WHEN rule.effective_to IS NULL THEN NULL ELSE datetime(rule.effective_to) END,
            r.active = rule.active,
            r.product_type = rule.product_type,
            r.monthly_commitment = rule.monthly_commitment,
            r.max_dsti = rule.max_dsti
        """
        with self.driver.session(database=self.database) as session:
            session.run(constraint).consume()
            if replace:
                deactivate = "MATCH (r:EligibilityRule) SET r.active = false RETURN count(r) AS deactivated"
                if hasattr(session, "begin_transaction"):
                    with session.begin_transaction() as transaction:
                        transaction.run(deactivate).consume()
                        transaction.run(upsert, rules=self.catalog).consume()
                    return
                session.run(deactivate).consume()
            session.run(upsert, rules=self.catalog).consume()

    def apply_governed_feed(self, payload):
        rules = [dict(rule) for rule in payload["rules"]]
        previous = self.catalog
        self.catalog = rules
        if self.mode == "neo4j":
            try:
                self.seed_catalog(replace=True)
            except Exception:
                self.catalog = previous
                raise

    def snapshot_governed_feed(self):
        return {
            "catalog_version": self.catalog[0]["catalog_version"] if self.catalog else "empty",
            "rules": copy.deepcopy(self.catalog),
        }

    def query_eligibility(self, signal_category, customer_segment):
        if self.mode == "memory":
            now = datetime.now(timezone.utc)
            for row in self.catalog:
                effective_from = datetime.fromisoformat(row["effective_from"])
                effective_to = datetime.fromisoformat(row["effective_to"]) if row["effective_to"] else None
                if (
                    row["trigger"] == signal_category
                    and row["segment"] == customer_segment
                    and row["active"]
                    and effective_from <= now
                    and (effective_to is None or effective_to > now)
                ):
                    return self._public_product(row)
            return None

        query = """
        MATCH (r:EligibilityRule {trigger: $trigger, segment: $segment, active: true})
        WHERE r.effective_from <= datetime($as_of)
          AND (r.effective_to IS NULL OR r.effective_to > datetime($as_of))
        RETURN r.product_id AS product_id,
               r.product AS product,
               r.rate AS rate,
               r.risk_tier AS risk_tier,
               r.product_type AS product_type,
               r.monthly_commitment AS monthly_commitment,
               r.max_dsti AS max_dsti,
               r.catalog_version AS catalog_version,
               toString(r.effective_from) AS effective_from,
               CASE WHEN r.effective_to IS NULL THEN NULL ELSE toString(r.effective_to) END AS effective_to
        ORDER BY r.catalog_version DESC
        LIMIT 1
        """
        with self.driver.session(database=self.database) as session:
            record = session.run(
                query,
                trigger=signal_category,
                segment=customer_segment,
                as_of=datetime.now(timezone.utc).isoformat(),
            ).single()
            return dict(record) if record else None

    def list_products(self):
        if self.mode == "memory":
            return [self._public_product(row) | {"trigger": row["trigger"], "segment": row["segment"]} for row in self.catalog if row["active"]]

        query = """
        MATCH (r:EligibilityRule {active: true})
        RETURN r.trigger AS trigger, r.segment AS segment,
               r.product_id AS product_id, r.product AS product,
               r.rate AS rate, r.risk_tier AS risk_tier,
               r.product_type AS product_type,
               r.monthly_commitment AS monthly_commitment,
               r.max_dsti AS max_dsti,
               r.catalog_version AS catalog_version,
               toString(r.effective_from) AS effective_from,
               CASE WHEN r.effective_to IS NULL THEN NULL ELSE toString(r.effective_to) END AS effective_to
        ORDER BY r.trigger, r.segment
        """
        with self.driver.session(database=self.database) as session:
            return [dict(record) for record in session.run(query)]

    @staticmethod
    def _public_product(row):
        return {
            "product_id": row["product_id"],
            "product": row["product"],
            "rate": row["rate"],
            "risk_tier": row["risk_tier"],
            "product_type": row["product_type"],
            "monthly_commitment": row["monthly_commitment"],
            "max_dsti": row["max_dsti"],
            "catalog_version": row["catalog_version"],
            "effective_from": row["effective_from"],
            "effective_to": row["effective_to"],
        }

    def health(self):
        current_version = self.catalog[0]["catalog_version"] if self.catalog else "empty"
        if self.mode == "neo4j":
            try:
                self.driver.verify_connectivity()
                return {"name": "product_catalog", "mode": "neo4j", "ready": True, "detail": current_version}
            except Exception as error:
                return {"name": "product_catalog", "mode": "neo4j", "ready": False, "detail": type(error).__name__}
        return {"name": "product_catalog", "mode": "memory", "ready": True, "detail": current_version}

    def close(self):
        if self.driver is not None:
            self.driver.close()
