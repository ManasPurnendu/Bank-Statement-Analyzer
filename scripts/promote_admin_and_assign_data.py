import sqlite3
import os
import sys

def promote_and_assign(email):
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'bank_statement.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Find user
    cursor.execute('SELECT user_id, role FROM users WHERE email = ?', (email,))
    user = cursor.fetchone()
    
    if not user:
        print(f"Error: User with email '{email}' not found.")
        conn.close()
        return
        
    user_id = user['user_id']
    
    # 2. Promote to admin
    if user['role'] != 'admin':
        cursor.execute('UPDATE users SET role = ? WHERE user_id = ?', ('admin', user_id))
        print(f"User '{email}' promoted to admin.")
    else:
        print(f"User '{email}' is already an admin.")
        
    # 3. Assign legacy data (where user_id is NULL)
    cursor.execute('UPDATE statements SET user_id = ? WHERE user_id IS NULL', (user_id,))
    stmt_count = cursor.rowcount
    
    cursor.execute('UPDATE transactions SET user_id = ? WHERE user_id IS NULL', (user_id,))
    tx_count = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"Successfully assigned {stmt_count} statements and {tx_count} transactions to user '{email}'.")

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python scripts/promote_admin_and_assign_data.py <email>")
        sys.exit(1)
        
    promote_and_assign(sys.argv[1])
