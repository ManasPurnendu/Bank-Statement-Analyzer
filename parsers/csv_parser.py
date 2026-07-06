import csv
import re
import os
import pandas as pd
from datetime import datetime
from parsers.utils import normalize_date, normalize_amount, normalize_headers, finalize_metadata, is_numeric_string
from services.categorizer import categorize_transaction, detect_merchant_and_payee, detect_payment_method, detect_subscription, load_category_rules
from database.models import compute_transaction_hash

def parse_csv_statement(file_path, original_filename):
    """
    Parses a CSV bank statement.
    Supports flexible schemas:
    - Separate Debit / Credit columns
    - Single Amount column + Credit/Debit Type column
    - Mixed date and currency formats
    Returns a dict with statement metadata and a list of normalized transactions.
    """
    # 1. Read raw lines to find metadata & locate the header row
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        # Detect delimiter (comma, semicolon, tab, etc.)
        content = f.read(2048)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(content)
            delimiter = dialect.delimiter
        except Exception:
            delimiter = ','
            
        reader = csv.reader(f, delimiter=delimiter)
        raw_rows = [row for row in reader]

    if not raw_rows:
        raise ValueError("The uploaded CSV file is empty.")

    # 2. Extract Metadata from non-tabular rows (first 20 rows)
    metadata = {
        "file_name": original_filename,
        "file_type": "CSV",
        "account_holder": "Unknown",
        "account_number": "Unknown",
        "bank_name": "Unknown",
        "opening_balance": 0.0,
        "closing_balance": 0.0
    }

    text_dump = ""
    for r in range(min(20, len(raw_rows))):
        row_str = " | ".join([str(val) for val in raw_rows[r] if val])
        text_dump += row_str + "\n"

    # Regex search for metadata
    # Bank Name
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

    # Account Number
    ac_match = re.search(r'(?:Account Number|Account No\.?|A/C No\.?|A/C Number)\s*[:\|\-\s]+\s*([0-9A-Za-z\-]+)', text_dump, re.IGNORECASE)
    if ac_match:
        metadata["account_number"] = ac_match.group(1).strip()

    # Account Holder
    holder_match = re.search(r'(?:Mr\.|Mrs\.|Ms\.)\s*([A-Za-z ]{3,30})', text_dump)
    if holder_match:
        metadata["account_holder"] = re.sub(r'\s+', ' ', holder_match.group(1).strip())
    else:
        holder_match2 = re.search(r'(?:Account Holder|Customer Name)\s*[:\|\-\s]+\s*([A-Za-z ]{3,30})', text_dump, re.IGNORECASE)
        if holder_match2:
            metadata["account_holder"] = re.sub(r'\s+', ' ', holder_match2.group(1).strip())

    # Opening/Closing Balance
    separator_pattern = r'[ \t]*(?:-(?!\d)|[:\| \t])+[ \t]*'
    op_match = re.search(r'(?:Opening Balance|Start Balance)' + separator_pattern + r'(-?[0-9,\.]+)', text_dump, re.IGNORECASE)
    if op_match:
        try:
            metadata["opening_balance"] = float(op_match.group(1).replace(",", ""))
        except ValueError:
            pass
            
    cl_match = re.search(r'(?<!Opening\s)(?<!Start\s)\b(?:Closing Balance|End Balance|Balance)\b' + separator_pattern + r'(-?[0-9,\.]+)', text_dump, re.IGNORECASE)
    if cl_match:
        try:
            metadata["closing_balance"] = float(cl_match.group(1).replace(",", ""))
        except ValueError:
            pass

    # 3. Find transaction header row
    header_idx = -1
    mapping = None
    for idx, row in enumerate(raw_rows):
        res = normalize_headers(row)
        if res["date"] is not None and res["description"] is not None:
            header_idx = idx
            mapping = res
            break

    # If no header row was detected, check if we can fall back to the first row of CSV
    if header_idx == -1:
        # Check first row
        if len(raw_rows) > 0:
            res = normalize_headers(raw_rows[0])
            if res["date"] is not None:
                header_idx = 0
                mapping = res

    if header_idx == -1 or mapping is None or mapping["date"] is None or mapping["description"] is None:
        # Smart Format-Agnostic Inference Fallback
        if len(raw_rows) > 0:
            df = pd.DataFrame(raw_rows[1:], columns=range(len(raw_rows[0])))
            headers = list(range(len(raw_rows[0])))
            
            if mapping is None:
                mapping = {"date": None, "description": None, "debit": None, "credit": None, "amount": None, "balance": None}
                
            date_scores = {}
            for col in headers:
                valid_dates = 0
                total_vals = 0
                for val in df[col].head(30):
                    if pd.notna(val) and str(val).strip():
                        total_vals += 1
                        try:
                            normalize_date(str(val))
                            valid_dates += 1
                        except Exception:
                            pass
                if total_vals > 0 and (valid_dates / total_vals) > 0.8:
                    date_scores[col] = valid_dates / total_vals
                    
            if date_scores:
                mapping['date'] = max(date_scores, key=date_scores.get)
                
            numeric_cols = []
            for col in headers:
                if col == mapping['date']: continue
                valid_nums = 0
                total_vals = 0
                for val in df[col].head(30):
                    if pd.notna(val) and str(val).strip() not in ('', '-', 'nan', 'None'):
                        total_vals += 1
                        if is_numeric_string(val):
                            valid_nums += 1
                if total_vals > 0 and (valid_nums / total_vals) > 0.8:
                    numeric_cols.append(col)
                    
            if len(numeric_cols) == 1:
                mapping['amount'] = numeric_cols[0]
            elif len(numeric_cols) == 2:
                mapping['debit'] = numeric_cols[0]
                mapping['credit'] = numeric_cols[1]
            elif len(numeric_cols) >= 3:
                mapping['debit'] = numeric_cols[0]
                mapping['credit'] = numeric_cols[1]
                mapping['balance'] = numeric_cols[2]
                
            desc_scores = {}
            for col in headers:
                if col == mapping['date'] or col in numeric_cols: continue
                vals = [str(val).strip() for val in df[col].head(30) if pd.notna(val) and str(val).strip()]
                if vals:
                    avg_len = sum(len(v) for v in vals) / len(vals)
                    desc_scores[col] = avg_len
            if desc_scores:
                mapping['description'] = max(desc_scores, key=desc_scores.get)
                
            if mapping['date'] is not None and mapping['description'] is not None:
                header_idx = 0
                
    if header_idx == -1 or mapping is None or mapping["date"] is None or mapping["description"] is None:
        raise ValueError("CSV parser error: missing required columns. Could not identify Date or Description headers.")

    # 4. Parse transactions
    transactions = []
    rules = load_category_rules()

    for idx in range(header_idx + 1, len(raw_rows)):
        row = raw_rows[idx]
        if not row:
            continue
            
        # Ensure row has enough columns for mapping
        max_idx = max([v for v in mapping.values() if v is not None])
        if len(row) <= max_idx:
            continue

        raw_date = row[mapping["date"]].strip()
        description = row[mapping["description"]].strip()
        if not raw_date or not description:
            continue

        try:
            transaction_date = normalize_date(raw_date)
        except Exception:
            continue # Skip row on invalid date formats

        amount = 0.0
        txn_type = 'Debit'

        # Determine Amount and Type based on layout
        # Case 1: Separate Debit and Credit columns
        if mapping["debit"] is not None and mapping["credit"] is not None:
            raw_deb = row[mapping["debit"]].strip()
            raw_cred = row[mapping["credit"]].strip()
            
            val_deb = normalize_amount(raw_deb)
            val_cred = normalize_amount(raw_cred)

            if val_deb > 0:
                amount = val_deb
                txn_type = 'Debit'
            elif val_cred > 0:
                amount = val_cred
                txn_type = 'Credit'
            else:
                continue # Zero transaction line
        # Case 2: Single Amount column
        elif mapping["amount"] is not None:
            raw_amt = row[mapping["amount"]].strip()
            try:
                val_amt = normalize_amount(raw_amt)
            except ValueError:
                continue

            if val_amt == 0.0:
                continue

            # Check for Type indicator column
            if mapping["type"] is not None:
                raw_type = row[mapping["type"]].upper().strip()
                if any(k in raw_type for k in ('CR', 'CREDIT', 'IN', '+')):
                    txn_type = 'Credit'
                    amount = abs(val_amt)
                else:
                    txn_type = 'Debit'
                    amount = abs(val_amt)
            else:
                # If no type column, sign determines Debit/Credit
                if val_amt < 0:
                    txn_type = 'Debit'
                    amount = abs(val_amt)
                else:
                    txn_type = 'Credit'
                    amount = val_amt
        else:
            continue # Missing amount columns

        # Parse Balance
        balance = 0.0
        if mapping["balance"] is not None:
            try:
                balance = normalize_amount(row[mapping["balance"]])
            except ValueError:
                pass

        # Apply classification and rules
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

    # Sort chronological ascending
    transactions.sort(key=lambda x: x["transaction_date"])
    
    # Finalize metadata properties
    metadata = finalize_metadata(metadata, transactions)

    # Compute transaction fingerprint hashes
    account_number = metadata.get("account_number") or "Unknown"
    for t in transactions:
        t["transaction_hash"] = compute_transaction_hash(
            account_number,
            t["transaction_date"],
            t["description"],
            t["amount"],
            t["transaction_type"],
            t["balance"]
        )

    return {
        "metadata": metadata,
        "transactions": transactions
    }
