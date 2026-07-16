from database.db import get_db_connection
import psycopg2
import hashlib
import re
from functools import lru_cache
from werkzeug.security import generate_password_hash, check_password_hash

def compute_transaction_hash(account_number, date, description, amount, txn_type, balance):
    # Normalize description: lowercase, strip, collapse multiple spaces
    norm_desc = re.sub(r'\s+', ' ', str(description).strip().lower())
    # Normalize amount: float to 2 decimal places
    try:
        norm_amount = f"{float(amount):.2f}"
    except (ValueError, TypeError):
        norm_amount = "0.00"
    # Normalize balance: float to 2 decimal places
    try:
        norm_balance = f"{float(balance):.2f}"
    except (ValueError, TypeError):
        norm_balance = "0.00"
        
    hash_str = f"{account_number or 'Unknown'}||{date}||{norm_desc}||{norm_amount}||{txn_type}||{norm_balance}"
    # SHA-256 is used for idempotency and security (Phase 2 requirement)
    return hashlib.sha256(hash_str.encode('utf-8')).hexdigest()

def add_statement(file_name, file_type, account_holder, account_number, bank_name,
                  statement_month, start_date, end_date, transaction_count,
                  opening_balance, closing_balance, file_hash=None, user_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO statements (
            file_name, file_type, account_holder, account_number, bank_name,
            statement_month, start_date, end_date, transaction_count,
            opening_balance, closing_balance, file_hash, user_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING statement_id
    ''', (file_name, file_type, account_holder, account_number, bank_name,
          statement_month, start_date, end_date, transaction_count,
          opening_balance, closing_balance, file_hash, user_id))
    row = cursor.fetchone()
    statement_id = row['statement_id'] if row else None
    conn.commit()
    conn.close()
    return statement_id

def get_statement(statement_id, user_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if user_id:
        cursor.execute('SELECT * FROM statements WHERE statement_id = %s AND user_id = %s', (statement_id, user_id))
    else:
        cursor.execute('SELECT * FROM statements WHERE statement_id = %s', (statement_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_statements(user_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if user_id:
        cursor.execute('SELECT * FROM statements WHERE user_id = %s ORDER BY start_date DESC', (user_id,))
    else:
        cursor.execute('SELECT * FROM statements ORDER BY start_date DESC')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_statement(statement_id, user_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Deleting statement will cascade delete transactions because of ON DELETE CASCADE
    if user_id:
        cursor.execute('DELETE FROM statements WHERE statement_id = %s AND user_id = %s', (statement_id, user_id))
    else:
        cursor.execute('DELETE FROM statements WHERE statement_id = %s', (statement_id,))
    conn.commit()
    conn.close()

def check_duplicate_statement(account_number, start_date, end_date, transaction_count, file_hash=None, user_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if file_hash:
        if user_id:
            cursor.execute('SELECT statement_id FROM statements WHERE file_hash = %s AND user_id = %s', (file_hash, user_id))
        else:
            cursor.execute('SELECT statement_id FROM statements WHERE file_hash = %s', (file_hash,))
        row = cursor.fetchone()
        if row:
            conn.close()
            return row['statement_id']
            
    if user_id:
        cursor.execute('''
            SELECT statement_id FROM statements 
            WHERE account_number = %s AND start_date = %s AND end_date = %s AND transaction_count = %s AND user_id = %s
        ''', (account_number, start_date, end_date, transaction_count, user_id))
    else:
        cursor.execute('''
            SELECT statement_id FROM statements 
            WHERE account_number = %s AND start_date = %s AND end_date = %s AND transaction_count = %s
        ''', (account_number, start_date, end_date, transaction_count))
        
    row = cursor.fetchone()
    conn.close()
    return row['statement_id'] if row else None

def delete_statement_by_details(account_number, start_date, end_date, transaction_count, user_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if user_id:
        cursor.execute('''
            DELETE FROM statements 
            WHERE account_number = %s AND start_date = %s AND end_date = %s AND transaction_count = %s AND user_id = %s
        ''', (account_number, start_date, end_date, transaction_count, user_id))
    else:
        cursor.execute('''
            DELETE FROM statements 
            WHERE account_number = %s AND start_date = %s AND end_date = %s AND transaction_count = %s
        ''', (account_number, start_date, end_date, transaction_count))
    conn.commit()
    conn.close()

def add_transactions_bulk(transactions_data):
    """
    transactions_data: list of dicts with keys:
    statement_id, transaction_date, description, amount, transaction_type,
    balance, category_id, payee_name, merchant_name, payment_method, is_subscription, transaction_hash, user_id
    """
    if not transactions_data:
        return
        
    for t in transactions_data:
        if 'is_subscription' in t:
            t['is_subscription'] = bool(t['is_subscription'])
            

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.executemany('''
        INSERT INTO transactions (
            statement_id, transaction_date, description, amount, transaction_type,
            balance, category_id, payee_name, merchant_name, payment_method, is_subscription,
            transaction_hash, user_id
        ) VALUES (
            %(statement_id)s, %(transaction_date)s, %(description)s, %(amount)s, %(transaction_type)s,
            %(balance)s, %(category_id)s, %(payee_name)s, %(merchant_name)s, %(payment_method)s, %(is_subscription)s,
            %(transaction_hash)s, %(user_id)s
        ) ON CONFLICT (transaction_hash) DO NOTHING
    ''', transactions_data)
    conn.commit()
    conn.close()
    
    # Run P2P auto-classification check
    try:
        auto_classify_p2p_payees()
    except Exception as e:
        print("Error in auto_classify_p2p_payees:", str(e))

def auto_classify_p2p_payees():
    """
    Finds payees with >= 5 transactions that don't contain business keywords,
    and automatically creates a 'Peer-to-Peer' rule for them.
    """
    import re
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Fetch category ID for 'Peer-to-P2P'
    cursor.execute("SELECT category_id FROM categories WHERE category_name = 'Peer-to-Peer'")
    p2p_row = cursor.fetchone()
    if not p2p_row:
        conn.close()
        return
    p2p_cat_id = p2p_row['category_id']
    
    # 2. Find payees with >= 5 transactions where payee_name is not null and merchant_name is null
    cursor.execute('''
        SELECT payee_name, COUNT(*) as cnt
        FROM transactions
        WHERE payee_name IS NOT NULL AND payee_name != '' AND merchant_name IS NULL
        GROUP BY payee_name
        HAVING cnt >= 5
    ''')
    payees = cursor.fetchall()
    
    business_keywords = {
        'STORE', 'SHOP', 'MART', 'RESTAURANT', 'CAFE', 'HOTEL', 'SALON', 'BAKERY', 'PHARMACY', 'CLINIC', 
        'SYSTEMS', 'ENTERPRISES', 'SERVICES', 'AGENCY', 'PETROL', 'FUELS', 'MEDICAL', 'SUPERMARKET', 
        'RETAIL', 'RETAILS', 'BAZAR', 'FOOD', 'SWEET', 'CHQ', 'RENT', 'BILL', 'INSURANCE', 'LOAN', 
        'EMI', 'INTEREST', 'SALARY', 'ZERODHA', 'MUTUAL', 'CABS', 'TRAVEL', 'ACADEMY', 'SCHOOL', 
        'COLLEGE', 'GYM', 'FITNESS', 'DRUG', 'PHARMA', 'ASSOCIATES', 'INDUSTRIES', 'HOLDINGS', 
        'VENTURES', 'CORP', 'CORPORATION', 'PVT', 'LTD', 'LIMITED', 'CLOTH', 'CLOTHING', 'FASHION', 
        'BOUTIQUE', 'JEWELLER', 'JEWELLERS', 'CATERER', 'CATERERS', 'DAIRY', 'PROVISION', 'PROVISIONS', 
        'STATIONERY', 'COMMUNICATION', 'COMMUNICATIONS', 'MOBILE', 'TELECOM', 'ELECTRICAL', 'ELECTRONIC', 
        'ELECTRONICS', 'HARDWARE', 'AUTO', 'AUTOMOBILE', 'AUTOMOBILES', 'GARAGE', 'WASH', 'AC', 
        'REPAIR', 'LOGISTICS', 'COURIER', 'POST', 'CARGO', 'MESS', 'SWEETS', 'SUPER',
        'BASKET', 'COFFEE', 'MILK', 'XER', 'XEROX', 'PAYMENT', 'PAYMENTS', 'WALLET', 'CASH', 'DIRECT', 'DIR',
        'ZEPTO', 'BLINK', 'RAPIDO', 'SUBWAY', 'DELHIV', 'OPENAI', 'APOLLO', 'INDIAN', 'UTS', 'DMART', 'SPN', 'STAR', 'AMUL', 'SRM', 'ADYAR',
        'WDL', 'TFR', 'DEP', 'UPI', 'MUMBAI', 'ROAD', 'NARIMAN', 'POINT', 'MADAME', 'CAMA', 'BRANCH', 'ATM', 'POS', 'PURCH', 'OTHPG',
        'BIGSAVE', 'R K SUP', 'SICILY', 'DUSKY', 'SELVA', 'AMRUT', 'WELLNESS', 'SAMS', 'SATHISH', 'A2B', 'EVERGREEN', 'BISTRO', 'KORA'
    }
    
    rules_added = 0
    for row in payees:
        payee = row['payee_name']
        payee_upper = payee.upper()
        
        # Check if the payee name contains any business keywords
        if any(kw in payee_upper for kw in business_keywords):
            continue
            
        # Check if a rule already exists for this payee keyword
        cursor.execute('SELECT category_id, created_by_user FROM category_rules WHERE keyword = %s', (payee_upper,))
        rule = cursor.fetchone()
        
        if rule:
            # If a rule exists and it's created by user, do not overwrite it
            if rule['created_by_user'] == 1:
                continue
            # If an autogenerated rule exists for a different category, update it to P2P
            if rule['category_id'] != p2p_cat_id:
                cursor.execute('UPDATE category_rules SET category_id = %s WHERE keyword = %s', (p2p_cat_id, payee_upper))
                # Update existing transactions matching this payee
                cursor.execute('UPDATE transactions SET category_id = %s WHERE UPPER(payee_name) = %s', (p2p_cat_id, payee_upper))
                rules_added += 1
        else:
            # Create a new P2P rule (autogenerated, created_by_user = 0)
            cursor.execute('INSERT INTO category_rules (keyword, category_id, created_by_user) VALUES (%s, %s, 0)', (payee_upper, p2p_cat_id))
            # Update existing transactions matching this payee
            cursor.execute('UPDATE transactions SET category_id = %s WHERE UPPER(payee_name) = %s', (p2p_cat_id, payee_upper))
            rules_added += 1
            
    if rules_added > 0:
        conn.commit()
    conn.close()
    
    return

def get_transactions(search_query=None, category_id=None, type_filter=None, 
                     start_date=None, end_date=None, sort_by='transaction_date', 
                     sort_order='DESC', offset=0, limit=50, user_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = '''
        SELECT t.*, c.category_name, s.file_name 
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.category_id
        LEFT JOIN statements s ON t.statement_id = s.statement_id
        WHERE 1=1
    '''
    params = []
    
    if user_id:
        query += " AND t.user_id = %s"
        params.append(user_id)
        
    if search_query:
        query += " AND (t.description LIKE %s OR t.payee_name LIKE %s OR t.merchant_name LIKE %s)"
        lk = f"%{search_query}%"
        params.extend([lk, lk, lk])
        
    if category_id:
        query += " AND t.category_id = %s"
        params.append(category_id)
        
    if type_filter:
        query += " AND t.transaction_type = %s"
        params.append(type_filter)
        
    if start_date:
        query += " AND t.transaction_date >= %s"
        params.append(start_date)
        
    if end_date:
        query += " AND t.transaction_date <= %s"
        params.append(end_date)
        
    # Validation for sort_by to prevent SQL injection
    valid_sort_cols = {
        'transaction_date': 't.transaction_date',
        'amount': 't.amount',
        'description': 't.description',
        'category_name': 'c.category_name',
        'merchant_name': 't.merchant_name'
    }
    sort_col = valid_sort_cols.get(sort_by, 't.transaction_date')
    
    sort_ord = 'DESC' if sort_order.upper() == 'DESC' else 'ASC'
    
    query += f" ORDER BY {sort_col} {sort_ord}, t.transaction_id DESC"
    query += " LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_transactions_count(search_query=None, category_id=None, type_filter=None, 
                           start_date=None, end_date=None, user_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = '''
        SELECT COUNT(*) as count 
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.category_id
        WHERE 1=1
    '''
    params = []
    
    if user_id:
        query += " AND t.user_id = %s"
        params.append(user_id)
        
    if search_query:
        query += " AND (t.description LIKE %s OR t.payee_name LIKE %s OR t.merchant_name LIKE %s)"
        lk = f"%{search_query}%"
        params.extend([lk, lk, lk])
        
    if category_id:
        query += " AND t.category_id = %s"
        params.append(category_id)
        
    if type_filter:
        query += " AND t.transaction_type = %s"
        params.append(type_filter)
        
    if start_date:
        query += " AND t.transaction_date >= %s"
        params.append(start_date)
        
    if end_date:
        query += " AND t.transaction_date <= %s"
        params.append(end_date)
        
    cursor.execute(query, params)
    row = cursor.fetchone()
    conn.close()
    return row['count'] if row else 0

def update_transaction_category(transaction_id, category_id, user_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if user_id:
        cursor.execute('''
            UPDATE transactions 
            SET category_id = %s 
            WHERE transaction_id = %s AND user_id = %s
        ''', (category_id, transaction_id, user_id))
    else:
        cursor.execute('''
            UPDATE transactions 
            SET category_id = %s 
            WHERE transaction_id = %s
        ''', (category_id, transaction_id))
    conn.commit()
    conn.close()

def update_merchant_category_rules(merchant_name, category_id):
    if not merchant_name or not category_id:
        return
    
    # Invalidate rules cache
    get_category_rules.cache_clear()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Insert or replace rule
    cursor.execute('''
        INSERT INTO category_rules (keyword, category_id, created_by_user)
        VALUES (%s, %s, TRUE)
        ON CONFLICT (keyword) DO UPDATE 
        SET category_id = EXCLUDED.category_id, created_by_user = EXCLUDED.created_by_user
    ''', (merchant_name.upper(), category_id))
    
    # Update existing transactions
    if merchant_name.upper().startswith("AMOUNT:"):
        try:
            amt_val = float(merchant_name.split(":", 1)[1])
            cursor.execute('''
                UPDATE transactions
                SET category_id = %s
                WHERE amount >= %s - 0.01 AND amount <= %s + 0.01
            ''', (category_id, amt_val, amt_val))
        except (ValueError, IndexError):
            pass
    else:
        cursor.execute('''
            UPDATE transactions
            SET category_id = %s
            WHERE UPPER(merchant_name) = %s 
               OR UPPER(description) LIKE %s 
               OR UPPER(payee_name) = %s 
               OR UPPER(payee_name) LIKE %s
        ''', (category_id, merchant_name.upper(), f"%{merchant_name.upper()}%", merchant_name.upper(), f"%{merchant_name.upper()}%"))
    
    conn.commit()
    conn.close()

@lru_cache(maxsize=1)
def get_all_categories():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM categories ORDER BY category_name ASC')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@lru_cache(maxsize=1)
def get_category_rules():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.*, c.category_name 
        FROM category_rules r
        JOIN categories c ON r.category_id = c.category_id
        ORDER BY r.keyword ASC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@lru_cache(maxsize=128)
def get_category_id_by_name(category_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT category_id FROM categories WHERE category_name = %s', (category_name,))
    row = cursor.fetchone()
    conn.close()
    return row['category_id'] if row else None

def get_all_transactions_for_analytics(start_date=None, end_date=None, user_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = '''
        SELECT t.*, c.category_name, s.bank_name, s.statement_month
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.category_id
        LEFT JOIN statements s ON t.statement_id = s.statement_id
        WHERE 1=1
    '''
    params = []
    if user_id is not None:
        query += " AND t.user_id = %s"
        params.append(user_id)
    if start_date:
        query += " AND t.transaction_date >= %s"
        params.append(start_date)
    if end_date:
        query += " AND t.transaction_date <= %s"
        params.append(end_date)
        
    query += " ORDER BY t.transaction_date ASC, t.transaction_id ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_user_by_email(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_user(email, password, role='user'):
    conn = get_db_connection()
    cursor = conn.cursor()
    password_hash = generate_password_hash(password)
    try:
        cursor.execute('''
            INSERT INTO users (email, password_hash, role)
            VALUES (%s, %s, %s) RETURNING user_id
        ''', (email, password_hash, role))
        row = cursor.fetchone()
        user_id = row['user_id'] if row else None
        conn.commit()
    except psycopg2.IntegrityError:
        user_id = None
    finally:
        conn.close()
    return user_id

def verify_user_credentials(email, password):
    user = get_user_by_email(email)
    if user and check_password_hash(user['password_hash'], password):
        return user
    return None

def record_failed_login(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users 
        SET failed_attempts = failed_attempts + 1,
            locked_until = CASE WHEN failed_attempts + 1 >= 5 THEN CURRENT_TIMESTAMP + INTERVAL '15 minutes' ELSE locked_until END
        WHERE user_id = %s
    ''', (user_id,))
    conn.commit()
    conn.close()

def reset_failed_attempts(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE user_id = %s', (user_id,))
    conn.commit()
    conn.close()

def set_user_role(user_id, role):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET role = %s WHERE user_id = %s', (role, user_id))
    conn.commit()
    conn.close()

def add_intelligence_report(report_data):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # We serialize list/dict to JSON strings if they aren't already
    import json
    
    risk_flags_str = report_data.get('risk_flags')
    if isinstance(risk_flags_str, list):
        risk_flags_str = json.dumps(risk_flags_str)
        
    positive_signals_str = report_data.get('positive_signals')
    if isinstance(positive_signals_str, list):
        positive_signals_str = json.dumps(positive_signals_str)
        
    calculation_metadata_str = report_data.get('calculation_metadata')
    if isinstance(calculation_metadata_str, dict):
        calculation_metadata_str = json.dumps(calculation_metadata_str)
        
    cursor.execute('''
        INSERT INTO income_intelligence_reports (
            user_id, statement_id, engine_version, data_sufficiency_grade,
            income_classification, base_salary, fixed_emi_obligations,
            foir_percentage, stability_score, statement_health_score,
            surplus_score, buffer_score, income_confidence_score,
            risk_flags, positive_signals, report_generation_time_ms,
            calculation_metadata
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) RETURNING report_id
    ''', (
        report_data.get('user_id'),
        report_data.get('statement_id'),
        report_data.get('engine_version', 'v2.3'),
        report_data.get('data_sufficiency_grade'),
        report_data.get('income_classification', 'PROCESSING_ERROR'),
        report_data.get('base_salary'),
        report_data.get('fixed_emi_obligations'),
        report_data.get('foir_percentage'),
        report_data.get('stability_score'),
        report_data.get('statement_health_score'),
        report_data.get('surplus_score'),
        report_data.get('buffer_score'),
        report_data.get('income_confidence_score'),
        risk_flags_str,
        positive_signals_str,
        report_data.get('report_generation_time_ms'),
        calculation_metadata_str
    ))
    
    row = cursor.fetchone()
    report_id = row['report_id'] if row else None
    conn.commit()
    conn.close()
    return report_id

def get_latest_intelligence_report(user_id=None, statement_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = 'SELECT * FROM income_intelligence_reports WHERE 1=1'
    params = []
    
    if user_id is not None:
        query += ' AND user_id = %s'
        params.append(user_id)
    if statement_id is not None:
        query += ' AND statement_id = %s'
        params.append(statement_id)
        
    query += ' ORDER BY created_at DESC LIMIT 1'
    
    cursor.execute(query, params)
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
        
    result = dict(row)
    import json
    # Deserialize JSON fields
    if result.get('risk_flags'):
        try: result['risk_flags'] = json.loads(result['risk_flags'])
        except: pass
    if result.get('positive_signals'):
        try: result['positive_signals'] = json.loads(result['positive_signals'])
        except: pass
    if result.get('calculation_metadata'):
        try: result['calculation_metadata'] = json.loads(result['calculation_metadata'])
        except: pass
        
    return result

