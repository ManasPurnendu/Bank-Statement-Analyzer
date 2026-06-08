import unittest
import os
import sqlite3
import pandas as pd

# Dynamic database override for tests to avoid dirtying live SQLite
import database.db
database.db.DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'bank_statement_test.db')

from database.db import init_db, get_db_connection, DB_PATH
from database.models import (
    add_statement, get_all_statements, check_duplicate_statement, 
    add_transactions_bulk, get_transactions, get_transactions_count,
    update_transaction_category, get_all_categories, update_merchant_category_rules
)
from services.categorizer import clean_description, detect_payment_method, detect_merchant_and_payee, categorize_transaction
from services.analytics import calculate_analytics
from services.forecast import generate_forecast
from generate_sample_data import create_sample_excel

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
        demo_file = 'sample_statement_jan_may_2025.xlsx'
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
        demo_file = 'sample_statement_jan_may_2025.xlsx'
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

if __name__ == "__main__":
    unittest.main()

