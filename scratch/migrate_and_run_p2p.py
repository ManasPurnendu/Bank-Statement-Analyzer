import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from database.db import init_db, DB_PATH
from database.models import get_category_rules, get_all_categories
import sqlite3

# Reset DB
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
    print("Database deleted.")

print("Running Database Init (Category seeding)...")
init_db()

# Upload Excel & PDF statements sequentially via test client
app.config['TESTING'] = True
client = app.test_client()

excel_path = "/Users/purne/Desktop/Internship/AccountStatement_07062026_094257.xlsx"
pdf_path = "/Users/purne/Desktop/Internship/AccountStatement_07062026_102218.pdf"
password = "93730210805"

print("\nUploading Excel statement (encrypted)...")
with open(excel_path, 'rb') as f:
    r = client.post('/api/upload', data={'files': (f, 'AccountStatement_07062026_094257.xlsx'), 'password': password})
    print("Excel Upload:", r.get_json())

print("\nUploading PDF statement (encrypted)...")
with open(pdf_path, 'rb') as f:
    r = client.post('/api/upload', data={'files': (f, 'AccountStatement_07062026_102218.pdf'), 'password': password})
    print("PDF Upload:", r.get_json())

# Query categories
print("\n--- ALL CATEGORIES ---")
categories = get_all_categories()
for c in categories:
    print(c)

# Query category rules
print("\n--- CATEGORY RULES ---")
rules = get_category_rules()
p2p_rules = [r for r in rules if r["category_name"] == "Peer-to-Peer"]
print(f"Total Peer-to-Peer Rules Generated: {len(p2p_rules)}")
for r in p2p_rules:
    print(r)

# Count transactions per category
print("\n--- TRANSACTIONS PER CATEGORY ---")
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute('''
    SELECT c.category_name, COUNT(t.transaction_id) as cnt
    FROM categories c
    LEFT JOIN transactions t ON c.category_id = t.category_id
    GROUP BY c.category_name
    ORDER BY cnt DESC
''')
for row in cursor.fetchall():
    print(f"{row['category_name']}: {row['cnt']}")
conn.close()
