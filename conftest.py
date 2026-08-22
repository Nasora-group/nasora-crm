"""Pytest bootstrap for the repository root.

Render runs pytest from the source directory, but some pytest import modes can
omit that directory from sys.path under newer Python versions. Explicitly add
it so tests import the same application package used by wsgi.py.
"""
from pathlib import Path
import sys

ROOT = str(Path(__file__).resolve().parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
