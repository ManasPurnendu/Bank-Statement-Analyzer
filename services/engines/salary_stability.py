import statistics
from services.engines.context import StatementContext

class SalaryStabilityEngine:
    """
    Measures the downward variance of base salary to determine stability.
    Upward variance (growth/bonuses) does not penalize stability.
    """
    @staticmethod
    def run(ctx: StatementContext):
        if not ctx.salary_candidates or len(ctx.salary_candidates) < 2:
            ctx.stability_score = 0.0
            ctx.add_audit_trail("SalaryStabilityEngine", "status", "Insufficient salary hits for stability analysis")
            return
            
        # Chronological amounts
        amounts = [float(t['amount']) for t in sorted(ctx.salary_candidates, key=lambda x: x['transaction_date'])]
        
        # Calculate downward variance only. 
        # Compare each month to the *max of all previous months* to see if income dropped.
        # Alternatively, use standard deviation but only for negative deviations from the median.
        
        median_salary = statistics.median(amounts)
        if median_salary == 0:
            ctx.stability_score = 0.0
            return
            
        downward_deviations = []
        for amt in amounts:
            if amt < median_salary:
                # How much did it drop from the median?
                drop = median_salary - amt
                downward_deviations.append(drop)
            else:
                # Zero downward deviation for upward growth
                downward_deviations.append(0)
                
        # Calculate mean downward deviation as a percentage of median
        mean_downward_drop = sum(downward_deviations) / len(downward_deviations)
        variance_pct = (mean_downward_drop / median_salary) * 100
        
        score = 0.0
        if variance_pct <= 5.0:
            score = 100.0 - variance_pct * 2 # 90-100 band
        elif variance_pct <= 10.0:
            score = 89.0 - (variance_pct - 5.0) * 2.8 # 75-89 band
        elif variance_pct <= 20.0:
            score = 74.0 - (variance_pct - 10.0) * 2.4 # 50-74 band
        else:
            score = max(0.0, 49.0 - (variance_pct - 20.0) * 1.5) # 0-49 band
            
        ctx.stability_score = round(score, 2)
        ctx.add_audit_trail("SalaryStabilityEngine", "downward_variance_pct", round(variance_pct, 2))
        ctx.add_audit_trail("SalaryStabilityEngine", "stability_score", ctx.stability_score)
        
        if variance_pct > 20.0:
            ctx.add_risk_flag("WARNING", "High Salary Downward Volatility", "Check for unpaid leaves or erratic income")
