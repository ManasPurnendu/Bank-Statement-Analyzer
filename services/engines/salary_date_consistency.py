import statistics
from datetime import datetime
from services.engines.context import StatementContext

class SalaryDateConsistencyEngine:
    """
    Calculates the variance in salary credit dates, specifically adjusting 
    for weekends to avoid false negatives (e.g. paying on Friday the 29th 
    because the 1st is a Sunday).
    """
    
    @staticmethod
    def _is_weekend(dt):
        return dt.isoweekday() >= 6 # 6 = Saturday, 7 = Sunday
        
    @staticmethod
    def _get_business_day_offset(dt):
        """
        Returns the effective 'target' day of the month.
        If a payment happened on Friday 29th, it might be targeting the 1st.
        For simplicity, we track the relative day drift ignoring weekends.
        """
        # A simple approximation: if it falls on Friday 29th, 30th, we treat it as 1st of next month
        # but to keep it mathematically sound for variance, we just calculate the difference 
        # in actual days, minus weekend days between them.
        pass

    @staticmethod
    def run(ctx: StatementContext):
        if not ctx.salary_candidates or len(ctx.salary_candidates) < 2:
            ctx.date_consistency_score = 0.0
            ctx.add_audit_trail("SalaryDateConsistency", "status", "Insufficient dates")
            return
            
        dates = []
        for t in ctx.salary_candidates:
            if isinstance(t['transaction_date'], str):
                dt = datetime.strptime(t['transaction_date'], '%Y-%m-%d')
            else:
                dt = t['transaction_date']
            # If the date is near the end of the month (28-31), normalize it to 0 for variance comparison
            # against the 1st/2nd. E.g., 29th and 1st have a distance of 2-3 days, not 28 days.
            
            day = dt.day
            if day >= 27:
                day = day - 31 # Normalizes late month to negative days (-4 to 0), close to the 1st
                
            dates.append(day)
            
        variance_days = max(dates) - min(dates)
        
        # We allow a baseline 2-day variance for weekends. 
        adjusted_variance = max(0, variance_days - 2)
        
        if adjusted_variance <= 3:
            ctx.date_consistency_score = 100.0 # Excellent
        elif adjusted_variance <= 7:
            ctx.date_consistency_score = 80.0  # Good
        elif adjusted_variance <= 14:
            ctx.date_consistency_score = 60.0  # Moderate
        else:
            ctx.date_consistency_score = 30.0  # Weak
            ctx.add_risk_flag("INFO", "Inconsistent Salary Dates", f"Salary drifts by up to {variance_days} days")
            
        ctx.add_audit_trail("SalaryDateConsistency", "max_variance_days", variance_days)
        ctx.add_audit_trail("SalaryDateConsistency", "adjusted_variance_days", adjusted_variance)
        ctx.add_audit_trail("SalaryDateConsistency", "score", ctx.date_consistency_score)
