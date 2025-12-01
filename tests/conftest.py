import sys
from pathlib import Path

# Ensure the repository version of OpenShockPY is importable before any
# user/site-installed copy. This avoids tests accidentally picking up an
# older installed package when running via a globally installed pytest entry
# point.
REPO_ROOT = Path(__file__).resolve().parents[1]
repo_str = str(REPO_ROOT)
if repo_str not in sys.path:
    sys.path.insert(0, repo_str)
