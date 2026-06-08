import pdfplumber
import PyPDF2
import re

pdf_path = "/Users/purne/Desktop/Internship/AccountStatement_07062026_102218.pdf"
password = "93730210805"

# Decrypt PDF
reader = PyPDF2.PdfReader(pdf_path)
reader.decrypt(password)
writer = PyPDF2.PdfWriter()
for page in reader.pages:
    writer.add_page(page)

decrypted_path = "/Users/purne/Desktop/Internship/scratch/temp_decrypted.pdf"
with open(decrypted_path, 'wb') as out_f:
    writer.write(out_f)

print(f"Decrypted to {decrypted_path}")

# Inspect pages
with pdfplumber.open(decrypted_path) as pdf:
    print("Total pages:", len(pdf.pages))
    
    # Let's count how many rows are extracted per page
    for i, page in enumerate(pdf.pages):
        tables = page.extract_tables()
        row_count = sum(len(table) for table in tables if table)
        text = page.extract_text() or ""
        print(f"Page {i+1}: rows in tables={row_count}, text length={len(text)}")
        # If text contains "2026" or "01-01-2026" or "01/01/2026"
        matches = re.findall(r'\b(?:01|02|03|04|05|06|07|08|09|10|11|12|13|14|15|16|17|18|19|20|21|22|23|24|25|26|27|28|29|30|31)[-/](?:01|02|03)[-/]2026\b', text)
        if matches:
            print(f"  Matches for 2026 Q1: {matches}")
        
        # Let's search for "Dec" or "Dec 2025" or similar
        dec_matches = re.findall(r'\b\d{2}[-/]\d{2}[-/]2025\b', text)
        # print first few matches
        if dec_matches:
            print(f"  Matches for 2025: {dec_matches[:5]}... total={len(dec_matches)}")
import os
import re
