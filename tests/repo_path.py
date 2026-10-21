import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(REPO_ROOT, "tests", "fixtures")

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
