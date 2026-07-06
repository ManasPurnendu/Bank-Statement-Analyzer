from services.engines.context import StatementContext

class StatementValidator:
    """
    Validates the physical integrity and minimum data requirements 
    of the bank statement before executing heavy analytic engines.
    """
    
    MIN_MONTHS_REQUIRED = 3
    MIN_TXNS_PER_MONTH = 5
    ABSOLUTE_MIN_TXNS = 5
    
    @staticmethod
    def validate_initial(ctx: StatementContext):
        """
        Runs before any engines. Checks basic data sufficiency.
        """
        if ctx.total_transactions == 0:
            ctx.income_classification = "PROCESSING_ERROR"
            ctx.add_audit_trail("StatementValidator", "failure_reason", "Zero transactions found")
            return
            
        if ctx.months_of_data < StatementValidator.MIN_MONTHS_REQUIRED:
            ctx.income_classification = "INSUFFICIENT_DATA"
            ctx.add_audit_trail(
                "StatementValidator", 
                "failure_reason", 
                f"Only {ctx.months_of_data} months of data available. Minimum {StatementValidator.MIN_MONTHS_REQUIRED} required."
            )
            return
            
        dynamic_min_txns = max(StatementValidator.ABSOLUTE_MIN_TXNS, ctx.months_of_data * StatementValidator.MIN_TXNS_PER_MONTH)
        if ctx.total_transactions < dynamic_min_txns:
            ctx.income_classification = "INSUFFICIENT_DATA"
            ctx.add_audit_trail(
                "StatementValidator", 
                "failure_reason", 
                f"Only {ctx.total_transactions} transactions available. Minimum {dynamic_min_txns} required for {ctx.months_of_data} months of data."
            )
            return
            
        # Basic parsing error check: ensure balances are numbers
        for t in ctx.transactions:
            if t.get('balance') is None or t.get('amount') is None:
                ctx.income_classification = "PROCESSING_ERROR"
                ctx.add_audit_trail("StatementValidator", "failure_reason", "Missing critical numeric fields (amount/balance)")
                return
                
        # If we pass basic checks, it is conditionally ELIGIBLE pending salary detection
        ctx.income_classification = "SALARIED_PENDING_SCORE"
        
        # Calculate Data Sufficiency Grade
        if ctx.months_of_data >= 12:
            ctx.data_sufficiency_grade = "Gold"
        elif ctx.months_of_data >= 6:
            ctx.data_sufficiency_grade = "Silver"
        else:
            ctx.data_sufficiency_grade = "Bronze"
            
        ctx.add_audit_trail("StatementValidator", "data_sufficiency_grade", ctx.data_sufficiency_grade)

    @staticmethod
    def validate_salary_presence(ctx: StatementContext):
        """
        Runs immediately after the Salary Detector. 
        Updates eligibility based on the multi-band confidence.
        """
        # If it was already failed by initial validation, don't override
        if ctx.income_classification not in ["SALARIED_PENDING_SCORE"]:
            return
            
        if not ctx.salary_confidence_band or ctx.salary_confidence_band == "Rejected":
            ctx.income_classification = "NON_SALARIED"
            ctx.add_audit_trail("StatementValidator", "failure_reason", "No reliable salary detected.")
            return
            
        # Confirmed, Likely, or Possible -> SALARIED_PENDING_SCORE
        ctx.income_classification = "SALARIED_PENDING_SCORE"
