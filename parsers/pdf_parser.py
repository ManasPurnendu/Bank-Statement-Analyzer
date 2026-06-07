import pdfplumber
import PyPDF2
import os
import re
import pandas as pd
from datetime import datetime
from services.categorizer import categorize_transaction, detect_merchant_and_payee, detect_payment_method, detect_subscription, load_category_rules

def is_pdf_encrypted(file_path):
    """
    Checks if a PDF file is encrypted/password-protected.
    """
    with open(file_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        return reader.is_encrypted

def decrypt_pdf(input_path, output_path, password):
    """
    Attempts to decrypt a password-protected PDF.
    Saves a decrypted copy to output_path.
    Returns True on success, False on failure.
    """
    try:
        with open(input_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            if reader.is_encrypted:
                result = reader.decrypt(password)
                if result == 0: # 0 means incorrect password
                    return False
            
            writer = PyPDF2.PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
                
            with open(output_path, 'wb') as out_f:
                writer.write(out_f)
            return True
    except Exception:
        return False

def parse_pdf_statement(file_path, original_filename, password=None):
    """
    Parses a PDF bank statement.
    Supports decryption.
    Returns a dict with statement metadata and a list of normalized transactions.
    """
    temp_decrypted_path = None
    
    # Check encryption
    if is_pdf_encrypted(file_path):
        if not password:
            raise ValueError("PasswordRequired")
        
        # Decrypt temporarily
        temp_decrypted_path = file_path + "_decrypted.pdf"
        success = decrypt_pdf(file_path, temp_decrypted_path, password)
        if not success:
            if os.path.exists(temp_decrypted_path):
                os.remove(temp_decrypted_path)
            raise ValueError("IncorrectPassword")
        
        parse_target = temp_decrypted_path
    else:
        parse_target = file_path

    # Extract data using pdfplumber
    transactions = []
    metadata = {
        "file_name": original_filename,
        "file_type": "PDF",
        "account_holder": "Unknown",
        "account_number": "Unknown",
        "bank_name": "Unknown",
        "statement_month": None,
        "start_date": None,
        "end_date": None,
        "opening_balance": 0.0,
        "closing_balance": 0.0
    }
    
    rules = load_category_rules()
    
    try:
        with pdfplumber.open(parse_target) as pdf:
            # 1. Inspect first pages for metadata (simpler extraction)
            first_page_text = pdf.pages[0].extract_text() or ""
            text_lines = first_page_text.split('\n')

            # 2. Extract transaction table rows
            # Try strategy A: extract_tables
            raw_table_rows = []
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if table:
                        print("\nTABLE FOUND")
                        for r in table[:5]:
                            print(r)
                    for row in table:
                        # Clean row values
                        row_vals = [str(val).strip() if val is not None else "" for val in row]
                        # Filter out empty rows
                        if any(val != "" for val in row_vals):
                            raw_table_rows.append(row_vals)
            
            # If Strategy A extracted very few rows, try Strategy B: extract_text and regex split
            if len(raw_table_rows) < 3:
                raw_table_rows = []
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    for line in page_text.split('\n'):
                        # Look for lines starting with a date pattern, e.g. 31 May 2025 or 30-05-2025
                        # A typical transaction line: "30 May 2025 Swiggy 518.00 Debit 45680.50"
                        # Or: "30-05-2025 Amazon Pay 2450.00 Debit 46198.50"
                        date_pattern = r'^(\d{1,2}[/\-\s](?:\d{1,2}|[A-Za-z]{3})[/\-\s]\d{2,4})'
                        match = re.match(date_pattern, line.strip())
                        if match:
                            # Split by whitespace, merging descriptions
                            tokens = line.strip().split()
                            if len(tokens) >= 4:
                                raw_table_rows.append(tokens)
            
            # 3. Parse transaction lists
            # Find column index for Date, Description, Amount, Type, Balance
            if not raw_table_rows:
                raise ValueError("No transaction rows found in PDF.")
                
            # Scan top rows of raw table rows to find header column indexes
            header_idx = -1
            for idx, row in enumerate(raw_table_rows[:10]):
                row_lower = [str(val).lower() for val in row]
                has_date = any("date" in val for val in row_lower)
                has_desc = any("desc" in val or "narr" in val or "part" in val or "detail" in val for val in row_lower)
                if has_date and has_desc:
                    header_idx = idx
                    break
            
            date_col_idx = 0
            desc_col_idx = 2
            debit_col_idx = -1
            credit_col_idx = -1
            amount_col_idx = -1
            balance_col_idx = -1
            type_col_idx = -1
            
            if header_idx != -1:
                header_row = [str(val).lower() for val in raw_table_rows[header_idx]]
                for idx, col in enumerate(header_row):
                    if any(kw in col for kw in ['transaction date', 'value date', 'date', 'tx date']):
                        date_col_idx = idx
                    elif any(kw in col for kw in ['description', 'narration', 'particulars', 'remarks', 'details']):
                        desc_col_idx = idx
                    elif any(kw in col for kw in ['debit', 'withdrawal', 'dr_amount', 'dr']):
                        debit_col_idx = idx
                    elif any(kw in col for kw in ['credit', 'deposit', 'cr_amount', 'cr']):
                        credit_col_idx = idx
                    elif any(kw in col for kw in ['amount', 'txn amount', 'sum']):
                        amount_col_idx = idx
                    elif any(kw in col for kw in ['balance', 'running balance', 'ledger balance']):
                        balance_col_idx = idx
                    elif any(kw in col for kw in ['type', 'indicator', 'dr/cr', 'cr/dr']):
                        type_col_idx = idx
                data_rows = raw_table_rows[header_idx+1:]
            else:
                # No header row found: guess columns
                # Let's assume standard format: Date (0), Description (1), Amount (2), Type (3), Balance (4)
                # Or Date (0), Description (1), Debit (2), Credit (3), Balance (4)
                data_rows = raw_table_rows
                
            # If columns were not guessed or mapped, let's establish defaults based on first row length
            for row in data_rows:
                # Skip header repetitions
                row_lower = [str(val).lower() for val in row]
                if any("date" in val for val in row_lower) or any("balance" in val for val in row_lower):
                    continue
                    
                if len(row) <= max(date_col_idx, desc_col_idx):
                    continue
                    
                raw_date = str(row[date_col_idx]).strip()
                description = str(row[desc_col_idx]).strip()
                
                if not raw_date or not description:
                    continue
                    
                # Date conversion
                try:
                    parsed_date = None
                    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%d/%m/%y', '%d-%b-%Y', '%d-%b-%y', '%b %d, %Y'):
                        try:
                            parsed_date = datetime.strptime(raw_date.split(" ")[0], fmt).date()
                            break
                        except ValueError:
                            continue
                    if not parsed_date:
                        parsed_date = pd.to_datetime(raw_date).date()
                except Exception:
                    continue # Date parsing failed, skip
                    
                transaction_date = parsed_date.strftime('%Y-%m-%d')
                
                amount = 0.0
                txn_type = 'Debit'
                
                # Check column widths and extract amount
                if debit_col_idx != -1 and credit_col_idx != -1 and debit_col_idx < len(row) and credit_col_idx < len(row):
                    raw_deb = str(row[debit_col_idx]).replace(",", "").strip()
                    raw_cred = str(row[credit_col_idx]).replace(",", "").strip()
                    
                    val_deb = float(raw_deb) if raw_deb not in ("", "-", "nan", "None") else 0.0
                    val_cred = float(raw_cred) if raw_cred not in ("", "-", "nan", "None") else 0.0
                    
                    if val_deb > 0:
                        amount = val_deb
                        txn_type = 'Debit'
                    elif val_cred > 0:
                        amount = val_cred
                        txn_type = 'Credit'
                    else:
                        continue
                elif amount_col_idx != -1 and amount_col_idx < len(row):
                    raw_amt = str(row[amount_col_idx]).replace(",", "").strip()
                    if raw_amt in ("", "-", "nan"):
                        continue
                    try:
                        val_amt = float(raw_amt)
                    except ValueError:
                        continue
                        
                    if type_col_idx != -1 and type_col_idx < len(row):
                        raw_type = str(row[type_col_idx]).upper().strip()
                        if 'CR' in raw_type or 'CREDIT' in raw_type or 'IN' in raw_type or '+' in raw_type:
                            txn_type = 'Credit'
                            amount = abs(val_amt)
                        else:
                            txn_type = 'Debit'
                            amount = abs(val_amt)
                    else:
                        if val_amt < 0:
                            txn_type = 'Debit'
                            amount = abs(val_amt)
                        else:
                            txn_type = 'Credit'
                            amount = val_amt
                else:
                    # Let's try heuristic: search row for numbers
                    # A typical row has: Date, Description, Numbers (Amount, Balance)
                    numbers = []
                    for val in row[2:]:
                        val_clean = str(val).replace(",", "").replace("-", "").strip()
                        try:
                            num = float(val_clean)
                            numbers.append(num)
                        except ValueError:
                            pass
                    if len(numbers) >= 2:
                        amount = numbers[0]
                        # Assume debit unless there's CR keyword
                        txn_type = 'Credit' if any('CR' in str(v).upper() or 'CREDIT' in str(v).upper() for v in row) else 'Debit'
                    elif len(numbers) == 1:
                        amount = numbers[0]
                        txn_type = 'Credit' if any('CR' in str(v).upper() or 'CREDIT' in str(v).upper() for v in row) else 'Debit'
                    else:
                        continue # No amount found
                        
                # Balance parse
                balance = 0.0
                if balance_col_idx != -1 and balance_col_idx < len(row):
                    try:
                        balance = float(str(row[balance_col_idx]).replace(",", ""))
                    except ValueError:
                        pass
                else:
                    # Guess last number in row is balance
                    numbers = []
                    for val in row[2:]:
                        val_clean = str(val).replace(",", "").replace("-", "").strip()
                        try:
                            num = float(val_clean)
                            numbers.append(num)
                        except ValueError:
                            pass
                    if len(numbers) >= 2:
                        balance = numbers[-1]
                
                # Category & name matching
                category_id = categorize_transaction(description, txn_type, rules, amount=amount)
                merchant_name, payee_name = detect_merchant_and_payee(description, txn_type)
                payment_method = detect_payment_method(description)
                is_subscription = detect_subscription(merchant_name, amount, txn_type)
                
                transactions.append({
                    "transaction_date": transaction_date,
                    "description": description,
                    "amount": amount,
                    "transaction_type": txn_type,
                    "balance": balance,
                    "category_id": category_id,
                    "payee_name": payee_name,
                    "merchant_name": merchant_name,
                    "payment_method": payment_method,
                    "is_subscription": 1 if is_subscription else 0
                })
                
    finally:
        # Cleanup temporary decrypted file if created
        if temp_decrypted_path and os.path.exists(temp_decrypted_path):
            os.remove(temp_decrypted_path)

    # Sort transactions
    transactions.sort(key=lambda x: (x["transaction_date"], x.get("balance", 0)))
    
    if not transactions:
        raise ValueError("No valid transactions could be parsed from the PDF file.")
    print(f"Parsed transactions: {len(transactions)}")
        
    dates = [t["transaction_date"] for t in transactions]
    metadata["start_date"] = min(dates)
    metadata["end_date"] = max(dates)
    metadata["transaction_count"] = len(transactions)
    
    start_dt = datetime.strptime(metadata["start_date"], "%Y-%m-%d")
    metadata["statement_month"] = start_dt.strftime("%Y-%m")
    
    if not metadata["opening_balance"] and len(transactions) > 0:
        first_txn = transactions[0]
        if first_txn["transaction_type"] == 'Credit':
            metadata["opening_balance"] = first_txn["balance"] - first_txn["amount"]
        else:
            metadata["opening_balance"] = first_txn["balance"] + first_txn["amount"]
            
    if not metadata["closing_balance"] and len(transactions) > 0:
        metadata["closing_balance"] = transactions[-1]["balance"]
        
    return {
        "metadata": metadata,
        "transactions": transactions
    }
