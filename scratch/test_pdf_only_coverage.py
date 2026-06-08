import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import get_db_connection
from services.analytics import calculate_analytics
import json

# Let's count transactions and coverage in DB for statement 2 only
conn = get_db_connection()
cursor = conn.cursor()
cursor.execute("SELECT * FROM statements WHERE statement_id = 2")
stmt = dict(cursor.fetchone())
conn.close()

print("Statement 2 in DB:", stmt)

# Calculate analytics for statement 2 period only
analytics = calculate_analytics('2025-04-01', '2026-03-31')

print("\n--- DATA COVERAGE FOR STATEMENT 2 RANGE ---")
for item in analytics['data_coverage']:
    print(item)

print("\n--- MONTHLY TRENDS FOR STATEMENT 2 RANGE ---")
for trend in analytics['monthly_trends']:
    print(trend)
