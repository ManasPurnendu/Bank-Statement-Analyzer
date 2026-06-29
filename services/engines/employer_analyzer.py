import re
from difflib import SequenceMatcher
from collections import defaultdict
from services.engines.context import StatementContext

class EmployerAnalyzer:
    """
    Cleans employer names from narratives, groups them using fuzzy matching, 
    and determines employer stability (handling sequential vs concurrent jobs).
    """
    
    CLEAN_WORDS = [
        r'\bPVT\b', r'\bPRIVATE\b', r'\bLTD\b', r'\bLIMITED\b', 
        r'\bPAYROLL\b', r'\bSALARY\b', r'\bSERVICES\b', r'\bTECHNOLOGIES\b',
        r'\bINC\b', r'\bLLP\b', r'\bCORP\b', r'\bCORPORATION\b'
    ]
    
    @staticmethod
    def clean_name(raw_name: str) -> str:
        name = raw_name.upper()
        # Remove common artifacts
        name = re.sub(r'[^A-Z0-9\s]', ' ', name)
        # Remove structural words
        for word in EmployerAnalyzer.CLEAN_WORDS:
            name = re.sub(word, '', name)
        # Collapse whitespace
        name = re.sub(r'\s+', ' ', name).strip()
        return name
        
    @staticmethod
    def is_similar(name1: str, name2: str) -> bool:
        if not name1 or not name2: return False
        # Over 80% similarity is a match
        ratio = SequenceMatcher(None, name1, name2).ratio()
        if ratio >= 0.80:
            return True
        # Substring match if one is significantly shorter
        if len(name1) > 3 and name1 in name2: return True
        if len(name2) > 3 and name2 in name1: return True
        return False

    @staticmethod
    def run(ctx: StatementContext):
        if not ctx.salary_candidates:
            ctx.employer_names = []
            ctx.primary_employer = None
            ctx.add_audit_trail("EmployerAnalyzer", "status", "No salary candidates to analyze")
            return
            
        # 1. Clean and group employer names
        employer_months = defaultdict(set) # Maps canonical name to set of month-strings
        
        for t in ctx.salary_candidates:
            raw_sender = str(t.get('payee_name', ''))
            if not raw_sender:
                # Fallback to first few words of description
                desc_words = str(t.get('description', '')).split()
                raw_sender = " ".join(desc_words[:3])
                
            cleaned = EmployerAnalyzer.clean_name(raw_sender)
            month_key = t['transaction_date'][:7]
            
            # Fuzzy match against existing canonical names
            matched = False
            for canonical in employer_months.keys():
                if EmployerAnalyzer.is_similar(canonical, cleaned):
                    employer_months[canonical].add(month_key)
                    matched = True
                    break
                    
            if not matched and cleaned:
                employer_months[cleaned].add(month_key)
                
        # 2. Determine Primary Employer and Employment Type
        canonical_names = list(employer_months.keys())
        ctx.employer_names = canonical_names
        
        if len(canonical_names) == 0:
            ctx.primary_employer = "UNKNOWN"
            ctx.add_audit_trail("EmployerAnalyzer", "status", "Could not extract employer names")
            return
            
        # The primary employer is the one present in the most months
        primary = max(canonical_names, key=lambda x: len(employer_months[x]))
        ctx.primary_employer = primary
        
        # 3. Analyze Sequential vs Concurrent
        if len(canonical_names) == 1:
            ctx.add_audit_trail("EmployerAnalyzer", "stability", "Single Stable Employer")
            ctx.add_positive_signal("Stable Employer")
        else:
            # Check if any two employers paid in the exact same month
            concurrent = False
            all_months_list = []
            for months in employer_months.values():
                all_months_list.extend(list(months))
                
            if len(all_months_list) > len(set(all_months_list)):
                concurrent = True
                
            if concurrent:
                ctx.add_audit_trail("EmployerAnalyzer", "stability", "Concurrent Employment (Multiple Income Sources)")
                ctx.add_positive_signal("Multiple Concurrent Income Streams")
            else:
                ctx.add_audit_trail("EmployerAnalyzer", "stability", "Sequential Employer Change (Job Switch)")
                ctx.add_risk_flag("WARNING", "Salary Source Changed", "Verify employment continuity")
                
        ctx.add_audit_trail("EmployerAnalyzer", "employers", canonical_names)
