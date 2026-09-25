"""HTTP API tests: optimize / reoptimize / evaluate-cost / compare / health."""

from shared.schemas.agent3_schemas import CandidateProductItem


def _cand(pid, cat, price, rel=0.8):
    return CandidateProductItem(
        product_id=pid, name=f"{pid}", category=cat, colour="black",
        price=price, store="Amazon", url=f"https://www.amazon.com/dp/{pid}",
        relevance_score=rel, availability=True,
    ).model_dump(mode="json")


def test_health(client):
    r = client.get("/budget/health")
    assert r.status_code == 200
    body = r.json()
    assert body["currency"] == "USD"
    assert body["db"] in ("postgres", "sqlite")


def test_root_and_ops_health(client):
    assert client.get("/").json()["currency"] == "USD"
    assert client.get("/health").status_code == 200


def test_optimize_within_budget(client, auth_headers):
    payload = {
        "request_id": "REQ-1",
        "budget": 100.0,
        "missing_categories": ["bottom"],
        "candidate_products_by_category": {"bottom": [_cand("P1", "bottom", 40.0, 0.9)]},
        "available_wardrobe": [],
    }
    r = client.post("/budget/optimize", json=payload, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "within_budget"
    assert body["budget_ceiling"] == 100.0
    assert body["options"]


def test_negative_budget_rejected(client, auth_headers):
    payload = {
        "request_id": "REQ-BAD",
        "budget": -5.0,
        "missing_categories": ["bottom"],
        "candidate_products_by_category": {},
        "available_wardrobe": [],
    }
    assert client.post("/budget/optimize", json=payload, headers=auth_headers).status_code == 422


def test_reoptimize_excludes_rejected(client, auth_headers):
    payload = {
        "request_id": "REQ-RE",
        "budget": 100.0,
        "rejected_combination_ids": ["OPT-BEST-VALUE"],
        "candidate_products_by_category": {"bottom": [_cand("P1", "bottom", 40.0, 0.9)]},
        "available_wardrobe": [],
    }
    r = client.post("/budget/reoptimize", json=payload, headers=auth_headers)
    assert r.status_code == 200
    ids = [o["combination_id"] for o in r.json()["options"]]
    assert "OPT-BEST-VALUE" not in ids


def test_evaluate_cost(client, auth_headers):
    r = client.post(
        "/budget/evaluate-cost",
        json={"budget": 50.0, "product_prices": [20.0, 10.0]},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total_cost"] == 30.0
    assert body["budget_remaining"] == 20.0
    assert body["is_within_budget"] is True


def test_compare_options_pandas_table(client, auth_headers):
    # First produce real options via optimize, then compare them.
    opt_payload = {
        "request_id": "REQ-CMP",
        "budget": 100.0,
        "missing_categories": ["bottom", "footwear"],
        "candidate_products_by_category": {
            "bottom": [_cand("P1", "bottom", 40.0, 0.9), _cand("P2", "bottom", 25.0, 0.6)],
            "footwear": [_cand("F1", "footwear", 30.0, 0.85)],
        },
        "available_wardrobe": [],
    }
    opts = client.post("/budget/optimize", json=opt_payload, headers=auth_headers).json()["options"]
    r = client.post(
        "/budget/compare-options",
        json={"options": opts, "budget": 100.0},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ranked_options"]
    assert "total_cost_usd" in body["ranked_options"][0]
    assert body["ranked_options"][0]["rank"] == 1
    assert "summary_stats" in body and "cheapest_usd" in body["summary_stats"]
