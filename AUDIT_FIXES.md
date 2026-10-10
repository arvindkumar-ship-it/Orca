# Risk-score evidence boundaries

Repair branch: `fix/internship-audit-20261010`. Changes are scoped to audit findings; no deployment or live provider action is included.

## Changed

Shared risk explanations return JSON-safe values for hard overrides and explicitly label heuristic/operational-validation status.

## Verification

`pytest -q tests/test_risk_contract.py`

Commands are entry points, not a claim that every live integration was executed. See the repair bundle for actual results.

## Setup and remaining evidence

This extends the WaveSafe family. Multi-service startup, real ingestion/agent tools, operational rescue outcomes and risk calibration remain open. Team ownership must be described from actual contributions; no individual authorship or deployment evidence was invented.
