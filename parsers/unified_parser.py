"""
unified_parser.py  –  Single entry point for all bank statement formats.

Dispatches to the appropriate format-specific parser and guarantees that every
caller receives the same canonical dict:

    {
        "metadata": {
            "file_name":        str,
            "file_type":        str,          # PDF | Excel | CSV | JSON
            "account_holder":   str,
            "account_number":   str,
            "bank_name":        str,
            "statement_month":  "YYYY-MM",
            "start_date":       "YYYY-MM-DD",
            "end_date":         "YYYY-MM-DD",
            "opening_balance":  float,
            "closing_balance":  float,
            "transaction_count": int
        },
        "transactions": [
            {
                "transaction_date":  "YYYY-MM-DD",
                "description":       str,
                "amount":            float   (always positive),
                "transaction_type":  "Credit" | "Debit",
                "balance":           float,
                "category_id":       int | None,
                "payee_name":        str | None,
                "merchant_name":     str | None,
                "payment_method":    str | None,
                "is_subscription":   0 | 1,
                "transaction_hash":  str
            },
            ...
        ]
    }
"""

import os


def parse_statement(file_path: str, original_filename: str, password: str = None) -> dict:
    """
    Detect the file type from its extension and route to the correct parser.

    Returns the canonical parsed-statement dict described above.

    Raises:
        ValueError  – "PasswordRequired" | "IncorrectPassword" | descriptive message
        RuntimeError – unrecoverable internal error (propagated from sub-parser)
    """
    if not os.path.exists(file_path):
        raise ValueError(f"File not found: {file_path}")

    ext = original_filename.rsplit('.', 1)[-1].lower() if '.' in original_filename else ''

    if ext == 'pdf':
        from parsers.pdf_parser import parse_pdf_statement
        result = parse_pdf_statement(file_path, original_filename, password=password)

    elif ext in ('xls', 'xlsx'):
        from parsers.excel_parser import parse_excel_statement
        result = parse_excel_statement(file_path, original_filename, password=password)

    elif ext == 'csv':
        from parsers.csv_parser import parse_csv_statement
        result = parse_csv_statement(file_path, original_filename)

    elif ext == 'json':
        from parsers.json_parser import parse_json_statement
        result = parse_json_statement(file_path, original_filename)

    else:
        raise ValueError(
            f"Unsupported file type: '{ext}'. Supported formats: PDF, XLS, XLSX, CSV, JSON."
        )

    # Guarantee canonical structure after every parser
    result = _canonicalize(result, original_filename, ext)
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _canonicalize(result: dict, filename: str, ext: str) -> dict:
    """
    Ensure the metadata dict has every required field with the correct type,
    and that every transaction dict is fully normalised.
    """
    meta = result.get("metadata", {})
    txns = result.get("transactions", [])

    # --- Metadata defaults / type coercions ---
    type_map = {'pdf': 'PDF', 'xls': 'Excel', 'xlsx': 'Excel', 'csv': 'CSV', 'json': 'JSON'}
    meta.setdefault("file_name", filename)
    meta.setdefault("file_type", type_map.get(ext, ext.upper()))
    meta.setdefault("account_holder", "Unknown")
    meta.setdefault("account_number", "Unknown")
    meta.setdefault("bank_name", "Unknown")

    # Ensure balances are floats, never None
    meta["opening_balance"] = _safe_float(meta.get("opening_balance"), 0.0)
    meta["closing_balance"] = _safe_float(meta.get("closing_balance"), 0.0)

    # Derive start / end / month from transactions when missing
    dates = [t["transaction_date"] for t in txns if t.get("transaction_date")]
    if dates:
        if not meta.get("start_date"):
            meta["start_date"] = min(dates)
        if not meta.get("end_date"):
            meta["end_date"] = max(dates)
    if not meta.get("statement_month") and meta.get("start_date"):
        meta["statement_month"] = meta["start_date"][:7]

    meta["transaction_count"] = len(txns)

    # If closing balance is still 0 but we have transaction balances, infer it
    if meta["closing_balance"] == 0.0 and txns:
        last_bal = txns[-1].get("balance", 0.0)
        if last_bal:
            meta["closing_balance"] = float(last_bal)

    # If opening balance is still 0 but we have transaction balances, infer it
    if meta["opening_balance"] == 0.0 and txns:
        first_txn = txns[0]
        first_bal = _safe_float(first_txn.get("balance"), 0.0)
        if first_bal:
            if first_txn.get("transaction_type") == "Credit":
                meta["opening_balance"] = first_bal - _safe_float(first_txn.get("amount"), 0.0)
            else:
                meta["opening_balance"] = first_bal + _safe_float(first_txn.get("amount"), 0.0)

    # --- Transaction field normalisation ---
    normalised = []
    for t in txns:
        nt = {
            "transaction_date":  str(t.get("transaction_date", "")).strip(),
            "description":       _clean_description(t.get("description", "")),
            "amount":            abs(_safe_float(t.get("amount"), 0.0)),
            "transaction_type":  _normalise_type(t.get("transaction_type", "Debit")),
            "balance":           _safe_float(t.get("balance"), 0.0),
            "category_id":       t.get("category_id"),
            "payee_name":        t.get("payee_name") or None,
            "merchant_name":     t.get("merchant_name") or None,
            "payment_method":    t.get("payment_method") or None,
            "is_subscription":   1 if t.get("is_subscription") else 0,
            "transaction_hash":  t.get("transaction_hash", ""),
        }
        if nt["transaction_date"] and nt["amount"] > 0:
            normalised.append(nt)

    return {"metadata": meta, "transactions": normalised}


def _safe_float(val, default=0.0) -> float:
    if val is None:
        return default
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return default


def _clean_description(desc: str) -> str:
    """Collapse newlines and extra whitespace in multiline PDF descriptions."""
    if not desc:
        return ""
    import re
    cleaned = re.sub(r'[\r\n]+', ' ', str(desc))
    cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
    return cleaned


def _normalise_type(raw: str) -> str:
    r = str(raw).strip().upper()
    if r in ("CREDIT", "CR", "C", "IN", "+"):
        return "Credit"
    return "Debit"
