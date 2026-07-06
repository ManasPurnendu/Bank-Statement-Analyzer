# Profiles configuration for generating synthetic transactions

PROFILES = {
    # 1. Ideal Borrower
    "admin@admin.com": {
        "starting_balance": 50000.0,
        "income": [
            {"type": "fixed_salary", "amount": 120000, "employer": "TECHCORP INC", "day": 1, "variation": 500}
        ],
        "fixed_expenses": [
            {"type": "emi", "amount": 15000, "lender": "HDFC", "day": 5},
            {"type": "sip", "amount": 5000, "day": 10},
            {"type": "subscription", "amount": 999, "merchant": "NETFLIX", "day": 15}
        ],
        "variable_expenses": {
            "upi_min": 1, "upi_max": 4, "upi_amt_min": 100, "upi_amt_max": 1000,
            "shopping_prob": 0.1, "shop_min": 2000, "shop_max": 8000,
            "grocery_prob": 0.2, "groc_min": 1000, "groc_max": 4000,
            "fuel_prob": 0.1, "fuel_min": 1000, "fuel_max": 2500,
            "atm_prob": 0.05, "atm_min": 2000, "atm_max": 5000
        },
        "edge_cases": {"bounce_prob": 0.0, "refund_prob": 0.05}
    },
    
    # 2. High Risk Borrower
    "abc@gmail.com": {
        "starting_balance": 5000.0,
        "income": [
            {"type": "fixed_salary", "amount": 50000, "employer": "RETAIL CO", "day": 1, "variation": 100}
        ],
        "fixed_expenses": [
            {"type": "emi", "amount": 18000, "lender": "BAJAJ FINSERV", "day": 5},
            {"type": "emi", "amount": 10000, "lender": "ICICI", "day": 7},
            {"type": "emi", "amount": 8000, "lender": "KOTAK", "day": 10}
        ],
        "variable_expenses": {
            "upi_min": 2, "upi_max": 6, "upi_amt_min": 50, "upi_amt_max": 500,
            "shopping_prob": 0.15, "shop_min": 1000, "shop_max": 15000,
            "grocery_prob": 0.1, "groc_min": 500, "groc_max": 2000,
            "fuel_prob": 0.1, "fuel_min": 500, "fuel_max": 1000,
            "atm_prob": 0.2, "atm_min": 500, "atm_max": 4000 # Frequent ATMs
        },
        "edge_cases": {"bounce_prob": 0.05, "refund_prob": 0.01} # High bounce prob
    },
    
    # 3. Freelancer / Business
    "bcd@gmail.com": {
        "starting_balance": 15000.0,
        "is_business": True,
        "income": [
            {"type": "freelance_random", "min": 5000, "max": 40000, "probability": 0.15, "clients": ["CLIENT A", "CLIENT B", "AGENCY LLC"]}
        ],
        "fixed_expenses": [
            {"type": "subscription", "amount": 2500, "merchant": "AWS CLOUD", "day": 10},
            {"type": "subscription", "amount": 1000, "merchant": "ADOBE", "day": 15}
        ],
        "variable_expenses": {
            "upi_min": 1, "upi_max": 5, "upi_amt_min": 200, "upi_amt_max": 2000,
            "shopping_prob": 0.05, "shop_min": 1000, "shop_max": 5000,
            "grocery_prob": 0.1, "groc_min": 1000, "groc_max": 3000,
            "fuel_prob": 0.1, "fuel_min": 1000, "fuel_max": 3000,
            "atm_prob": 0.05, "atm_min": 1000, "atm_max": 10000
        },
        "edge_cases": {"bounce_prob": 0.01, "refund_prob": 0.03}
    },
    
    # 4. Student
    "student@test.com": {
        "starting_balance": 2000.0,
        "income": [
            {"type": "freelance_random", "min": 1000, "max": 5000, "probability": 0.05, "clients": ["DAD", "MOM"]} # "freelance" logic acts as random deposits
        ],
        "fixed_expenses": [
            {"type": "subscription", "amount": 199, "merchant": "SPOTIFY", "day": 12}
        ],
        "variable_expenses": {
            "upi_min": 3, "upi_max": 8, "upi_amt_min": 20, "upi_amt_max": 400, # Lots of small upi
            "shopping_prob": 0.05, "shop_min": 500, "shop_max": 2000,
            "grocery_prob": 0.05, "groc_min": 200, "groc_max": 1000,
            "fuel_prob": 0.0, "fuel_min": 0, "fuel_max": 0,
            "atm_prob": 0.02, "atm_min": 500, "atm_max": 1000
        },
        "edge_cases": {"bounce_prob": 0.0, "refund_prob": 0.05}
    },
    
    # 5. Recently Employed (Handled in seed_test_data by truncating history)
    "recent_hire@test.com": {
        "starting_balance": 5000.0,
        "income": [
            {"type": "fixed_salary", "amount": 40000, "employer": "STARTUP LLC", "day": 1, "variation": 0}
        ],
        "fixed_expenses": [
            {"type": "emi", "amount": 8000, "lender": "EDULOAN", "day": 7}
        ],
        "variable_expenses": {
            "upi_min": 1, "upi_max": 3, "upi_amt_min": 100, "upi_amt_max": 600,
            "shopping_prob": 0.1, "shop_min": 1000, "shop_max": 3000,
            "grocery_prob": 0.1, "groc_min": 1000, "groc_max": 2500,
            "fuel_prob": 0.05, "fuel_min": 500, "fuel_max": 1000,
            "atm_prob": 0.05, "atm_min": 1000, "atm_max": 3000
        },
        "edge_cases": {"bounce_prob": 0.0, "refund_prob": 0.02},
        "special": "recent_hire" # Signals generator to only add salary in last 2 months
    },
    
    # 6. Salary + Bonus
    "bonus_user@test.com": {
        "starting_balance": 80000.0,
        "income": [
            {"type": "fixed_salary", "amount": 150000, "employer": "BIG TECH", "day": 1, "variation": 0},
            {"type": "bonus", "amount": 200000, "months": [3, 9], "day": 15}
        ],
        "fixed_expenses": [
            {"type": "emi", "amount": 45000, "lender": "HDFC HOME", "day": 5},
            {"type": "sip", "amount": 25000, "day": 10}
        ],
        "variable_expenses": {
            "upi_min": 1, "upi_max": 4, "upi_amt_min": 200, "upi_amt_max": 1500,
            "shopping_prob": 0.15, "shop_min": 3000, "shop_max": 15000,
            "grocery_prob": 0.15, "groc_min": 2000, "groc_max": 8000,
            "fuel_prob": 0.1, "fuel_min": 2000, "fuel_max": 4000,
            "atm_prob": 0.02, "atm_min": 5000, "atm_max": 10000
        },
        "edge_cases": {"bounce_prob": 0.0, "refund_prob": 0.05}
    },
    
    # 7. Salary + Side Income
    "side_hustle@test.com": {
        "starting_balance": 30000.0,
        "income": [
            {"type": "fixed_salary", "amount": 60000, "employer": "DAY JOB INC", "day": 1, "variation": 200},
            {"type": "freelance_random", "min": 5000, "max": 15000, "probability": 0.08, "clients": ["FREELANCE GIG", "UPWORK", "FIVERR"]}
        ],
        "fixed_expenses": [
            {"type": "emi", "amount": 12000, "lender": "CAR LOAN", "day": 5}
        ],
        "variable_expenses": {
            "upi_min": 1, "upi_max": 3, "upi_amt_min": 100, "upi_amt_max": 800,
            "shopping_prob": 0.1, "shop_min": 1000, "shop_max": 5000,
            "grocery_prob": 0.15, "groc_min": 1000, "groc_max": 3000,
            "fuel_prob": 0.1, "fuel_min": 1000, "fuel_max": 2000,
            "atm_prob": 0.05, "atm_min": 1000, "atm_max": 3000
        },
        "edge_cases": {"bounce_prob": 0.0, "refund_prob": 0.03}
    },
    
    # 8. Salary with Frequent Cash Deposits
    "cash_heavy@test.com": {
        "starting_balance": 10000.0,
        "income": [
            {"type": "fixed_salary", "amount": 40000, "employer": "LOCAL BIZ", "day": 1, "variation": 100},
            {"type": "cash_deposit", "probability": 0.1, "min": 2000, "max": 15000}
        ],
        "fixed_expenses": [
            {"type": "emi", "amount": 5000, "lender": "PERSONAL LOAN", "day": 7}
        ],
        "variable_expenses": {
            "upi_min": 1, "upi_max": 3, "upi_amt_min": 50, "upi_amt_max": 500,
            "shopping_prob": 0.05, "shop_min": 500, "shop_max": 2000,
            "grocery_prob": 0.1, "groc_min": 500, "groc_max": 2000,
            "fuel_prob": 0.1, "fuel_min": 500, "fuel_max": 1000,
            "atm_prob": 0.1, "atm_min": 1000, "atm_max": 5000
        },
        "edge_cases": {"bounce_prob": 0.02, "refund_prob": 0.01}
    }
}
