class BalanceEngine:
    """Tracks running balance through time for a specific statement/user."""
    
    def __init__(self, starting_balance=10000.0):
        self.balance = starting_balance
        self.opening_balance = starting_balance
        self.credits = 0.0
        self.debits = 0.0
        self.transaction_count = 0
        
    def process_transaction(self, amount, tx_type):
        """Update balance. tx_type must be 'Credit' or 'Debit'."""
        if tx_type == 'Credit':
            self.balance += amount
            self.credits += amount
        elif tx_type == 'Debit':
            self.balance -= amount
            self.debits += amount
        self.transaction_count += 1
        return round(self.balance, 2)
        
    def get_summary(self):
        return {
            'opening_balance': round(self.opening_balance, 2),
            'closing_balance': round(self.balance, 2),
            'transaction_count': self.transaction_count
        }
