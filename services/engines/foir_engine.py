from services.engines.context import StatementContext

class FOIREngine:
    """
    Calculates the Fixed Obligation to Income Ratio (FOIR).
    Provides risk flags if FOIR exceeds thresholds.
    """
    
    @staticmethod
    def run(ctx: StatementContext):
        if ctx.confirmed_salary <= 0:
            ctx.foir_percentage = 0.0
            ctx.add_audit_trail("FOIREngine", "status", "No confirmed salary to calculate FOIR")
            return
            
        foir = (ctx.total_fixed_obligations / ctx.confirmed_salary) * 100
        ctx.foir_percentage = round(foir, 2)
        
        explanation = (
            f"Calculated FOIR of {ctx.foir_percentage}% based on total fixed obligations "
            f"of ₹{ctx.total_fixed_obligations:,.2f} against a confirmed monthly salary "
            f"of ₹{ctx.confirmed_salary:,.2f}."
        )
        ctx.add_audit_trail("FOIREngine", "explanation", explanation)
        ctx.add_audit_trail("FOIREngine", "foir_pct", ctx.foir_percentage)
        
        if ctx.foir_percentage > 60.0:
            ctx.add_risk_flag("CRITICAL", "High FOIR", f"FOIR is {ctx.foir_percentage}% (>60%). Debt trap risk.")
        elif ctx.foir_percentage > 50.0:
            ctx.add_risk_flag("WARNING", "Elevated FOIR", f"FOIR is {ctx.foir_percentage}% (>50%).")
        elif ctx.foir_percentage < 20.0 and ctx.foir_percentage > 0.0:
            ctx.add_positive_signal(f"Very Low FOIR ({ctx.foir_percentage}%)")
