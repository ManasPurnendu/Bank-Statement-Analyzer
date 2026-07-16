import psycopg2
import psycopg2.extras
import os
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(psycopg2.OperationalError)
)
def get_db_connection():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is required for PostgreSQL connection.")
    
    conn = psycopg2.connect(database_url)
    # Return dictionary-like rows similar to sqlite3.Row
    conn.cursor_factory = psycopg2.extras.DictCursor
    return conn

def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create Users Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                failed_attempts INTEGER DEFAULT 0,
                locked_until TIMESTAMP
            )
        ''')
        
        # Create Statements Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS statements (
                statement_id SERIAL PRIMARY KEY,
                file_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                account_holder TEXT,
                account_number TEXT,
                bank_name TEXT,
                statement_month TEXT,
                start_date DATE,
                end_date DATE,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                transaction_count INTEGER DEFAULT 0,
                opening_balance REAL,
                closing_balance REAL,
                file_hash TEXT,
                user_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        
        # Create Categories Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                category_id SERIAL PRIMARY KEY,
                category_name TEXT NOT NULL UNIQUE
            )
        ''')
        
        # Create Transactions Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id SERIAL PRIMARY KEY,
                statement_id INTEGER NOT NULL,
                transaction_date DATE NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                transaction_type TEXT NOT NULL, -- 'Credit' or 'Debit'
                balance REAL,
                category_id INTEGER,
                payee_name TEXT,
                merchant_name TEXT,
                payment_method TEXT, -- 'UPI', 'Card', 'ATM', 'NEFT', 'IMPS', 'RTGS', 'Cheque', 'Other'
                is_subscription BOOLEAN DEFAULT FALSE,
                transaction_hash TEXT,
                user_id INTEGER,
                FOREIGN KEY (statement_id) REFERENCES statements(statement_id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(category_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                UNIQUE(user_id, transaction_hash)
            )
        ''')
        
        # Create Category Rules Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS category_rules (
                rule_id SERIAL PRIMARY KEY,
                keyword TEXT NOT NULL UNIQUE,
                category_id INTEGER NOT NULL,
                created_by_user BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE CASCADE
            )
        ''')
        
        # Create Income Intelligence Reports Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS income_intelligence_reports (
                report_id SERIAL PRIMARY KEY,
                user_id INTEGER,
                statement_id INTEGER,
                engine_version TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_sufficiency_grade TEXT,
                income_classification TEXT,
                base_salary REAL,
                fixed_emi_obligations REAL,
                foir_percentage REAL,
                stability_score REAL,
                statement_health_score REAL,
                surplus_score REAL,
                buffer_score REAL,
                income_confidence_score REAL,
                risk_flags TEXT,
                positive_signals TEXT,
                report_generation_time_ms REAL,
                calculation_metadata TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (statement_id) REFERENCES statements(statement_id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_reports_user_id ON income_intelligence_reports(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_reports_statement_id ON income_intelligence_reports(statement_id)')

        # Create Report Explanations Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS report_explanations (
                explanation_id SERIAL PRIMARY KEY,
                report_id INTEGER NOT NULL,
                metric_name TEXT NOT NULL,
                explanation_text TEXT NOT NULL,
                FOREIGN KEY (report_id) REFERENCES income_intelligence_reports(report_id) ON DELETE CASCADE
            )
        ''')

        # Run dynamic alter migrations for existing databases
        try:
            cursor.execute("ALTER TABLE statements ADD COLUMN IF NOT EXISTS file_hash TEXT")
        except psycopg2.Error:
            pass
            
        try:
            cursor.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS transaction_hash TEXT")
        except psycopg2.Error:
            pass
            
        try:
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_transaction_hash ON transactions(transaction_hash)")
        except psycopg2.Error:
            pass

        cursor.execute("SELECT COUNT(*) as count FROM categories")
        count = cursor.fetchone()['count']
        if count == 0:
            default_categories = [
                'Income', 'Salary', 'Freelance/Gig', 'Interest/Dividends',
                'Housing', 'Rent', 'Mortgage', 'Utilities',
                'Food', 'Groceries', 'Dining Out',
                'Transportation', 'Fuel', 'Public Transit', 'Ride Share',
                'Insurance', 'Health', 'Life', 'Auto',
                'Debt', 'Credit Card', 'Loan/EMI',
                'Investments', 'Mutual Funds', 'Stocks', 'Crypto',
                'Entertainment', 'Subscriptions', 'Shopping',
                'Education', 'Healthcare', 'Travel',
                'Transfers', 'Self-Transfer', 'ATM Withdrawal',
                'Miscellaneous', 'Uncategorized'
            ]
            for cat in default_categories:
                cursor.execute("INSERT INTO categories (category_name) VALUES (%s) ON CONFLICT (category_name) DO NOTHING", (cat,))
                
        # Insert some basic seed rules
        cursor.execute("SELECT COUNT(*) as count FROM category_rules")
        count = cursor.fetchone()['count']
        if count == 0:
            # Fetch categories mappings for rules seeding
            cursor.execute('SELECT category_id, category_name FROM categories')
            cat_map = {row['category_name']: row['category_id'] for row in cursor.fetchall()}
            
            # Seed Initial Category Rules (keyword to category ID)
            system_rules = [
                ("RESTAURANT", cat_map.get("Dining Out")),
                ("CAFETERIA", cat_map.get("Dining Out")),
                ("DOMINOS", cat_map.get("Dining Out")),
                ("STARBUCKS", cat_map.get("Dining Out")),
                ("SWEET", cat_map.get("Dining Out")),
                ("FOOD", cat_map.get("Dining Out")),
                ("AMAZON", cat_map.get("Shopping")),
                ("FLIPKART", cat_map.get("Shopping")),
                ("RELIANCE RETAIL", cat_map.get("Shopping")),
                ("MYNTRA", cat_map.get("Shopping")),
                ("DMART", cat_map.get("Shopping")),
                ("SUPERMARKET", cat_map.get("Shopping")),
                ("GROCERY", cat_map.get("Shopping")),
                ("DECATHLON", cat_map.get("Shopping")),
                ("ZARA", cat_map.get("Shopping")),
                ("UBER", cat_map.get("Travel")),
                ("OLA", cat_map.get("Travel")),
                ("IRCTC", cat_map.get("Travel")),
                ("METRO", cat_map.get("Travel")),
                ("MAKEMYTRIP", cat_map.get("Travel")),
                ("INDIGO", cat_map.get("Travel")),
                ("FUEL", cat_map.get("Travel")),
                ("PETROL", cat_map.get("Travel")),
                ("SHELL", cat_map.get("Travel")),
                ("ELECTRICITY", cat_map.get("Utilities")),
                ("POWER", cat_map.get("Utilities")),
                ("WATER", cat_map.get("Utilities")),
                ("BESCOM", cat_map.get("Utilities")),
                ("ACT FIBERNET", cat_map.get("Utilities")),
                ("BROADBAND", cat_map.get("Utilities")),
                ("AIRTEL", cat_map.get("Utilities")),
                ("JIO", cat_map.get("Utilities")),
                ("VODAFONE", cat_map.get("Utilities")),
                ("NETFLIX", cat_map.get("Entertainment")),
                ("SPOTIFY", cat_map.get("Entertainment")),
                ("YOUTUBE", cat_map.get("Entertainment")),
                ("PRIME VIDEO", cat_map.get("Entertainment")),
                ("BOOKMYSHOW", cat_map.get("Entertainment")),
                ("HOTSTAR", cat_map.get("Entertainment")),
                ("PLAYSTATION", cat_map.get("Entertainment")),
                ("STEAM", cat_map.get("Entertainment")),
                ("HOSPITAL", cat_map.get("Healthcare")),
                ("PHARMACY", cat_map.get("Healthcare")),
                ("APOLLO", cat_map.get("Healthcare")),
                ("CLINIC", cat_map.get("Healthcare")),
                ("MEDPLUS", cat_map.get("Healthcare")),
                ("DOCTOR", cat_map.get("Healthcare")),
                ("SALARY", cat_map.get("Salary")),
                ("PAYSLIP", cat_map.get("Salary")),
                ("DIRECT DEP", cat_map.get("Salary")),
                ("INTEREST", cat_map.get("Salary")),
                ("MUTUAL FUND", cat_map.get("Investments")),
                ("ZERODHA", cat_map.get("Investments")),
                ("GROWW", cat_map.get("Investments")),
                ("STOCK", cat_map.get("Investments")),
                ("SECURITIES", cat_map.get("Investments")),
                ("FD DEPOSIT", cat_map.get("Investments")),
                ("TRANSFER TO", cat_map.get("Transfers")),
                ("TRANSFER FROM", cat_map.get("Transfers")),
                ("PAYTM", cat_map.get("Transfers")),
                ("PHONEPE", cat_map.get("Transfers")),
                ("GPAY", cat_map.get("Transfers")),
                ("SCHOOL", cat_map.get("Education")),
                ("COLLEGE", cat_map.get("Education")),
                ("UNIVERSITY", cat_map.get("Education")),
                ("TUITION", cat_map.get("Education")),
                ("UDEMY", cat_map.get("Education")),
                ("COURSERA", cat_map.get("Education")),
                ("RENT", cat_map.get("Housing")),
                ("INSURANCE", cat_map.get("Insurance")),
                ("LOAN", cat_map.get("Debt")),
                ("EMI", cat_map.get("Debt")),
                ("CREDIT CARD BILL", cat_map.get("Debt")),
                ("ATM WDL", cat_map.get("ATM Withdrawal")),
                ("ATM CASH", cat_map.get("ATM Withdrawal")),
                ("CASH WDL", cat_map.get("ATM Withdrawal")),
                ("CASH WITHDRAWAL", cat_map.get("ATM Withdrawal"))
            ]
            
            for keyword, cat_id in system_rules:
                if cat_id is not None:
                    try:
                        cursor.execute(
                            "INSERT INTO category_rules (keyword, category_id, created_by_user) VALUES (%s, %s, FALSE) ON CONFLICT (keyword) DO NOTHING",
                            (keyword, cat_id)
                        )
                    except psycopg2.Error:
                        pass
                    
        conn.commit()
        conn.close()
    except psycopg2.Error as e:
        print(f"Database initialization concurrent execution or error: {e}")
        try:
            conn.close()
        except:
            pass
    
    # Auto-classify P2P payees on existing data
    try:
        from database.models import auto_classify_p2p_payees
        auto_classify_p2p_payees()
    except Exception as e:
        print("Error running P2P auto-classification:", str(e))

if __name__ == '__main__':
    init_db()
