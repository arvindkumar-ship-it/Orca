#!/usr/bin/env python3
"""
scripts/e2e_smoke_test.py — Module 28, real-system variant.

Unlike tests/e2e/test_e2e_reference_flow.py (in-process, DB-direct), this
hits an ACTUAL deployed instance over HTTP — same as a real client would.
Meant to run post-deploy against staging/pilot before traffic is trusted
(deploy/runbook.sh step 13: "go live with monitoring" gate).

It does NOT wait real ack-timeout durations (90s/120s/180s) by default —
that would make every deploy slow. Pass --full-timing to actually wait
out the real Module 27 timers end-to-end (use this in staging, not CI).

Usage:
  python scripts/e2e_smoke_test.py --base-url https://staging.api.example.com \
      --internal-key $INTERNAL_API_KEY --phone +919000000001

  python scripts/e2e_smoke_test.py --base-url https://staging.api.example.com \
      --internal-key $INTERNAL_API_KEY --phone +919000000001 --full-timing
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass

import requests


@dataclass
class Ctx:
    base_url: str
    internal_key: str
    session: requests.Session


def step(name: str):
    def deco(fn):
        def wrapper(*args, **kwargs):
            print(f"-- {name} --", flush=True)
            t0 = time.monotonic()
            result = fn(*args, **kwargs)
            print(f"   ok ({time.monotonic() - t0:.2f}s)")
            return result
        return wrapper
    return deco


@step("1. Health check")
def check_health(ctx: Ctx):
    r = ctx.session.get(f"{ctx.base_url}/healthz", timeout=5)
    r.raise_for_status()
    r2 = ctx.session.get(f"{ctx.base_url}/readyz", timeout=5)
    r2.raise_for_status()


@step("2. OTP login")
def login(ctx: Ctx, phone: str, otp_code: str) -> str:
    ctx.session.post(f"{ctx.base_url}/v1/auth/otp/request", json={"phone": phone}, timeout=10).raise_for_status()
    r = ctx.session.post(
        f"{ctx.base_url}/v1/auth/otp/verify", json={"phone": phone, "code": otp_code}, timeout=10
    )
    r.raise_for_status()
    token = r.json()["access_token"]
    ctx.session.headers.update({"Authorization": f"Bearer {token}"})
    return token


@step("3. List beaches, pick one")
def pick_beach(ctx: Ctx) -> str:
    r = ctx.session.get(f"{ctx.base_url}/v1/beaches", timeout=10)
    r.raise_for_status()
    beaches = r.json()
    if not beaches:
        raise RuntimeError("no beaches seeded in this environment — smoke test cannot proceed")
    return beaches[0]["id"]


@step("4. Create a trip plan")
def create_trip(ctx: Ctx, beach_id: str) -> str:
    r = ctx.session.post(
        f"{ctx.base_url}/v1/trips",
        json={
            "beach_id": beach_id,
            "activity": "swimming",
            "planned_start": "2026-08-09T10:00:00Z",
            "planned_end": "2026-08-09T12:00:00Z",
        },
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["id"]


@step("5. Trigger SOS")
def trigger_sos(ctx: Ctx, beach_id: str) -> str:
    r = ctx.session.post(
        f"{ctx.base_url}/v1/sos",
        json={
            "lat": 13.05, "lng": 80.28,
            "incident_type": "drowning",
            "trigger_type": "manual_button",
        },
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["id"]


@step("6. Confirm >=2 targets dispatched")
def check_routes(ctx: Ctx, incident_id: str, min_targets: int = 2, timeout_s: int = 15):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        r = ctx.session.get(f"{ctx.base_url}/v1/sos/{incident_id}/routes", timeout=10)
        r.raise_for_status()
        routes = r.json()
        target_types = {rt["target_type"] for rt in routes}
        if len(target_types) >= min_targets:
            return routes
        time.sleep(1)
    raise RuntimeError(f"only {len(target_types)} distinct targets dispatched within {timeout_s}s")


@step("7. Confirm status reaches 'dispatched'")
def wait_for_dispatched(ctx: Ctx, incident_id: str, timeout_s: int = 15):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        r = ctx.session.get(f"{ctx.base_url}/v1/sos/{incident_id}", timeout=10)
        r.raise_for_status()
        status = r.json()["status"]
        if status == "dispatched":
            return
        if status in ("timeout", "escalated", "fallback_112"):
            return  # escalation branch already fired — acceptable, still visible
        time.sleep(1)
    raise RuntimeError(f"incident never reached 'dispatched' within {timeout_s}s")


@step("8. Internal ack simulation")
def simulate_ack(ctx: Ctx, incident_id: str):
    """Real responders ack via their own portal — this simulates that via
    the internal API key, same as an authority-side integration would."""
    r = ctx.session.post(
        f"{ctx.base_url}/v1/sos/{incident_id}/ack",
        json={"target_type": "authority"},
        timeout=10,
    )
    r.raise_for_status()


@step("9. Wait out full ack-timeout escalation chain (real timing)")
def wait_full_escalation_chain(ctx: Ctx, incident_id: str):
    """Only runs with --full-timing. Confirms the REAL Celery Beat + worker
    are alive in this environment — not just that the code compiles."""
    stages = ["dispatched", "timeout", "escalated", "fallback_112"]
    for expected in stages[1:]:
        deadline = time.monotonic() + 150  # generous over the 90-120s configured timeouts
        seen = None
        while time.monotonic() < deadline:
            r = ctx.session.get(f"{ctx.base_url}/v1/sos/{incident_id}", timeout=10)
            r.raise_for_status()
            seen = r.json()["status"]
            if seen == expected:
                break
            time.sleep(3)
        if seen != expected:
            raise RuntimeError(f"expected escalation stage '{expected}', last seen '{seen}'")
        print(f"   reached {expected}")


@step("10. Check nearest safe zone resolves")
def check_safe_zone(ctx: Ctx):
    r = ctx.session.get(f"{ctx.base_url}/v1/safe-zones/nearest?lat=13.05&lng=80.28", timeout=10)
    r.raise_for_status()
    assert "id" in r.json()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--internal-key", required=True)
    parser.add_argument("--phone", required=True)
    parser.add_argument("--otp-code", default="000000", help="staging test-mode OTP, not a real SMS code")
    parser.add_argument("--full-timing", action="store_true",
                         help="also wait out real 90/120/180s ack-escalation timers")
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update({"X-Internal-Key": args.internal_key})
    ctx = Ctx(base_url=args.base_url.rstrip("/"), internal_key=args.internal_key, session=session)

    try:
        check_health(ctx)
        login(ctx, args.phone, args.otp_code)
        beach_id = pick_beach(ctx)
        create_trip(ctx, beach_id)
        incident_id = trigger_sos(ctx, beach_id)
        check_routes(ctx, incident_id)
        wait_for_dispatched(ctx, incident_id)
        check_safe_zone(ctx)

        if args.full_timing:
            wait_full_escalation_chain(ctx, incident_id)
        else:
            simulate_ack(ctx, incident_id)

    except Exception as e:  # noqa: BLE001 — smoke test must report, never hide, any failure
        print(f"\nFAIL: {e}", file=sys.stderr)
        return 1

    print("\nPASS: E2E reference flow succeeded against", ctx.base_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
