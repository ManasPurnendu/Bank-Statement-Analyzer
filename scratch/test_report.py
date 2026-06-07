import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.report_generator import generate_pdf_report
import traceback

try:
    print("Attempting to generate test PDF report...")
    generate_pdf_report("generated_reports/test_report.pdf", "Summary", "Jan to May 2025")
    print("Report generated successfully!")
except Exception as e:
    print("Error generating report:")
    traceback.print_exc()
