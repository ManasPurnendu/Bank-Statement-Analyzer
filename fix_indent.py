with open("/Users/purne/Desktop/Internship/parsers/pdf_parser.py", "r") as f:
    lines = f.readlines()

out = []
for i, line in enumerate(lines):
    if i == 508 - 1:
        out.append("    with pdfplumber.open(file_path, password=password or '') as pdf:\n")
        continue
    if i > 509 - 1 and i < 610 - 1:
        if line.startswith("    ") and not line.startswith("        "):
            out.append("    " + line)
        else:
            out.append(line)
    else:
        out.append(line)

with open("/Users/purne/Desktop/Internship/parsers/pdf_parser.py", "w") as f:
    f.writelines(out)
print("done")
