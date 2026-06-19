import unittest
import os
import sqlite3
import pandas as pd

# Dynamic database override for tests to avoid dirtying live SQLite
import database.db
database.db.DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'bank_statement_test.db')


from database.db import init_db, get_db_connection, DB_PATH
from database.models import (
    add_statement, get_all_statements, check_duplicate_statement, 
    add_transactions_bulk, get_transactions, get_transactions_count,
    update_transaction_category, get_all_categories, update_merchant_category_rules
)
from services.categorizer import clean_description, detect_payment_method, detect_merchant_and_payee, categorize_transaction
from services.analytics import calculate_analytics
from services.forecast import generate_forecast
from tests.generate_sample_data import create_sample_excel

class TestBankStatementAnalyzer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Remove any existing test database to start clean
        if os.path.exists(database.db.DB_PATH):
            try:
                os.remove(database.db.DB_PATH)
            except Exception:
                pass
            
        # 1. Initialize SQLite schema
        init_db()
        # 2. Generate sample data Excel for testing
        create_sample_excel()
        # 3. Pre-populate database with transactions for other tests
        from parsers.excel_parser import parse_excel_statement
        demo_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'sample_statement_jan_may_2025.xlsx')
        parsed = parse_excel_statement(demo_file, demo_file)
        metadata = parsed["metadata"]
        transactions = parsed["transactions"]
        
        stmt_id = add_statement(
            metadata["file_name"], metadata["file_type"], metadata["account_holder"],
            metadata["account_number"], metadata["bank_name"], metadata["statement_month"],
            metadata["start_date"], metadata["end_date"], metadata["transaction_count"],
            metadata["opening_balance"], metadata["closing_balance"]
        )
        for t in transactions:
            t["statement_id"] = stmt_id
        add_transactions_bulk(transactions)

    @classmethod
    def tearDownClass(cls):
        # Remove test database file
        if os.path.exists(database.db.DB_PATH):
            try:
                os.remove(database.db.DB_PATH)
            except Exception:
                pass

    def test_database_init(self):
        """Test if tables are created and seeded with default categories."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check tables existence
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row['name'] for row in cursor.fetchall()]
        self.assertIn('statements', tables)
        self.assertIn('transactions', tables)
        self.assertIn('categories', tables)
        self.assertIn('category_rules', tables)
        
        # Check categories seeding
        categories = get_all_categories()
        self.assertTrue(len(categories) >= 12)
        
        conn.close()

    def test_categorizer_text_cleansing(self):
        """Test regex text cleansing inside categorizer."""
        self.assertEqual(clean_description("UPI-SWIGGY-12345@OKAXIS"), "UPI-SWIGGY-12345@OKAXIS")
        self.assertEqual(clean_description("  TRANSFER TO   ANUJ  "), "TRANSFER TO ANUJ")

    def test_payment_method_detection(self):
        """Test payment method parsing rules."""
        self.assertEqual(detect_payment_method("UPI-SWIGGY-12345@OKAXIS"), "UPI")
        self.assertEqual(detect_payment_method("ATM CASH WDL BANGALORE"), "ATM")
        self.assertEqual(detect_payment_method("CHQ PAID TO SELF"), "Cheque")
        self.assertEqual(detect_payment_method("POS DEBIT CARD SPEND"), "Card")
        self.assertEqual(detect_payment_method("GENERIC PAYMENT"), "Other")

    def test_merchant_vs_payee_detection(self):
        """Test separation of merchant names vs payee names."""
        m1, p1 = detect_merchant_and_payee("UPI-SWIGGY-RESTAURANT", "Debit")
        self.assertEqual(m1, "Swiggy")
        self.assertIsNone(p1)
        
        m2, p2 = detect_merchant_and_payee("TRANSFER TO ANUJ IN 9876", "Debit")
        self.assertIsNone(m2)
        self.assertEqual(p2, "Anuj")

    def test_end_to_end_ingestion(self):
        """Test importing the sample statement into SQLite and verifying database reads."""
        demo_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'sample_statement_jan_may_2025.xlsx')
        self.assertTrue(os.path.exists(demo_file))
        
        # Let's import the file
        from parsers.excel_parser import parse_excel_statement
        parsed = parse_excel_statement(demo_file, demo_file)
        
        metadata = parsed["metadata"]
        transactions = parsed["transactions"]
        
        self.assertEqual(metadata["account_holder"], "Manas Purnendu")
        self.assertEqual(metadata["bank_name"], "Standard Bank")
        self.assertTrue(len(transactions) > 0)
        
        # Check duplicate check returns None (before adding)
        dup = check_duplicate_statement(
            metadata["account_number"], 
            metadata["start_date"], 
            metadata["end_date"], 
            metadata["transaction_count"]
        )
        # Clear database if already exists to make test repeatable
        if dup:
            from database.models import delete_statement
            delete_statement(dup)
            
        # Add statement
        stmt_id = add_statement(
            metadata["file_name"], metadata["file_type"], metadata["account_holder"],
            metadata["account_number"], metadata["bank_name"], metadata["statement_month"],
            metadata["start_date"], metadata["end_date"], metadata["transaction_count"],
            metadata["opening_balance"], metadata["closing_balance"]
        )
        
        # Link and add transactions bulk
        for t in transactions:
            t["statement_id"] = stmt_id
        add_transactions_bulk(transactions)
        
        # Verify entries in DB
        db_stmts = get_all_statements()
        self.assertTrue(any(s['statement_id'] == stmt_id for s in db_stmts))
        
        txs_count = get_transactions_count()
        self.assertEqual(txs_count, len(transactions))
        
        # Check duplicate check now finds it
        dup_now = check_duplicate_statement(
            metadata["account_number"], 
            metadata["start_date"], 
            metadata["end_date"], 
            metadata["transaction_count"]
        )
        self.assertEqual(dup_now, stmt_id)

    def test_analytics_computations(self):
        """Test analytics KPIs logic against inserted database entries."""
        analytics = calculate_analytics()
        kpis = analytics["kpis"]
        
        self.assertTrue(kpis["income"] > 0)
        self.assertTrue(kpis["expense"] > 0)
        self.assertEqual(kpis["savings"], kpis["income"] - kpis["expense"])
        self.assertEqual(kpis["balance"], 108740.00) # Verify ending balance matches statement values
        
        # Verify subscriptions
        self.assertTrue(len(analytics["subscriptions"]) > 0)
        sub_merchants = [s["merchant_name"] for s in analytics["subscriptions"]]
        self.assertIn("Netflix", sub_merchants)
        self.assertIn("Spotify", sub_merchants)

    def test_forecasts_engine(self):
        """Test forecasting calculations and what-if simulation hooks."""
        forecast = generate_forecast()
        self.assertTrue(forecast["success"])
        self.assertEqual(len(forecast["forecast_details"]), 3) # Next 3 months
        
        # Run simulator
        sim = generate_forecast("Shopping", 20.0)
        self.assertTrue(sim["success"])
        self.assertTrue(sim["what_if"]["adjusted_saving"] > 0)

    def test_amount_based_categorization_rules(self):
        """Test categorization based on amount rules and that update_merchant_category_rules updates DB properly."""
        # 1. Create a dummy category rules entry
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get a category ID
        cursor.execute("SELECT category_id FROM categories WHERE category_name = 'Bills'")
        bills_cat_id = cursor.fetchone()['category_id']
        
        # Get Uncategorized category ID
        cursor.execute("SELECT category_id FROM categories WHERE category_name = 'Uncategorized'")
        uncat_id = cursor.fetchone()['category_id']
        conn.close()
        
        # Test categorizer with amount parameter directly
        test_rules = [("AMOUNT:10200.0", bills_cat_id), ("SWIGGY", uncat_id)]
        res_cat = categorize_transaction("RANDOM TRANSACTION", "Debit", rules=test_rules, amount=10200.0)
        self.assertEqual(res_cat, bills_cat_id)
        
        # Test description fallback works and skips AMOUNT rules
        res_cat_desc = categorize_transaction("AMOUNT:10200.0", "Debit", rules=test_rules)
        self.assertEqual(res_cat_desc, uncat_id) # should fallback to Uncategorized (12 or whatever) because it skips AMOUNT rules for description matching
        
        # 2. Test update_merchant_category_rules for amount
        # First, insert a transaction with amount 10200.0
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT statement_id FROM statements LIMIT 1")
        stmt_id = cursor.fetchone()['statement_id']
        cursor.execute('''
            INSERT INTO transactions (statement_id, transaction_date, description, amount, transaction_type, category_id)
            VALUES (?, '2025-01-01', 'Monthly Rent Payment', 10200.0, 'Debit', ?)
        ''', (stmt_id, uncat_id))
        conn.commit()
        
        cursor.execute("SELECT transaction_id FROM transactions WHERE description = 'Monthly Rent Payment'")
        txn_id = cursor.fetchone()['transaction_id']
        conn.close()
        
        # Apply the rule
        update_merchant_category_rules("AMOUNT:10200.0", bills_cat_id)
        
        # Verify transaction was updated
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT category_id FROM transactions WHERE transaction_id = ?", (txn_id,))
        updated_cat_id = cursor.fetchone()['category_id']
        
        # Verify the rule exists in category_rules table
        cursor.execute("SELECT category_id FROM category_rules WHERE keyword = 'AMOUNT:10200.0'")
        rule_cat_id = cursor.fetchone()['category_id']
        conn.close()
        
        self.assertEqual(updated_cat_id, bills_cat_id)
        self.assertEqual(rule_cat_id, bills_cat_id)

    def test_edit_category_route_always_updates_and_creates_amount_rules(self):
        """Test PUT /api/transaction/category API updates current transaction and handles remember_amount."""
        from app import app
        app.config['TESTING'] = True
        client = app.test_client()
        
        # Get Uncategorized category ID and a target category ID
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT category_id FROM categories WHERE category_name = 'Uncategorized'")
        uncat_id = cursor.fetchone()['category_id']
        cursor.execute("SELECT category_id FROM categories WHERE category_name = 'Utilities'")
        util_cat_id = cursor.fetchone()['category_id']
        
        # Insert a dummy transaction for the API test
        cursor.execute("SELECT statement_id FROM statements LIMIT 1")
        stmt_id = cursor.fetchone()['statement_id']
        cursor.execute('''
            INSERT INTO transactions (statement_id, transaction_date, description, amount, transaction_type, category_id)
            VALUES (?, '2025-01-02', 'Utility Rent Payment X', 5500.0, 'Debit', ?)
        ''', (stmt_id, uncat_id))
        conn.commit()
        
        cursor.execute("SELECT transaction_id FROM transactions WHERE description = 'Utility Rent Payment X'")
        txn_id = cursor.fetchone()['transaction_id']
        conn.close()
        
        # Call the API to update the category and check both remember and remember_amount
        response = client.put('/api/transaction/category', json={
            "transaction_id": txn_id,
            "category_id": util_cat_id,
            "remember": True,
            "remember_amount": True
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        
        # Verify database is updated for that transaction
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT category_id FROM transactions WHERE transaction_id = ?", (txn_id,))
        self.assertEqual(cursor.fetchone()['category_id'], util_cat_id)
        
        # Verify rules are created
        cursor.execute("SELECT category_id FROM category_rules WHERE keyword = 'AMOUNT:5500.0'")
        self.assertEqual(cursor.fetchone()['category_id'], util_cat_id)
        
        conn.close()

    def test_cash_atm_categorization(self):
        """Test that ATM/Cash transactions are auto-categorized under 'Cash & ATM'."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT category_id FROM categories WHERE category_name = 'Cash & ATM'")
        cash_atm_row = cursor.fetchone()
        self.assertIsNotNone(cash_atm_row)
        cash_atm_id = cash_atm_row['category_id']
        conn.close()

        # Test the categorization logic directly
        self.assertEqual(categorize_transaction("ATM WDL CASH 12345", "Debit"), cash_atm_id)
        self.assertEqual(categorize_transaction("ATM CASH WITHDRAWAL", "Debit"), cash_atm_id)
        self.assertEqual(categorize_transaction("CASH WDL FROM BRANCH", "Debit"), cash_atm_id)
        self.assertEqual(categorize_transaction("CASH WITHDRAWAL FROM ATM", "Debit"), cash_atm_id)

    def test_negative_balance_excel_parsing(self):
        """Test that negative balances are parsed correctly from Excel metadata without sign stripping."""
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Statement"
        ws.cell(row=1, column=1).value = "Opening Balance: | -54321.10"
        ws.cell(row=2, column=1).value = "Closing Balance: | -12345.50"
        ws.cell(row=3, column=1).value = "Account Number: | 9988776655"
        
        headers = ["Date", "Description", "Debit", "Credit", "Balance"]
        for col, h in enumerate(headers, 1):
            ws.cell(row=4, column=col).value = h
            
        row_data = ["2025-01-01", "UPI-SWIGGY-FOOD", 100, None, -54421.10]
        for col, val in enumerate(row_data, 1):
            ws.cell(row=5, column=col).value = val
            
        test_file = 'test_neg_balance.xlsx'
        wb.save(test_file)
        try:
            from parsers.excel_parser import parse_excel_statement
            parsed = parse_excel_statement(test_file, test_file)
            metadata = parsed["metadata"]
            self.assertEqual(metadata["opening_balance"], -54321.10)
            self.assertEqual(metadata["closing_balance"], -12345.50)
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    def test_reverse_chronological_excel_parsing(self):
        """Test that reverse-chronological statements are correctly chronologized ascending."""
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Statement"
        ws.cell(row=1, column=1).value = "Account Number: | 11223344"
        
        headers = ["Date", "Description", "Debit", "Credit", "Balance"]
        for col, h in enumerate(headers, 1):
            ws.cell(row=2, column=col).value = h
            
        # Reverse chronological (newest first)
        rows_data = [
            ["2025-01-02", "Tx C (Newest on Jan 2)", 10, None, 10030],
            ["2025-01-01", "Tx B (Newer on Jan 1)", 50, None, 10050],
            ["2025-01-01", "Tx A (Older on Jan 1)", None, 100, 10100]
        ]
        
        for r_idx, r_data in enumerate(rows_data, 3):
            for c_idx, val in enumerate(r_data, 1):
                ws.cell(row=r_idx, column=c_idx).value = val
                
        test_file = 'test_rev_chrono.xlsx'
        wb.save(test_file)
        try:
            from parsers.excel_parser import parse_excel_statement
            parsed = parse_excel_statement(test_file, test_file)
            transactions = parsed["transactions"]
            metadata = parsed["metadata"]
            
            # Check transaction count
            self.assertEqual(len(transactions), 3)
            # Verify they are now ordered: Tx A -> Tx B -> Tx C
            self.assertEqual(transactions[0]["description"], "Tx A (Older on Jan 1)")
            self.assertEqual(transactions[1]["description"], "Tx B (Newer on Jan 1)")
            self.assertEqual(transactions[2]["description"], "Tx C (Newest on Jan 2)")
            
            # Verify deduced opening balance (before Tx A, which was Credit 100 from starting balance 10000)
            # Tx A balance was 10100, so opening balance should be 10000
            self.assertEqual(metadata["opening_balance"], 10000.0)
            # Verify deduced closing balance (latest txn Tx C balance which is 10030)
            self.assertEqual(metadata["closing_balance"], 10030.0)
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    def test_forecasting_accuracy_linear_increase(self):
        """Test forecasting accuracy under a linear increase trend, verifying MAPE < 10%."""
        import services.forecast
        from services.forecast import generate_forecast
        
        # Save original calculate_analytics reference
        orig_calc = services.forecast.calculate_analytics
        
        historical_trends = [
            {"month": "2025-01", "income": 30000.0, "expense": 10000.0, "savings": 20000.0, "savings_rate": 66.6, "transaction_count": 10},
            {"month": "2025-02", "income": 30000.0, "expense": 12000.0, "savings": 18000.0, "savings_rate": 60.0, "transaction_count": 10},
            {"month": "2025-03", "income": 30000.0, "expense": 14000.0, "savings": 16000.0, "savings_rate": 53.3, "transaction_count": 10},
            {"month": "2025-04", "income": 30000.0, "expense": 16000.0, "savings": 14000.0, "savings_rate": 46.6, "transaction_count": 10},
            {"month": "2025-05", "income": 30000.0, "expense": 18000.0, "savings": 12000.0, "savings_rate": 40.0, "transaction_count": 10},
        ]
        
        services.forecast.calculate_analytics = lambda *args, **kwargs: {
            "start_date": "2025-01-01",
            "end_date": "2025-05-01",
            "account_holder": "Test User",
            "kpis": {"balance": 50000.0},
            "category_spending": [],
            "monthly_trends": historical_trends,
            "subscriptions": []
        }
        
        try:
            res = generate_forecast(horizon=1)
            self.assertTrue(res["success"])
            pred_jun_expense = res["forecast_details"][0]["projected_expense"]
            actual_jun_expense = 20000.0
            mape = (abs(pred_jun_expense - actual_jun_expense) / actual_jun_expense) * 100
            
            # The MAPE must be under 10% (our blended model gets ~7.60%)
            self.assertTrue(mape < 10.0, f"Expected MAPE < 10%, got {mape:.2f}%")
        finally:
            services.forecast.calculate_analytics = orig_calc

    def test_forecasting_accuracy_trends_and_damping(self):
        """Test forecasting stability and trend damping for upward and downward profiles."""
        import services.forecast
        from services.forecast import generate_forecast
        
        orig_calc = services.forecast.calculate_analytics
        
        # Test Downward Trend: should decrease sequentially without sudden starting spikes
        downward_trends = [
            {"month": "2025-01", "income": 50000.0, "expense": 30000.0, "savings": 20000.0, "savings_rate": 40.0, "transaction_count": 10},
            {"month": "2025-02", "income": 50000.0, "expense": 25000.0, "savings": 25000.0, "savings_rate": 50.0, "transaction_count": 10},
            {"month": "2025-03", "income": 50000.0, "expense": 20000.0, "savings": 30000.0, "savings_rate": 60.0, "transaction_count": 10},
            {"month": "2025-04", "income": 50000.0, "expense": 15000.0, "savings": 35000.0, "savings_rate": 70.0, "transaction_count": 10},
            {"month": "2025-05", "income": 50000.0, "expense": 10000.0, "savings": 40000.0, "savings_rate": 80.0, "transaction_count": 10},
        ]
        
        services.forecast.calculate_analytics = lambda *args, **kwargs: {
            "start_date": "2025-01-01",
            "end_date": "2025-05-01",
            "account_holder": "Test User",
            "kpis": {"balance": 10000.0},
            "category_spending": [],
            "monthly_trends": downward_trends,
            "subscriptions": []
        }
        
        try:
            res = generate_forecast(horizon=3)
            self.assertTrue(res["success"])
            details = res["forecast_details"]
            
            # Verify predicted values decrease sequentially
            self.assertTrue(details[0]["projected_expense"] > details[1]["projected_expense"])
            self.assertTrue(details[1]["projected_expense"] > details[2]["projected_expense"])
            
            # Verify no starting spike (Month 1 expense must be close to May's 10,000, e.g. < 15,000)
            self.assertTrue(details[0]["projected_expense"] < 15000.0)
        finally:
            services.forecast.calculate_analytics = orig_calc

    def test_duplicate_integrity(self):
        """Test file hash statement rejection and overlapping statement transaction-level deduplication."""
        # 1. Test duplicate statement check by hash
        account_number = "123456789"
        start_date = "2025-06-01"
        end_date = "2025-06-30"
        transaction_count = 5
        file_hash = "abc123xyz456"
        
        # Add a test statement with file_hash
        stmt_id = add_statement(
            "statement_a.xlsx", "Excel", "Test User",
            account_number, "Test Bank", "2025-06",
            start_date, end_date, transaction_count,
            1000.0, 1500.0, file_hash=file_hash
        )
        
        # Verify check_duplicate_statement finds it by hash
        dup_by_hash = check_duplicate_statement(
            "different_acc", "2025-01-01", "2025-01-31", 99, file_hash=file_hash
        )
        self.assertEqual(dup_by_hash, stmt_id)
        
        # 2. Test transaction-level deduplication on overlapping bulk insert
        from database.models import compute_transaction_hash
        
        # Let's insert transactions with identical fingerprints but one legitimate repeated transaction (same date, desc, amount, different balance)
        txs = [
            # Original transaction 1
            {
                "statement_id": stmt_id,
                "transaction_date": "2025-06-05",
                "description": "UPI-SWIGGY",
                "amount": 150.0,
                "transaction_type": "Debit",
                "balance": 850.0,
                "category_id": None,
                "payee_name": "Swiggy",
                "merchant_name": "Swiggy",
                "payment_method": "UPI",
                "is_subscription": 0
            },
            # Legitimate repeated transaction on same day (different running balance)
            {
                "statement_id": stmt_id,
                "transaction_date": "2025-06-05",
                "description": "UPI-SWIGGY",
                "amount": 150.0,
                "transaction_type": "Debit",
                "balance": 700.0,
                "category_id": None,
                "payee_name": "Swiggy",
                "merchant_name": "Swiggy",
                "payment_method": "UPI",
                "is_subscription": 0
            }
        ]
        
        # Calculate hashes
        for t in txs:
            t["transaction_hash"] = compute_transaction_hash(
                account_number,
                t["transaction_date"],
                t["description"],
                t["amount"],
                t["transaction_type"],
                t["balance"]
            )
            
        # Add to DB
        add_transactions_bulk(txs)
        
        # Get count of inserted transactions
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM transactions WHERE statement_id = ?", (stmt_id,))
        first_insert_count = cursor.fetchone()["count"]
        self.assertEqual(first_insert_count, 2)
        
        # 3. Simulate overlapping statement ingestion containing the exact same transactions + one new transaction
        new_stmt_id = add_statement(
            "statement_b.xlsx", "Excel", "Test User",
            account_number, "Test Bank", "2025-06",
            "2025-06-05", "2025-06-10", 3,
            700.0, 1200.0, file_hash="def456uvw789"
        )
        
        overlapping_txs = [
            # Exact duplicate of transaction 1
            {
                "statement_id": new_stmt_id,
                "transaction_date": "2025-06-05",
                "description": "UPI-SWIGGY",
                "amount": 150.0,
                "transaction_type": "Debit",
                "balance": 850.0,
                "category_id": None,
                "payee_name": "Swiggy",
                "merchant_name": "Swiggy",
                "payment_method": "UPI",
                "is_subscription": 0
            },
            # Exact duplicate of transaction 2
            {
                "statement_id": new_stmt_id,
                "transaction_date": "2025-06-05",
                "description": "UPI-SWIGGY",
                "amount": 150.0,
                "transaction_type": "Debit",
                "balance": 700.0,
                "category_id": None,
                "payee_name": "Swiggy",
                "merchant_name": "Swiggy",
                "payment_method": "UPI",
                "is_subscription": 0
            },
            # A completely new transaction in the overlap statement
            {
                "statement_id": new_stmt_id,
                "transaction_date": "2025-06-08",
                "description": "SALARY DEP",
                "amount": 500.0,
                "transaction_type": "Credit",
                "balance": 1200.0,
                "category_id": None,
                "payee_name": "Salary",
                "merchant_name": "Salary",
                "payment_method": "Other",
                "is_subscription": 0
            }
        ]
        
        # Calculate hashes
        for t in overlapping_txs:
            t["transaction_hash"] = compute_transaction_hash(
                account_number,
                t["transaction_date"],
                t["description"],
                t["amount"],
                t["transaction_type"],
                t["balance"]
            )
            
        # Ingest overlapping
        add_transactions_bulk(overlapping_txs)
        
        # Verify database counts
        # Overlapping duplicates should have been skipped, but the new salary transaction should be inserted
        cursor.execute("SELECT COUNT(*) as count FROM transactions WHERE statement_id = ?", (new_stmt_id,))
        new_stmt_inserted_count = cursor.fetchone()["count"]
        # Only the new unique salary transaction should be inserted under new_stmt_id, other 2 skipped
        self.assertEqual(new_stmt_inserted_count, 1)
        
        # Total transactions for this account/range should be 3
        cursor.execute("SELECT COUNT(*) as count FROM transactions WHERE statement_id IN (?, ?)", (stmt_id, new_stmt_id))
        total_txs = cursor.fetchone()["count"]
        self.assertEqual(total_txs, 3)
        
        # Clean up statements
        cursor.execute("DELETE FROM statements WHERE statement_id IN (?, ?)", (stmt_id, new_stmt_id))
        conn.commit()
        conn.close()

    def test_csv_parser_separate_debit_credit(self):
        """Test parsing of CSV statements with separate Debit and Credit columns."""
        csv_content = """Date,Description,Debit,Credit,Balance
2025-01-01,Swiggy Payment,150.00,,9850.00
2025-01-02,Salary Credited,,25000.00,34850.00
"""
        test_file = 'test_sep_debit_credit.csv'
        with open(test_file, 'w') as f:
            f.write(csv_content)
            
        try:
            from parsers.csv_parser import parse_csv_statement
            parsed = parse_csv_statement(test_file, test_file)
            metadata = parsed["metadata"]
            transactions = parsed["transactions"]
            
            self.assertEqual(len(transactions), 2)
            self.assertEqual(transactions[0]["transaction_type"], "Debit")
            self.assertEqual(transactions[0]["amount"], 150.0)
            self.assertEqual(transactions[0]["balance"], 9850.0)
            
            self.assertEqual(transactions[1]["transaction_type"], "Credit")
            self.assertEqual(transactions[1]["amount"], 25000.0)
            self.assertEqual(transactions[1]["balance"], 34850.0)
            
            self.assertEqual(metadata["opening_balance"], 10000.0)
            self.assertEqual(metadata["closing_balance"], 34850.0)
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    def test_csv_parser_single_amount_type(self):
        """Test parsing of CSV statements with a single Amount column and Type column."""
        csv_content = """Date,Description,Amount,Balance,Type
01/01/2025,Starbucks Coffee,120.00,9880.00,Debit
02/01/2025,Transfer from Friend,500.00,10380.00,CR
03/01/2025,Refund,-100.00,10280.00,
"""
        test_file = 'test_single_amount_type.csv'
        with open(test_file, 'w') as f:
            f.write(csv_content)
            
        try:
            from parsers.csv_parser import parse_csv_statement
            parsed = parse_csv_statement(test_file, test_file)
            transactions = parsed["transactions"]
            
            self.assertEqual(len(transactions), 3)
            self.assertEqual(transactions[0]["transaction_type"], "Debit")
            self.assertEqual(transactions[0]["amount"], 120.0)
            
            self.assertEqual(transactions[1]["transaction_type"], "Credit")
            self.assertEqual(transactions[1]["amount"], 500.0)
            
            # Negative sign fallback when type is missing/unknown
            self.assertEqual(transactions[2]["transaction_type"], "Debit")
            self.assertEqual(transactions[2]["amount"], 100.0)
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    def test_json_parser_top_level(self):
        """Test parsing of JSON statements with a top-level transactions array."""
        json_content = """{
            "bank_name": "Axis Bank",
            "account_holder": "Manas Purnendu",
            "account_number": "12345678",
            "opening_balance": 5000.00,
            "closing_balance": 4850.00,
            "transactions": [
                {
                    "date": "2025-01-01",
                    "description": "ZOMATO ORDER",
                    "debit": 150.00,
                    "credit": 0.00,
                    "balance": 4850.00
                }
            ]
        }"""
        test_file = 'test_top_level.json'
        with open(test_file, 'w') as f:
            f.write(json_content)
            
        try:
            from parsers.json_parser import parse_json_statement
            parsed = parse_json_statement(test_file, test_file)
            metadata = parsed["metadata"]
            transactions = parsed["transactions"]
            
            self.assertEqual(metadata["bank_name"], "Axis Bank")
            self.assertEqual(metadata["account_holder"], "Manas Purnendu")
            self.assertEqual(metadata["account_number"], "12345678")
            self.assertEqual(metadata["opening_balance"], 5000.0)
            self.assertEqual(metadata["closing_balance"], 4850.0)
            
            self.assertEqual(len(transactions), 1)
            self.assertEqual(transactions[0]["description"], "ZOMATO ORDER")
            self.assertEqual(transactions[0]["amount"], 150.0)
            self.assertEqual(transactions[0]["transaction_type"], "Debit")
            self.assertEqual(transactions[0]["balance"], 4850.0)
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    def test_json_parser_nested_statement(self):
        """Test parsing of JSON statements with a nested statement object."""
        json_content = """{
            "statement": {
                "bank": "HDFC Bank",
                "holder": "Purnendu",
                "opening_balance": 1000.00,
                "closing_balance": 2000.00,
                "data": [
                    {
                        "transaction_date": "2025-01-05",
                        "remarks": "SALARY CREDIT",
                        "amount": 1000.00,
                        "type": "Credit",
                        "balance": 2000.00
                    }
                ]
            }
        }"""
        test_file = 'test_nested.json'
        with open(test_file, 'w') as f:
            f.write(json_content)
            
        try:
            from parsers.json_parser import parse_json_statement
            parsed = parse_json_statement(test_file, test_file)
            metadata = parsed["metadata"]
            transactions = parsed["transactions"]
            
            self.assertEqual(metadata["bank_name"], "HDFC Bank")
            self.assertEqual(metadata["account_holder"], "Purnendu")
            self.assertEqual(metadata["opening_balance"], 1000.0)
            self.assertEqual(metadata["closing_balance"], 2000.0)
            
            self.assertEqual(len(transactions), 1)
            self.assertEqual(transactions[0]["description"], "SALARY CREDIT")
            self.assertEqual(transactions[0]["amount"], 1000.0)
            self.assertEqual(transactions[0]["transaction_type"], "Credit")
            self.assertEqual(transactions[0]["balance"], 2000.0)
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

if __name__ == "__main__":
    unittest.main()
