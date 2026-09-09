#!/usr/bin/env bash
# deploy/runbook.sh — Module 30 deployment steps, in order.
# Usage: ./runbook.sh <environment>   e.g. ./runbook.sh staging
set -euo pipefail

ENV="${1:?usage: runbook.sh <local|dev|staging|pilot|production>}"
COMPOSE="docker compose -f deploy/docker-compose.yml --env-file .env.${ENV}"

echo "== Deploying environment: ${ENV} =="

echo "-- [1/14] DB migrations --"
$COMPOSE run --rm api alembic upgrade head

echo "-- [2/14] Core APIs --"
$COMPOSE up -d db redis api

echo "-- [3/14] Ingestion workers --"
$COMPOSE up -d worker_ingestion

echo "-- [4/14] Risk engine worker --"
$COMPOSE up -d worker_risk

echo "-- [5/14] Notification workers --"
$COMPOSE up -d worker_notification worker_escalation worker_cleanup beat

echo "-- [6/14] Admin console (served by api + frontend /admin) --"
$COMPOSE up -d frontend

echo "-- [7/14] Mobile app beta --"
echo "   (not applicable — this build targets website, per Module 0/29 scope freeze)"

echo "-- [8/14] Sandbox tests --"
$COMPOSE run --rm api pytest -m "not disaster_sim and not e2e" || { echo "sandbox tests failed"; exit 1; }

echo "-- [8b/14] Module 28: E2E reference flow (in-process) --"
$COMPOSE run --rm api pytest tests/e2e -m e2e || { echo "e2e reference flow failed"; exit 1; }

if [[ "$ENV" != "local" ]]; then
  echo "-- [8c/14] Module 28: E2E smoke test against live ${ENV} --"
  python scripts/e2e_smoke_test.py \
    --base-url "${PUBLIC_API_BASE_URL:?set in .env.${ENV}}" \
    --internal-key "${INTERNAL_API_KEY:?set in .env.${ENV}}" \
    --phone "${SMOKE_TEST_PHONE:?set in .env.${ENV}}" \
    --otp-code "${SMOKE_TEST_OTP:-000000}" \
    || { echo "live e2e smoke test failed"; exit 1; }
fi

echo "-- [9/14] Disaster simulations --"
if [[ "$ENV" != "local" ]]; then
  $COMPOSE run --rm api pytest -m disaster_sim || { echo "disaster simulation failed"; exit 1; }
else
  echo "   (skipped on local)"
fi

echo "-- [10/14] Pilot on one coast/state --"
echo "   Manual gate: confirm PILOT_STATE is set and jurisdictions seeded before proceeding."

echo "-- [11/14] Validate alert latency --"
$COMPOSE exec api python -m app.ops.check_alert_latency --threshold-seconds 60

echo "-- [12/14] Validate SOS routing --"
$COMPOSE exec api python -m app.ops.check_sos_routing --min-targets 2

echo "-- [13/14] Go live with monitoring --"
echo "   Confirm SENTRY_DSN and LOG_LEVEL set in .env.${ENV}, dashboards wired before flipping traffic."

echo "-- [14/14] Rollback readiness --"
echo "   Previous image tags retained by registry; rollback = redeploy prior tag + 'alembic downgrade -1' if migration is reversible."

echo "== Deployment steps complete for ${ENV} =="
