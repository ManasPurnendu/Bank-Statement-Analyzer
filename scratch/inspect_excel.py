import pandas as pd
import msoffcrypto
import io

excel_path = "/Users/purne/Desktop/Internship/AccountStatement_07062026_094257.xlsx"
password = "93730210805"

# Decrypt and read Excel
decrypted_workbook = io.BytesIO()
with open(excel_path, 'rb') as f:
    office_file = msoffcrypto.OfficeFile(f)
    office_file.load_key(password=password)
    office_file.decrypt(decrypted_workbook)
decrypted_workbook.seek(0)
xls = pd.ExcelFile(decrypted_workbook)
df = pd.read_excel(xls, sheet_name=0, header=None)

print("Excel rows total:", len(df))
print("\n--- FIRST 20 ROWS ---")
for idx, row in df.head(20).iterrows():
    print(idx, [val for val in row if pd.notna(val)])

print("\n--- LAST 20 ROWS ---")
for idx, row in df.tail(20).iterrows():
    print(idx, [val for val in row if pd.notna(val)])
