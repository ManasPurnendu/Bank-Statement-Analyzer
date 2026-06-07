import openpyxl
from datetime import datetime, timedelta
import random

def create_sample_excel():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Statement"
    
    # Write metadata
    ws["A1"] = "STANDARD BANK - ACCOUNT STATEMENT"
    ws["A1"].font = openpyxl.styles.Font(bold=True, size=14)
    
    ws["A2"] = "Account Holder:"
    ws["B2"] = "Manas Purnendu"
    ws["A3"] = "Account Number:"
    ws["B3"] = "10098765432"
    ws["A4"] = "Bank Name:"
    ws["B4"] = "Standard Bank"
    ws["A5"] = "Statement Period:"
    ws["B5"] = "01 Jan 2025 - 31 May 2025"
    ws["A6"] = "Opening Balance:"
    ws["B6"] = -100000.00 # Offset to match Ending Balance vs Net Savings
    
    # Write headers
    headers = ["Date", "Description", "Debit", "Credit", "Balance"]
    for col_idx, text in enumerate(headers, 1):
        cell = ws.cell(row=8, column=col_idx)
        cell.value = text
        cell.font = openpyxl.styles.Font(bold=True)
        cell.fill = openpyxl.styles.PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        cell.font = openpyxl.styles.Font(color="FFFFFF", bold=True)

    # We want to generate transactions from Jan 1 2025 to May 31 2025
    # Total Income: 6,24,560.00
    # Total Expenses: 3,78,879.50
    # Current Balance: 145,680.50
    
    # Let's outline the specific credit/debit totals we want for each month:
    # May: Inc 124,560.00, Exp 78,879.50
    # Apr: Inc 105,120.00, Exp 70,150.00
    # Mar: Inc 118,340.00, Exp 72,430.50
    # Feb: Inc  98,760.00, Exp 61,230.00
    # Jan: Inc 110,430.00, Exp 65,780.00
    
    # Let's seed merchants with totals:
    # Amazon: 28,450 (Shopping)
    # Swiggy: 17,230 (Food & Dining)
    # Reliance Retail: 12,890 (Shopping)
    # Zomato: 11,450 (Food & Dining)
    # Flipkart: 9,980 (Shopping)
    
    # Subscriptions:
    # Netflix: 649 (Monthly, around 10th)
    # Amazon Prime: 179 (Monthly, around 15th)
    # Spotify: 119 (Monthly, around 5th)
    # Microsoft 365: 499 (Yearly, let's place it in May 2025)
    # Youtube Premium: 129 (Monthly, around 18th)
    
    # Monthly Salaries:
    # May: Salary 1,20,000, Interest 4,560
    # Apr: Salary 1,00,000, Interest 5,120
    # Mar: Salary 1,15,000, Interest 3,340
    # Feb: Salary 95,000, Interest 3,760
    # Jan: Salary 1,05,000, Interest 5,430
    
    current_balance = -100000.00
    
    # Month list
    months_data = [
        {"year": 2025, "month": 1, "salary": 105000, "interest": 5430, "target_exp": 65780.00},
        {"year": 2025, "month": 2, "salary": 95000, "interest": 3760, "target_exp": 61230.00},
        {"year": 2025, "month": 3, "salary": 115000, "interest": 3340, "target_exp": 72430.50},
        {"year": 2025, "month": 4, "salary": 100000, "interest": 5120, "target_exp": 70150.00},
        {"year": 2025, "month": 5, "salary": 120000, "interest": 4560, "target_exp": 78879.50}
    ]
    
    row_num = 9
    
    # Distribute top merchant spends across months
    # Totals: Amazon: 28450, Swiggy: 17230, Reliance: 12890, Zomato: 11450, Flipkart: 9980
    amazon_spends = [5000, 6000, 4500, 7500, 5450] # 5 items
    swiggy_spends = [3200, 3500, 3100, 3930, 3500] # 5 items
    reliance_spends = [2500, 2000, 3000, 2390, 3000] # 5 items
    zomato_spends = [2000, 2200, 2150, 2600, 2500] # 5 items
    flipkart_spends = [1500, 1800, 2200, 2000, 2480] # 5 items
    
    for idx, m in enumerate(months_data):
        y, mn = m["year"], m["month"]
        
        # We will collect transactions for this month and write them in order
        month_txs = []
        
        # Credits (Income)
        # Salary Credit
        salary_day = 27 if mn == 2 else 28
        month_txs.append((datetime(y, mn, salary_day), "SALARY CREDIT - TECHCORP", None, m["salary"]))
        # Interest Credit
        interest_day = 28 if mn == 2 else (30 if mn == 4 else 31)
        month_txs.append((datetime(y, mn, interest_day), "INTEREST CREDIT", None, m["interest"]))
        
        # Debits (Expenses)
        # Subscriptions
        month_txs.append((datetime(y, mn, 5), "UPI-SPOTIFY-RECURRING", 119.00, None))
        month_txs.append((datetime(y, mn, 10), "CARD-NETFLIX-MEMBERSHIP", 649.00, None))
        month_txs.append((datetime(y, mn, 15), "UPI-AMAZON PRIME-RECURRING", 179.00, None))
        month_txs.append((datetime(y, mn, 18), "CARD-YOUTUBE PREMIUM-REC", 129.00, None))
        
        if mn == 5: # May 2025 Microsoft 365 subscription
            month_txs.append((datetime(y, mn, 21), "CARD-MICROSOFT 365 SUBSCRIPTION", 499.00, None))
            
        # Top Merchants
        month_txs.append((datetime(y, mn, 12), "UPI-AMAZON PAY-SHOPPING", amazon_spends[idx], None))
        month_txs.append((datetime(y, mn, 4), "UPI-SWIGGY-FOOD", swiggy_spends[idx], None))
        month_txs.append((datetime(y, mn, 22), "CARD-RELIANCE RETAIL-GROCERY", reliance_spends[idx], None))
        month_txs.append((datetime(y, mn, 16), "UPI-ZOMATO-DINING", zomato_spends[idx], None))
        month_txs.append((datetime(y, mn, 25), "CARD-FLIPKART-PURCHASE", flipkart_spends[idx], None))
        
        # Fixed expenses (Rent, Electricity)
        month_txs.append((datetime(y, mn, 1), "CHQ-HOUSE RENT PAYMENT", 15000.00, None))
        month_txs.append((datetime(y, mn, 7), "UPI-ELECTRICITY BILL", 1280.00, None))
        
        # We need to fill up the remaining expenses to match the target expense for this month exactly!
        current_exp_sum = sum(t[2] for t in month_txs if t[2] is not None)
        rem_exp = m["target_exp"] - current_exp_sum
        
        if rem_exp > 0:
            # Distribute remaining expense into miscellaneous categories: Travel, Healthcare, etc.
            # Let's add an Uber Ride
            month_txs.append((datetime(y, mn, 14), "UPI-UBER RIDE-TRAVEL", 260.00, None))
            # Let's add a Pharmacy/Apollo spend
            month_txs.append((datetime(y, mn, 20), "CARD-APOLLO PHARMACY", 1500.00, None))
            
            # Recompute remaining
            current_exp_sum = sum(t[2] for t in month_txs if t[2] is not None)
            rem_exp = m["target_exp"] - current_exp_sum
            
            if rem_exp > 0:
                # Add a generic cash withdrawal or transfer to Ramesh/Anuj
                month_txs.append((datetime(y, mn, 26), "ATM-CASH WITHDRAWAL", rem_exp, None))
                
        # Sort month transactions chronologically by date
        month_txs.sort(key=lambda x: x[0])
        
        # Write to sheet
        for date_obj, desc, debit, credit in month_txs:
            ws.cell(row=row_num, column=1).value = date_obj.strftime("%d %b %Y")
            ws.cell(row=row_num, column=2).value = desc
            
            if debit is not None:
                ws.cell(row=row_num, column=3).value = debit
                current_balance -= debit
            else:
                ws.cell(row=row_num, column=3).value = ""
                
            if credit is not None:
                ws.cell(row=row_num, column=4).value = credit
                current_balance += credit
            else:
                ws.cell(row=row_num, column=4).value = ""
                
            ws.cell(row=row_num, column=5).value = current_balance
            row_num += 1

    wb.save("sample_statement_jan_may_2025.xlsx")
    print("Successfully generated sample_statement_jan_may_2025.xlsx")

if __name__ == "__main__":
    create_sample_excel()
