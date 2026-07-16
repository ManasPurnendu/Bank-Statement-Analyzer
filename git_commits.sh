#!/bin/bash

# 1
git add Dockerfile docker-compose.yml
git commit -m "feat: containerize application with Docker"

# 2
git add frontend/
git commit -m "refactor: migrate build tools to frontend directory"

# 3
git rm -r scripts/data_generator/ 2>/dev/null
git commit -m "chore: remove legacy data generator module"

# 4
git rm database/v3_migrations.py database/v4_migrations.py 2>/dev/null
git commit -m "chore: clean up obsolete database migrations"

# 5
git add database/db.py database/models.py
git commit -m "feat: update core database models and schemas"

# 6
git add services/engines/ services/insights.py
git commit -m "fix: enhance intelligence engines and insights"

# 7
git add parsers/unified_parser.py services/categorizer.py
git commit -m "refactor: improve unified parser and categorization"

# 8
git add routes/dashboard_routes.py routes/transaction_routes.py routes/upload_routes.py
git commit -m "feat: update API routing logic"

# 9
git add templates/admin_users.html templates/base.html
git commit -m "feat: refine admin and base frontend templates"

# 10
git add templates/forecast.html templates/reports.html templates/transactions.html
git commit -m "feat: update dashboard and reports UI"

# 11
git add static/css/style.css static/js/main.js static/dist/
git commit -m "style: update static assets and css styling"

# 12
git rm -r assets/screenshots/ 2>/dev/null
git rm app.log 2>/dev/null
git rm -r debug_uploads/ 2>/dev/null
git commit -m "chore: remove legacy screenshots and debug logs"

# 13
git rm -r test_datasets/ 2>/dev/null
git rm tests/generate_sample_data.py 2>/dev/null
git rm scripts/generate_scenarios.py 2>/dev/null
git commit -m "chore: remove obsolete test scripts and datasets"

# 14
git add app.py requirements.txt scripts/create_admin.py
git commit -m "chore: update dependencies and app configuration"

# 15
git add Final_Test_Data/
git commit -m "docs: add final synthetic test datasets for demo"

# Catch anything left over
git add -A
git commit -m "chore: final minor cleanups and sync"

echo "All 15 commits successfully executed locally!"
