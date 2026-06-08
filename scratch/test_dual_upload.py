import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from database.db import init_db

print("Starting E2E Dual Ingestion Verification...")
app.config['TESTING'] = True
client = app.test_client()

excel_path = "/Users/purne/Desktop/Internship/AccountStatement_07062026_094257.xlsx"
pdf_path = "/Users/purne/Desktop/Internship/AccountStatement07062026_102218.pdf"

# Reset DB
from database.db import DB_PATH
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
init_db()

# Upload Excel statement (with password)
print("\nUploading Excel statement...")
with open(excel_path, 'rb') as f:
    r = client.post('/api/upload', data={'files': (f, 'AccountStatement_07062026_094257.xlsx'), 'password': '93730210805'})
    print("Excel Upload:", r.get_json())

# Upload PDF statement (unencrypted)
print("\nUploading PDF statement...")
with open(pdf_path, 'rb') as f:
    r = client.post('/api/upload', data={'files': (f, 'AccountStatement07062026_102218.pdf')})
    print("PDF Upload:", r.get_json())

# Get dashboard data
print("\nFetching dashboard data...")
r = client.get('/api/dashboard?range=all')
data = r.get_json()

print("\n--- DASHBOARD DATA ---")
analytics = data["analytics"]
print(f"Start Date: {analytics['start_date']}")
print(f"End Date: {analytics['end_date']}")
print(f"Total Transactions count: {analytics['kpis']['transaction_count']}")
print(f"Opening Balance: {analytics['kpis']['balance']}")

print("\n--- Monthly Trends ---")
for m in analytics["monthly_trends"]:
    print(f"Month: {m['month']} | Income: {m['income']} | Expense: {m['expense']} | TX Count: {m['transaction_count']}")

print("\n--- Data Coverage ---")
for c in analytics["data_coverage"]:
    print(f"Period: {c['period']} | Status: {c['status']}")
