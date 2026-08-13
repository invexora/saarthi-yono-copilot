import re

# Prototype deterministic checks. These do not replace SBI privacy, DLP, or model-risk controls.
class InputGuardian:
    MASKS = {
        "pan": "[MASKED PAN]",
        "aadhaar": "[MASKED AADHAAR]",
        "email": "[MASKED EMAIL]",
        "card": "[MASKED CARD]",
        "mobile": "[MASKED MOBILE]",
        "account": "[MASKED ACCOUNT]",
        "upi": "[MASKED UPI]",
        "passport": "[MASKED PASSPORT]",
    }

    # Exact, normalized field aliases provide a stronger boundary for structured
    # payloads than trying to infer the identifier type from its value alone.
    FIELD_MASKS = {
        "pan": MASKS["pan"],
        "panno": MASKS["pan"],
        "pannumber": MASKS["pan"],
        "permanentaccountnumber": MASKS["pan"],
        "aadhaar": MASKS["aadhaar"],
        "aadhar": MASKS["aadhaar"],
        "aadhaarno": MASKS["aadhaar"],
        "aadharno": MASKS["aadhaar"],
        "aadhaarnumber": MASKS["aadhaar"],
        "aadharnumber": MASKS["aadhaar"],
        "email": MASKS["email"],
        "emailaddress": MASKS["email"],
        "customeremail": MASKS["email"],
        "contactemail": MASKS["email"],
        "mobile": MASKS["mobile"],
        "mobileno": MASKS["mobile"],
        "mobilenumber": MASKS["mobile"],
        "phone": MASKS["mobile"],
        "phoneno": MASKS["mobile"],
        "phonenumber": MASKS["mobile"],
        "msisdn": MASKS["mobile"],
        "accountno": MASKS["account"],
        "accountnumber": MASKS["account"],
        "bankaccountno": MASKS["account"],
        "bankaccountnumber": MASKS["account"],
        "sbiaccountno": MASKS["account"],
        "sbiaccountnumber": MASKS["account"],
        "cardno": MASKS["card"],
        "cardnumber": MASKS["card"],
        "creditcardno": MASKS["card"],
        "creditcardnumber": MASKS["card"],
        "debitcardno": MASKS["card"],
        "debitcardnumber": MASKS["card"],
        "upi": MASKS["upi"],
        "upiid": MASKS["upi"],
        "vpa": MASKS["upi"],
        "virtualpaymentaddress": MASKS["upi"],
        "passport": MASKS["passport"],
        "passportno": MASKS["passport"],
        "passportnumber": MASKS["passport"],
    }

    def __init__(self):
        # Longer numeric identifiers are evaluated first so that a complete card
        # or Aadhaar value cannot be partially consumed by a shorter pattern.
        self.text_patterns = (
            (
                self.MASKS["email"],
                re.compile(
                    r"(?<![A-Z0-9._%+\-])[A-Z0-9._%+\-]+@"
                    r"(?:[A-Z0-9\-]+\.)+[A-Z]{2,63}(?![A-Z0-9._%+\-])",
                    re.IGNORECASE,
                ),
            ),
            (
                self.MASKS["card"],
                re.compile(r"(?<!\d)(?:\d{4}[ -]?){3}\d{4}(?!\d)"),
            ),
            (
                self.MASKS["aadhaar"],
                re.compile(r"(?<!\d)(?:\d{4}[ -]?){2}\d{4}(?!\d)"),
            ),
            (
                self.MASKS["pan"],
                re.compile(r"(?<![A-Z0-9])[A-Z]{5}\d{4}[A-Z](?![A-Z0-9])", re.IGNORECASE),
            ),
            (
                self.MASKS["passport"],
                re.compile(r"(?<![A-Z0-9])[A-PR-WY]\d{7}(?![A-Z0-9])", re.IGNORECASE),
            ),
            (
                self.MASKS["mobile"],
                re.compile(r"(?<!\d)(?:(?:\+91|0)[ -]?)?[6-9]\d{4}[ -]?\d{5}(?!\d)"),
            ),
            (
                self.MASKS["account"],
                re.compile(r"(?<!\d)\d{11}(?!\d)"),
            ),
            (
                self.MASKS["upi"],
                re.compile(
                    r"(?<![A-Z0-9._+\-])[A-Z0-9][A-Z0-9._\-]{1,254}@"
                    r"(?:upi|ybl|ibl|axl|apl|paytm|oksbi|okhdfcbank|okicici|okaxis|"
                    r"sbi|icici|hdfcbank|axisbank|kotak|indus|federal|boi|pnb|"
                    r"barodampay|aubank|yesbank|dbs|rbl)(?![A-Z0-9._\-])",
                    re.IGNORECASE,
                ),
            ),
        )

    @staticmethod
    def _normalized_field_name(field_name):
        if not isinstance(field_name, str):
            return None
        return re.sub(r"[^a-z0-9]", "", field_name.lower())

    def _mask_text(self, value):
        sanitized = value
        for marker, pattern in self.text_patterns:
            sanitized = pattern.sub(marker, sanitized)
        return sanitized

    def _mask_field_value(self, value, marker):
        if value is None:
            return None
        if isinstance(value, list):
            return [self._mask_field_value(item, marker) for item in value]
        if isinstance(value, tuple):
            return tuple(self._mask_field_value(item, marker) for item in value)
        if isinstance(value, dict):
            return marker
        return marker

    def mask_pii(self, payload):
        """Return a recursively masked copy of a JSON-like payload.

        String values are screened for supported identifier shapes. Structured
        fields with an explicit sensitive alias are masked even when the value is
        numeric or uses an unfamiliar provider-specific format. Input containers
        are never modified in place.
        """
        if isinstance(payload, str):
            return self._mask_text(payload)
        if isinstance(payload, list):
            return [self.mask_pii(item) for item in payload]
        if isinstance(payload, tuple):
            return tuple(self.mask_pii(item) for item in payload)
        if isinstance(payload, dict):
            masked = {}
            for key, value in payload.items():
                field_marker = self.FIELD_MASKS.get(self._normalized_field_name(key))
                safe_key = self._mask_text(key) if isinstance(key, str) else key
                masked[safe_key] = (
                    self._mask_field_value(value, field_marker)
                    if field_marker
                    else self.mask_pii(value)
                )
            return masked
        return payload

class OutputGuardian:
    def __init__(self):
        pass

    def verify_compliance(self, recommendation_text, has_consent=False, customer_risk_tier='low'):
        """Applies a small set of prototype output-policy checks."""
        if isinstance(has_consent, str):
            has_consent = "consent given" in has_consent.lower()

        if not has_consent:
            return False, "Output rejected: Active purpose-specific consent is required."

        # Ensure interest rates match exact limits
        rate_matches = re.findall(r'(\d+\.?\d*)\s*%', recommendation_text)

        for rate_str in rate_matches:
            rate = float(rate_str)
            if rate >= 36.0:
                # Flag extremely high interest rates (potential predatory lending safeguard)
                return False, f"Output rejected: Recommendation contains non-compliant interest rate of {rate}%."

        # Enforce the prototype's configured vulnerable-customer policy.
        if customer_risk_tier == 'support' and "loan" in recommendation_text.lower():
            return False, "Output rejected: vulnerable-customer support mode blocks loan promotion."

        # Ensure Key Fact Statement (KFS) disclosure rules for credit products
        if "loan" in recommendation_text.lower() or "credit" in recommendation_text.lower():
            if "kfs" not in recommendation_text.lower() and "key fact statement" not in recommendation_text.lower():
                return False, "Output rejected: Proposing a credit product requires KFS disclosure."

        return True, "Output approved."

if __name__ == "__main__":
    guardian = InputGuardian()
    raw_event_detail = "User ID: SBI-772910 | Email: priya.sharma@gmail.com | Aadhaar: 4532 9981 1204 | PAN: ABCDE1234F"
    print("Testing Inbound PII Guardrail:")
    print(f" - Raw Payload: {raw_event_detail}")
    print(f" - Masked Payload: {guardian.mask_pii(raw_event_detail)}")

    print("\nTesting prototype outbound policy checks:")
    out_guardian = OutputGuardian()
    nudge_text = "Demo loan illustration only; pricing and eligibility require live SBI systems. Refer to KFS."
    status, msg = out_guardian.verify_compliance(nudge_text, True)
    print(f" - Nudge text: {nudge_text}")
    print(f" - Status: {msg}")
