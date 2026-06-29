from services.engines.context import StatementContext

class StatementHealthEngine:
    """
    Applies graduated penalties based on poor banking behaviors 
    (bounces, negative balances, low balances).
    """
    
    RETURN_KEYWORDS = ['RETURN', 'BOUNCE', 'INSUFFICIENT FUNDS', 'CHQ RET', 'ECS RET', 'REJECT']
    
    @staticmethod
    def run(ctx: StatementContext):
        score = 100.0
        
        negative_balance_events = 0
        low_balance_events = 0
        return_events = 0
        
        for t in ctx.transactions:
            bal = float(t.get('balance') or 0.0)
            if bal < 0:
                negative_balance_events += 1
            elif bal < 500:
                low_balance_events += 1
                
            desc = str(t.get('description', '')).upper()
            if any(kw in desc for kw in StatementHealthEngine.RETURN_KEYWORDS):
                return_events += 1
                
        # Apply Graduated Penalties
        
        # Negative Balances
        if negative_balance_events >= 4:
            score -= 40
        elif negative_balance_events >= 2:
            score -= 20
        elif negative_balance_events == 1:
            score -= 10
            
        # Low Balances
        if low_balance_events >= 10:
            score -= 30
        elif low_balance_events >= 6:
            score -= 15
        elif low_balance_events >= 1:
            score -= 5
            
        # Returned Txns
        if return_events >= 5:
            score -= 40
        elif return_events >= 2:
            score -= 20
        elif return_events == 1:
            score -= 10
            
        ctx.statement_health_score = max(0.0, score)
        
        ctx.add_audit_trail("StatementHealth", "negative_events", negative_balance_events)
        ctx.add_audit_trail("StatementHealth", "low_events", low_balance_events)
        ctx.add_audit_trail("StatementHealth", "return_events", return_events)
        
        if return_events >= 2:
            ctx.add_risk_flag("WARNING", "Multiple Returned Transactions", "Check for poor cash flow management")
        if negative_balance_events >= 3:
            ctx.add_risk_flag("CRITICAL", "Frequent Negative Balances", "Account frequently operates in OD or penalties")
        elif return_events == 0 and negative_balance_events == 0:
            ctx.add_positive_signal("Zero Returned Transactions")
