import os
import json
import random
from datetime import datetime, timedelta

# ponytail: mock data generator with random fallback, upgrade to live SBI Core Banking APIs integration
try:
    from faker import Faker
    HAS_FAKER = True
except ImportError:
    HAS_FAKER = False

class CustomerDataSynthesizer:
    def __init__(self, seed=42):
        random.seed(seed)
        if HAS_FAKER:
            self.fake = Faker('en_IN')
            Faker.seed(seed)
        else:
            self.indian_names = ["Priya Sharma", "Ramesh Kumar", "Amit Patel", "Suresh Raina", "Sunita Rao", "Vijay Mallya", "Deepak Chahar"]

    def generate_customer_profile(self):
        """Generates anonymized customer demographic and accounts data."""
        if HAS_FAKER:
            name = self.fake.name()
            first_name = name.split()[0]
            email = f"{first_name.lower()}.{self.fake.last_name().lower()}@example.in"
            pan = self.fake.bothify("?????####?").upper()
            aadhaar = self.fake.bothify("#### #### ####")
        else:
            name = random.choice(self.indian_names)
            first_name = name.split()[0]
            email = f"{first_name.lower()}.{random.randint(10,99)}@sbi-synthetic.in"
            pan = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=5)) + "".join(random.choices("0123456789", k=4)) + random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            aadhaar = f"{random.randint(1000,9999)} {random.randint(1000,9999)} {random.randint(1000,9999)}"
        
        # Determine income tier
        salary = random.choice([45000, 95000, 145000, 185000])
        savings_balance = random.randint(30000, 800000)
        
        # CC debt pattern (opportunity nudge candidate)
        has_card_debt = random.choice([True, False])
        cc_debt = random.randint(15000, 130000) if has_card_debt else 0
        cc_interest = round(cc_debt * 0.035) if has_card_debt else 0 # 42% p.a.
        
        return {
            "customer_id": f"SBI-{random.randint(100000, 999999)}",
            "name": name,
            "email": email,
            "pan": pan,
            "aadhaar": aadhaar,
            "monthly_salary": salary,
            "savings_balance": savings_balance,
            "card_debt_outstanding": cc_debt,
            "monthly_card_interest_paid": cc_interest
        }

    def generate_transaction_logs(self, profile, days=30):
        """Synthesizes transaction history containing potential signals."""
        logs = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Insert Salary Transaction
        logs.append({
            "timestamp": (end_date - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
            "type": "CREDIT",
            "category": "Salary",
            "amount": profile["monthly_salary"],
            "description": "ACH SALARY CREDIT / TECH CORP INDIA",
            "channel": "ACH"
        })
        
        # Add monthly card interest transaction if they have card debt
        if profile["card_debt_outstanding"] > 0:
            logs.append({
                "timestamp": (end_date - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S"),
                "type": "DEBIT",
                "category": "Finance Charges",
                "amount": profile["monthly_card_interest_paid"],
                "description": "FINANCE CHARGE CC OUTSTANDING",
                "channel": "CARD_SYSTEM"
            })
            
        # Add random transactions
        current_date = start_date
        while current_date < end_date:
            current_date += timedelta(days=random.choice([1, 2, 3]))
            is_credit = random.random() < 0.2
            amount = random.randint(100, 8000)
            
            if is_credit:
                logs.append({
                    "timestamp": current_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "type": "CREDIT",
                    "category": "Peer Transfer",
                    "amount": amount,
                    "description": f"UPI INBOUND / TRANSFER",
                    "channel": "UPI"
                })
            else:
                logs.append({
                    "timestamp": current_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "type": "DEBIT",
                    "category": "Merchant Pay",
                    "amount": amount,
                    "description": f"UPI OUTBOUND / RETAIL MERCHANT",
                    "channel": "UPI"
                })
                
        return sorted(logs, key=lambda x: x["timestamp"], reverse=True)

if __name__ == "__main__":
    synthesizer = CustomerDataSynthesizer()
    print("Generating synthetic sample profiles...")
    for _ in range(3):
        profile = synthesizer.generate_customer_profile()
        transactions = synthesizer.generate_transaction_logs(profile, days=7)
        print(f"\nProfile: {profile['name']} ({profile['customer_id']})")
        print(f"Salary: INR {profile['monthly_salary']} | Savings: INR {profile['savings_balance']}")
        print(f"Outstanding Card Debt: INR {profile['card_debt_outstanding']}")
        print(f"Recent Transactions (Last 3):")
        for tx in transactions[:3]:
            print(f" - [{tx['timestamp']}] {tx['type']} of INR {tx['amount']} via {tx['channel']} ({tx['description']})")
