with open("/Users/purne/Desktop/Internship/parsers/pdf_parser.py", "r") as f:
    lines = f.readlines()

out = []
for i, line in enumerate(lines):
    if line.strip() == "try:" and lines[i+1].strip().startswith("with pdfplumber.open("):
        continue # skip the try:
    
    if line.strip() == "finally:":
        # skip finally block
        break
    
    # if it's inside the try block (lines between try and finally), unindent by 4 spaces
    if i > 509 and i < 611 and line.startswith("    "):
        out.append(line[4:])
    else:
        out.append(line)

# Now add the remaining lines after finally block
for line in lines[615:]:
    out.append(line)

with open("/Users/purne/Desktop/Internship/parsers/pdf_parser.py", "w") as f:
    f.writelines(out)
print("done")
