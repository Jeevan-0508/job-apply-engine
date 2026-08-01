import pdfplumber

IGNORE_KEYWORDS = [
    "contact", "email", "linkedin", "phone",
    "education", "certification", "skills summary",
    "jeeve", "gmail", "india", "germany"
]

def extract_resume_sections(pdf_path):
    sections = {
        "experience": []
    }

    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(
            page.extract_text() for page in pdf.pages if page.extract_text()
        )

    for line in text.split("\n"):
        l = line.strip()
        if not l or len(l) < 15:
            continue

        lower = l.lower()
        if any(k in lower for k in IGNORE_KEYWORDS):
            continue

        sections["experience"].append(l)

    return sections
