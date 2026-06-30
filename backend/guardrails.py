import re

# ponytail: regex-based guardrail, replace with Guardrails AI framework or NeMo Guardrails for LLM semantic containment
class InputGuardian:
    def __init__(self):
        # Indian standard financial identification patterns
        self.pan_pattern = re.compile(r'[a-zA-Z]{5}[0-9]{4}[a-zA-Z]')
        self.aadhaar_pattern = re.compile(r'[0-9]{4}\s[0-9]{4}\s[0-9]{4}')
        self.email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
        self.card_pattern = re.compile(r'[0-9]{4}-XXXX-XXXX-[0-9]{4}')

    def mask_pii(self, payload_str):
        """Sanitizes sensitive identifiers to satisfy DPDP Data Minimization guidelines."""
        sanitized = payload_str
        
        # Mask PAN
        sanitized = self.pan_pattern.sub("[MASKED PAN]", sanitized)
        
        # Mask Aadhaar
        sanitized = self.aadhaar_pattern.sub("[MASKED AADHAAR]", sanitized)
        
        # Mask Emails
        sanitized = self.email_pattern.sub("[MASKED EMAIL]", sanitized)
        
        # Mask Credit Cards
        sanitized = self.card_pattern.sub("[MASKED CARD]", sanitized)
        
        return sanitized

class OutputGuardian:
    def __init__(self):
        pass

    def verify_compliance(self, recommendation_text, compliance_rules):
        """Validates outputs for compliance with the RBI Fair Practices Code."""
        # Ensure interest rates match exact limits
        rate_matches = re.findall(r'(\d+\.?\d*)\s*%', recommendation_text)
        
        for rate_str in rate_matches:
            rate = float(rate_str)
            if rate > 36.0:
                # Flag extremely high interest rates (potential predatory lending safeguard)
                return False, f"Output rejected: Recommendation contains non-compliant interest rate of {rate}%."
                
        # Ensure explicit consent notice is present when proposing credit products
        if "loan" in recommendation_text.lower() and "consent" not in compliance_rules.lower():
            return False, "Output rejected: Proposing a credit product requires explicit consent disclosure."
            
        return True, "Output approved."

if __name__ == "__main__":
    guardian = InputGuardian()
    raw_event_detail = "User ID: SBI-772910 | Email: priya.sharma@gmail.com | Aadhaar: 4532 9981 1204 | PAN: ABCDE1234F"
    print("Testing Inbound PII Guardrail:")
    print(f" - Raw Payload: {raw_event_detail}")
    print(f" - Masked Payload: {guardian.mask_pii(raw_event_detail)}")

    print("\nTesting Outbound Output Guardian (RBI Compliance):")
    out_guardian = OutputGuardian()
    nudge_text = "Apply for pre-approved Consolidation Personal Loan at 10.5% interest."
    status, msg = out_guardian.verify_compliance(nudge_text, "FPC Gating active, consent optional")
    print(f" - Nudge text: {nudge_text}")
    print(f" - Status: {msg}")
