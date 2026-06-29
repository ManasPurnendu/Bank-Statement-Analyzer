from services.engines.context import StatementContext

class BonusDetector:
    """
    Isolates variable pay (bonuses, arrears, incentives) from base salary.
    Checks for >150% spikes or explicit bonus keywords from the primary employer.
    """
    
    BONUS_KEYWORDS = ['BONUS', 'INCENTIVE', 'ARREARS', 'PERFORMANCE', 'VARIABLE PAY', 'EX-GRATIA']
    
    @staticmethod
    def run(ctx: StatementContext):
        ctx.bonus_amount = 0.0
        
        if not ctx.primary_employer or ctx.primary_employer == "UNKNOWN":
            ctx.add_audit_trail("BonusDetector", "status", "No primary employer to detect bonuses against")
            return
            
        base_salary = ctx.confirmed_salary
        if base_salary == 0:
            return
            
        all_credits = [t for t in ctx.transactions if t['transaction_type'] == 'Credit']
        
        detected_bonuses = []
        
        for t in all_credits:
            # Only consider credits from the primary employer
            sender = str(t.get('payee_name', '')).upper()
            desc = str(t.get('description', '')).upper()
            combined = f"{sender} {desc}"
            
            # Very loose matching to ensure we catch it
            # We already have a clean canonical name in ctx.primary_employer
            from services.engines.employer_analyzer import EmployerAnalyzer
            cleaned_sender = EmployerAnalyzer.clean_name(combined)
            
            if EmployerAnalyzer.is_similar(ctx.primary_employer, cleaned_sender):
                amt = float(t['amount'])
                is_bonus = False
                reason = ""
                
                # Check for keywords
                if any(kw in combined for kw in BonusDetector.BONUS_KEYWORDS):
                    is_bonus = True
                    reason = "Keyword Match"
                # Check for massive spike (150% of base)
                elif amt > (base_salary * 1.5):
                    is_bonus = True
                    reason = ">150% Spike"
                    
                if is_bonus:
                    # Is this transaction already in the base salary candidates?
                    # If it's a massive spike, it shouldn't be the base salary.
                    # We isolate the extra amount.
                    if amt > base_salary * 1.5:
                        isolated_bonus = amt - base_salary
                    else:
                        isolated_bonus = amt
                        
                    detected_bonuses.append({
                        "amount": isolated_bonus,
                        "date": t['transaction_date'],
                        "reason": reason
                    })
                    
        total_bonus = sum(b['amount'] for b in detected_bonuses)
        ctx.bonus_amount = total_bonus
        
        if total_bonus > 0:
            ctx.add_audit_trail("BonusDetector", "bonuses_found", detected_bonuses)
            ctx.add_positive_signal("Variable Pay / Bonus Detected")
