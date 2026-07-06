from collections import defaultdict
import statistics
import re
from services.engines.context import StatementContext

class SalaryDetector:
    """
    Identifies base salary with high confidence using a multi-band scoring model.
    Filters out reimbursements, UPI transfers, and business income.
    """
    
    FLOOR_AMOUNT = 5000.0
    
    STRONG_KEYWORDS = [
        'SALARY', 'PAYROLL', 'SAL', 'EMPLOYEE', 'HR ', 'WAGES', 
        'REMUNERATION', 'ACH CREDIT', 'CMS CREDIT', 'NEFT SALARY', 'SALARY CREDIT'
    ]
    
    WEAK_KEYWORDS = ['NEFT', 'IMPS', 'TRANSFER', 'BANK CREDIT']
    
    EXCLUSION_KEYWORDS = [
        'REFUND', 'CASH DEP', 'CASH DEPOSIT', 'UPI', 'WALLET', 
        'SWIGGY', 'ZOMATO', 'AMAZON', 'FLIPKART', 'REVERSAL', 
        'CASHBACK', 'REWARD', 'LOAN', 'EMI'
    ]

    # Precompile regex for massive speedup
    EXCLUSION_PATTERN = re.compile(r'REFUND|CASH DEP|CASH DEPOSIT|UPI|WALLET|SWIGGY|ZOMATO|AMAZON|FLIPKART|REVERSAL|CASHBACK|REWARD|LOAN|EMI')
    STRONG_PATTERN = re.compile(r'SALARY|PAYROLL|SAL|EMPLOYEE|HR |WAGES|REMUNERATION|ACH CREDIT|CMS CREDIT|NEFT SALARY|SALARY CREDIT')
    WEAK_PATTERN = re.compile(r'NEFT|IMPS|TRANSFER|BANK CREDIT')

    @staticmethod
    def run(ctx: StatementContext):
        # 1. Filter out obvious exclusions and below floor amount
        valid_candidates = []
        for t in ctx.credits:
            amt = float(t.get('amount', 0))
            if amt < SalaryDetector.FLOOR_AMOUNT:
                continue
                
            combined_text = t.get('combined_text', '')
            
            # Check exclusions using regex
            if SalaryDetector.EXCLUSION_PATTERN.search(combined_text):
                # Hard exclusion for UPI credits unless it explicitly says SALARY
                if 'UPI' in combined_text and 'SALARY' not in combined_text:
                    continue
                if 'REFUND' in combined_text or 'CASHBACK' in combined_text:
                    continue
            
            valid_candidates.append(t)
            
        # 2. Group candidates by approximate amount (to find recurrence)
        # We'll group by rounded amount (nearest 1000) or by sender name.
        # Grouping by sender is safer if available, but Indian descriptions are messy.
        # Let's group by extracting the sender name from description.
        
        sender_groups = defaultdict(list)
        for t in valid_candidates:
            # Simple sender extraction: use payee_name if exists, else first 2 words of desc
            sender = str(t.get('payee_name', '')).strip().upper()
            if not sender:
                desc = str(t.get('description', '')).strip().upper()
                words = desc.replace('-', ' ').split()
                sender = " ".join(words[:2]) if len(words) >= 2 else desc
            
            # Clean up standard artifacts
            for artifact in ['NEFT', 'IMPS', 'RTGS', 'UPI', 'CR', 'BY']:
                sender = sender.replace(artifact, '').strip()
                
            if not sender:
                sender = "UNKNOWN"
                
            sender_groups[sender].append(t)
            
        # 3. Evaluate each group using the Confidence Model
        best_group = None
        best_score = -1
        best_metadata = {}
        
        for sender, txns in sender_groups.items():
            score = 0
            audit = {}
            
            # A. Keyword Match (+40)
            combined_all_text = " ".join([t.get('combined_text', '') for t in txns])
            if SalaryDetector.STRONG_PATTERN.search(combined_all_text):
                score += 40
                audit['keyword_match'] = "Strong"
            elif SalaryDetector.WEAK_PATTERN.search(combined_all_text):
                score += 20
                audit['keyword_match'] = "Weak"
            else:
                audit['keyword_match'] = "None"
                
            # B. Monthly Recurrence (+30)
            months_present = set(t['transaction_date'][:7] for t in txns)
            recurrence_ratio = len(months_present) / float(ctx.months_of_data) if ctx.months_of_data > 0 else 0
            if recurrence_ratio >= 0.8:
                score += 30
            elif recurrence_ratio >= 0.5:
                score += 15
            audit['recurrence_ratio'] = recurrence_ratio
                
            # C. Amount Stability (+20)
            amounts = [float(t['amount']) for t in txns]
            if len(amounts) >= 2:
                mean_amt = statistics.mean(amounts)
                std_dev = statistics.stdev(amounts) if len(amounts) > 1 else 0
                cv = std_dev / mean_amt if mean_amt > 0 else 1
                if cv <= 0.05:
                    score += 20
                elif cv <= 0.20:
                    score += 10
                audit['amount_cv'] = cv
            else:
                audit['amount_cv'] = "N/A"
                
            # D. Same Sender Consistency (+10)
            # Since we grouped by sender, this is highly consistent unless the name is generic.
            if sender != "UNKNOWN" and len(txns) >= 2:
                score += 10
                audit['sender_consistency'] = "High"
            else:
                audit['sender_consistency'] = "Low"
                
            audit['total_confidence_score'] = score
            
            if score > best_score:
                best_score = score
                best_group = txns
                best_metadata = audit
                
        # 4. Assign results to context
        if best_score >= 90:
            ctx.salary_confidence_band = "Confirmed"
        elif best_score >= 75:
            ctx.salary_confidence_band = "Likely"
        elif best_score >= 60:
            ctx.salary_confidence_band = "Possible"
        else:
            ctx.salary_confidence_band = "Rejected"
            
        explanation = (
            f"Salary detection assigned a confidence band of '{ctx.salary_confidence_band}' "
            f"with a score of {best_score}/100. "
            f"Keyword Match: {best_metadata.get('keyword_match', 'None')}, "
            f"Recurrence: {best_metadata.get('recurrence_ratio', 0):.0%}, "
            f"Amount Variation (CV): {best_metadata.get('amount_cv', 'N/A')}."
        )
        
        ctx.add_audit_trail("SalaryDetector", "explanation", explanation)
        ctx.add_audit_trail("SalaryDetector", "best_score", best_score)
        ctx.add_audit_trail("SalaryDetector", "band", ctx.salary_confidence_band)
        ctx.add_audit_trail("SalaryDetector", "details", best_metadata)
            
        if ctx.salary_confidence_band != "Rejected" and best_group:
            ctx.salary_candidates = best_group
            
            # Aggregate salary amounts by month
            monthly_totals = defaultdict(float)
            for t in best_group:
                month = t['transaction_date'][:7]
                monthly_totals[month] += float(t['amount'])
                
            # Use median of the monthly totals to avoid bonus skew
            if monthly_totals:
                ctx.confirmed_salary = statistics.median(monthly_totals.values())
            else:
                ctx.confirmed_salary = 0.0
        else:
            ctx.salary_candidates = []
            ctx.confirmed_salary = 0.0
