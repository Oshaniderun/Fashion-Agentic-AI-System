"""
Feature 5 — decision audit log: what is recorded, and who may read it.
"""

import re

import pytest


def _body(req):
    return req.model_dump(mode="json")


@pytest.fixture
def audit_db(tmp_path, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    path = tmp_path / "audit" / "audit.db"
    monkeypatch.setattr(settings, "AUDIT_DB_PATH", str(path), raising=False)
    monkeypatch.setattr(settings, "AUDIT_ENABLED", True, raising=False)
    return path


def _decide(client, headers, req):
    return client.post("/decision/recommend", json=_body(req), headers=headers)


def _request(colour="white"):
    import payloads as P

    prod = P.product("P1", category="top", price=45.0, colour=colour,
                     name="White silk blouse")
    return P.decision_request(
        options=[P.option("OPT-A", products=[P.candidate(prod)])],
        a1=P.agent1_output(required=["top"], missing=["top"], colour_prefs=[colour]),
        products_by_category={"top": [prod]},
    )


def test_decision_id_is_returned_and_deterministic(client, auth_headers, audit_db):
    first = _decide(client, auth_headers, _request()).json()
    second = _decide(client, auth_headers, _request()).json()
    assert re.fullmatch(r"dec_[0-9a-f]{16}", first["decision_id"])
    assert first["decision_id"] == second["decision_id"]


def test_audit_entry_holds_ids_scores_and_hashes_only(client, auth_headers, audit_db):
    body = _decide(client, auth_headers, _request()).json()
    r = client.get(f"/audit/{body['decision_id']}", headers=auth_headers)
    assert r.status_code == 200, r.text
    entry = r.json()

    assert entry["candidate_ids"] == ["OPT-A"]
    assert entry["chosen_combination_id"] == "OPT-A"
    assert entry["decision_status"] == "complete"
    assert entry["reject_reason_codes"] == []
    assert entry["confidence_score"] == body["decision"]["confidence_score"]
    assert entry["confidence_level"] == "high"
    assert entry["explanation_source"] == "template"
    assert entry["explanation_verified"] is True
    assert entry["reoptimization_round"] == 0
    assert entry["weights_version"]
    assert re.fullmatch(r"[0-9a-f]{64}", entry["input_sha256"])
    breakdown = entry["score_breakdowns"][0]
    assert set(breakdown["sub_scores"]) == {
        "colour_harmony", "formality_match", "occasion_fit", "budget_fit",
        "constraint_satisfaction",
    }


def test_raw_request_content_is_never_written_to_disk(client, auth_headers, audit_db):
    _decide(client, auth_headers, _request()).json()
    stored = audit_db.read_bytes()
    for secret in (b"White silk blouse", b"Test Retailer", b"smart_casual", b"silk"):
        assert secret not in stored


def test_rejected_decision_records_reason_codes(client, auth_headers, audit_db):
    import payloads as P

    over = P.product("P-OVER", category="top", price=300.0, name="Costly jacket")
    req = P.decision_request(
        options=[P.option("OPT-OVER", products=[P.candidate(over)], within_budget=False)],
        products_by_category={"top": [over]},
    )
    body = _decide(client, auth_headers, req).json()
    entry = client.get(f"/audit/{body['decision_id']}", headers=auth_headers).json()
    assert entry["chosen_combination_id"] is None
    assert entry["decision_status"] == "no_suitable_outfit"
    assert "OVER_BUDGET" in entry["reject_reason_codes"]


def test_audit_list_is_paginated_newest_first(client, auth_headers, audit_db):
    ids = []
    for colour in ("white", "ivory"):
        body = _decide(client, auth_headers, _request(colour=colour)).json()
        ids.append(body["decision_id"])
    assert len(set(ids)) == 2

    page = client.get("/audit?page=1&page_size=1", headers=auth_headers).json()
    assert page["total"] == 2
    assert page["page_size"] == 1
    assert len(page["items"]) == 1
    assert page["items"][0]["decision_id"] == ids[-1]

    second = client.get("/audit?page=2&page_size=1", headers=auth_headers).json()
    assert second["items"][0]["decision_id"] == ids[0]


def test_audit_endpoints_require_the_service_token(client, user_headers, audit_db):
    assert client.get("/audit", headers=user_headers).status_code == 403
    assert client.get("/audit/dec_0000000000000000", headers=user_headers).status_code == 403
    assert client.get("/audit").status_code == 401


def test_unknown_decision_id_is_not_found(client, auth_headers, audit_db):
    assert client.get("/audit/dec_0000000000000000", headers=auth_headers).status_code == 404


def test_malformed_decision_id_is_rejected_without_a_trace(client, auth_headers, audit_db):
    for path in ("/audit/not-an-id", "/audit/dec_%2e%2e%2f%2e%2e", "/audit/../../etc/passwd"):
        r = client.get(path, headers=auth_headers)
        assert r.status_code in (404, 422), path
        assert "Traceback" not in r.text and "sqlite" not in r.text.lower()


def test_oversized_page_size_is_rejected(client, auth_headers, audit_db):
    from app.core.config import get_settings

    too_big = get_settings().AUDIT_MAX_PAGE_SIZE + 1
    assert client.get(f"/audit?page_size={too_big}", headers=auth_headers).status_code == 422


def test_disabling_the_audit_log_leaves_the_decision_intact(client, auth_headers, audit_db, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "AUDIT_ENABLED", False, raising=False)
    body = _decide(client, auth_headers, _request()).json()
    assert body["decision"]["status"] == "complete"
    assert body["decision_id"] is None
    assert not audit_db.exists()


def test_audit_failure_never_breaks_the_decision(client, auth_headers, audit_db, monkeypatch):
    import sqlite3

    from app.services import audit_service

    def boom():
        raise sqlite3.Error("disk full")

    monkeypatch.setattr(audit_service, "_connect", boom)
    r = _decide(client, auth_headers, _request())
    assert r.status_code == 200
    body = r.json()
    assert body["decision"]["status"] == "complete"
    assert body["decision_id"] is None
