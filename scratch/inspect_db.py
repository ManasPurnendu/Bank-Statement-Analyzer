import sqlite3
import os

DB_PATH = "/Users/purne/Desktop/Internship/database/bank_statement.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("--- STATEMENTS IN DB ---")
cursor.execute("SELECT * FROM statements")
for row in cursor.fetchall():
    print(dict(row))

print("\n--- TRANSACTIONS SUMMARY BY STATEMENT ---")
cursor.execute("SELECT statement_id, COUNT(*), MIN(transaction_date), MAX(transaction_date) FROM transactions GROUP BY statement_id")
for row in cursor.fetchall():
    print(dict(row))

print("\n--- DISTINCT YEARS/MONTHS IN TRANSACTIONS ---")
cursor.execute("SELECT substr(transaction_date, 1, 7) as ym, COUNT(*) FROM transactions GROUP BY ym")
for row in cursor.fetchall():
    print(dict(row))

conn.close()
