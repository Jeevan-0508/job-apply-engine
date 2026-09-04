"""
Prints the Streamlit Secrets block for the hosted app, read from your local
config/profile.py.

The hosted app gets your real profile through one PROFILE_JSON secret instead
of through git, so nothing personal is ever committed. Run this, then paste the
output into Streamlit Cloud -> App settings -> Secrets.

    python tools/make_secret.py                 # print it
    python tools/make_secret.py -o secrets.toml # write it somewhere untracked
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", help="write to this file instead of stdout")
    args = ap.parse_args()

    try:
        from config.profile import PROFILE
    except ImportError:
        sys.exit("config/profile.py not found -- fill it in first (it is gitignored).")

    # A TOML multi-line basic string keeps the JSON readable in the secrets box.
    # Streamlit reads it back as one string, which loader.get_profile() parses.
    payload = json.dumps(PROFILE, ensure_ascii=False, indent=2)
    block = 'PROFILE_JSON = """\n' + payload.replace("\\", "\\\\") + '\n"""\n'

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(block)
        print(f"Wrote {args.out} ({len(block)} bytes). This file holds personal data -- "
              "keep it out of git.")
    else:
        sys.stdout.write(block)


if __name__ == "__main__":
    main()
