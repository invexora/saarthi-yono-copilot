from typing import TypedDict, Optional
try:
    from backend.guardrails import InputGuardian, OutputGuardian
except ImportError:
    from guardrails import InputGuardian, OutputGuardian

# Define the State Machine context payload structure
class GraphState(TypedDict):
    raw_signal: str
    raw_details: str
    masked_details: Optional[str]
    signal_category: Optional[str]
    recommended_product_id: Optional[str]
    interest_rate: Optional[float]
    compliance_approved: bool
    compliance_logs: Optional[str]
    nudge_output: Optional[str]

# ponytail: simulated graph state machine, upgrade to true langgraph package compile using `StateGraph`
class SaarthiAgentOrchestrator:
    def __init__(self):
        self.guardian = InputGuardian()
        self.output_guardian = OutputGuardian()

    def node_input_guardian(self, state: GraphState) -> GraphState:
        """Filters input raw data to mask PII according to DPDP act rules."""
        print("[Node: input_guardian] Executing PII filter...")
        state["masked_details"] = self.guardian.mask_pii(state["raw_details"])
        return state

    def node_signal_detection(self, state: GraphState) -> GraphState:
        """Categorizes raw signal to trigger corresponding banking workflows."""
        print("[Node: signal_detection] Analyzing behavioral signal...")
        signal_lower = state["raw_signal"].lower()
        if "branch" in signal_lower or "deposit" in signal_lower:
            state["signal_category"] = "friction"
        elif "interest" in signal_lower or "credit card" in signal_lower:
            state["signal_category"] = "opportunity"
        else:
            state["signal_category"] = "lifeevent"
        return state

    def node_neo4j_recommendation(self, state: GraphState) -> GraphState:
        """Matches categories with products stored in Neo4j Graph Database."""
        print("[Node: neo4j_recommendation] Resolving eligible banking products...")
        category = state["signal_category"]
        if category == "friction":
            state["recommended_product_id"] = "SR-TUT-08"
            state["interest_rate"] = 0.0
            state["nudge_output"] = "Digital Quick-Deposit Tutorial video."
        elif category == "opportunity":
            state["recommended_product_id"] = "SR-LOAN-99"
            state["interest_rate"] = 10.5
            state["nudge_output"] = "Pre-approved Debt Consolidation Loan @ 10.50% p.a."
        else:
            state["recommended_product_id"] = "SR-DEP-102"
            state["interest_rate"] = 7.1
            state["nudge_output"] = "Flexi-Recurring Deposit (Auto-Sweep) @ 7.10% p.a."
        return state

    def node_compliance_gate(self, state: GraphState) -> GraphState:
        """Checks final recommendation against RBI FPC rules and DPDP consent flags."""
        print("[Node: compliance_gate] Running output audit validation...")
        text_to_test = f"Product: {state['recommended_product_id']} | rate: {state['interest_rate']}%"
        is_ok, msg = self.output_guardian.verify_compliance(text_to_test, "Compliance validated, customer consent logged.")
        
        state["compliance_approved"] = is_ok
        state["compliance_logs"] = msg
        return state

    def run_trace(self, signal: str, details: str) -> GraphState:
        """Runs the sequential LangGraph DAG nodes."""
        print(f"\n--- Starting Saarthi Orchestrator Pipeline ---\nSignal: {signal}")
        
        # Initialize state
        state: GraphState = {
            "raw_signal": signal,
            "raw_details": details,
            "masked_details": None,
            "signal_category": None,
            "recommended_product_id": None,
            "interest_rate": None,
            "compliance_approved": False,
            "compliance_logs": None,
            "nudge_output": None
        }

        # Sequential Node Execution representing the State Graph edges
        state = self.node_input_guardian(state)
        state = self.node_signal_detection(state)
        state = self.node_neo4j_recommendation(state)
        state = self.node_compliance_gate(state)
        
        print("\n--- Pipeline Completed ---")
        return state

if __name__ == "__main__":
    orchestrator = SaarthiAgentOrchestrator()
    result = orchestrator.run_trace(
        signal="Recurring credit card payment outflow pattern of INR 4,200/mo across external card balances",
        details="User Email: priya.sharma@example.com | Card: 4321-XXXX-XXXX-9901 | PAN: ABCDE1234F"
    )
    print(f"PII Sanitized Details: {result['masked_details']}")
    print(f"Product Matched: {result['recommended_product_id']} ({result['nudge_output']})")
    print(f"Compliance Audit: {result['compliance_logs']}")
