import pandas as pd
import numpy as np
import re
import io
import msoffcrypto
from datetime import datetime
from services.categorizer import categorize_transaction, detect_merchant_and_payee, detect_payment_method, detect_subscription, load_category_rules

def is_excel_encrypted(file_path):
    """
    Checks if an Excel file is password-protected.
    """
    try:
        with open(file_path, 'rb') as f:
            office_file = msoffcrypto.OfficeFile(f)
            return office_file.is_encrypted()
    except Exception:
        return False

def parse_excel_statement(file_path, original_filename, password=None):
    """
    Parses an Excel bank statement (.xls, .xlsx).
    Supports decryption for password-protected Excel workbooks.
    Returns a dict with statement metadata and a list of normalized transactions.
    """
    # 1. Load Excel file (with decryption if needed)
    if is_excel_encrypted(file_path):
        if not password:
            raise ValueError("PasswordRequired")
        
        try:
            decrypted_workbook = io.BytesIO()
            with open(file_path, 'rb') as f:
                office_file = msoffcrypto.OfficeFile(f)
                office_file.load_key(password=password)
                office_file.decrypt(decrypted_workbook)
            decrypted_workbook.seek(0)
            xls = pd.ExcelFile(decrypted_workbook)
            df = pd.read_excel(xls, sheet_name=0, header=None)
        except Exception:
            raise ValueError("IncorrectPassword")
    else:
        try:
            xls = pd.ExcelFile(file_path)
            df = pd.read_excel(xls, sheet_name=0, header=None)
        except Exception as e:
            raise ValueError(f"Unable to read Excel file: {str(e)}")
        
    rows_count = len(df)
    if rows_count == 0:
        raise ValueError("The uploaded Excel file is empty.")

    # 2. Extract Metadata from non-tabular headers (first few rows)
    metadata = {
        "file_name": original_filename,
        "file_type": "Excel",
        "account_holder": "Unknown",
        "account_number": "Unknown",
        "bank_name": "Unknown",
        "statement_month": None,
        "start_date": None,
        "end_date": None,
        "opening_balance": 0.0,
        "closing_balance": 0.0
    }
    
    # Simple regex searches in the sheet text for metadata
    text_dump = ""
    for r in range(min(15, rows_count)):
        row_str = " | ".join([str(val) for val in df.iloc[r] if pd.notna(val)])
        text_dump += row_str + "\n"
        
    # Bank Name detection
    if "state bank of india" in text_dump.lower():
        metadata["bank_name"] = "State Bank of India"
    elif "standard bank" in text_dump.lower():
        metadata["bank_name"] = "Standard Bank"
    elif "hdfc" in text_dump.lower():
        metadata["bank_name"] = "HDFC Bank"
    elif "icici" in text_dump.lower():
        metadata["bank_name"] = "ICICI Bank"
    elif "axis" in text_dump.lower():
        metadata["bank_name"] = "Axis Bank"
    else:
        bank_match = re.search(r'Bank Name\s*[:\|\-\s]+\s*([A-Za-z ]{3,20})', text_dump, re.IGNORECASE)
        if bank_match:
            metadata["bank_name"] = bank_match.group(1).strip()
        else:
            bank_match2 = re.search(r'([A-Za-z ]+ Bank)', text_dump, re.IGNORECASE)
            if bank_match2:
                metadata["bank_name"] = bank_match2.group(1).strip()
            else:
                bank_match3 = re.search(r'Bank\s*[:\|\-\s]+\s*([A-Za-z ]{3,20})', text_dump, re.IGNORECASE)
                if bank_match3:
                    metadata["bank_name"] = bank_match3.group(1).strip()

    # Account Holder detection
    holder_match = re.search(r'(?:Mr\.|Mrs\.|Ms\.)\s*([A-Za-z ]{3,30})', text_dump)
    if holder_match:
        metadata["account_holder"] = re.sub(r'\s+', ' ', holder_match.group(1).strip())
    else:
        holder_match2 = re.search(r'(?:Account Holder|Customer Name)\s*[:\|\-\s]+\s*([A-Za-z ]{3,30})', text_dump, re.IGNORECASE)
        if holder_match2:
            metadata["account_holder"] = re.sub(r'\s+', ' ', holder_match2.group(1).strip())
        else:
            lines = [l.strip() for l in text_dump.split('\n') if l.strip()]
            for line in lines[:15]:
                clean_line = line.replace(' | ', ' ').strip()
                if re.match(r'^[A-Za-z\s\.]+$', clean_line) and len(clean_line) > 5 and not any(k in clean_line.upper() for k in ["ACCOUNT", "STATEMENT", "SUMMARY", "BRANCH", "MOBILE", "EMAIL", "IFSC", "NOMINEE", "WELCOME", "BANK", "DATE", "DESCRIPTION", "DEBIT", "CREDIT", "BALANCE", "PARTICULARS", "AMOUNT", "TRANSACTION"]):
                    metadata["account_holder"] = clean_line
                    break

    # Account Number detection
    ac_match = re.search(r'(?:Account Number|Account No\.?|A/C No\.?|A/C Number)\s*[:\|\-\s]+\s*([0-9A-Za-z\-]+)', text_dump, re.IGNORECASE)
    if ac_match:
        metadata["account_number"] = ac_match.group(1).strip()
    else:
        ac_match2 = re.search(r'(?:Account Number|Account No|A/c No|A/c)[:\s]+([0-9A-Za-z\-]{6,20})', text_dump, re.IGNORECASE)
        if ac_match2:
            metadata["account_number"] = ac_match2.group(1).strip()

    # Look for opening balance
    op_match = re.search(r'(?:Opening Balance|Start Balance)\s*[:\|\-\s]+\s*([0-9,\-\.]+)', text_dump, re.IGNORECASE)
    if op_match:
        try:
            metadata["opening_balance"] = float(op_match.group(1).replace(",", ""))
        except ValueError:
            pass
            
    # Look for closing balance
    cl_match = re.search(r'(?:Closing Balance|End Balance|Balance)\s*[:\|\-\s]+\s*([0-9,\-\.]+)', text_dump, re.IGNORECASE)
    if cl_match:
        try:
            metadata["closing_balance"] = float(cl_match.group(1).replace(",", ""))
        except ValueError:
            pass

    # 3. Find the Transaction Table Header Row
    header_idx = -1
    required_keywords = ["date", "description", "narration", "particulars"]
    for r in range(rows_count):
        row_vals = [str(val).lower() for val in df.iloc[r] if pd.notna(val)]
        # Check if row has date and description keywords
        has_date = any("date" in val for val in row_vals)
        has_desc = any("desc" in val or "narr" in val or "part" in val or "detail" in val for val in row_vals)
        if has_date and has_desc:
            header_idx = r
            break
            
    if header_idx == -1:
        # Fallback: find the first row that has >= 4 columns with non-empty values
        for r in range(rows_count):
            non_empty = [val for val in df.iloc[r] if pd.notna(val)]
            if len(non_empty) >= 4:
                header_idx = r
                break
                
    if header_idx == -1:
        raise ValueError("Unable to identify the transaction table header row.")

    # Re-read DataFrame with headers starting at header_idx
    headers = [str(h).strip() for h in df.iloc[header_idx]]
    data_df = df.iloc[header_idx+1:].copy()
    data_df.columns = headers
    
    # 4. Map Columns to Standard Names
    date_col = None
    desc_col = None
    debit_col = None
    credit_col = None
    amount_col = None
    balance_col = None
    type_col = None # E.g., DR/CR indicator
    
    for col in headers:
        col_lower = str(col).lower()
        if not col_lower or col_lower == 'nan':
            continue
        if any(kw in col_lower for kw in ['transaction date', 'value date', 'date', 'tx date']):
            if not date_col: date_col = col
        elif any(kw in col_lower for kw in ['description', 'narration', 'particulars', 'remarks', 'details']):
            if not desc_col: desc_col = col
        elif any(kw in col_lower for kw in ['debit', 'withdrawal', 'withdrawal amount', 'dr_amount', 'dr']):
            if not debit_col: debit_col = col
        elif any(kw in col_lower for kw in ['credit', 'deposit', 'deposit amount', 'cr_amount', 'cr']):
            if not credit_col: credit_col = col
        elif any(kw in col_lower for kw in ['amount', 'txn amount', 'sum']):
            if not amount_col: amount_col = col
        elif any(kw in col_lower for kw in ['balance', 'running balance', 'ledger balance']):
            if not balance_col: balance_col = col
        elif any(kw in col_lower for kw in ['type', 'indicator', 'dr/cr', 'cr/dr']):
            if not type_col: type_col = col
            
    if not date_col or not desc_col:
        raise ValueError("Bank statement must contain 'Date' and 'Description' columns.")

    # 5. Extract & Normalize Transactions
    transactions = []
    rules = load_category_rules()
    
    for idx, row in data_df.iterrows():
        # Skip row if Date or Description is null
        if pd.isna(row[date_col]) or pd.isna(row[desc_col]):
            continue
            
        raw_date = str(row[date_col]).strip()
        description = str(row[desc_col]).strip()
        
        if not raw_date or not description:
            continue
            
        # Standardize Date
        try:
            # Try multiple parsing patterns
            parsed_date = None
            for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%d/%m/%y', '%d-%b-%Y', '%d-%b-%y', '%b %d, %Y'):
                try:
                    parsed_date = datetime.strptime(raw_date.split(" ")[0], fmt).date()
                    break
                except ValueError:
                    continue
            if not parsed_date:
                # pandas to_datetime helper
                parsed_date = pd.to_datetime(raw_date).date()
        except Exception:
            continue # Date formatting error, skip row
            
        transaction_date = parsed_date.strftime('%Y-%m-%d')
        
        # Calculate Amount and Type
        amount = 0.0
        txn_type = 'Debit'
        
        if debit_col and credit_col:
            raw_deb = row[debit_col]
            raw_cred = row[credit_col]
            
            # Clean numeric strings
            val_deb = float(str(raw_deb).replace(",", "")) if pd.notna(raw_deb) and str(raw_deb).strip() not in ("", "-", "nan", "None") else 0.0
            val_cred = float(str(raw_cred).replace(",", "")) if pd.notna(raw_cred) and str(raw_cred).strip() not in ("", "-", "nan", "None") else 0.0
            
            if val_deb > 0:
                amount = val_deb
                txn_type = 'Debit'
            elif val_cred > 0:
                amount = val_cred
                txn_type = 'Credit'
            else:
                continue # Zero transaction value, skip
        elif amount_col:
            raw_amt = row[amount_col]
            if pd.isna(raw_amt) or str(raw_amt).strip() in ("", "-", "nan"):
                continue
            try:
                val_amt = float(str(raw_amt).replace(",", ""))
            except ValueError:
                continue
                
            if type_col:
                raw_type = str(row[type_col]).upper().strip()
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
            continue # No amount column detected, skip
            
        # Parse Balance
        balance = 0.0
        if balance_col and pd.notna(row[balance_col]):
            try:
                balance = float(str(row[balance_col]).replace(",", ""))
            except ValueError:
                pass

        # Compute Categorization and names
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

    # Sort transactions stably by normalized date only (preserves spreadsheet order)
    transactions.sort(key=lambda x: x["transaction_date"])
    
    if not transactions:
        raise ValueError("No valid transactions could be parsed from the Excel file.")

    # Update metadata with actual parsed values
    dates = [t["transaction_date"] for t in transactions]
    metadata["start_date"] = min(dates)
    metadata["end_date"] = max(dates)
    metadata["transaction_count"] = len(transactions)
    
    # Attempt to extract month from period, e.g. "2025-05"
    start_dt = datetime.strptime(metadata["start_date"], "%Y-%m-%d")
    metadata["statement_month"] = start_dt.strftime("%Y-%m")
    
    if not metadata["opening_balance"] and len(transactions) > 0:
        # Deduce opening balance if not explicitly parsed: balance - credit + debit of the first transaction
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
