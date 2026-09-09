"""
check_imports.py — run this from backend/ folder: python check_imports.py

Scans every .py file under app/, tries to actually import it, and reports EVERY
broken import across the whole codebase in one pass — instead of finding them
one at a time via uvicorn restarts.

Usage:
    cd backend
    python check_imports.py

Output: a list of every file that fails to import, with the exact error, sorted
by folder so you can batch-fix related files together.
"""
import importlib
import sys
import traceback
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent / "app"
FAILURES = []
CHECKED = 0

for py_file in sorted(APP_ROOT.rglob("*.py")):
    if "__pycache__" in str(py_file):
        continue
    if py_file.name == "__init__.py":
        continue

    rel = py_file.relative_to(APP_ROOT.parent)
    module_name = str(rel.with_suffix("")).replace("\\", ".").replace("/", ".")

    CHECKED += 1
    try:
        if module_name in sys.modules:
            del sys.modules[module_name]
        importlib.import_module(module_name)
    except Exception as e:
        FAILURES.append((module_name, f"{type(e).__name__}: {e}"))

print(f"\nChecked {CHECKED} files.\n")

if not FAILURES:
    print("✅ ALL FILES IMPORT CLEANLY.")
else:
    print(f"❌ {len(FAILURES)} FILES FAILED TO IMPORT:\n")
    for mod, err in FAILURES:
        print(f"  {mod}\n      -> {err}\n")