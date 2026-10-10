import json
from risk_engine.scoring import compute_risk


def test_hard_override_explanation_is_valid_json():
    score, label, explanation = compute_risk({}, {}, ['beach_closure'])
    assert score == 1 and label == 'unsafe'
    payload = explanation.to_dict()
    json.dumps(payload, allow_nan=False)
    assert payload['hard_override'] is True
    assert payload['validated_for_operational_use'] is False


def test_neutral_fixture_is_not_claimed_as_calibrated():
    score, label, explanation = compute_risk({}, {}, [])
    assert score == 0.5 and label == 'caution'
    assert explanation.to_dict()['score_kind'] == 'uncalibrated_heuristic'


def test_coverage_gap_does_not_saturate_with_zero_iqr():
    score, _, explanation = compute_risk({'coverage_gap': 0.5}, {'coverage_gap': (0, 0)}, [])
    assert 0.5 < score < 0.6
    assert explanation.z_scores['coverage_gap'] == 0.5
