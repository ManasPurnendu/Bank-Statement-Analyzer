"""
pdf_parser.py  –  Robust PDF bank statement parser.

Strategy:
  1. Try pdfplumber table extraction (structured).
  2. If that yields <3 rows, fall back to line-by-line regex parsing.
  3. Multiple column layouts are auto-detected:
       * 7-col SBI:  Date | Date | Description | - | Debit | - | Credit | Balance
       * 6-col:      Date | Description | Ref | Debit | Credit | Balance
       * 5-col:      Date | Description | Debit | Credit | Balance
       * 4-col:      Date | Description | Amount | Balance
       * 3-col+type: Date | Description | Amount (signed or with CR/DR)

Balances are extracted from:
  - Header section text ("Statement Summary", "Clear Balance", numeric CR/DR values)
  - Last-page summary line ("Brought Forward … Closing Balance")
  - Fallback: first/last transaction row balance column
"""

import pdfplumber
import PyPDF2
import os
import re
import pandas as pd
from datetime import datetime
import concurrent.futures
from services.categorizer import (categorize_transaction, detect_merchant_and_payee,
                                   detect_payment_method, detect_subscription, load_category_rules)
from database.models import compute_transaction_hash

def _process_pdf_page(file_path, password, page_idx):
    """Worker function for multiprocessing PDF page extraction."""
    try:
        with pdfplumber.open(file_path, password=password or '') as pdf:
            page = pdf.pages[page_idx]
            tables = page.extract_tables()
            text = page.extract_text() or ""
            return (page_idx, tables, text)
    except Exception as e:
        print(f"Error processing page {page_idx}: {e}")
        return (page_idx, [], "")


# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------

def is_pdf_encrypted(file_path):
    with open(file_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        return reader.is_encrypted


def decrypt_pdf(input_path, output_path, password):
    try:
        with open(input_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            if reader.is_encrypted:
                result = reader.decrypt(password)
                if result == 0:
                    return False
            writer = PyPDF2.PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            with open(output_path, 'wb') as out_f:
                writer.write(out_f)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

_DATE_FORMATS = (
    '%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d/%m/%y', '%d-%m-%y',
    '%d-%b-%Y', '%d-%b-%y', '%d %b %Y', '%d %b %y',
    '%b %d, %Y', '%Y/%m/%d',
)


def _parse_date(raw: str):
    """Return datetime.date or None."""
    raw = str(raw).strip()
    # Strip trailing time component
    raw = raw.split()[0] if raw.split() else raw
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    try:
        return pd.to_datetime(raw, dayfirst=True).date()
    except Exception:
        return None


def _fmt_date(d) -> str:
    return d.strftime('%Y-%m-%d')


def _is_date_str(s: str) -> bool:
    return _parse_date(s) is not None


# ---------------------------------------------------------------------------
# Amount helpers
# ---------------------------------------------------------------------------

def _parse_amount(s: str) -> float:
    """Parse a money string like '1,23,456.78' or '1234.56CR' → float (always positive)."""
    s = str(s).strip()
    # Remove CR/DR suffix for later use by caller
    s = re.sub(r'(?i)(cr|dr)$', '', s)
    s = re.sub(r'[^\d\.\-\+]', '', s)
    if not s or s in ('.', '-', '+'):
        return 0.0
    try:
        return abs(float(s))
    except ValueError:
        return 0.0


def _cr_or_dr(s: str) -> str:
    """Return 'CR' if the string ends with CR, 'DR' if it ends with DR, else ''."""
    s = str(s).strip().upper()
    if s.endswith('CR'):
        return 'CR'
    if s.endswith('DR'):
        return 'DR'
    return ''


# ---------------------------------------------------------------------------
# Metadata extraction helpers
# ---------------------------------------------------------------------------

_BANK_PATTERNS = [
    ('state bank of india', 'State Bank of India'),
    ('sbi ', 'State Bank of India'),
    ('hdfc bank', 'HDFC Bank'),
    ('hdfc', 'HDFC Bank'),
    ('icici bank', 'ICICI Bank'),
    ('icici', 'ICICI Bank'),
    ('axis bank', 'Axis Bank'),
    ('kotak', 'Kotak Mahindra Bank'),
    ('yes bank', 'Yes Bank'),
    ('standard bank', 'Standard Bank'),
    ('pnb', 'Punjab National Bank'),
    ('punjab national', 'Punjab National Bank'),
    ('canara', 'Canara Bank'),
    ('union bank', 'Union Bank of India'),
    ('bank of baroda', 'Bank of Baroda'),
    ('idbi', 'IDBI Bank'),
    ('indusind', 'IndusInd Bank'),
    ('rbl bank', 'RBL Bank'),
]


def _detect_bank(text: str) -> str:
    tl = text.lower()
    for keyword, name in _BANK_PATTERNS:
        if keyword in tl:
            return name
    m = re.search(r'([A-Za-z ]+\bBank\b)', text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return "Unknown"


def _extract_metadata_from_text(full_text: str) -> dict:
    """
    Extract account holder, number, bank, balances, period from free text.
    Returns a partial metadata dict (only fields that could be found).
    """
    meta = {}

    # Bank name
    meta['bank_name'] = _detect_bank(full_text)

    # Account number  (several possible labels)
    ac = re.search(
        r'(?:Account\s*(?:Number|No\.?)|A[/\.]?C\s*(?:No\.?|Number))[\s:\-]+([0-9A-Za-z]{6,20})',
        full_text, re.IGNORECASE)
    if ac:
        meta['account_number'] = ac.group(1).strip()

    # Account holder
    holder = re.search(r'(?:Mr\.|Mrs\.|Ms\.)\s*([A-Za-z .]{3,40})', full_text)
    if holder:
        meta['account_holder'] = re.sub(r'\s+', ' ', holder.group(1).strip())
    else:
        # Try "Customer Name:" label
        h2 = re.search(r'(?:Customer\s*Name|Account\s*Holder)\s*[:\-]\s*([A-Za-z .]{3,40})',
                       full_text, re.IGNORECASE)
        if h2:
            meta['account_holder'] = h2.group(1).strip()
        else:
            # Heuristic: prominent ALL-CAPS line in first 15 lines
            for line in full_text.split('\n')[:15]:
                line = line.strip()
                if (re.match(r'^[A-Z][A-Z .]{4,}$', line) and
                        not any(k in line for k in (
                            'ACCOUNT', 'STATEMENT', 'BRANCH', 'BANK', 'DATE',
                            'BALANCE', 'CREDIT', 'DEBIT', 'PARTICULARS',
                            'AMOUNT', 'NARRATION', 'TRANSACTION', 'IFSC',
                            'WELCOME', 'SUMMARY', 'MOBILE', 'EMAIL', 'PAN',
                        ))):
                    meta['account_holder'] = line
                    break

    # Statement period  (DD-MM-YYYY to DD-MM-YYYY style)
    period = re.search(
        r'(?:Statement\s*(?:From|Period)?|Period)\s*[:\-]?\s*'
        r'(\d{1,2}[-/\s]\d{1,2}[-/\s]\d{2,4})\s*(?:to|To|\-)\s*'
        r'(\d{1,2}[-/\s]\d{1,2}[-/\s]\d{2,4})',
        full_text, re.IGNORECASE)
    if period:
        sd = _parse_date(period.group(1).replace(' ', '-'))
        ed = _parse_date(period.group(2).replace(' ', '-'))
        if sd:
            meta['start_date'] = _fmt_date(sd)
        if ed:
            meta['end_date'] = _fmt_date(ed)

    # Opening / Closing balances
    sep = r'[\s:\-|]*'
    # Named labels
    ob = re.search(r'(?:Opening\s*Balance|Start\s*Balance|Brought\s*Forward)' + sep +
                   r'([0-9,]+\.?\d*\s*(?:CR|DR)?)', full_text, re.IGNORECASE)
    if ob:
        meta['opening_balance'] = _parse_amount(ob.group(1))

    cb = re.search(r'(?:Closing\s*Balance|End\s*Balance)' + sep +
                   r'([0-9,]+\.?\d*\s*(?:CR|DR)?)', full_text, re.IGNORECASE)
    if cb:
        meta['closing_balance'] = _parse_amount(cb.group(1))

    # SBI-specific "Clear Balance" is the CURRENT account balance (real-time),
    # NOT the statement period closing balance.  We store it in a separate key
    # so that the last-page summary line can override with the correct period CB.
    clr = re.search(
        r'Clear\s*Balance\s*[:\-]\s*([0-9,]+\.?\d*)', full_text, re.IGNORECASE)
    if clr:
        meta['_clear_balance'] = _parse_amount(clr.group(1))

    return meta


def _extract_summary_line(last_page_text: str) -> dict:
    """
    Parse SBI-style summary line:
      Brought Forward( ) Dr Count Cr Count Total Debits( ) Total Credits( ) Closing Balance( )
      24.18CR  1011  494  5,18,144.03  5,32,063.94  13,944.09CR
    Returns partial metadata.
    """
    meta = {}
    # Find the data line below "Brought Forward"
    lines = [l.strip() for l in last_page_text.split('\n') if l.strip()]
    for i, line in enumerate(lines):
        if 'brought forward' in line.lower() and 'closing balance' in line.lower():
            if i + 1 < len(lines):
                tokens = lines[i + 1].split()
                # Expect: BF Amt, DrCount, CrCount, TotalDr, TotalCr, CB Amt
                if len(tokens) >= 2:
                    ob_raw = tokens[0]
                    cb_raw = tokens[-1]
                    ob = _parse_amount(ob_raw)
                    cb = _parse_amount(cb_raw)
                    if ob:
                        meta['opening_balance'] = ob
                    if cb:
                        meta['closing_balance'] = cb
            break

    # Also look for "Statement Summary : DD-MM-YYYY To DD-MM-YYYY"
    period = re.search(
        r'Statement\s*Summary\s*[:\-]\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})\s*(?:To|to|-)\s*'
        r'(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
        last_page_text, re.IGNORECASE)
    if period:
        sd = _parse_date(period.group(1))
        ed = _parse_date(period.group(2))
        if sd:
            meta['start_date'] = _fmt_date(sd)
        if ed:
            meta['end_date'] = _fmt_date(ed)

    return meta


# ---------------------------------------------------------------------------
# Column-layout detection
# ---------------------------------------------------------------------------

def _detect_column_layout(header_row: list) -> dict:
    """
    Given a list of header strings, return index mapping:
      {date, description, debit, credit, amount, balance, type}
    All values are int indices or None.
    """
    mapping = {k: None for k in (
        'date', 'description', 'debit', 'credit', 'amount', 'balance', 'type')}
    synonyms = {
        'date': ['transaction date', 'txn date', 'value date', 'date', 'tx date', 'posting date'],
        'description': ['description', 'narration', 'particulars', 'remarks', 'details',
                        'transaction details', 'narrations'],
        'debit': ['debit', 'withdrawal', 'withdrawals', 'dr amount', 'dr', 'wdl', 'cheque amount'],
        'credit': ['credit', 'deposit', 'deposits', 'cr amount', 'cr', 'dep'],
        'amount': ['amount', 'txn amount', 'transaction amount', 'sum'],
        'balance': ['balance', 'closing balance', 'running balance', 'ledger balance', 'bal'],
        'type': ['type', 'indicator', 'dr/cr', 'cr/dr', 'drcr', 'dr cr'],
    }
    for idx, col in enumerate(header_row):
        col_l = str(col).lower().strip()
        if not col_l or col_l in ('nan', '-', ''):
            continue
        for key, syns in synonyms.items():
            if mapping[key] is not None:
                continue
            for syn in syns:
                if syn == col_l or (len(syn) > 2 and syn in col_l):
                    # Avoid mapping "description" to amount columns
                    if key in ('debit', 'credit', 'amount') and 'desc' in col_l:
                        continue
                    mapping[key] = idx
                    break
    return mapping


def _auto_detect_layout(sample_rows: list, n_cols: int) -> dict:
    """
    Heuristically assign column layout when no header row found.
    Works for the most common PDF layouts.
    """
    mapping = {k: None for k in (
        'date', 'description', 'debit', 'credit', 'amount', 'balance', 'type')}
    if n_cols == 7:
        # SBI layout: Date | Date | Description | separator | Debit | separator | Credit | Balance
        # But pdfplumber extracts 7 values:
        # idx 0: date1, 1: date2, 2: description, 3: '-', 4: debit, 5: credit(or '-'), 6: balance
        mapping.update({'date': 0, 'description': 2,
                       'debit': 4, 'credit': 5, 'balance': 6})
    elif n_cols == 6:
        # Date | Description | Ref/Cheque | Debit | Credit | Balance
        mapping.update({'date': 0, 'description': 1,
                       'debit': 3, 'credit': 4, 'balance': 5})
    elif n_cols == 5:
        # Date | Description | Debit | Credit | Balance
        mapping.update({'date': 0, 'description': 1,
                       'debit': 2, 'credit': 3, 'balance': 4})
    elif n_cols == 4:
        # Date | Description | Amount | Balance
        mapping.update({'date': 0, 'description': 1,
                       'amount': 2, 'balance': 3})
    elif n_cols == 3:
        # Date | Description | Amount(signed)
        mapping.update({'date': 0, 'description': 1, 'amount': 2})
    else:
        # Best guess
        mapping.update({'date': 0, 'description': 1,
                       'amount': 2, 'balance': n_cols - 1})
    return mapping


# ---------------------------------------------------------------------------
# Row parser
# ---------------------------------------------------------------------------

def _parse_row(row: list, mapping: dict) -> dict | None:
    """
    Convert a raw table row to a transaction dict.
    Returns None if the row should be skipped.
    """
    if len(row) == 0:
        return None

    # --- Date ---
    di = mapping.get('date')
    if di is None or di >= len(row):
        return None
    raw_date = str(row[di]).split('\n')[0].strip()   # take first line only
    parsed_date = _parse_date(raw_date)
    if parsed_date is None:
        return None

    # --- Description ---
    desc_i = mapping.get('description')
    if desc_i is None or desc_i >= len(row):
        return None
    description = str(row[desc_i]).strip()
    # For SBI the description has newlines – clean them into spaces
    description = re.sub(r'[\r\n]+', ' ', description).strip()
    # Remove the WDL TFR / DEP TFR prefix that SBI puts as first line
    description = re.sub(r'^(?:WDL\s*TFR|DEP\s*TFR|ATM\s*WDR|NEFT|IMPS|RTGS)\s+', '',
                         description, flags=re.IGNORECASE).strip()
    if not description:
        return None

    # --- Amount & type ---
    amount = 0.0
    txn_type = 'Debit'

    deb_i = mapping.get('debit')
    crd_i = mapping.get('credit')
    amt_i = mapping.get('amount')
    typ_i = mapping.get('type')

    if deb_i is not None and crd_i is not None:
        raw_deb = str(row[deb_i]).strip() if deb_i < len(row) else ''
        raw_crd = str(row[crd_i]).strip() if crd_i < len(row) else ''
        val_deb = _parse_amount(raw_deb)
        val_crd = _parse_amount(raw_crd)
        if val_deb > 0 and (raw_deb not in ('', '-', 'nan', 'None')):
            amount = val_deb
            txn_type = 'Debit'
        elif val_crd > 0 and (raw_crd not in ('', '-', 'nan', 'None')):
            amount = val_crd
            txn_type = 'Credit'
    
    if amount == 0 and amt_i is not None and amt_i < len(row):
        raw_amt = str(row[amt_i]).strip()
        val_amt = _parse_amount(raw_amt)
        if val_amt > 0:
            if typ_i is not None and typ_i < len(row):
                raw_type = str(row[typ_i]).upper().strip()
                txn_type = 'Credit' if any(k in raw_type for k in (
                    'CR', 'CREDIT', '+')) else 'Debit'
            else:
                suffix = _cr_or_dr(raw_amt)
                if suffix == 'CR':
                    txn_type = 'Credit'
                elif suffix == 'DR':
                    txn_type = 'Debit'
                else:
                    try:
                        raw_signed = re.sub(r'[^\d\.\-]', '', raw_amt)
                        txn_type = 'Debit' if float(raw_signed) < 0 else 'Credit'
                    except ValueError:
                        txn_type = 'Credit'
            amount = val_amt

    # Advanced Regex Fallback for space-split lines (like Velocity Bank)
    if amount == 0:
        line_str = " ".join(str(v) for v in row)
        # Match: <Date> ... <Amount> <Balance> at the end of the string
        # e.g., "Rs. 247,043.19 Rs. 448,092.94" or "247043.19 448092.94"
        amt_match = re.search(r'(?:Rs\.?\s*)?([\d,]+\.\d{2})\s+(?:Rs\.?\s*)?([\d,]+\.\d{2})(?:\s*(Cr|Dr|CR|DR))?$', line_str.strip())
        if amt_match:
            amount = _parse_amount(amt_match.group(1))
            balance = _parse_amount(amt_match.group(2))
            
            # Extract description by removing date and amounts
            desc_str = line_str[:amt_match.start()].strip()
            desc_str = re.sub(r'^(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{1,2}\s+[A-Za-z]{3}\s+\d{2,4})', '', desc_str).strip()
            
            # Infer type from description "Cr-" or "Dr-" or default to Credit
            if 'Dr-' in desc_str or 'WDL' in desc_str or 'Withdrawal' in desc_str:
                txn_type = 'Debit'
            elif 'Cr-' in desc_str or 'DEP' in desc_str:
                txn_type = 'Credit'
            elif amt_match.group(3):
                txn_type = 'Credit' if amt_match.group(3).upper() == 'CR' else 'Debit'
            else:
                txn_type = 'Debit' # Default guess, or could use balance delta

            if amount > 0:
                return {
                    'transaction_date': _fmt_date(parsed_date),
                    'description': desc_str,
                    'amount': round(amount, 2),
                    'transaction_type': txn_type,
                    'balance': round(balance, 2),
                }
    else:
        # Last resort: find numbers in cols from index 2 onwards
        numbers = []
        for v in row[2:]:
            cleaned = re.sub(r'[^\d\.]', '', str(v).replace(',', ''))
            try:
                num = float(cleaned)
                if num > 0:
                    numbers.append((num, str(v)))
            except ValueError:
                pass
        if len(numbers) >= 2:
            amount = numbers[0][0]
            any_cr = any('cr' in v.lower() for _, v in numbers)
            txn_type = 'Credit' if any_cr else 'Debit'
        elif len(numbers) == 1:
            amount = numbers[0][0]
        else:
            return None

    if amount <= 0:
        return None

    # --- Balance ---
    bal_i = mapping.get('balance')
    balance = 0.0
    if bal_i is not None and bal_i < len(row):
        balance = _parse_amount(str(row[bal_i]).strip())

    return {
        'transaction_date': _fmt_date(parsed_date),
        'description': description,
        'amount': round(amount, 2),
        'transaction_type': txn_type,
        'balance': round(balance, 2),
    }


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_pdf_statement(file_path: str, original_filename: str, password: str = None) -> dict:
    """
    Parse a PDF bank statement and return canonical parsed data.
    """
    if is_pdf_encrypted(file_path):
        if not password:
            # Try empty password first for PDFs with only a permissions password
            try:
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    if reader.decrypt(''):
                        password = ''
                    else:
                        raise ValueError("PasswordRequired")
            except Exception:
                raise ValueError("PasswordRequired")

        # Verify password is correct
        try:
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                if reader.decrypt(password) == 0:
                    raise ValueError("IncorrectPassword")
        except Exception:
            raise ValueError("IncorrectPassword")

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
        "closing_balance": 0.0,
    }
    rules = load_category_rules()
    transactions = []

    # Get total pages via PyPDF2 quickly
    total_pages = 0
    with open(file_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        if reader.is_encrypted:
            reader.decrypt(password or '')
        total_pages = len(reader.pages)

    page_results = []
    # Multiprocessing across CPU cores
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [executor.submit(_process_pdf_page, file_path, password, i) for i in range(total_pages)]
        for future in concurrent.futures.as_completed(futures):
            page_results.append(future.result())

    # Sort results by page index to keep chronological order
    page_results.sort(key=lambda x: x[0])

    header_text = ""
    last_text = ""
    raw_table_rows = []
    text_fallback_rows = []
    date_pat = re.compile(r'^(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{1,2}\s+[A-Za-z]{3}\s+\d{2,4})')

    for idx, tables, text in page_results:
        if idx < 3:
            header_text += text + "\n"
        if idx == total_pages - 1:
            last_text = text

        for table in tables:
            for row in table:
                cleaned = [str(v).strip() if v is not None else '' for v in row]
                if any(v for v in cleaned):
                    raw_table_rows.append(cleaned)

        for line in text.split('\n'):
            line = line.strip()
            if date_pat.match(line):
                tokens = line.split()
                if len(tokens) >= 3:
                    text_fallback_rows.append(tokens)

    # ---- Step 1: Extract metadata from first 3 pages ----
    try:
        meta_from_text = _extract_metadata_from_text(header_text)
        metadata.update({k: v for k, v in meta_from_text.items() if v})
    except Exception as e:
        print(f"[pdf_parser] header metadata error: {e}")

    # ---- Step 2: Extract metadata from last page (authoritative) ----
    try:
        summary_meta = _extract_summary_line(last_text)
        for k, v in summary_meta.items():
            if v:
                metadata[k] = v
    except Exception as e:
        print(f"[pdf_parser] last-page metadata error: {e}")

    # Use _clear_balance as last-resort closing balance if still 0
    if not metadata.get('closing_balance') and metadata.get('_clear_balance'):
        metadata['closing_balance'] = metadata['_clear_balance']
    metadata.pop('_clear_balance', None)

    # ---- Step 4: Fall back to text-based row extraction ----
    if len(raw_table_rows) < 3:
        raw_table_rows = text_fallback_rows

    if not raw_table_rows:
        raise ValueError("No transaction rows could be extracted from the PDF.")

        # ---- Step 5: Detect header row & column layout ----
        header_idx = -1
        mapping = None

        for i, row in enumerate(raw_table_rows[:15]):
            row_lower = [str(v).lower() for v in row]
            has_date = any('date' in v for v in row_lower)
            has_desc = any(kw in v for kw in
                           ('desc', 'narr', 'part', 'detail', 'particular') for v in row_lower)
            if has_date and has_desc:
                header_idx = i
                mapping = _detect_column_layout(row)
                break

        # Determine data rows
        if header_idx != -1:
            data_rows = raw_table_rows[header_idx + 1:]
        else:
            data_rows = raw_table_rows

        # If no header found or mapping incomplete, auto-detect from sample row width
        if mapping is None or (mapping.get('date') is None):
            # Find the most common row length
            from collections import Counter
            lengths = [len(r) for r in data_rows if len(r) >= 3]
            if lengths:
                modal_len = Counter(lengths).most_common(1)[0][0]
            else:
                modal_len = 5
            mapping = _auto_detect_layout(data_rows[:10], modal_len)

        # ---- Step 6: Parse each data row ----
        skip_keywords = {'date', 'balance', 'narration', 'description',
                         'particulars', 'debit', 'credit', 'amount', 'withdrawal',
                         'deposit', 'brought forward', 'page', 'total'}

        for row in data_rows:
            # Skip header repetitions
            row_lower_set = {str(v).lower().strip() for v in row}
            if row_lower_set & skip_keywords:
                continue

            txn = _parse_row(row, mapping)
            if txn is None:
                continue
            transactions.append(txn)

    if not transactions:
        raise ValueError("No valid transactions could be parsed from the PDF file.")

    # ---- Step 7: Sort chronologically ----
    transactions.sort(key=lambda x: x['transaction_date'])

    # ---- Step 8: Finalise metadata ----
    dates = [t['transaction_date'] for t in transactions]
    if not metadata.get('start_date'):
        metadata['start_date'] = min(dates)
    if not metadata.get('end_date'):
        metadata['end_date'] = max(dates)

    if metadata.get('start_date'):
        metadata['statement_month'] = metadata['start_date'][:7]

    metadata['transaction_count'] = len(transactions)

    # Infer balances from first/last transaction if still missing
    if not metadata.get('opening_balance') and transactions:
        first = transactions[0]
        if first.get('balance'):
            if first['transaction_type'] == 'Credit':
                metadata['opening_balance'] = round(first['balance'] - first['amount'], 2)
            else:
                metadata['opening_balance'] = round(first['balance'] + first['amount'], 2)

    if not metadata.get('closing_balance') and transactions:
        metadata['closing_balance'] = transactions[-1].get('balance', 0.0)

    # ---- Step 9: Enrich transactions (categorise, hash, etc.) ----
    account_number = metadata.get('account_number') or 'Unknown'
    for t in transactions:
        desc = t['description']
        ttype = t['transaction_type']
        amt = t['amount']

        t['category_id'] = categorize_transaction(desc, ttype, rules, amount=amt)
        t['merchant_name'], t['payee_name'] = detect_merchant_and_payee(desc, ttype)
        t['payment_method'] = detect_payment_method(desc)
        t['is_subscription'] = 1 if detect_subscription(t.get('merchant_name'), amt, ttype) else 0
        t['transaction_hash'] = compute_transaction_hash(
            account_number, t['transaction_date'], desc, amt, ttype, t['balance'])

    return {'metadata': metadata, 'transactions': transactions}
