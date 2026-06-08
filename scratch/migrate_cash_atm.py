import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'bank_statement.db')

def migrate():
    print(f"Connecting to database at: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Ensure "Cash & ATM" category exists
    try:
        cursor.execute('INSERT INTO categories (category_name) VALUES ("Cash & ATM")')
        print("Inserted 'Cash & ATM' category.")
    except sqlite3.IntegrityError:
        print("'Cash & ATM' category already exists.")
        
    cursor.execute('SELECT category_id FROM categories WHERE category_name = "Cash & ATM"')
    cat_row = cursor.fetchone()
    cash_atm_id = cat_row['category_id']
    print(f"'Cash & ATM' category ID is: {cash_atm_id}")
    
    # 2. Seed rules
    rules = [
        "ATM WDL",
        "ATM CASH",
        "CASH WDL",
        "CASH WITHDRAWAL"
    ]
    
    for rule in rules:
        try:
            cursor.execute('INSERT INTO category_rules (keyword, category_id, created_by_user) VALUES (?, ?, 0)', (rule, cash_atm_id))
            print(f"Added rule: {rule} -> 'Cash & ATM'")
        except sqlite3.IntegrityError:
            print(f"Rule for '{rule}' already exists.")
            
    # 3. Update existing transactions
    # We target transactions that contain the keywords in description and are currently uncategorized (category_id = 13 or similar)
    # or any transaction matching ATM/Cash keywords that hasn't been manually updated (created_by_user = 0 rule context)
    # We can check which category is "Uncategorized"
    cursor.execute('SELECT category_id FROM categories WHERE category_name = "Uncategorized"')
    uncat_row = cursor.fetchone()
    uncat_id = uncat_row['category_id'] if uncat_row else None
    
    query = '''
        UPDATE transactions
        SET category_id = ?
        WHERE (category_id = ? OR category_id IS NULL)
          AND (
               UPPER(description) LIKE '%ATM WDL%' OR
               UPPER(description) LIKE '%ATM CASH%' OR
               UPPER(description) LIKE '%CASH WDL%' OR
               UPPER(description) LIKE '%CASH WITHDRAWAL%'
          )
    '''
    cursor.execute(query, (cash_atm_id, uncat_id))
    rows_affected = cursor.rowcount
    print(f"Updated {rows_affected} existing transactions to 'Cash & ATM' category.")
    
    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == '__main__':
    migrate()
