from app.scoring.engine import DEFAULT_WEIGHTS, compose, confidence_shape


def test_compose_pure_math():
    dims = {"likelihood": 0.8, "expected_scale": 0.6, "timing_fit": 0.5,
            "confidence": 0.7, "sector_relevance": 0.5, "strategic_relevance": 0.5}
    w = DEFAULT_WEIGHTS["origination"]
    b = compose(dims, w, confidence=0.7)
    # Recompute manually to pin the contract
    norm = sum(w.values())
    expected = sum(dims[k] * (w[k] / norm) for k in dims) * confidence_shape(0.7)
    assert abs(b.score - round(expected, 4)) < 1e-6
    assert b.confidence == 0.7


def test_confidence_shape_dampens_but_not_zero():
    assert confidence_shape(0.0) == 0.5
    assert confidence_shape(1.0) == 1.0
    assert 0.5 < confidence_shape(0.5) < 1.0


def test_default_weights_sum_close_to_one():
    for module, w in DEFAULT_WEIGHTS.items():
        assert abs(sum(w.values()) - 1.0) < 1e-9, module
