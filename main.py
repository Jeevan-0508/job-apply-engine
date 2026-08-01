# =========================
# Standard library imports
# =========================
import sys
import os
import re
from datetime import datetime
import pandas as pd

# =========================
# Helper functions
# =========================
def safe_folder_name(name):
    return re.sub(r'[^a-zA-Z0-9_\- ]', '', name).replace(" ", "_")

# =========================
# Region selection (MUST be first)
# =========================
if len(sys.argv) < 2:
    print("Usage: python main.py germany | india")
    sys.exit(1)

region = sys.argv[1].lower()

if region == "germany":
    from config.germany import *
elif region == "india":
    from config.india import *
else:
    raise ValueError("Unknown region. Use germany or india")

# =========================
# Engine imports (AFTER config)
# =========================
from engine.matcher import score_match
from engine.indeed_scraper import search_indeed, fetch_job_description
from engine.resume_parser import extract_resume_sections
from engine.jd_analyzer import analyze_jd
from engine.tailor import tailor_lines

# =========================
# Ensure output folders exist
# =========================
os.makedirs("data", exist_ok=True)
os.makedirs("applications", exist_ok=True)

# =========================
# Job search
# =========================
jobs = search_indeed(
    query=QUERY,
    location=LOCATION,
    pages=1
)
print("\nDEBUG: Number of jobs scraped =", len(jobs))

if not jobs:
    print("DEBUG: No jobs returned from Indeed")


results = []

# =========================
# Main processing loop
# =========================
for job in jobs:
    print("DEBUG: Processing job ->", job["title"], "|", job["company"])
    jd_text = fetch_job_description(job["link"])
    if not jd_text:
        continue

    score, matched = score_match(RESUME_PATH, jd_text)
    decision = "APPLY" if score >= 60 else "SKIP"

    print(f"\n{job['company']} | {job['title']}")
    print("Score:", score, "| Decision:", decision)

    results.append({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "region": region,
        "company": job["company"],
        "title": job["title"],
        "score": score,
        "decision": decision,
        "link": job["link"]
    })

    # =========================
    # Tailored resume generation
    # =========================
    if decision == "APPLY":
        company_folder = safe_folder_name(job["company"])
        base_path = f"applications/{company_folder}"
        os.makedirs(base_path, exist_ok=True)

        # Analyze JD
        jd_signal = analyze_jd(jd_text)

        # Parse resume
        resume = extract_resume_sections(RESUME_PATH)

        # Tailor experience
        tailored_lines = tailor_lines(resume["experience"], jd_signal)
        tailored_lines = tailored_lines[:8]

        # Write tailored resume
        with open(f"{base_path}/resume_tailored.txt", "w", encoding="utf-8") as f:
            f.write("TAILORED RESUME – DRAFT\n\n")
            for line in tailored_lines:
                f.write(f"- {line}\n")

        # Write match report
        with open(f"{base_path}/match_report.txt", "w", encoding="utf-8") as f:
            f.write("MATCHED SKILLS:\n")
            for skill, weight in jd_signal.items():
                f.write(f"- {skill} (weight {weight})\n")

        # Write job link
        with open(f"{base_path}/job_link.txt", "w", encoding="utf-8") as f:
            f.write(job["link"])

# =========================
# Save results CSV
# =========================
filename = f"data/indeed_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
df = pd.DataFrame(results)
df.to_csv(filename, index=False)

print(f"\nSaved results to {filename}")
print("Run completed successfully.")
