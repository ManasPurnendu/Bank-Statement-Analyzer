from database.db import get_db_connection
import sqlite3

def add_statement(file_name, file_type, account_holder, account_number, bank_name, 
                  statement_month, start_date, end_date, transaction_count, 
                  opening_balance, closing_balance):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO statements (
            file_name, file_type, account_holder, account_number, bank_name,
            statement_month, start_date, end_date, transaction_count,
            opening_balance, closing_balance
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (file_name, file_type, account_holder, account_number, bank_name,
          statement_month, start_date, end_date, transaction_count,
          opening_balance, closing_balance))
    statement_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return statement_id

def get_statement(statement_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM statements WHERE statement_id = ?', (statement_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_statements():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM statements ORDER BY start_date DESC')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_statement(statement_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Deleting statement will cascade delete transactions because of ON DELETE CASCADE
    cursor.execute('DELETE FROM statements WHERE statement_id = ?', (statement_id,))
    conn.commit()
    conn.close()

def check_duplicate_statement(account_number, start_date, end_date, transaction_count):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT statement_id FROM statements 
        WHERE account_number = ? AND start_date = ? AND end_date = ? AND transaction_count = ?
    ''', (account_number, start_date, end_date, transaction_count))
    row = cursor.fetchone()
    conn.close()
    return row['statement_id'] if row else None

def delete_statement_by_details(account_number, start_date, end_date, transaction_count):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM statements 
        WHERE account_number = ? AND start_date = ? AND end_date = ? AND transaction_count = ?
    ''', (account_number, start_date, end_date, transaction_count))
    conn.commit()
    conn.close()

def add_transactions_bulk(transactions_data):
    """
    transactions_data: list of dicts with keys:
    statement_id, transaction_date, description, amount, transaction_type, balance,
    category_id, payee_name, merchant_name, payment_method, is_subscription
    """
    if not transactions_data:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.executemany('''
        INSERT INTO transactions (
            statement_id, transaction_date, description, amount, transaction_type,
            balance, category_id, payee_name, merchant_name, payment_method, is_subscription
        ) VALUES (
            :statement_id, :transaction_date, :description, :amount, :transaction_type,
            :balance, :category_id, :payee_name, :merchant_name, :payment_method, :is_subscription
        )
    ''', transactions_data)
    conn.commit()
    conn.close()

def get_transactions(search_query=None, category_id=None, type_filter=None, 
                     start_date=None, end_date=None, sort_by='transaction_date', 
                     sort_order='DESC', offset=0, limit=50):
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
    
    if search_query:
        query += " AND (t.description LIKE ? OR t.payee_name LIKE ? OR t.merchant_name LIKE ?)"
        lk = f"%{search_query}%"
        params.extend([lk, lk, lk])
        
    if category_id:
        query += " AND t.category_id = ?"
        params.append(category_id)
        
    if type_filter:
        query += " AND t.transaction_type = ?"
        params.append(type_filter)
        
    if start_date:
        query += " AND t.transaction_date >= ?"
        params.append(start_date)
        
    if end_date:
        query += " AND t.transaction_date <= ?"
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
    query += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_transactions_count(search_query=None, category_id=None, type_filter=None, 
                           start_date=None, end_date=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = '''
        SELECT COUNT(*) as count 
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.category_id
        WHERE 1=1
    '''
    params = []
    
    if search_query:
        query += " AND (t.description LIKE ? OR t.payee_name LIKE ? OR t.merchant_name LIKE ?)"
        lk = f"%{search_query}%"
        params.extend([lk, lk, lk])
        
    if category_id:
        query += " AND t.category_id = ?"
        params.append(category_id)
        
    if type_filter:
        query += " AND t.transaction_type = ?"
        params.append(type_filter)
        
    if start_date:
        query += " AND t.transaction_date >= ?"
        params.append(start_date)
        
    if end_date:
        query += " AND t.transaction_date <= ?"
        params.append(end_date)
        
    cursor.execute(query, params)
    row = cursor.fetchone()
    conn.close()
    return row['count'] if row else 0

def update_transaction_category(transaction_id, category_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE transactions 
        SET category_id = ? 
        WHERE transaction_id = ?
    ''', (category_id, transaction_id))
    conn.commit()
    conn.close()

def update_merchant_category_rules(merchant_name, category_id):
    """
    Creates/updates a category rule for a merchant/amount and updates all existing 
    transactions matching it to the new category.
    """
    if not merchant_name:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Insert or replace rule
    cursor.execute('''
        INSERT OR REPLACE INTO category_rules (keyword, category_id, created_by_user)
        VALUES (?, ?, 1)
    ''', (merchant_name.upper(), category_id))
    
    # Update existing transactions
    if merchant_name.upper().startswith("AMOUNT:"):
        try:
            amt_val = float(merchant_name.split(":", 1)[1])
            cursor.execute('''
                UPDATE transactions
                SET category_id = ?
                WHERE amount >= ? - 0.01 AND amount <= ? + 0.01
            ''', (category_id, amt_val, amt_val))
        except (ValueError, IndexError):
            pass
    else:
        cursor.execute('''
            UPDATE transactions
            SET category_id = ?
            WHERE UPPER(merchant_name) = ? 
               OR UPPER(description) LIKE ? 
               OR UPPER(payee_name) = ? 
               OR UPPER(payee_name) LIKE ?
        ''', (category_id, merchant_name.upper(), f"%{merchant_name.upper()}%", merchant_name.upper(), f"%{merchant_name.upper()}%"))
    
    conn.commit()
    conn.close()

def get_all_categories():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM categories ORDER BY category_name ASC')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

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

def get_category_id_by_name(category_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT category_id FROM categories WHERE category_name = ?', (category_name,))
    row = cursor.fetchone()
    conn.close()
    return row['category_id'] if row else None

def get_all_transactions_for_analytics(start_date=None, end_date=None):
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
    if start_date:
        query += " AND t.transaction_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND t.transaction_date <= ?"
        params.append(end_date)
        
    query += " ORDER BY t.transaction_date ASC, t.transaction_id ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
