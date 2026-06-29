from services.engines.context import StatementContext

class ReadinessEngine:
    """
    Calculates the final Loan Readiness Score using a weighted model.
    Applies data sufficiency capping to prevent short histories from artificially
    achieving 'Excellent' status.
    """
    
    # Configurable weights (Must equal 1.0)
    WEIGHTS = {
        'FOIR': 0.25,
        'STABILITY': 0.25,
        'HEALTH': 0.20,
        'CONFIDENCE': 0.15,
        'SURPLUS': 0.15
    }
    
    @staticmethod
    def run(ctx: StatementContext):
        if ctx.eligibility_status not in ["SALARIED_PENDING_SCORE"]:
            ctx.final_readiness_score = 0.0
            return
            
        # 1. FOIR Component (Lower is better. 0-20% is 100 points, >60% is 0 points)
        foir_score = max(0.0, 100.0 - (ctx.foir_percentage * 1.5))
        if ctx.foir_percentage > 60: foir_score = 0
            
        # 2. Stability Component
        stability_score = ctx.stability_score
        
        # 3. Health Component
        health_score = ctx.statement_health_score
        
        # 4. Confidence Component
        conf_map = {"Confirmed": 100.0, "Likely": 80.0, "Possible": 60.0, "Rejected": 0.0}
        confidence_score = conf_map.get(ctx.salary_confidence_band, 0.0)
        
        # 5. Surplus Component
        surplus_score = ctx.surplus_score
        
        # Calculate Base Readiness
        raw_score = (
            (foir_score * ReadinessEngine.WEIGHTS['FOIR']) +
            (stability_score * ReadinessEngine.WEIGHTS['STABILITY']) +
            (health_score * ReadinessEngine.WEIGHTS['HEALTH']) +
            (confidence_score * ReadinessEngine.WEIGHTS['CONFIDENCE']) +
            (surplus_score * ReadinessEngine.WEIGHTS['SURPLUS'])
        )
        
        # Apply Data Sufficiency Caps
        # Bronze: Max 60 (Moderate)
        # Silver: Max 80 (Low Risk)
        # Gold: Max 100 (Excellent)
        
        capped_score = raw_score
        if ctx.data_sufficiency_grade == "Bronze":
            capped_score = min(raw_score, 60.0)
        elif ctx.data_sufficiency_grade == "Silver":
            capped_score = min(raw_score, 80.0)
            
        ctx.final_readiness_score = round(capped_score, 2)
        
        # Assign Final Income Profile
        if ctx.final_readiness_score >= 80:
            ctx.eligibility_status = "EXCELLENT_PROFILE"
        elif ctx.final_readiness_score >= 60:
            ctx.eligibility_status = "STABLE_PROFILE"
        else:
            ctx.eligibility_status = "MARGINAL_PROFILE"
        
        # Decision Explanation Engine Integration
        ctx.add_audit_trail("ReadinessEngine", "raw_score", round(raw_score, 2))
        ctx.add_audit_trail("ReadinessEngine", "capped_score", ctx.final_readiness_score)
        ctx.add_audit_trail("ReadinessEngine", "assigned_profile", ctx.eligibility_status)
        
        # Build human readable explanation
        contributors = []
        deductions = []
        
        if foir_score > 80: contributors.append("+ Strong capacity (Low FOIR)")
        elif foir_score < 40: deductions.append("- High existing debt burden")
        
        if stability_score > 80: contributors.append("+ Highly stable income")
        elif stability_score < 50: deductions.append("- Erratic income history")
        
        if health_score == 100: contributors.append("+ Perfect banking discipline")
        elif health_score < 70: deductions.append("- Poor banking discipline (Bounces/Penalties)")
        
        if raw_score > capped_score:
            deductions.append(f"- Score capped due to {ctx.data_sufficiency_grade} data sufficiency")
            
        ctx.add_audit_trail("DecisionExplanation", "Contributors", contributors)
        ctx.add_audit_trail("DecisionExplanation", "Deductions", deductions)
