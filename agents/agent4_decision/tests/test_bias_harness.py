"""
Feature 5 — the bias harness must run offline in mock mode, report honestly,
and actually be able to detect a difference.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_HARNESS = Path(__file__).resolve().parent / "bias" / "run_bias_harness.py"


@pytest.fixture(scope="module")
def harness():
    spec = importlib.util.spec_from_file_location("agent4_bias_harness", _HARNESS)
    module = importlib.util.module_from_spec(spec)
    # Registered before execution: the harness uses postponed annotations, and
    # dataclasses resolves them through sys.modules[cls.__module__].
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def client_token():
    from app.core.config import get_settings

    return get_settings().AGENT_SERVICE_TOKEN


def test_pairs_cover_every_required_attribute_and_change_one_thing(harness):
    assert len(harness.PAIRS) >= 15
    attributes = " ".join(p.attribute.lower() for p in harness.PAIRS)
    for required in ("gender", "budget", "occasion", "style"):
        assert required in attributes
    covered = {p.expectation for p in harness.PAIRS}
    assert covered == {"neutral", "signal"}
    # each profile is a diff on the same baseline, never a different plan
    for pair in harness.PAIRS:
        assert set(pair.left.kwargs) <= {
            "styles", "occasion", "colour_prefs", "item_types", "stated_budget",
            "requested_types", "ceiling",
        }
        assert set(pair.right.kwargs) <= {
            "styles", "occasion", "colour_prefs", "item_types", "stated_budget",
            "requested_types", "ceiling",
        }


def test_no_neutral_pair_is_flagged_on_the_real_engine(harness, client_token):
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.main import app

    rows = harness.evaluate(
        harness.PAIRS, TestClient(app), client_token, get_settings().BIAS_FLAG_THRESHOLD
    )
    assert len(rows) == len(harness.PAIRS)
    assert [r for r in rows if r["flagged"]] == []
    for row in rows:
        assert row["left"]["choice"] or row["left"]["status"] == "no_suitable_outfit"


def test_the_harness_does_flag_a_real_difference(harness, client_token):
    # Same engine, deliberately different plan, labelled neutral: detection works.
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.main import app

    rigged = harness.Pair(
        99, "Rigged control pair", harness.NEUTRAL,
        harness.Profile({"ceiling": 200.0}),
        harness.Profile({"ceiling": 60.0}),
    )
    rows = harness.evaluate(
        [rigged], TestClient(app), client_token, get_settings().BIAS_FLAG_THRESHOLD
    )
    assert rows[0]["flagged"] is True
    assert rows[0]["diff"]["choice_differs"] is True


def test_report_is_written_with_a_results_table(harness, tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(harness, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(harness, "PAIRS", harness.PAIRS[:3])
    token = get_settings().AGENT_SERVICE_TOKEN

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    rows = harness.evaluate(harness.PAIRS[:3], client, token, get_settings().BIAS_FLAG_THRESHOLD)
    report = harness.render_report(
        rows, get_settings().BIAS_FLAG_THRESHOLD, get_settings().SCORE_WEIGHTS_VERSION, "mock"
    )
    out = tmp_path / "docs" / "responsible_ai" / "agent4_bias_report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")

    text = out.read_text(encoding="utf-8")
    assert text.startswith("# Agent 4 — Decision Bias Harness")
    assert "| 1 | Gender-coded style label | neutral |" in text
    assert "No neutral-coded pair was flagged" in text
    assert "## Limitations" in text
    # the report never quotes request content
    assert "White silk blouse" not in text
