"""
ORCA — NEW: route_optimizer/optimizer.py (R9 — route optimization / safe
navigation). No WaveSafe file does this; built from first principles.

Algorithm: A* search over a uniform lat/lng grid. Each grid cell is a node;
edges connect a cell to its 8 neighbors (standard grid connectivity). Edge
cost combines:
  1. Great-circle distance between cell centers (haversine) — the "it costs
     fuel/time to move" term, always present and always positive.
  2. A risk penalty from route_optimizer.risk_window.compute_cell_risk for
     the destination cell over the requested time window — makes A*
     prefer safer water, not just shorter water.
  3. A hard geofence penalty (effectively infinite) for any edge whose
     destination cell falls inside a no_entry MPA — A* will never route
     through it; it is not merely discouraged.

Heuristic: haversine distance from a cell to the goal, converted to the
same cost units as g(n) via a MIN_COST_PER_METER constant equal to the
lowest possible per-meter cost (distance term alone, risk=0). This keeps
the heuristic admissible (it never overestimates the true remaining cost,
since risk/geofence penalties only ever ADD cost on top of the distance
floor) — an inadmissible heuristic would make A* return a route that LOOKS
optimal but isn't, which is unacceptable for a "is this route safe" claim.
Admissibility is why MIN_COST_PER_METER is a floor, not an average.
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from datetime import datetime

from app.services import geofence_service
from .risk_window import compute_cell_risk

EARTH_RADIUS_M = 6_371_000.0
MIN_COST_PER_METER = 1.0          # cost floor at zero risk — keeps the heuristic admissible, see module docstring
RISK_WEIGHT = 5_000.0             # meters-equivalent cost added per unit of risk_score (0..1) at a cell
NO_ENTRY_PENALTY = float("inf")   # hard exclusion, not a large-but-finite discouragement
NEIGHBOR_OFFSETS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


@dataclass(order=True)
class _PQItem:
    f_score: float
    counter: int = field(compare=True)
    cell: tuple[int, int] = field(compare=False)


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


class RiskGrid:
    """Uniform lat/lng grid over the bounding box spanning origin and
    destination, padded so the search has room to route around hazards
    rather than being boxed in exactly on the straight line."""

    def __init__(self, origin: tuple[float, float], destination: tuple[float, float],
                 cell_size_deg: float = 0.05, padding_deg: float = 0.5):
        lat0, lng0 = origin
        lat1, lng1 = destination
        self.min_lat = min(lat0, lat1) - padding_deg
        self.max_lat = max(lat0, lat1) + padding_deg
        self.min_lng = min(lng0, lng1) - padding_deg
        self.max_lng = max(lng0, lng1) + padding_deg
        self.cell_size = cell_size_deg
        self.rows = max(1, int((self.max_lat - self.min_lat) / cell_size_deg) + 1)
        self.cols = max(1, int((self.max_lng - self.min_lng) / cell_size_deg) + 1)

    def cell_of(self, lat: float, lng: float) -> tuple[int, int]:
        r = int((lat - self.min_lat) / self.cell_size)
        c = int((lng - self.min_lng) / self.cell_size)
        return max(0, min(self.rows - 1, r)), max(0, min(self.cols - 1, c))

    def center_of(self, cell: tuple[int, int]) -> tuple[float, float]:
        r, c = cell
        return (self.min_lat + (r + 0.5) * self.cell_size, self.min_lng + (c + 0.5) * self.cell_size)

    def neighbors(self, cell: tuple[int, int]):
        r, c = cell
        for dr, dc in NEIGHBOR_OFFSETS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < self.rows and 0 <= nc < self.cols:
                yield (nr, nc)


def _edge_cost(db, grid: RiskGrid, from_cell: tuple[int, int], to_cell: tuple[int, int],
               activity_type: str, window_start: datetime, window_end: datetime,
               risk_cache: dict) -> float:
    lat_a, lng_a = grid.center_of(from_cell)
    lat_b, lng_b = grid.center_of(to_cell)
    distance_m = _haversine_m(lat_a, lng_a, lat_b, lng_b)

    if to_cell not in risk_cache:
        geofence = geofence_service.check_point(db, lat_b, lng_b, window_start)
        if geofence["verdict"] == "breach_no_entry":
            risk_cache[to_cell] = None  # sentinel: impassable
        else:
            cell_risk = compute_cell_risk(db, lat_b, lng_b, activity_type, window_start, window_end)
            boundary_penalty = 0.0
            if geofence["verdict"] == "boundary_critical":
                boundary_penalty = RISK_WEIGHT  # as costly as maximum weather risk — a boundary breach is a real hazard, not a formality
            elif geofence["verdict"] == "boundary_warning":
                boundary_penalty = RISK_WEIGHT * 0.3
            risk_cache[to_cell] = cell_risk.max_risk * RISK_WEIGHT + boundary_penalty

    cached = risk_cache[to_cell]
    if cached is None:
        return NO_ENTRY_PENALTY
    return distance_m + cached


def find_safe_route(db, origin: tuple[float, float], destination: tuple[float, float],
                     activity_type: str, window_start: datetime, window_end: datetime,
                     cell_size_deg: float = 0.05) -> dict:
    """
    Standard A* over the risk-weighted grid. Returns {path: [(lat,lng),...],
    total_cost, distance_m, feasible}. path is empty and feasible=False if
    no route avoids all no_entry zones within the search grid's extent.
    """
    grid = RiskGrid(origin, destination, cell_size_deg=cell_size_deg)
    start_cell = grid.cell_of(*origin)
    goal_cell = grid.cell_of(*destination)

    def heuristic(cell: tuple[int, int]) -> float:
        lat_c, lng_c = grid.center_of(cell)
        lat_g, lng_g = grid.center_of(goal_cell)
        return _haversine_m(lat_c, lng_c, lat_g, lng_g) * MIN_COST_PER_METER

    open_heap: list[_PQItem] = []
    counter = 0
    g_score = {start_cell: 0.0}
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    risk_cache: dict[tuple[int, int], float | None] = {}
    closed: set[tuple[int, int]] = set()

    heapq.heappush(open_heap, _PQItem(heuristic(start_cell), counter, start_cell))

    while open_heap:
        current = heapq.heappop(open_heap).cell
        if current in closed:
            continue
        if current == goal_cell:
            return _reconstruct(grid, came_from, current, g_score[current])
        closed.add(current)

        for neighbor in grid.neighbors(current):
            if neighbor in closed:
                continue
            cost = _edge_cost(db, grid, current, neighbor, activity_type, window_start, window_end, risk_cache)
            if cost == NO_ENTRY_PENALTY:
                continue  # hard-excluded, not merely discouraged (see module docstring)
            tentative_g = g_score[current] + cost
            if tentative_g < g_score.get(neighbor, float("inf")):
                g_score[neighbor] = tentative_g
                came_from[neighbor] = current
                counter += 1
                heapq.heappush(open_heap, _PQItem(tentative_g + heuristic(neighbor), counter, neighbor))

    return {"path": [], "total_cost": None, "distance_m": None, "feasible": False,
            "reason": "no route avoids all no-entry zones within the search grid"}


def _reconstruct(grid: RiskGrid, came_from: dict, current: tuple[int, int], total_cost: float) -> dict:
    path_cells = [current]
    while current in came_from:
        current = came_from[current]
        path_cells.append(current)
    path_cells.reverse()
    path_latlng = [grid.center_of(c) for c in path_cells]

    distance_m = sum(
        _haversine_m(path_latlng[i][0], path_latlng[i][1], path_latlng[i + 1][0], path_latlng[i + 1][1])
        for i in range(len(path_latlng) - 1)
    )
    return {"path": path_latlng, "total_cost": round(total_cost, 1), "distance_m": round(distance_m, 1), "feasible": True}
