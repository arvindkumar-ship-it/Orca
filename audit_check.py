"""
audit.py — comprehensive static analysis, run from backend/: python audit.py

Does NOT import/execute any code (avoids Settings/.env cascade noise entirely).
Pure AST parsing. Finds, in ONE pass:
  1. Every `__tablename__` across the whole project, flags duplicates (the exact bug
     class that hit you with incident_notification.py and trip.py).
  2. Every `from X import Y` statement anywhere under app/, risk_engine/, forecast_engine/,
     and checks whether Y is actually defined (as class/def/assignment) in the file X
     resolves to. Flags every one that doesn't match.

Usage:
    cd backend
    python audit.py
"""
import ast
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent
SCAN_DIRS = ["app", "risk_engine", "forecast_engine", "trip_planner", "ingestion", "normalization"]

py_files = []
for d in SCAN_DIRS:
    p = ROOT / d
    if p.exists():
        py_files.extend(sorted(p.rglob("*.py")))
py_files = [f for f in py_files if "__pycache__" not in str(f)]


def module_name(f: Path) -> str:
    return str(f.relative_to(ROOT).with_suffix("")).replace("\\", ".").replace("/", ".")


def file_for_module(mod: str) -> Path | None:
    """Resolve 'app.models.core' -> backend/app/models/core.py (or /__init__.py)."""
    parts = mod.split(".")
    candidate = ROOT.joinpath(*parts).with_suffix(".py")
    if candidate.exists():
        return candidate
    candidate_init = ROOT.joinpath(*parts, "__init__.py")
    if candidate_init.exists():
        return candidate_init
    return None


def top_level_names(f: Path) -> set[str]:
    """All class/function/variable names defined at module top level."""
    try:
        tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError as e:
        print(f"  ⚠️  SYNTAX ERROR in {f}: {e}")
        return set()
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            # re-exported names (e.g. `from .core import User` inside __init__.py)
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


# ---------- PART 1: duplicate __tablename__ ----------
print("=" * 70)
print("PART 1: DUPLICATE __tablename__ CHECK")
print("=" * 70)

tablename_to_files = defaultdict(list)
for f in py_files:
    try:
        tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for stmt in node.body:
                if isinstance(stmt, ast.Assign):
                    for t in stmt.targets:
                        if isinstance(t, ast.Name) and t.id == "__tablename__":
                            if isinstance(stmt.value, ast.Constant):
                                tablename_to_files[stmt.value.value].append(
                                    f"{f.relative_to(ROOT)} (class {node.name})"
                                )

dupes_found = False
for tbl, locations in tablename_to_files.items():
    if len(locations) > 1:
        dupes_found = True
        print(f"\n❌ DUPLICATE TABLE '{tbl}' defined in {len(locations)} places:")
        for loc in locations:
            print(f"     - {loc}")

if not dupes_found:
    print("\n✅ No duplicate __tablename__ found.")

# ---------- PART 2: broken imports (name not found in source module) ----------
print("\n" + "=" * 70)
print("PART 2: BROKEN 'from X import Y' CHECK (internal project modules only)")
print("=" * 70)

broken = []
for f in py_files:
    try:
        tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module
            if node.level and node.level > 0:
                # relative import — resolve relative to f's package
                pkg_parts = list(f.relative_to(ROOT).parent.parts)
                pkg_parts = pkg_parts[: len(pkg_parts) - (node.level - 1)] if node.level > 1 else pkg_parts
                mod = ".".join(pkg_parts + (mod.split(".") if mod else []))
            if not (mod.startswith("app") or mod.startswith(tuple(SCAN_DIRS))):
                continue  # skip third-party imports (fastapi, sqlalchemy, etc.)
            target_file = file_for_module(mod)
            if target_file is None:
                broken.append((str(f.relative_to(ROOT)), mod, "MODULE NOT FOUND", None))
                continue
            defined = top_level_names(target_file)
            for alias in node.names:
                if alias.name != "*" and alias.name not in defined:
                    broken.append((str(f.relative_to(ROOT)), mod, alias.name, str(target_file.relative_to(ROOT))))

if broken:
    for src, mod, name, target in broken:
        if target:
            print(f"\n❌ {src}\n     imports '{name}' from '{mod}'\n     -> not found in {target}")
        else:
            print(f"\n❌ {src}\n     imports from '{mod}' -> {name}")
else:
    print("\n✅ No broken internal imports found.")

print("\n" + "=" * 70)
print(f"DONE. {len(tablename_to_files)} tables scanned, {len(py_files)} files scanned, "
      f"{sum(1 for v in tablename_to_files.values() if len(v)>1)} duplicate tables, "
      f"{len(broken)} broken imports.")
print("=" * 70)