import os
import sys
import csv
import random
from datetime import datetime, timedelta

# Add project root to sys.path so we can import app modules
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.data_generator.profiles import PROFILES
from scripts.data_generator.transaction_generator import TransactionGenerator
from scripts.data_generator.balance_engine import BalanceEngine

def export_profile_to_csv(email, profile, months_to_generate, output_dir):
    """Generate a CSV file for a specific profile."""
    
    end_date = datetime(2026, 6, 30) # Default end date as requested
    start_date = end_date - timedelta(days=months_to_generate * 30)
    
    is_recent_hire = profile.get("special") == "recent_hire"
    recent_hire_threshold = end_date - timedelta(days=60)
    
    file_name = f"BankStatement_{email.split('@')[0]}_{months_to_generate}M.csv"
    file_path = os.path.join(output_dir, file_name)
    
    tx_gen = TransactionGenerator(profile)
    bal_engine = BalanceEngine(starting_balance=profile["starting_balance"])
    
    current_date = start_date
    all_transactions = []
    
    # Generate Transactions
    while current_date <= end_date:
        if is_recent_hire and current_date < recent_hire_threshold:
            original_income = profile.get("income", [])
            tx_gen.profile["income"] = []
            daily_txs = tx_gen.generate_daily_transactions(current_date)
            tx_gen.profile["income"] = original_income
        else:
            daily_txs = tx_gen.generate_daily_transactions(current_date)
            
        for tx in daily_txs:
            running_bal = bal_engine.process_transaction(tx["amount"], tx["type"])
            all_transactions.append({
                "Date": tx["date"].strftime("%d/%m/%Y"),
                "Description": tx["desc"],
                "Amount": f"{tx['amount']:.2f}",
                "Type": tx["type"],
                "Balance": f"{running_bal:.2f}"
            })
            
        current_date += timedelta(days=1)
        
    summary = bal_engine.get_summary()
    
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Write some metadata at the top so parser can pick it up
        writer.writerow(["Bank Name: HDFC Bank"])
        writer.writerow([f"Account Number: {random.randint(1000000000, 9999999999)}"])
        writer.writerow([f"Account Holder: {email.split('@')[0].upper()}"])
        writer.writerow([f"Opening Balance: {summary['opening_balance']:.2f}"])
        writer.writerow([])
        writer.writerow(["Date", "Description", "Amount", "Type", "Balance"])
        
        for tx in all_transactions:
            writer.writerow([tx["Date"], tx["Description"], tx["Amount"], tx["Type"], tx["Balance"]])
            
        writer.writerow([])
        writer.writerow([f"Closing Balance: {summary['closing_balance']:.2f}"])
            
    print(f"✅ Exported {len(all_transactions)} transactions to {file_name}")

def main():
    import argparse
    import random
    
    parser = argparse.ArgumentParser(description="Generate synthetic bank statement CSV files.")
    parser.add_argument("--months", type=int, default=6, help="Number of months of data to generate")
    parser.add_argument("--users", type=str, help="Comma separated list of emails to generate (default: all profiles)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--outdir", type=str, default="synthetic_statements", help="Output directory")
    
    args = parser.parse_args()
    random.seed(args.seed)
    
    # Ensure output directory exists
    output_dir = os.path.join(PROJECT_ROOT, args.outdir)
    os.makedirs(output_dir, exist_ok=True)
    
    emails_to_seed = args.users.split(',') if args.users else list(PROFILES.keys())
    
    print(f"🌱 Generating CSV Statements ({args.months} months, {len(emails_to_seed)} users)")
    
    try:
        for email in emails_to_seed:
            if email in PROFILES:
                export_profile_to_csv(email, PROFILES[email], args.months, output_dir)
            else:
                print(f"⚠️ Warning: Profile for {email} not found. Skipping.")
                
        print(f"🎉 Successfully completed! Files saved in {output_dir}/")
    except Exception as e:
        print(f"❌ Error during generation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
