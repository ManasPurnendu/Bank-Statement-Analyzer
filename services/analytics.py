from database.models import get_all_transactions_for_analytics, get_all_statements
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

def get_date_range_for_type(range_type):
    statements = get_all_statements()
    if not statements:
        return None, None
        
    all_ends = [pd.to_datetime(s['end_date']) for s in statements]
    max_end = max(all_ends).to_pydatetime()
    
    if range_type == 'this-month':
        start_date = max_end.replace(day=1)
        end_date = max_end
    elif range_type == 'last-month':
        first_of_this_month = max_end.replace(day=1)
        last_month_end = first_of_this_month - timedelta(days=1)
        start_date = last_month_end.replace(day=1)
        end_date = last_month_end
    elif range_type == 'this-quarter':
        q_start_month = ((max_end.month - 1) // 3) * 3 + 1
        start_date = datetime(max_end.year, q_start_month, 1)
        end_date = max_end
    elif range_type == 'last-3-months':
        start_date = (max_end - pd.DateOffset(months=2)).replace(day=1).to_pydatetime()
        end_date = max_end
    elif range_type == 'last-6-months':
        start_date = (max_end - pd.DateOffset(months=5)).replace(day=1).to_pydatetime()
        end_date = max_end
    elif range_type == 'this-year':
        start_date = datetime(max_end.year, 1, 1)
        end_date = max_end
    elif range_type == 'last-year':
        start_date = datetime(max_end.year - 1, 1, 1)
        end_date = datetime(max_end.year - 1, 12, 31)
    else: # 'all' or default
        # Return all statements range for All Time filter to enable explicit date ranges
        all_starts = [pd.to_datetime(s['start_date']) for s in statements]
        start_date = min(all_starts).to_pydatetime()
        end_date = max_end
        
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

def calculate_analytics(start_date=None, end_date=None):
    """
    Computes all analytical aggregates from stored transaction data.
    """
    txs = get_all_transactions_for_analytics(start_date, end_date)
    statements = get_all_statements()
    
    if not txs:
        account_holder = "Manas Purnendu"
        if statements:
            for s in statements:
                if s.get("account_holder"):
                    account_holder = s["account_holder"]
                    break
        return {
            "start_date": start_date or "",
            "end_date": end_date or "",
            "account_holder": account_holder,
            "kpis": {
                "income": 0.0,
                "expense": 0.0,
                "savings": 0.0,
                "savings_rate": 0.0,
                "balance": 0.0,
                "transaction_count": 0,
                "average_monthly_spend": 0.0,
                "busiest_day": "None",
                "highest_category": "None"
            },
            "category_spending": [],
            "monthly_trends": [],
            "top_merchants": [],
            "top_contacts": [],
            "subscriptions": [],
            "payment_methods": [],
            "weekly_heatmap": {d: 0.0 for d in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]},
            "data_coverage": [],
            "raw_count": 0
        }

    # Load into DataFrame for easy calculations
    df = pd.DataFrame(txs)
    df['transaction_date'] = pd.to_datetime(df['transaction_date'])
    df['amount'] = df['amount'].astype(float)
    df['balance'] = df['balance'].astype(float)
    
    # 1. KPIs
    credits = df[df['transaction_type'] == 'Credit']
    debits = df[df['transaction_type'] == 'Debit']
    
    total_income = credits['amount'].sum()
    total_expense = debits['amount'].sum()
    net_savings = total_income - total_expense
    savings_rate = (net_savings / total_income * 100) if total_income > 0 else 0.0
    
    # Current balance is the balance of the latest transaction
    # Chronological sort is done in models, so the last element is the latest
    current_balance = float(df.iloc[-1]['balance']) if 'balance' in df.columns and len(df) > 0 else 0.0
    
    # Calculate months span
    min_date = df['transaction_date'].min()
    max_date = df['transaction_date'].max()
    
    active_start = start_date if start_date else min_date.strftime('%Y-%m-%d')
    active_end = end_date if end_date else max_date.strftime('%Y-%m-%d')
    
    start_dt = pd.to_datetime(active_start)
    end_dt = pd.to_datetime(active_end)
    if start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt
    all_months = pd.period_range(start=start_dt, end=end_dt, freq='M').astype(str).tolist()
    
    month_span = len(all_months)
    average_monthly_spend = total_expense / max(1, month_span)
    
    # Busiest Day of week
    df['day_name'] = df['transaction_date'].dt.day_name()
    day_spend = df[df['transaction_type'] == 'Debit'].groupby('day_name')['amount'].sum()
    busiest_day = day_spend.idxmax() if not day_spend.empty else "None"
    busiest_day_amount = day_spend.max() if not day_spend.empty else 0.0

    # 2. Category Spending (Debits only)
    cat_df = df[df['transaction_type'] == 'Debit'].groupby('category_name')['amount'].sum().reset_index()
    cat_df['percentage'] = (cat_df['amount'] / total_expense * 100) if total_expense > 0 else 0.0
    cat_df = cat_df.sort_values(by='amount', ascending=False)
    category_spending = cat_df.to_dict(orient='records')
    
    highest_category = category_spending[0]['category_name'] if category_spending else "None"
    
    # 3. Monthly Trends
    df['month_period'] = df['transaction_date'].dt.to_period('M').astype(str)
    monthly_inc = df[df['transaction_type'] == 'Credit'].groupby('month_period')['amount'].sum()
    monthly_exp = df[df['transaction_type'] == 'Debit'].groupby('month_period')['amount'].sum()
    
    # Identify covered months across all statements
    covered_months = set()
    for s in statements:
        try:
            s_start = pd.to_datetime(s['start_date']).to_period('M')
            s_end = pd.to_datetime(s['end_date']).to_period('M')
            p_range = pd.period_range(start=s_start, end=s_end, freq='M').astype(str).tolist()
            covered_months.update(p_range)
        except Exception:
            continue
            
    # Fallback to include any months that actually have transaction records
    all_months_with_txs = set(df['month_period']) if 'month_period' in df.columns else set()
    covered_months.update(all_months_with_txs)
    
    monthly_trends = []
    for m in all_months:
        if m in covered_months:
            inc = float(monthly_inc.get(m, 0.0))
            exp = float(monthly_exp.get(m, 0.0))
            sav = inc - exp
            sav_rate = (sav / inc * 100) if inc > 0 else 0.0
            tx_count = int((df['month_period'] == m).sum())
        else:
            inc = None
            exp = None
            sav = None
            sav_rate = None
            tx_count = None
            
        monthly_trends.append({
            "month": m, # "2025-01"
            "income": inc,
            "expense": exp,
            "savings": sav,
            "savings_rate": sav_rate,
            "transaction_count": tx_count
        })
        
    # 4. Merchant Analysis
    merchants_df = df[(df['transaction_type'] == 'Debit') & df['merchant_name'].notna() & (df['merchant_name'] != '')]
    if not merchants_df.empty:
        m_agg = merchants_df.groupby('merchant_name').agg(
            total_spend=('amount', 'sum'),
            transaction_count=('amount', 'count'),
            average_transaction_value=('amount', 'mean')
        ).reset_index()
        m_agg = m_agg.sort_values(by='total_spend', ascending=False)
        top_merchants = m_agg.to_dict(orient='records')
    else:
        top_merchants = []
        
    # 5. Contact Analysis
    contacts_df = df[(df['transaction_type'] == 'Debit') & df['payee_name'].notna() & (df['payee_name'] != '')]
    # Filter out merchant duplicates that might have leaked into payee_name
    merchant_keywords = ["AMAZON", "SWIGGY", "ZOMATO", "UBER", "OLA", "NETFLIX", "SPOTIFY", "RELIANCE", "FLIPKART", "MICROSOFT", "YOUTUBE", "PRIME", "GOOGLE", "APPLE", "BESCOM", "ACT FIBERNET"]
    if not contacts_df.empty:
        contacts_df = contacts_df[~contacts_df['payee_name'].str.upper().str.contains('|'.join(merchant_keywords), na=False)]
        
    if not contacts_df.empty:
        c_agg = contacts_df.groupby('payee_name').agg(
            total_spend=('amount', 'sum'),
            transaction_count=('amount', 'count'),
            average_transaction_value=('amount', 'mean')
        ).reset_index()
        c_agg = c_agg.sort_values(by='total_spend', ascending=False)
        top_contacts = c_agg.to_dict(orient='records')
    else:
        top_contacts = []
        
    # 6. Subscription Detection
    # Subscriptions are recurring debits. Look for debits from the same merchant (or payee) with similar amounts at regular intervals.
    subscriptions = []
    # Group by merchant name
    sub_candidates = df[df['transaction_type'] == 'Debit'].copy()
    
    # We can group by merchant_name or payee_name
    sub_candidates['entity'] = sub_candidates['merchant_name'].fillna(sub_candidates['payee_name'])
    sub_candidates = sub_candidates[sub_candidates['entity'].notna() & (sub_candidates['entity'] != '')]
    
    # Hardcoded known subscription merchants to auto-detect
    known_subs = ['Netflix', 'Spotify', 'Youtube Premium', 'Amazon Prime', 'Google One', 'Apple Music', 'Microsoft 365', 'Disney+ Hotstar', 'Apple', 'Google', 'Github', 'Adobe', 'Zoom', 'Canva', 'Slack', 'Claude', 'OpenAI', 'ChatGPT', 'Microsoft']
    
    if not sub_candidates.empty:
        for entity, group in sub_candidates.groupby('entity'):
            # Clean entity name for checks
            entity_upper = entity.upper()
            
            # Check if this is a known sub (case-insensitive check)
            is_known = any(ks.upper() in entity_upper for ks in known_subs)
            
            # Check for obvious false positives (cheques, rent, dining, pharmacy, person names)
            exclude_kws = ["RENT", "PHARMACY", "APOLLO", "DOMINO", "PIZZA", "ANISH", "NATH", "CHEQUE", "CHQ-", "CASH", "ATM", "TRANSFER", "REFUND", "INTEREST", "SWIGGY", "ZOMATO"]
            is_excluded = any(kw in entity_upper for kw in exclude_kws)
            
            # If it contains exclude keywords and is not a verified known sub, skip it
            if is_excluded and not is_known:
                continue
                
            # Check category: exclude food, healthcare, travel, personal transfers, etc., unless verified known sub
            cat_name = group.iloc[0]['category_name']
            if cat_name in ["Food & Dining", "Healthcare", "Travel", "Transfer", "Investment", "Shopping", "Uncategorized"]:
                if not is_known:
                    continue
            
            # Sort group by date
            group = group.sort_values(by='transaction_date')
            
            if len(group) >= 2 or is_known:
                # Calculate gaps in days between consecutive transactions
                dates = group['transaction_date'].tolist()
                gaps = [(dates[i] - dates[i-1]).days for i in range(1, len(dates))]
                
                # Check for monthly recurring (~30 days)
                is_monthly = any(25 <= g <= 35 for g in gaps)
                is_quarterly = any(80 <= g <= 100 for g in gaps)
                is_yearly = any(340 <= g <= 380 for g in gaps)
                
                # Check for similar amount (+/- 15%)
                amounts = group['amount'].tolist()
                avg_amt = np.mean(amounts)
                similar_amt = all(abs(a - avg_amt) / avg_amt < 0.15 for a in amounts) if len(amounts) > 1 else True
                
                if is_known or ((is_monthly or is_quarterly or is_yearly) and similar_amt):
                    # Determine frequency
                    frequency = "Monthly"
                    if is_quarterly:
                        frequency = "Quarterly"
                    elif is_yearly:
                        frequency = "Yearly"
                        
                    # Estimate next billing date (last date + frequency period)
                    last_date = dates[-1]
                    if frequency == "Monthly":
                        next_billing = last_date + timedelta(days=30)
                    elif frequency == "Quarterly":
                        next_billing = last_date + timedelta(days=90)
                    else:
                        next_billing = last_date + timedelta(days=365)
                        
                    status_date = df['transaction_date'].max().date()
                    subscriptions.append({
                        "merchant_name": entity,
                        "category_name": cat_name,
                        "amount": float(avg_amt),
                        "frequency": frequency,
                        "next_billing": next_billing.strftime('%Y-%m-%d'),
                        "status": "Active" if next_billing.date() >= status_date else "Inactive"
                    })
                    
    # 7. Payment Method Analysis
    pay_agg = df.groupby('payment_method').agg(
        total_amount=('amount', 'sum'),
        transaction_count=('amount', 'count')
    ).reset_index()
    pay_agg['percentage'] = (pay_agg['total_amount'] / df['amount'].sum() * 100) if df['amount'].sum() > 0 else 0.0
    pay_agg = pay_agg.sort_values(by='total_amount', ascending=False)
    payment_methods = pay_agg.to_dict(orient='records')
    
    # 8. Weekly Heatmap (Total spend per day of week)
    weekly_heatmap = {d: 0.0 for d in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]}
    deb_df = df[df['transaction_type'] == 'Debit']
    if not deb_df.empty:
        heatmap_agg = deb_df.groupby('day_name')['amount'].sum()
        for day, amt in heatmap_agg.items():
            weekly_heatmap[day] = float(amt)
            
    # 9. Data Coverage
    # List of months from start_date to end_date
    coverage_dict = {}
    if len(statements) > 0:
        # Get start/end range across all statements
        all_starts = [pd.to_datetime(s['start_date']) for s in statements]
        all_ends = [pd.to_datetime(s['end_date']) for s in statements]
        
        min_start = min(all_starts)
        max_end = max(all_ends)
        
        # Build list of periods
        coverage_periods = pd.period_range(start=min_start, end=max_end, freq='M').astype(str).tolist()
        
        # Check active months based on transaction presence or statement coverage
        all_months_with_txs = set(df['month_period']) if 'month_period' in df.columns else set()
        
        # Create a full list from Jan 2025 to May 2025 or whatever is the range, plus next two months as dashes
        for m in coverage_periods:
            is_covered = m in all_months_with_txs
            if not is_covered:
                for s in statements:
                    try:
                        s_start_month = pd.to_datetime(s['start_date']).strftime('%Y-%m')
                        s_end_month = pd.to_datetime(s['end_date']).strftime('%Y-%m')
                        if s_start_month <= m <= s_end_month:
                            is_covered = True
                            break
                    except Exception:
                        continue
            coverage_dict[m] = is_covered
            
        # Add next two months as placeholders (dashes) as seen in screenshots
        last_coverage_date = datetime.strptime(coverage_periods[-1] + "-01", "%Y-%m-%d")
        next_month_1 = (last_coverage_date + timedelta(days=32)).replace(day=1)
        next_month_2 = (next_month_1 + timedelta(days=32)).replace(day=1)
        
        coverage_dict[next_month_1.strftime("%Y-%m")] = None
        coverage_dict[next_month_2.strftime("%Y-%m")] = None
        
    # Format data coverage as a sorted list of dicts: {"month": "2025-01", "name": "Jan 2025", "status": "active"|"missing"|"placeholder"}
    data_coverage = []
    month_names_mapping = {
        "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "Jun",
        "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"
    }
    for period, status in sorted(coverage_dict.items()):
        yr, mn = period.split("-")
        month_name = f"{month_names_mapping[mn]} {yr}"
        
        status_str = "missing"
        if status is True:
            status_str = "active"
        elif status is None:
            status_str = "placeholder"
            
        data_coverage.append({
            "period": period,
            "name": month_name,
            "status": status_str
        })
        

    account_holder = "Manas Purnendu"
    if statements:
        for s in statements:
            if s.get("account_holder"):
                account_holder = s["account_holder"]
                break
                
    return {
        "start_date": active_start,
        "end_date": active_end,
        "account_holder": account_holder,
        "kpis": {
            "income": float(total_income),
            "expense": float(total_expense),
            "savings": float(net_savings),
            "savings_rate": float(savings_rate),
            "balance": float(current_balance),
            "transaction_count": len(df),
            "average_monthly_spend": float(average_monthly_spend),
            "busiest_day": busiest_day,
            "busiest_day_amount": float(busiest_day_amount),
            "highest_category": highest_category
        },
        "category_spending": category_spending,
        "monthly_trends": monthly_trends,
        "top_merchants": top_merchants[:5], # top 5
        "top_contacts": top_contacts[:5],   # top 5
        "subscriptions": subscriptions,
        "payment_methods": payment_methods,
        "weekly_heatmap": weekly_heatmap,
        "data_coverage": data_coverage,
        "raw_count": len(df)
    }
