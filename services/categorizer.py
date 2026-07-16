import re
from database.db import get_db_connection

def load_category_rules():
    """
    Loads all category rules from the database as a list of (keyword, category_id) tuples.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT keyword, category_id FROM category_rules')
    rows = cursor.fetchall()
    conn.close()
    return [(row['keyword'].upper(), row['category_id']) for row in rows]

def clean_description(description):
    """
    Cleans descriptions by removing txn references, UPI IDs, dates, numbers, etc.
    to extract the raw name.
    """
    desc = description.upper().strip()
    
    # Remove common prefixes/suffixes like Ref numbers, dates, codes
    # Examples: "UPI-SWIGGY-12345@OKAXIS" -> "SWIGGY"
    # "TRANSFER TO ANUJ IN 9876..." -> "ANUJ"
    
    # Remove transaction IDs / reference numbers
    desc = re.sub(r'\b[0-9]{10,}\b', '', desc)
    desc = re.sub(r'\bREF\b', '', desc)
    desc = re.sub(r'\bTXN\b', '', desc)
    desc = re.sub(r'\bNO\b', '', desc)
    
    # Clean up excess spaces
    desc = re.sub(r'\s+', ' ', desc).strip()
    return desc

def detect_payment_method(description):
    """
    Detects payment method from transaction description.
    """
    desc = description.upper()
    if 'UPI' in desc or 'PAYTM' in desc or 'PHONEPE' in desc or 'GPAY' in desc or 'G PAY' in desc or 'BHIM' in desc:
        return 'UPI'
    elif 'ATM' in desc or 'CASH WDL' in desc or 'CASH WITHDRAWAL' in desc or 'CASH-WDL' in desc:
        return 'ATM'
    elif 'NEFT' in desc:
        return 'NEFT'
    elif 'IMPS' in desc:
        return 'IMPS'
    elif 'RTGS' in desc:
        return 'RTGS'
    elif 'CHQ' in desc or 'CHEQUE' in desc:
        return 'Cheque'
    elif 'CARD' in desc or 'POS' in desc or 'DEBIT CARD' in desc or 'CREDIT CARD' in desc or 'ECOM' in desc:
        return 'Card'
    else:
        return 'Other'

def detect_merchant_and_payee(description, transaction_type):
    """
    Identifies if a transaction is associated with a business merchant or a personal contact.
    Returns: (merchant_name, payee_name)
    """
    desc = clean_description(description)
    
    # Known merchants list
    known_merchants = [
        ('AMAZON', 'Amazon'),
        ('SWIGGY', 'Swiggy'),
        ('ZOMATO', 'Zomato'),
        ('UBER', 'Uber'),
        ('OLA', 'Ola'),
        ('NETFLIX', 'Netflix'),
        ('SPOTIFY', 'Spotify'),
        ('RELIANCE RETAIL', 'Reliance Retail'),
        ('FLIPKART', 'Flipkart'),
        ('MICROSOFT', 'Microsoft 365'),
        ('YOUTUBE', 'Youtube Premium'),
        ('PRIME VIDEO', 'Amazon Prime'),
        ('GOOGLE', 'Google One'),
        ('APPLE', 'Apple Music'),
        ('BESCOM', 'Bescom Electricity'),
        ('ACT FIBERNET', 'ACT Fibernet'),
        ('AIRTEL', 'Airtel'),
        ('JIO', 'Jio'),
        ('ELECTRICITY', 'Electricity Bill'),
        ('STARBUCKS', 'Starbucks'),
        ('DMART', 'DMart'),
        ('DOMINOS', 'Dominos Pizza'),
        ('HOTSTAR', 'Disney+ Hotstar')
    ]
    
    # Check known merchants
    for keyword, display_name in known_merchants:
        if keyword in desc:
            return display_name, None
            
    # Extract clean name from UPI pattern: UPI/CR/txn_id/NAME/BANK/upi_id/...
    upi_match = re.search(r'UPI/(?:CR|DR)/[0-9]+/([^/]+)', description, re.IGNORECASE)
    if upi_match:
        name = upi_match.group(1).replace('\n', ' ').strip()
        name_clean = re.sub(r'\b(?:UPI|P2P|BANK|MOBILE|A/C|XX+|ACCOUNT|IN|ON|FOR|AT)\b', '', name, flags=re.IGNORECASE).strip()
        name_clean = re.sub(r'\s+', ' ', name_clean).strip()
        if len(name_clean) >= 3 and not re.match(r'^[0-9]+$', name_clean):
            return None, name_clean.title()
            
    # If it's a debit and looks like payment to a person (UPI P2P, transfer, send)
    if transaction_type == 'Debit':
        # E.g., "TRANSFER TO ANUJ", "UPI-ANUJ-...", "PAID TO RAMESH"
        transfer_match = re.search(r'(?:TRANSFER TO|TO|PAID TO|SENT TO|UPI[-_])\s*([A-Z\s]{3,15})', desc)
        if transfer_match:
            name = transfer_match.group(1).strip()
            # Remove helper words
            name = re.sub(r'\b(?:UPI|P2P|BANK|MOBILE|A/C|XX+|ACCOUNT|IN|ON|FOR|AT)\b', '', name).strip()
            if len(name) >= 3:
                return None, name.title()
                
        # Fallback to cleaned description for payee if no merchant matched
        return None, desc.title()
    else:
        # For credits (Income/Refunds)
        # E.g., "SALARY FROM INTEL", "REFUND FROM AMAZON"
        refund_match = re.search(r'(?:REFUND FROM|FROM|SALARY FROM|PAYMENT FROM)\s*([A-Z\s]{3,15})', desc)
        if refund_match:
            name = refund_match.group(1).strip()
            return None, name.title()
            
        return None, desc.title()

def categorize_transaction(description, transaction_type, rules=None, amount=None):
    """
    Matches clean description or amount with category rules.
    Returns: category_id
    """
    if rules is None:
        rules = load_category_rules()
        
    # First, try to match amount-based rules if amount is provided
    if amount is not None:
        try:
            amt_val = float(amount)
            for keyword, category_id in rules:
                if keyword.startswith("AMOUNT:"):
                    try:
                        rule_amt = float(keyword.split(":", 1)[1])
                        if abs(amt_val - rule_amt) < 0.01:
                            return category_id
                    except (ValueError, IndexError):
                        pass
        except ValueError:
            pass

    desc = clean_description(description)
    
    # Try exact or substring matches against keywords, skipping AMOUNT: rules
    for keyword, category_id in rules:
        if keyword.startswith("AMOUNT:"):
            continue
        if keyword in desc:
            return category_id
            
    # Default category
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT category_id FROM categories WHERE category_name = 'Uncategorized'")
    row = cursor.fetchone()
    conn.close()
    return row['category_id'] if row else 12

def detect_subscription(merchant_name, amount, transaction_type):
    """
    Simple check for subscription based on merchant name.
    Detailed checks are performed in the analytics engine for recurring amounts.
    """
    if transaction_type != 'Debit' or not merchant_name:
        return False
        
    sub_merchants = ['Netflix', 'Spotify', 'Youtube Premium', 'Amazon Prime', 'Google One', 'Apple Music', 'Microsoft 365', 'Disney+ Hotstar']
    return merchant_name in sub_merchants
