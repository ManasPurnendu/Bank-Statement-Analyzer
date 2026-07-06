import random
from datetime import datetime
from scripts.data_generator.narration_generator import NarrationGenerator
from scripts.data_generator.utils import is_weekend, is_month_start, is_month_end, get_random_time

class TransactionGenerator:
    """Simulates daily banking behavior based on probabilistic distributions."""
    
    def __init__(self, profile):
        self.profile = profile

    def generate_daily_transactions(self, current_date: datetime):
        """Returns a list of transaction dicts for a given day based on profile rules."""
        transactions = []
        
        # 1. SALARY / INCOME (Monthly fixed / Semi-fixed)
        for inc_cfg in self.profile.get("income", []):
            if inc_cfg["type"] == "fixed_salary":
                # Check if today is the salary date (with some +/- variation allowed if not fixed)
                expected_day = inc_cfg.get("day", 1)
                
                # Introduce variation
                if current_date.day == expected_day:
                    amount = inc_cfg["amount"] + random.randint(-inc_cfg.get("variation", 0), inc_cfg.get("variation", 0))
                    transactions.append({
                        "date": current_date,
                        "amount": amount,
                        "type": "Credit",
                        "desc": NarrationGenerator.get_salary_narration(inc_cfg.get("employer", "TECHCORP")),
                        "is_subscription": False
                    })
            elif inc_cfg["type"] == "freelance_random":
                # E.g., 10% chance on any day to receive a payment
                if random.random() < inc_cfg.get("probability", 0.10):
                    amount = random.randint(inc_cfg["min"], inc_cfg["max"])
                    transactions.append({
                        "date": current_date,
                        "amount": amount,
                        "type": "Credit",
                        "desc": NarrationGenerator.get_client_payment(random.choice(inc_cfg.get("clients", ["CLIENT A"]))),
                        "is_subscription": False
                    })
            elif inc_cfg["type"] == "bonus":
                # Quarterly bonus
                if current_date.month in inc_cfg.get("months", [3, 6, 9, 12]) and current_date.day == inc_cfg.get("day", 15):
                    transactions.append({
                        "date": current_date,
                        "amount": inc_cfg["amount"],
                        "type": "Credit",
                        "desc": "NEFT BONUS PAYOUT",
                        "is_subscription": False
                    })
                    
            elif inc_cfg["type"] == "cash_deposit":
                if random.random() < inc_cfg.get("probability", 0.05):
                    amount = random.randint(inc_cfg["min"], inc_cfg["max"])
                    transactions.append({
                        "date": current_date,
                        "amount": amount,
                        "type": "Credit",
                        "desc": "CASH DEPOSIT BRANCH",
                        "is_subscription": False
                    })

        # 2. FIXED EXPENSES (EMIs, SIPs, Subs)
        for exp_cfg in self.profile.get("fixed_expenses", []):
            if current_date.day == exp_cfg.get("day", 5):
                # EMI
                if exp_cfg["type"] == "emi":
                    transactions.append({
                        "date": current_date,
                        "amount": exp_cfg["amount"],
                        "type": "Debit",
                        "desc": NarrationGenerator.get_emi_narration(exp_cfg.get("lender", "HDFC")),
                        "is_subscription": True
                    })
                # SIP
                elif exp_cfg["type"] == "sip":
                    transactions.append({
                        "date": current_date,
                        "amount": exp_cfg["amount"],
                        "type": "Debit",
                        "desc": "ACH MUTUAL FUND SIP",
                        "is_subscription": True
                    })
                # Subscription
                elif exp_cfg["type"] == "subscription":
                    transactions.append({
                        "date": current_date,
                        "amount": exp_cfg["amount"],
                        "type": "Debit",
                        "desc": NarrationGenerator.get_subscription_narration(exp_cfg.get("merchant", "NETFLIX")),
                        "is_subscription": True
                    })

        # 3. VARIABLE EXPENSES
        var_cfg = self.profile.get("variable_expenses", {})
        
        # 3a. UPI Daily (Food, Small Transfers)
        num_upi = random.randint(var_cfg.get("upi_min", 0), var_cfg.get("upi_max", 3))
        # Increase frequency on weekends
        if is_weekend(current_date):
            num_upi += random.randint(1, 3)
            
        for _ in range(num_upi):
            merchant = random.choice(["SWIGGY", "ZOMATO", "ZEPTO", "BLINKIT", "UBER", "OLA", None])
            amount = random.randint(var_cfg.get("upi_amt_min", 50), var_cfg.get("upi_amt_max", 800))
            transactions.append({
                "date": current_date,
                "amount": amount,
                "type": "Debit",
                "desc": NarrationGenerator.get_upi_narration(merchant),
                "is_subscription": False
            })

        # 3b. Shopping
        if random.random() < var_cfg.get("shopping_prob", 0.1):
            amount = random.randint(var_cfg.get("shop_min", 1000), var_cfg.get("shop_max", 5000))
            merchant = random.choice(["AMAZON", "FLIPKART", "MYNTRA", "AJIO"])
            transactions.append({
                "date": current_date,
                "amount": amount,
                "type": "Debit",
                "desc": NarrationGenerator.get_shopping_narration(merchant),
                "is_subscription": False
            })

        # 3c. Groceries / Supermarket
        if random.random() < var_cfg.get("grocery_prob", 0.15):
            amount = random.randint(var_cfg.get("groc_min", 500), var_cfg.get("groc_max", 3000))
            merchant = random.choice(["DMART", "RELIANCE SMART", "BIGBASKET"])
            transactions.append({
                "date": current_date,
                "amount": amount,
                "type": "Debit",
                "desc": NarrationGenerator.get_shopping_narration(merchant),
                "is_subscription": False
            })

        # 3d. Fuel
        if random.random() < var_cfg.get("fuel_prob", 0.08):
            amount = random.randint(var_cfg.get("fuel_min", 500), var_cfg.get("fuel_max", 2000))
            transactions.append({
                "date": current_date,
                "amount": amount,
                "type": "Debit",
                "desc": "POS/INDIANOIL/PETROL PUMP",
                "is_subscription": False
            })

        # 3e. ATM Withdrawals
        if random.random() < var_cfg.get("atm_prob", 0.05):
            amount = random.randint(var_cfg.get("atm_min", 1000), var_cfg.get("atm_max", 10000))
            # Round to nearest 500
            amount = round(amount / 500) * 500
            if amount > 0:
                transactions.append({
                    "date": current_date,
                    "amount": amount,
                    "type": "Debit",
                    "desc": NarrationGenerator.get_atm_withdrawal(),
                    "is_subscription": False
                })

        # 3f. Business/Freelance expenses
        if self.profile.get("is_business", False):
            if random.random() < 0.2:
                amount = random.randint(1000, 15000)
                transactions.append({
                    "date": current_date,
                    "amount": amount,
                    "type": "Debit",
                    "desc": NarrationGenerator.get_freelance_expense(random.choice(["AWS", "GOOGLE CLOUD", "VENDOR A", "VENDOR B"])),
                    "is_subscription": False
                })

        # 4. EDGE CASES / OCCASIONAL (Bounces, Fees, Refunds)
        edge_cfg = self.profile.get("edge_cases", {})
        if random.random() < edge_cfg.get("bounce_prob", 0.0):
            transactions.append({
                "date": current_date,
                "amount": 590, # 500 + GST
                "type": "Debit",
                "desc": NarrationGenerator.get_bank_charge("BOUNCE"),
                "is_subscription": False
            })
            
        if random.random() < edge_cfg.get("refund_prob", 0.02):
            transactions.append({
                "date": current_date,
                "amount": random.randint(500, 2000),
                "type": "Credit",
                "desc": "UPI/REFUND/AMAZON",
                "is_subscription": False
            })

        # Assign random times to transactions on this day
        for tx in transactions:
            tx["date"] = get_random_time(tx["date"])
            
        # Sort chronologically
        transactions.sort(key=lambda x: x["date"])
        
        return transactions
