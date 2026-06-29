from services.engines.context import StatementContext

class BufferEngine:
    """
    Calculates the Emergency Buffer (how many months of expenses the user can survive).
    Implements the 'Wealthy but Illiquid' fix by treating investments as buffer.
    """
    
    INVESTMENT_KEYWORDS = ['SIP', 'MUTUAL FUND', 'ZERODHA', 'GROWW', 'FD DEPOSIT', 'INDMONEY', 'UPSTOX', 'KITE']
    
    @staticmethod
    def run(ctx: StatementContext):
        # 1. Calculate Average Daily Balance
        balances = []
        investments = 0.0
        
        for t in ctx.transactions:
            if t.get('balance') is not None:
                balances.append(float(t['balance']))
                
            # Track investments
            if t['transaction_type'] == 'Debit':
                desc = str(t.get('description', '')).upper()
                payee = str(t.get('payee_name', '')).upper()
                combined = f"{desc} {payee}"
                if any(kw in combined for kw in BufferEngine.INVESTMENT_KEYWORDS):
                    investments += float(t['amount'])
                    
        avg_daily_balance = (sum(balances) / len(balances)) if balances else 0.0
        avg_monthly_investment = investments / ctx.months_of_data if ctx.months_of_data > 0 else 0.0
        
        # Effective liquidity buffer includes average bank balance + monthly investments
        # (Assuming they have accumulated investments roughly equal to 12x their monthly, 
        # but conservatively we just add the monthly run rate or a multiplier).
        # Actually, let's just add the total investments seen in the period to the available liquidity.
        
        effective_liquidity = avg_daily_balance + investments
        
        if ctx.average_monthly_expenses <= 0:
            ctx.buffer_score = 0.0
            return
            
        months_of_buffer = effective_liquidity / ctx.average_monthly_expenses
        
        if months_of_buffer >= 6.0:
            ctx.buffer_score = 100.0
            ctx.add_positive_signal("Excellent Emergency Buffer (>6 months)")
        elif months_of_buffer >= 3.0:
            ctx.buffer_score = 80.0
            ctx.add_positive_signal("Strong Emergency Buffer (>3 months)")
        elif months_of_buffer >= 1.0:
            ctx.buffer_score = 50.0
        else:
            ctx.buffer_score = 20.0
            
        ctx.add_audit_trail("BufferEngine", "avg_daily_balance", avg_daily_balance)
        ctx.add_audit_trail("BufferEngine", "total_investments_seen", investments)
        ctx.add_audit_trail("BufferEngine", "months_of_buffer", round(months_of_buffer, 2))
