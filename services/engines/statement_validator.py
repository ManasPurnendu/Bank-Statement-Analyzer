from services.engines.context import StatementContext

class StatementValidator:
    """
    Validates the physical integrity and minimum data requirements 
    of the bank statement before executing heavy analytic engines.
    """
    
    MIN_MONTHS_REQUIRED = 3
    MIN_TRANSACTIONS_REQUIRED = 20
    
    @staticmethod
    def validate_initial(ctx: StatementContext):
        """
        Runs before any engines. Checks basic data sufficiency.
        """
        if ctx.total_transactions == 0:
            ctx.eligibility_status = "PROCESSING_ERROR"
            ctx.add_audit_trail("StatementValidator", "failure_reason", "Zero transactions found")
            return
            
        if ctx.months_of_data < StatementValidator.MIN_MONTHS_REQUIRED:
            ctx.eligibility_status = "INSUFFICIENT_DATA"
            ctx.add_audit_trail(
                "StatementValidator", 
                "failure_reason", 
                f"Only {ctx.months_of_data} months of data available. Minimum {StatementValidator.MIN_MONTHS_REQUIRED} required."
            )
            return
            
        if ctx.total_transactions < StatementValidator.MIN_TRANSACTIONS_REQUIRED:
            ctx.eligibility_status = "INSUFFICIENT_DATA"
            ctx.add_audit_trail(
                "StatementValidator", 
                "failure_reason", 
                f"Only {ctx.total_transactions} transactions available. Minimum {StatementValidator.MIN_TRANSACTIONS_REQUIRED} required."
            )
            return
            
        # Basic parsing error check: ensure balances are numbers
        for t in ctx.transactions:
            if t.get('balance') is None or t.get('amount') is None:
                ctx.eligibility_status = "PROCESSING_ERROR"
                ctx.add_audit_trail("StatementValidator", "failure_reason", "Missing critical numeric fields (amount/balance)")
                return
                
        # If we pass basic checks, it is conditionally ELIGIBLE pending salary detection
        ctx.eligibility_status = "SALARIED_PENDING_SCORE"
        
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
        if ctx.eligibility_status not in ["SALARIED_PENDING_SCORE"]:
            return
            
        if not ctx.salary_confidence_band or ctx.salary_confidence_band == "Rejected":
            ctx.eligibility_status = "NON_SALARIED"
            ctx.add_audit_trail("StatementValidator", "failure_reason", "No reliable salary detected.")
            return
            
        # Confirmed, Likely, or Possible -> SALARIED_PENDING_SCORE
        ctx.eligibility_status = "SALARIED_PENDING_SCORE"
