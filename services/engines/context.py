from datetime import datetime
from collections import defaultdict
import math

class StatementContext:
    """
    A unified data object that is passed sequentially through all 
    Income Intelligence Engines. It holds the raw transactions, 
    calculated metadata, and the evolving outputs of each engine.
    """
    def __init__(self, transactions, statement_metadata=None):
        # Sort transactions by date for reliable chronological processing
        try:
            self.transactions = sorted(
                transactions, 
                key=lambda t: datetime.strptime(t['transaction_date'], '%Y-%m-%d')
            )
        except Exception:
            self.transactions = sorted(
                transactions, 
                key=lambda t: t['transaction_date']
            )
            
        self.metadata = statement_metadata or {}
        
        # --- Pre-Computed Transaction Meta ---
        self.total_transactions = len(self.transactions)
        
        if self.transactions:
            self.start_date = datetime.strptime(self.transactions[0]['transaction_date'], '%Y-%m-%d')
            self.end_date = datetime.strptime(self.transactions[-1]['transaction_date'], '%Y-%m-%d')
            delta = self.end_date - self.start_date
            self.months_of_data = max(1, math.ceil(delta.days / 30.0))
        else:
            self.start_date = None
            self.end_date = None
            self.months_of_data = 0
            
        # Group by month string (YYYY-MM) and pre-categorize for performance
        self.monthly_transactions = defaultdict(list)
        self.credits = []
        self.debits = []
        
        for t in self.transactions:
            month_key = t['transaction_date'][:7]
            self.monthly_transactions[month_key].append(t)
            
            # Pre-compute combined text for faster regex searching across engines
            desc = str(t.get('description', ''))
            payee = str(t.get('payee_name', ''))
            t['combined_text'] = f"{desc} {payee}".upper()
            
            if t.get('transaction_type') == 'Credit':
                self.credits.append(t)
            elif t.get('transaction_type') == 'Debit':
                self.debits.append(t)
            
        # --- Engine Outputs (Populated during pipeline execution) ---
        
        # Validation & Sufficiency
        self.eligibility_status = None # EXCELLENT_PROFILE, STABLE_PROFILE, MARGINAL_PROFILE, NON_SALARIED, INSUFFICIENT_DATA, PROCESSING_ERROR
        self.data_sufficiency_grade = None # Bronze, Silver, Gold
        
        # Salary & Employer
        self.salary_candidates = [] # High-confidence recurring credits
        self.confirmed_salary = 0.0
        self.salary_confidence_band = None # Confirmed, Likely, Possible, Rejected
        self.stability_score = 0.0
        self.date_consistency_score = 0.0
        self.employer_names = []
        self.primary_employer = None
        self.bonus_amount = 0.0
        
        # EMI & FOIR
        self.confirmed_emis = []
        self.total_fixed_obligations = 0.0
        self.foir_percentage = 0.0
        
        # Health & Balances
        self.statement_health_score = 100.0
        self.average_monthly_expenses = 0.0
        self.surplus_score = 0.0
        self.buffer_score = 0.0
        
        # Final Outputs
        self.final_readiness_score = 0.0
        self.risk_flags = []       # Dicts with severity, reason, action
        self.positive_signals = [] # Strings
        
        # Auditability
        self.calculation_metadata = {} # Engine decisions explaining WHY

    def add_audit_trail(self, engine_name, key, value):
        if engine_name not in self.calculation_metadata:
            self.calculation_metadata[engine_name] = {}
        self.calculation_metadata[engine_name][key] = value
        
    def add_risk_flag(self, severity, reason, action=None):
        self.risk_flags.append({
            "severity": severity,
            "reason": reason,
            "action": action
        })
        
    def add_positive_signal(self, signal):
        self.positive_signals.append(signal)

