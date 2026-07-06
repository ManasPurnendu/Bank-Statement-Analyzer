import random

class NarrationGenerator:
    """Generates realistic Indian bank transaction narrations based on categories/types."""
    
    @staticmethod
    def get_salary_narration(employer_name="TECHCORP INC"):
        choices = [
            f"NEFT SALARY {employer_name}",
            f"CMS CREDIT PAYROLL",
            f"ACH CREDIT {employer_name}",
            f"SALARY CREDIT {employer_name}",
            f"NACH SALARY {employer_name}",
            f"NEFT-{employer_name}-SALARY"
        ]
        return random.choice(choices)

    @staticmethod
    def get_emi_narration(lender="HDFC"):
        choices = [
            f"{lender} HOME LOAN EMI",
            f"{lender} EMI",
            f"NACH-{lender}-LOAN",
            f"ACH DEBIT {lender} FINSERV",
            f"AUTO-DEBIT {lender} EMI"
        ]
        return random.choice(choices)

    @staticmethod
    def get_upi_narration(merchant=None):
        base_choices = [
            "UPI/GPAY",
            "UPI/PHONEPE",
            "UPI/PAYTM",
            "UPI/BHIM",
            "UPI/CRED"
        ]
        prefix = random.choice(base_choices)
        
        if merchant:
            return f"{prefix}/{merchant}/UPI_REF_{random.randint(100000, 999999)}"
        else:
            return f"{prefix}/P2P_TRANSFER_{random.randint(100000, 999999)}"

    @staticmethod
    def get_shopping_narration(merchant="AMAZON"):
        choices = [
            f"POS/{merchant}",
            f"ECOM/{merchant}/ONLINE",
            f"UPI/{merchant}/PAYMENT",
            f"CARD PAYMENT {merchant}"
        ]
        return random.choice(choices)

    @staticmethod
    def get_bill_narration(merchant="AIRTEL"):
        choices = [
            f"BILLPAY/{merchant}",
            f"UPI/{merchant}",
            f"BBPS/{merchant}/BILL"
        ]
        return random.choice(choices)

    @staticmethod
    def get_subscription_narration(merchant="NETFLIX"):
        choices = [
            f"RECURRING/{merchant}",
            f"NACH/{merchant}",
            f"E-MANDATE/{merchant}",
            f"CARD RECURRING {merchant}"
        ]
        return random.choice(choices)

    @staticmethod
    def get_atm_withdrawal():
        choices = [
            "ATM WDL/SBI",
            "CASH WDL/HDFC ATM",
            "ATM WITHDRAWAL",
            "ATM/CASH/LOCAL"
        ]
        return random.choice(choices)

    @staticmethod
    def get_bank_charge(charge_type="SMS"):
        charges = {
            "SMS": "SMS ALERT CHARGE",
            "ATM": "ATM USAGE FEE",
            "LATE": "LATE PAYMENT FEE",
            "ANNUAL": "ANNUAL CARD FEE",
            "BOUNCE": "NACH RETURN PENALTY"
        }
        return charges.get(charge_type, "MISC BANK CHARGE")

    @staticmethod
    def get_client_payment(client="CLIENT INC"):
        choices = [
            f"NEFT FROM {client}",
            f"IMPS/{client}/PAYMENT",
            f"RTGS/{client}/INV SETTLEMENT"
        ]
        return random.choice(choices)

    @staticmethod
    def get_freelance_expense(vendor="AWS"):
        choices = [
            f"POS/{vendor}",
            f"ECOM/{vendor}",
            f"GST PAYMENT/PORTAL",
            f"UPI/VENDORTFR/{vendor}"
        ]
        return random.choice(choices)
