"""
parsers/utils.py  –  Shared normalisation helpers for all format parsers.
"""

import re
import pandas as pd
from datetime import datetime

# ---------------------------------------------------------------------------
# Date normalisation
# ---------------------------------------------------------------------------

_DATE_FORMATS = (
    '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%d/%m/%y', '%d-%m-%y',
    '%d-%b-%Y', '%d-%b-%y', '%d %b %Y', '%d %b %y',
    '%-d %b %Y', '%-d %b %y', '%-d-%b-%Y', '%-d-%b-%y',
    '%b %d, %Y', '%Y/%m/%d',
    '%d %B %Y', '%d %B %y',  # e.g. "01 January 2025"
)


def normalize_date(date_str: str) -> str:
    """
    Convert a date string in any common format to ISO 'YYYY-MM-DD'.
    Raises ValueError on failure.
    Handles formats including:
      - YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY, DD/MM/YY
      - DD-MMM-YYYY, DD MMM YYYY (e.g. 01 Jan 2025, 1 Jan 2025)
      - DD-MMM-YY, MMM DD, YYYY
    """
    if not date_str:
        raise ValueError("Empty date string")
    date_str = str(date_str).strip()

    # Strip time component ONLY if the next token looks like HH:MM or HH:MM:SS
    # (to preserve "01 Jan 2025" which has spaces but no time)
    import re as _re
    for sep in ('T', '\r', '\n'):
        if sep in date_str:
            date_str = date_str.split(sep)[0].strip()
    # Check if there's a time-like suffix: space followed by HH:MM
    m = _re.match(r'^(.+?)\s+(\d{1,2}:\d{2}(?::\d{2})?)$', date_str)
    if m:
        date_str = m.group(1).strip()

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt).date().strftime('%Y-%m-%d')
        except ValueError:
            continue

    try:
        return pd.to_datetime(date_str, dayfirst=True).date().strftime('%Y-%m-%d')
    except Exception:
        raise ValueError(f"Invalid date format: {date_str}")


# ---------------------------------------------------------------------------
# Amount normalisation
# ---------------------------------------------------------------------------

def is_numeric_string(amount_val) -> bool:
    """
    Check if a string represents a numeric money value.
    """
    if amount_val is None:
        return False
    val_str = str(amount_val).strip()
    if val_str in ('', '-', 'nan', 'None', 'N/A', 'NA'):
        return False
    val_str = re.sub(r'(?i)(cr|dr)$', '', val_str).replace(',', '')
    try:
        float(val_str)
        return True
    except ValueError:
        return False


def normalize_amount(amount_val) -> float:
    """
    Convert a money string / number to a plain Python float.
    Handles:
      - Comma-separated thousands: '1,23,456.78'
      - CR / DR suffix:           '12345.67CR'
      - Currency symbols:         'Rs.1234', '₹1,234.56'
    Always returns the absolute value (sign/direction is handled by the caller).
    Raises ValueError on completely unparseable input.
    """
    if amount_val is None:
        return 0.0
    val_str = str(amount_val).strip()
    if val_str in ('', '-', 'nan', 'None', 'N/A', 'NA'):
        return 0.0
    # Remove currency symbols, CR/DR suffix, commas, spaces
    val_str = re.sub(r'(?i)(cr|dr)$', '', val_str)
    val_str = re.sub(r'[^\d\.\-\+]', '', val_str)
    if not val_str or val_str in ('.', '-', '+'):
        return 0.0
    try:
        return abs(float(val_str))
    except ValueError:
        raise ValueError(f"Invalid amount value: {amount_val}")


def cr_dr_suffix(raw: str) -> str:
    """Return 'CR', 'DR', or '' depending on trailing suffix."""
    s = str(raw).strip().upper()
    if s.endswith('CR'):
        return 'CR'
    if s.endswith('DR'):
        return 'DR'
    return ''


# ---------------------------------------------------------------------------
# Description cleaning
# ---------------------------------------------------------------------------

def clean_description(desc: str) -> str:
    """
    Collapse newlines / carriage returns and extra whitespace.
    Also removes the WDL TFR / DEP TFR SBI-style prefix.
    """
    if not desc:
        return ""
    cleaned = re.sub(r'[\r\n]+', ' ', str(desc))
    cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
    # Strip SBI transaction-type prefix lines
    cleaned = re.sub(
        r'^(?:WDL\s*TFR|DEP\s*TFR|ATM\s*WDR|NEFT|IMPS|RTGS)\s+',
        '', cleaned, flags=re.IGNORECASE).strip()
    return cleaned


# ---------------------------------------------------------------------------
# Header / column mapping
# ---------------------------------------------------------------------------

def normalize_headers(headers_list: list) -> dict:
    """
    Given a list of header strings (one per column), return a dict:
      { 'date': idx|None, 'description': idx|None, 'debit': idx|None,
        'credit': idx|None, 'amount': idx|None, 'balance': idx|None, 'type': idx|None }
    """
    mapping = {k: None for k in ('date', 'description', 'debit', 'credit', 'amount', 'balance', 'type')}

    synonyms = {
        'date': ['transaction date', 'txn date', 'tx date', 'value date', 'date',
                 'posting date', 'entry date'],
        'description': ['description', 'narration', 'particulars', 'remarks', 'details',
                        'name', 'payee', 'comment', 'trans_desc', 'transaction details',
                        'narrations', 'mode'],
        'debit': ['debit', 'withdrawal', 'withdrawals', 'dr_amount', 'dr', 'wdl', 'cheque amount'],
        'credit': ['credit', 'deposit', 'deposits', 'cr_amount', 'cr', 'dep'],
        'amount': ['amount', 'txn amount', 'transaction amount', 'sum'],
        'balance': ['balance', 'closing balance', 'running balance', 'ledger balance', 'bal'],
        'type': ['type', 'indicator', 'dr/cr', 'cr/dr', 'drcr', 'dr cr'],
    }

    for idx, col in enumerate(headers_list):
        col_lower = re.sub(r'[^\w\s/]', '', str(col).lower().strip())
        if not col_lower:
            continue

        for key, syns in synonyms.items():
            if mapping[key] is not None:
                continue
            for syn in syns:
                if syn == col_lower:
                    mapping[key] = idx
                    break
                elif len(syn) <= 2:
                    if syn in col_lower.split():
                        mapping[key] = idx
                        break
                else:
                    if syn in col_lower:
                        # Avoid mapping amount columns to description
                        if key in ('debit', 'credit', 'amount') and 'desc' in col_lower:
                            continue
                        mapping[key] = idx
                        break

    return mapping


# ---------------------------------------------------------------------------
# Metadata finalisation
# ---------------------------------------------------------------------------

def finalize_metadata(metadata: dict, transactions: list) -> dict:
    """
    Fill in missing metadata fields from the parsed transaction list.
    Raises ValueError if no valid transactions exist.
    """
    if not transactions:
        raise ValueError("No valid transactions could be parsed.")

    dates = [t['transaction_date'] for t in transactions if t.get('transaction_date')]
    if not dates:
        raise ValueError("No valid transaction dates found.")

    metadata.setdefault('start_date', min(dates))
    metadata.setdefault('end_date', max(dates))
    if not metadata.get('start_date'):
        metadata['start_date'] = min(dates)
    if not metadata.get('end_date'):
        metadata['end_date'] = max(dates)

    metadata['transaction_count'] = len(transactions)

    try:
        metadata['statement_month'] = metadata['start_date'][:7]
    except Exception:
        metadata['statement_month'] = None

    # Infer opening balance
    if not metadata.get('opening_balance') and transactions:
        first = transactions[0]
        bal = first.get('balance', 0.0) or 0.0
        amt = first.get('amount', 0.0) or 0.0
        if bal:
            if first.get('transaction_type') == 'Credit':
                metadata['opening_balance'] = round(bal - amt, 2)
            else:
                metadata['opening_balance'] = round(bal + amt, 2)
        else:
            metadata['opening_balance'] = 0.0

    # Infer closing balance
    if not metadata.get('closing_balance') and transactions:
        metadata['closing_balance'] = transactions[-1].get('balance', 0.0) or 0.0

    return metadata
