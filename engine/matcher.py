import pdfplumber
import re

def extract_text_from_pdf(path):
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + " "
    return text.lower()

def score_match(resume_path, job_description):
    resume_text = extract_text_from_pdf(resume_path)

    jd_words = set(re.findall(r'\b[a-z]{3,}\b', job_description.lower()))
    resume_words = set(re.findall(r'\b[a-z]{3,}\b', resume_text))

    matched = jd_words.intersection(resume_words)

    score = round((len(matched) / len(jd_words)) * 100, 2) if jd_words else 0

    return score, sorted(list(matched))
