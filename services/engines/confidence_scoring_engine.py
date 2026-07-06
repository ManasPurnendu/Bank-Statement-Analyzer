from services.engines.context import StatementContext

class ConfidenceScoringEngine:
    """
    Calculates the final Salary Confidence Score based on detection metrics.
    Applies data sufficiency capping to prevent short histories from achieving 'Verified' status.
    """
    
    @staticmethod
    def run(ctx: StatementContext):
        if ctx.income_classification not in ["SALARIED_PENDING_SCORE"]:
            ctx.income_confidence_score = 0.0
            return
            
        # 1. Fetch raw confidence score from SalaryDetector
        salary_detector_metadata = ctx.calculation_metadata.get("SalaryDetector", {})
        raw_score = salary_detector_metadata.get("best_score", 0.0)
        
        # Apply Data Sufficiency Caps
        # Bronze (1-2 months): Max 60 (Possible)
        # Silver (3-5 months): Max 80 (Likely)
        # Gold (6+ months): Max 100 (Verified)
        
        capped_score = raw_score
        if ctx.data_sufficiency_grade == "Bronze":
            capped_score = min(raw_score, 60.0)
        elif ctx.data_sufficiency_grade == "Silver":
            capped_score = min(raw_score, 80.0)
            
        ctx.income_confidence_score = round(capped_score, 2)
        
        # Assign Final Income Profile
        if ctx.income_confidence_score >= 90:
            ctx.income_classification = "VERIFIED_SALARY"
        elif ctx.income_confidence_score >= 75:
            ctx.income_classification = "LIKELY_SALARY"
        elif ctx.income_confidence_score >= 60:
            ctx.income_classification = "POSSIBLE_SALARY"
        else:
            ctx.income_classification = "UNVERIFIED_INCOME"
        
        # Decision Explanation Engine Integration
        ctx.add_audit_trail("ConfidenceScoringEngine", "raw_score", round(raw_score, 2))
        ctx.add_audit_trail("ConfidenceScoringEngine", "capped_score", ctx.income_confidence_score)
        ctx.add_audit_trail("ConfidenceScoringEngine", "assigned_profile", ctx.income_classification)
        
        # Build human readable explanation
        contributors = []
        deductions = []
        
        if salary_detector_metadata.get("keyword_match") == "Strong":
            contributors.append("+ Strong payroll keyword match")
        elif salary_detector_metadata.get("keyword_match") == "None":
            deductions.append("- Missing standard payroll keywords")
            
        if salary_detector_metadata.get("recurrence_ratio", 0) >= 0.8:
            contributors.append("+ High monthly recurrence")
        elif salary_detector_metadata.get("recurrence_ratio", 0) < 0.5:
            deductions.append("- Irregular recurrence pattern")
            
        if raw_score > capped_score:
            deductions.append(f"- Confidence capped due to {ctx.data_sufficiency_grade} data sufficiency")
            
        ctx.add_audit_trail("DecisionExplanation", "Contributors", contributors)
        ctx.add_audit_trail("DecisionExplanation", "Deductions", deductions)
