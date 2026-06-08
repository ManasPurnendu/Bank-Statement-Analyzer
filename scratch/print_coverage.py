import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
import json

app.config['TESTING'] = True
client = app.test_client()

r = client.get('/api/dashboard?range=all')
res_data = r.get_json()

print("--- DATA COVERAGE ---")
for item in res_data['analytics']['data_coverage']:
    print(item)

print("\n--- MONTHLY TRENDS ---")
for trend in res_data['analytics']['monthly_trends']:
    print(trend)
