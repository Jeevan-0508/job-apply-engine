"""Puts the repository root on sys.path for the test suite.

pytest prepends only a test file's own directory, which is enough for
``import fixtures`` but not for ``from engine import ...``. Running
``python -m pytest`` happens to add the working directory too, so the suite
passed by accident of invocation; this removes that dependency.
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
