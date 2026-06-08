import pdfplumber
import PyPDF2

pdf_path = "/Users/purne/Desktop/Internship/AccountStatement_07062026_102218.pdf"
password = "93730210805"

reader = PyPDF2.PdfReader(pdf_path)
reader.decrypt(password)
writer = PyPDF2.PdfWriter()
writer.add_page(reader.pages[0])
writer.add_page(reader.pages[1])
writer.add_page(reader.pages[2])

with open("scratch/temp_p1_3.pdf", "wb") as f:
    writer.write(f)

with pdfplumber.open("scratch/temp_p1_3.pdf") as pdf:
    for i in range(3):
        print(f"--- PAGE {i+1} ---")
        print(pdf.pages[i].extract_text()[:2000])
