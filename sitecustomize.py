"""Automatic venv site-packages loader for RE:TRACE offline environment."""
import os
import sys

_ws = os.path.dirname(os.path.abspath(__file__))
_venv_site = os.path.join(_ws, ".venv", "lib", "python3.9", "site-packages")
if os.path.isdir(_venv_site) and _venv_site not in sys.path:
    sys.path.insert(0, _venv_site)
