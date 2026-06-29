from collections import defaultdict
import statistics
from services.engines.context import StatementContext

class EMIDetector:
    """
    Identifies fixed monthly obligations. 
    Implements the 'New EMI' override rule: explicit keywords override the 3-hit requirement.
    """
    
    EXCLUSION_DICT = [
        'NETFLIX', 'SPOTIFY', 'YOUTUBE', 'AMAZON', 'APPLE', 'GOOGLE', 
        'SWIGGY', 'ZEPTO', 'HOTSTAR', 'JIOCINEMA', 'ZOMATO', 'BLINKIT',
        'SIP', 'MUTUAL FUND', 'ZERODHA', 'GROWW', 'LIC', 'INSURANCE' # Investments are not debt
    ]
    
    INCLUSION_KEYWORDS = [
        'LOAN', 'EMI', 'FINANCE', 'BAJAJ', 'MORTGAGE', 'REPAYMENT', 
        'HOME LOAN', 'PERSONAL LOAN', 'AUTO LOAN', 'KOTAK MAHINDRA PRIME'
    ]

    @staticmethod
    def run(ctx: StatementContext):
        debits = [t for t in ctx.transactions if t['transaction_type'] == 'Debit']
        
        # Group debits by rounded amount (EMIs are typically exact amounts)
        # We will group by amount + sender
        grouped_debits = defaultdict(list)
        
        for t in debits:
            desc = str(t.get('description', '')).upper()
            payee = str(t.get('payee_name', '')).upper()
            combined = f"{desc} {payee}"
            
            if any(ex in combined for ex in EMIDetector.EXCLUSION_DICT):
                continue
                
            amt = float(t['amount'])
            if amt < 500: # Ignore tiny recurring charges
                continue
                
            # Key = Amount (rounded to nearest integer)
            key = int(round(amt, 0))
            grouped_debits[key].append((t, combined))
            
        confirmed_emis = []
        
        for amount_key, txns_data in grouped_debits.items():
            txns = [item[0] for item in txns_data]
            combined_texts = " ".join([item[1] for item in txns_data])
            
            has_keyword = any(kw in combined_texts for kw in EMIDetector.INCLUSION_KEYWORDS)
            
            # Rule: 3 occurrences required OR explicit keyword
            if len(txns) >= 3 or has_keyword:
                # Need to verify it's monthly recurring
                months = set(t['transaction_date'][:7] for t in txns)
                
                # If we have a keyword, we confirm it even if it's 1 month (New EMI blindspot fix)
                if has_keyword or len(months) >= 3:
                    band = "Confirmed" if has_keyword else "Likely"
                    
                    confirmed_emis.append({
                        "amount": amount_key, # Use the rounded recurring amount
                        "occurrences": len(txns),
                        "months_active": len(months),
                        "confidence_band": band,
                        "description_sample": txns[0].get('description')
                    })
                    
        ctx.confirmed_emis = confirmed_emis
        ctx.total_fixed_obligations = sum(emi['amount'] for emi in confirmed_emis)
        
        ctx.add_audit_trail("EMIDetector", "total_obligations", ctx.total_fixed_obligations)
        ctx.add_audit_trail("EMIDetector", "detected_count", len(confirmed_emis))
