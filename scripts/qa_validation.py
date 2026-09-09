"""Module 1 — QA: geometry validation + duplicate flagging (steps 8-11).
ASSUMPTION: app.db as in Module 2. Run after every data load, not automatically."""
from __future__ import annotations
from sqlalchemy import text
from app.db import get_session   # ASSUMPTION

_TABLES_WITH_GEOM = {
    "beaches": "geom", "safe_zones": "geom", "hospitals": "geom",
    "rescue_posts": "geom", "jurisdictions": "service_area_geom",
}
DUPLICATE_DISTANCE_M = 50


def find_invalid_geometries() -> dict[str, list[dict]]:
    """step 11: geometry validation — must be run and cleared before go-live."""
    results = {}
    with get_session() as session:
        for table, col in _TABLES_WITH_GEOM.items():
            rows = session.execute(text(
                f"SELECT id, name FROM {table} WHERE NOT ST_IsValid({col})"
            )).mappings().all()
            if rows:
                results[table] = [dict(r) for r in rows]
    return results


def find_possible_duplicates(table: str, geom_col: str = "geom") -> list[dict]:
    """step 9: flag near-identical locations for manual review — never auto-merge."""
    if table not in _TABLES_WITH_GEOM:
        raise ValueError(f"unsupported table '{table}'")
    with get_session() as session:
        rows = session.execute(text(f"""
            SELECT a.id AS id_a, a.name AS name_a, b.id AS id_b, b.name AS name_b,
                   ST_Distance(a.{geom_col}::geography, b.{geom_col}::geography) AS dist_m
            FROM {table} a
            JOIN {table} b ON a.id < b.id
            WHERE ST_DWithin(a.{geom_col}::geography, b.{geom_col}::geography, :max_dist)
            ORDER BY dist_m
        """), {"max_dist": DUPLICATE_DISTANCE_M}).mappings().all()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    invalid = find_invalid_geometries()
    if invalid:
        print("INVALID GEOMETRIES FOUND — fix before go-live:")
        for table, rows in invalid.items():
            print(f"  {table}: {rows}")
    else:
        print("all geometries valid.")

    for table in ("beaches", "safe_zones", "hospitals", "rescue_posts"):
        dups = find_possible_duplicates(table)
        if dups:
            print(f"\npossible duplicates in {table} (review manually, do not auto-merge):")
            for d in dups:
                print(f"  {d}")
