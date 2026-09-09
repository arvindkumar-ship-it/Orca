"""
ORCA — app/main.py

GENERALIZE of WaveSafe's app/main.py. CORS block copied unchanged per the
build spec's constraint. Router wiring:
  - DROPPED: beach.py (-> zones.py), safezone.py (-> safe_harbors.py),
    trips.py (-> route.py; trip_service.py's logic was lifted into
    route_optimizer/, not reused as a router — see reuse matrix Section 3.6).
  - ADDED: zones.py, safe_harbors.py, geofence.py, route.py, chat.py — all
    self-prefix "/v1" in their own APIRouter(...) call (see each file), so
    mounted with NO extra prefix, same convention WaveSafe's beach.py used.
  - UNCHANGED (COPY, still self-prefixed or absolute-path as WaveSafe's own
    main.py documented): incidents, emergency_share, notifications,
    offline_sync, admin(auth_router), audit, internal, internal_dispatch,
    tracking, authority_router, hospital_router, health.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import authority_router, hospital_router, tracking, health
from app.api.v1 import (
    offline_sync, admin, audit, incidents, emergency_share, notifications,
    internal, auth_router as auth_router_module,
    zones, safe_harbors, geofence, route, chat, ocean,
)
from app.api import internal_dispatch

app = FastAPI(title="ORCA — Marine EcoSystem Reasoning with Collaborative Agents")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://orca.onrender.com",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ORCA-specific routers — each self-prefixes "/v1" in its own APIRouter(...)
app.include_router(zones.router)
app.include_router(safe_harbors.router)
app.include_router(geofence.router)
app.include_router(route.router)
app.include_router(chat.router)
app.include_router(ocean.router)

# COPY, unchanged from WaveSafe (see this file's docstring for prefix notes)
app.include_router(incidents.sos_router)
app.include_router(incidents.incidents_router)
app.include_router(emergency_share.router)
app.include_router(notifications.router)
app.include_router(offline_sync.router)
app.include_router(admin.router)
app.include_router(auth_router_module.auth_router)
app.include_router(audit.router)
app.include_router(internal.router)
app.include_router(internal_dispatch.router)
app.include_router(tracking.router, prefix="/v1")
app.include_router(authority_router.router)
app.include_router(hospital_router.router)
app.include_router(health.router)
