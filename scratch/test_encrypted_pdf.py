import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parsers.pdf_parser import parse_pdf_statement

pdf_path = "/Users/purne/Desktop/Internship/AccountStatement_07062026_102218.pdf"
password = "93730210805"

try:
    print("Parsing encrypted PDF with password...")
    res = parse_pdf_statement(pdf_path, "AccountStatement_07062026_102218.pdf", password)
    print("Success!")
    print("Metadata:", res["metadata"])
    print("Num transactions:", len(res["transactions"]))
except Exception as e:
    print("FAILED with exception:", str(e))
    import traceback
    traceback.print_exc()
