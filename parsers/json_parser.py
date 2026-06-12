import json
import os
import re
from datetime import datetime
from parsers.utils import normalize_date, normalize_amount, finalize_metadata
from services.categorizer import categorize_transaction, detect_merchant_and_payee, detect_payment_method, detect_subscription, load_category_rules
from database.models import compute_transaction_hash

def find_transactions_list(data):
    """
    Helper to locate the transactions array in the JSON document.
    """
    if isinstance(data, list):
        return data, {}
        
    if not isinstance(data, dict):
        return None, {}

    # Drill down into nested fields if they exist
    for nest_key in ('statement', 'data', 'account'):
        if nest_key in data and isinstance(data[nest_key], dict):
            # Try to see if this dictionary contains transactions
            txs, meta = find_transactions_list(data[nest_key])
            if txs is not None:
                # Merge parent metadata with nested metadata
                merged_meta = {k: v for k, v in data.items() if k != nest_key and not isinstance(v, (dict, list))}
                merged_meta.update(meta)
                return txs, merged_meta

    # Look for common transaction array keys
    for tx_key in ('transactions', 'txns', 'records', 'items', 'data', 'rows'):
        if tx_key in data and isinstance(data[tx_key], list):
            meta = {k: v for k, v in data.items() if k != tx_key and not isinstance(v, (dict, list))}
            return data[tx_key], meta

    # General search: find the first list of dicts
    for k, v in data.items():
        if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
            meta = {k2: v2 for k2, v2 in data.items() if k2 != k and not isinstance(v2, (dict, list))}
            return v, meta

    return None, {}

def parse_json_statement(file_path, original_filename):
    """
    Parses a JSON bank statement.
    Supports nested statements and flexible column mapping.
    Returns a dict with statement metadata and a list of normalized transactions.
    """
    # 1. Read JSON file
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            data = json.load(f)
    except Exception as e:
        raise ValueError(f"JSON parser error: invalid JSON. {str(e)}")

    # 2. Locate transactions array and associated metadata
    tx_list, meta_src = find_transactions_list(data)
    if tx_list is None:
        raise ValueError("JSON parser error: unsupported structure. Could not find a list of transaction records.")

    # 3. Extract Metadata from JSON structure
    metadata = {
        "file_name": original_filename,
        "file_type": "JSON",
        "account_holder": "Unknown",
        "account_number": "Unknown",
        "bank_name": "Unknown",
        "opening_balance": 0.0,
        "closing_balance": 0.0
    }

    # Extract metadata using known keys
    def extract_field(src, keys, default="Unknown"):
        for k in keys:
            if k in src and src[k] is not None:
                return str(src[k]).strip()
        return default

    metadata["bank_name"] = extract_field(meta_src, ('bank_name', 'bank', 'bankName'), "Unknown")
    metadata["account_holder"] = extract_field(meta_src, ('account_holder', 'holder', 'accountHolder', 'customer_name', 'name'), "Unknown")
    metadata["account_number"] = extract_field(meta_src, ('account_number', 'account_no', 'accountNo', 'acc_no', 'account'), "Unknown")

    # Balances
    for balance_key in ('opening_balance', 'openingBalance', 'start_balance', 'startBalance'):
        if balance_key in meta_src and meta_src[balance_key] is not None:
            try:
                metadata["opening_balance"] = float(str(meta_src[balance_key]).replace(",", ""))
                break
            except ValueError:
                pass

    for balance_key in ('closing_balance', 'closingBalance', 'end_balance', 'endBalance', 'balance'):
        if balance_key in meta_src and meta_src[balance_key] is not None:
            try:
                metadata["closing_balance"] = float(str(meta_src[balance_key]).replace(",", ""))
                break
            except ValueError:
                pass

    # 4. Map transactions
    transactions = []
    rules = load_category_rules()

    # Search keys mapping
    synonyms = {
        "date": ('txn_date', 'transaction_date', 'transactionDate', 'date', 'tx_date', 'value_date'),
        "description": ('description', 'narration', 'particulars', 'remarks', 'details'),
        "debit": ('debit', 'withdrawal', 'dr', 'dr_amount'),
        "credit": ('credit', 'deposit', 'cr', 'cr_amount'),
        "amount": ('amount', 'value', 'txn_amount'),
        "balance": ('balance', 'running_balance', 'runningBalance'),
        "type": ('type', 'indicator', 'dr_cr', 'drcr')
    }

    for tx in tx_list:
        if not isinstance(tx, dict):
            continue

        # Find mapping keys present in transaction dict
        def find_val(syns):
            for s in syns:
                if s in tx and tx[s] is not None:
                    return tx[s]
            return None

        raw_date = find_val(synonyms["date"])
        raw_desc = find_val(synonyms["description"])

        if raw_date is None or raw_desc is None:
            continue
            
        raw_date = str(raw_date).strip()
        description = str(raw_desc).strip()
        if not raw_date or not description:
            continue

        try:
            transaction_date = normalize_date(raw_date)
        except Exception:
            continue # Skip row on invalid date

        amount = 0.0
        txn_type = 'Debit'

        # Check values
        raw_deb = find_val(synonyms["debit"])
        raw_cred = find_val(synonyms["credit"])
        raw_amt = find_val(synonyms["amount"])
        raw_type = find_val(synonyms["type"])

        # Check layout: Debit/Credit columns
        if raw_deb is not None or raw_cred is not None:
            val_deb = normalize_amount(raw_deb)
            val_cred = normalize_amount(raw_cred)
            if val_deb > 0:
                amount = val_deb
                txn_type = 'Debit'
            elif val_cred > 0:
                amount = val_cred
                txn_type = 'Credit'
            else:
                continue
        # Check layout: single Amount column
        elif raw_amt is not None:
            try:
                val_amt = normalize_amount(raw_amt)
            except ValueError:
                continue

            if val_amt == 0.0:
                continue

            if raw_type is not None:
                type_str = str(raw_type).upper().strip()
                if any(k in type_str for k in ('CR', 'CREDIT', 'IN', '+')):
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
            continue

        # Parse Balance
        balance = 0.0
        raw_bal = find_val(synonyms["balance"])
        if raw_bal is not None:
            try:
                balance = normalize_amount(raw_bal)
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

    if not transactions:
        raise ValueError("JSON parser error: unsupported structures. Could not find or parse valid transactions.")

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
