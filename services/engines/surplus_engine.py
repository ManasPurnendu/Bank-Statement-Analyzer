from services.engines.context import StatementContext

class SurplusEngine:
    """
    Calculates the actual unencumbered cash remaining at the end of the month.
    """
    @staticmethod
    def run(ctx: StatementContext):
        if ctx.months_of_data <= 0 or ctx.confirmed_salary <= 0:
            ctx.average_monthly_expenses = 0.0
            ctx.surplus_score = 0.0
            return
            
        # Exclude massive outliers from general living expenses (e.g., transfers, investments)
        max_living_expense = (ctx.confirmed_salary * 1.5) if ctx.confirmed_salary > 0 else float('inf')
        
        all_debits = []
        for t in ctx.transactions:
            if t['transaction_type'] == 'Debit':
                amt = float(t['amount'])
                if amt <= max_living_expense:
                    all_debits.append(amt)
                    
        total_debits = sum(all_debits)
        
        # Approximate monthly non-EMI expenses
        # total_debits includes EMIs. We want general living expenses.
        # But for total outflow, we can just use total_debits / months.
        average_total_outflow = total_debits / ctx.months_of_data
        
        ctx.average_monthly_expenses = max(0, average_total_outflow - ctx.total_fixed_obligations)
        
        absolute_surplus = ctx.confirmed_salary - ctx.total_fixed_obligations - ctx.average_monthly_expenses
        surplus_pct = (absolute_surplus / ctx.confirmed_salary) * 100 if ctx.confirmed_salary > 0 else 0
        
        if surplus_pct > 40:
            ctx.surplus_score = 100.0
        elif surplus_pct >= 25:
            ctx.surplus_score = 80.0
        elif surplus_pct >= 10:
            ctx.surplus_score = 60.0
        elif surplus_pct > 0:
            ctx.surplus_score = 30.0
        else:
            ctx.surplus_score = 0.0
            ctx.add_risk_flag("WARNING", "Negative Surplus", "Living expenses exceed income.")
            
        if surplus_pct > 25:
            ctx.add_positive_signal("Healthy Monthly Surplus")
            
        ctx.add_audit_trail("SurplusEngine", "absolute_surplus", absolute_surplus)
        ctx.add_audit_trail("SurplusEngine", "surplus_pct", round(surplus_pct, 2))
