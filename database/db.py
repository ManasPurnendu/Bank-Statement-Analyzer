import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bank_statement.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create Statements Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS statements (
            statement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL,
            file_type TEXT NOT NULL,
            account_holder TEXT,
            account_number TEXT,
            bank_name TEXT,
            statement_month TEXT,
            start_date DATE,
            end_date DATE,
            upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            transaction_count INTEGER DEFAULT 0,
            opening_balance REAL,
            closing_balance REAL,
            file_hash TEXT
        )
    ''')
    
    # Create Categories Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_name TEXT NOT NULL UNIQUE
        )
    ''')
    
    # Create Transactions Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            is_subscription BOOLEAN DEFAULT 0,
            transaction_hash TEXT UNIQUE,
            FOREIGN KEY (statement_id) REFERENCES statements(statement_id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(category_id)
        )
    ''')
    
    # Create Category Rules Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS category_rules (
            rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL UNIQUE,
            category_id INTEGER NOT NULL,
            created_by_user BOOLEAN DEFAULT 0,
            FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE CASCADE
        )
    ''')
    
    # Create Income Intelligence Reports Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS income_intelligence_reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            statement_id INTEGER,
            engine_version TEXT NOT NULL,
            data_sufficiency_grade TEXT,
            eligibility_status TEXT NOT NULL,
            base_salary REAL,
            fixed_emi_obligations REAL,
            foir_percentage REAL,
            stability_score REAL,
            statement_health_score REAL,
            surplus_score REAL,
            buffer_score REAL,
            final_readiness_score REAL,
            risk_flags TEXT,
            positive_signals TEXT,
            report_generation_time_ms REAL,
            calculation_metadata TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (statement_id) REFERENCES statements(statement_id) ON DELETE CASCADE
        )
    ''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_reports_user_id ON income_intelligence_reports(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_reports_statement_id ON income_intelligence_reports(statement_id)')

    
    # Run dynamic alter migrations for existing databases
    try:
        cursor.execute("ALTER TABLE statements ADD COLUMN file_hash TEXT")
    except sqlite3.OperationalError:
        pass # Already exists
        
    try:
        cursor.execute("ALTER TABLE transactions ADD COLUMN transaction_hash TEXT")
    except sqlite3.OperationalError:
        pass # Already exists
        
    try:
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_transaction_hash ON transactions(transaction_hash)")
    except sqlite3.OperationalError:
        pass
        
    conn.commit()
    
    # Seed Initial Categories
    initial_categories = [
        "Food & Dining",
        "Shopping",
        "Travel",
        "Utilities",
        "Entertainment",
        "Healthcare",
        "Salary",
        "Investment",
        "Transfer",
        "Education",
        "Bills",
        "Peer-to-Peer",
        "Cash & ATM",
        "Uncategorized"
    ]
    
    for cat in initial_categories:
        try:
            cursor.execute('INSERT INTO categories (category_name) VALUES (?)', (cat,))
        except sqlite3.IntegrityError:
            pass # Already exists
            
    conn.commit()
    
    # Fetch categories mappings for rules seeding
    cursor.execute('SELECT category_id, category_name FROM categories')
    cat_map = {row['category_name']: row['category_id'] for row in cursor.fetchall()}
    
    # Seed Initial Category Rules (keyword to category ID)
    # Rules are checked case-insensitively
    system_rules = [
        ("SWIGGY", cat_map["Food & Dining"]),
        ("ZOMATO", cat_map["Food & Dining"]),
        ("RESTAURANT", cat_map["Food & Dining"]),
        ("CAFETERIA", cat_map["Food & Dining"]),
        ("DOMINOS", cat_map["Food & Dining"]),
        ("STARBUCKS", cat_map["Food & Dining"]),
        ("SWEET", cat_map["Food & Dining"]),
        ("FOOD", cat_map["Food & Dining"]),
        
        ("AMAZON", cat_map["Shopping"]),
        ("FLIPKART", cat_map["Shopping"]),
        ("RELIANCE RETAIL", cat_map["Shopping"]),
        ("MYNTRA", cat_map["Shopping"]),
        ("DMART", cat_map["Shopping"]),
        ("SUPERMARKET", cat_map["Shopping"]),
        ("GROCERY", cat_map["Shopping"]),
        ("DECATHLON", cat_map["Shopping"]),
        ("ZARA", cat_map["Shopping"]),
        
        ("UBER", cat_map["Travel"]),
        ("OLA", cat_map["Travel"]),
        ("IRCTC", cat_map["Travel"]),
        ("METRO", cat_map["Travel"]),
        ("MAKEMYTRIP", cat_map["Travel"]),
        ("INDIGO", cat_map["Travel"]),
        ("FUEL", cat_map["Travel"]),
        ("PETROL", cat_map["Travel"]),
        ("SHELL", cat_map["Travel"]),
        
        ("ELECTRICITY", cat_map["Utilities"]),
        ("POWER", cat_map["Utilities"]),
        ("WATER", cat_map["Utilities"]),
        ("BESCOM", cat_map["Utilities"]),
        ("ACT FIBERNET", cat_map["Utilities"]),
        ("BROADBAND", cat_map["Utilities"]),
        ("AIRTEL", cat_map["Utilities"]),
        ("JIO", cat_map["Utilities"]),
        ("VODAFONE", cat_map["Utilities"]),
        
        ("NETFLIX", cat_map["Entertainment"]),
        ("SPOTIFY", cat_map["Entertainment"]),
        ("YOUTUBE", cat_map["Entertainment"]),
        ("PRIME VIDEO", cat_map["Entertainment"]),
        ("BOOKMYSHOW", cat_map["Entertainment"]),
        ("HOTSTAR", cat_map["Entertainment"]),
        ("PLAYSTATION", cat_map["Entertainment"]),
        ("STEAM", cat_map["Entertainment"]),
        
        ("HOSPITAL", cat_map["Healthcare"]),
        ("PHARMACY", cat_map["Healthcare"]),
        ("APOLLO", cat_map["Healthcare"]),
        ("CLINIC", cat_map["Healthcare"]),
        ("MEDPLUS", cat_map["Healthcare"]),
        ("DOCTOR", cat_map["Healthcare"]),
        
        ("SALARY", cat_map["Salary"]),
        ("PAYSLIP", cat_map["Salary"]),
        ("DIRECT DEP", cat_map["Salary"]),
        ("INTEREST", cat_map["Salary"]),
        
        ("MUTUAL FUND", cat_map["Investment"]),
        ("ZERODHA", cat_map["Investment"]),
        ("GROWW", cat_map["Investment"]),
        ("STOCK", cat_map["Investment"]),
        ("SECURITIES", cat_map["Investment"]),
        ("FD DEPOSIT", cat_map["Investment"]),
        
        ("TRANSFER TO", cat_map["Transfer"]),
        ("TRANSFER FROM", cat_map["Transfer"]),
        ("PAYTM", cat_map["Transfer"]),
        ("PHONEPE", cat_map["Transfer"]),
        ("GPAY", cat_map["Transfer"]),
        
        ("SCHOOL", cat_map["Education"]),
        ("COLLEGE", cat_map["Education"]),
        ("UNIVERSITY", cat_map["Education"]),
        ("TUITION", cat_map["Education"]),
        ("UDEMY", cat_map["Education"]),
        ("COURSERA", cat_map["Education"]),
        
        ("RENT", cat_map["Bills"]),
        ("INSURANCE", cat_map["Bills"]),
        ("LOAN", cat_map["Bills"]),
        ("EMI", cat_map["Bills"]),
        ("CREDIT CARD BILL", cat_map["Bills"]),
        
        ("ATM WDL", cat_map["Cash & ATM"]),
        ("ATM CASH", cat_map["Cash & ATM"]),
        ("CASH WDL", cat_map["Cash & ATM"]),
        ("CASH WITHDRAWAL", cat_map["Cash & ATM"])
    ]
    
    for kw, cid in system_rules:
        try:
            cursor.execute('INSERT INTO category_rules (keyword, category_id, created_by_user) VALUES (?, ?, 0)', (kw, cid))
        except sqlite3.IntegrityError:
            pass # Already exists
            
    conn.commit()
    conn.close()
    
    # Auto-classify P2P payees on existing data
    try:
        from database.models import auto_classify_p2p_payees
        auto_classify_p2p_payees()
    except Exception as e:
        print("Error running P2P auto-classification:", str(e))

if __name__ == "__main__":
    init_db()
