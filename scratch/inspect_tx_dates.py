import sqlite3

DB_PATH = "/Users/purne/Desktop/Internship/database/bank_statement.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("--- STATEMENT 1 TRANSACTION DATES ---")
cursor.execute("SELECT transaction_date, COUNT(*) FROM transactions WHERE statement_id = 1 GROUP BY transaction_date ORDER BY transaction_date ASC")
for row in cursor.fetchall():
    print(dict(row))

print("\n--- STATEMENT 2 TRANSACTION DATES (First 20) ---")
cursor.execute("SELECT transaction_date, COUNT(*) FROM transactions WHERE statement_id = 2 GROUP BY transaction_date ORDER BY transaction_date ASC LIMIT 20")
for row in cursor.fetchall():
    print(dict(row))

conn.close()
