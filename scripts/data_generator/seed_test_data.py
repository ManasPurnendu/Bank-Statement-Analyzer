import argparse
import sys
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

# Add project root to sys.path so we can import app modules
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.data_generator.utils import get_db, generate_transaction_hash
from scripts.data_generator.profiles import PROFILES
from scripts.data_generator.transaction_generator import TransactionGenerator
from scripts.data_generator.balance_engine import BalanceEngine

def ensure_user(cursor, email):
    """Ensure the user exists in the database and return their user_id."""
    cursor.execute("SELECT user_id FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    if row:
        return row['user_id']
    else:
        # Create user
        print(f"Creating new user: {email}")
        pw_hash = generate_password_hash("Password@123")
        cursor.execute(
            "INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
            (email, pw_hash, "user")
        )
        return cursor.lastrowid

def seed_profile(cursor, email, profile, months_to_generate):
    """Seed data for a specific profile."""
    user_id = ensure_user(cursor, email)
    
    # Calculate date range
    end_date = datetime(2026, 6, 30) # Default end date as requested
    start_date = end_date - timedelta(days=months_to_generate * 30)
    
    # If recent hire, they only get salary in the last 60 days
    # We implement this by modifying the transaction generator's behaviour for this user,
    # or we just remove the salary config if the current_date is before 60 days ago.
    # A simpler way: we'll handle this inside the loop below.
    is_recent_hire = profile.get("special") == "recent_hire"
    recent_hire_threshold = end_date - timedelta(days=60)
    
    # Create Statement Record
    file_name = f"BankStatement_{email.split('@')[0]}_{months_to_generate}M.pdf"
    file_hash = f"hash_{email}_{months_to_generate}"
    
    cursor.execute(
        """INSERT INTO statements 
        (file_name, file_type, account_holder, account_number, bank_name, statement_month, start_date, end_date, user_id, file_hash) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (file_name, "application/pdf", email.split("@")[0].upper(), "1234567890", "HDFC Bank", f"{months_to_generate} Months", 
         start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), user_id, file_hash)
    )
    statement_id = cursor.lastrowid
    
    # Engines
    tx_gen = TransactionGenerator(profile)
    bal_engine = BalanceEngine(starting_balance=profile["starting_balance"])
    
    current_date = start_date
    total_inserted = 0
    
    # Generate Transactions
    while current_date <= end_date:
        # Check if we need to suppress salary for recent hire
        if is_recent_hire and current_date < recent_hire_threshold:
            # Temporarily disable salary config
            original_income = profile.get("income", [])
            tx_gen.profile["income"] = []
            
            daily_txs = tx_gen.generate_daily_transactions(current_date)
            
            # Restore income config
            tx_gen.profile["income"] = original_income
        else:
            daily_txs = tx_gen.generate_daily_transactions(current_date)
            
        for tx in daily_txs:
            # Update running balance
            running_bal = bal_engine.process_transaction(tx["amount"], tx["type"])
            
            # Insert transaction
            tx_hash = generate_transaction_hash(user_id, tx["date"], tx["amount"], tx["desc"])
            
            cursor.execute(
                """INSERT INTO transactions 
                (statement_id, transaction_date, description, amount, transaction_type, balance, transaction_hash, user_id, is_subscription)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (statement_id, tx["date"].strftime("%Y-%m-%d"), tx["desc"], tx["amount"], tx["type"], running_bal, tx_hash, user_id, tx["is_subscription"])
            )
            total_inserted += 1
            
        current_date += timedelta(days=1)
        
    # Update Statement with Aggregates
    summary = bal_engine.get_summary()
    cursor.execute(
        """UPDATE statements 
        SET transaction_count = ?, opening_balance = ?, closing_balance = ? 
        WHERE statement_id = ?""",
        (summary['transaction_count'], summary['opening_balance'], summary['closing_balance'], statement_id)
    )
    
    print(f"✅ Seeded {total_inserted} transactions for {email}")
    return total_inserted

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic bank statement data.")
    parser.add_argument("--months", type=int, default=6, help="Number of months of data to generate")
    parser.add_argument("--users", type=str, help="Comma separated list of emails to seed (default: all profiles)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    
    args = parser.parse_args()
    
    # Set random seed
    import random
    random.seed(args.seed)
    
    conn = get_db()
    cursor = conn.cursor()
    
    emails_to_seed = args.users.split(',') if args.users else list(PROFILES.keys())
    
    print(f"🌱 Starting Synthetic Data Generation ({args.months} months, {len(emails_to_seed)} users)")
    
    total_txs = 0
    try:
        for email in emails_to_seed:
            if email in PROFILES:
                total_txs += seed_profile(cursor, email, PROFILES[email], args.months)
            else:
                print(f"⚠️ Warning: Profile for {email} not found. Skipping.")
                
        conn.commit()
        print(f"🎉 Successfully completed! Generated {total_txs} total transactions.")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error during generation: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
