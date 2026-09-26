"""
Requested-type validation (category covered, wrong garment).

Agent 1 records per-item types ("heel"), and Agent 4 must not let a product
merely labelled 'footwear' silently satisfy a heels request — but it also
must not hard-reject on a heuristic, so a mismatch downgrades confidence,
adds a warning, and loses head-to-head ranking to a type-matching option.
"""

import payloads as P


def _body(req):
    return req.model_dump(mode="json")


def _recommend(client, auth_headers, req):
    return client.post("/decision/recommend", json=_body(req), headers=auth_headers).json()


def test_socks_labelled_footwear_flagged_when_heels_requested(client, auth_headers):
    socks = P.product("SO1", category="footwear", name="GOLDTOE Cushioned Crew Socks 6-Pack")
    a1 = P.agent1_output(required=["footwear"], item_types={"footwear": "heel"})
    req = P.decision_request(
        options=[P.option("OPT-SOCKS", products=[P.candidate(socks)])],
        a1=a1,
        products_by_category={"footwear": [socks]},
    )
    body = _recommend(client, auth_headers, req)
    # Honest about the gap: not "high confidence complete" anymore...
    assert body["decision"]["confidence_score"] <= 0.65
    assert body["decision"]["confidence_level"] != "high"
    codes = {i["code"] for i in body["validation_issues"]}
    assert "type_mismatch" in codes
    # ...but still a usable answer, and the note reaches the user text.
    assert body["decision"]["status"] == "complete"
    assert "heel" in body["explanation"]


def test_matching_type_passes_clean(client, auth_headers):
    heels = P.product("HE1", category="footwear", name="White Patent High Heels Pumps")
    a1 = P.agent1_output(required=["footwear"], item_types={"footwear": "heel"})
    req = P.decision_request(
        options=[P.option("OPT-HEELS", products=[P.candidate(heels)])],
        a1=a1,
        products_by_category={"footwear": [heels]},
    )
    body = _recommend(client, auth_headers, req)
    codes = {i["code"] for i in body["validation_issues"]}
    assert "type_mismatch" not in codes
    assert body["decision"]["confidence_level"] == "high"


def test_type_matching_option_outranks_identical_scoring_mismatch(client, auth_headers):
    # Same price, same relevance, same scores — only the garment word differs.
    socks = P.product("SO1", category="footwear", name="Cushioned Crew Socks 6-Pack")
    heels = P.product("HE1", category="footwear", name="White Block Heel Shoes")
    a1 = P.agent1_output(required=["footwear"], item_types={"footwear": "heel"})
    req = P.decision_request(
        options=[
            P.option("OPT-SOCKS", products=[P.candidate(socks)]),
            P.option("OPT-HEELS", products=[P.candidate(heels)]),
        ],
        a1=a1,
        products_by_category={"footwear": [socks, heels]},
    )
    body = _recommend(client, auth_headers, req)
    assert body["selected_combination_id"] == "OPT-HEELS"


def test_wardrobe_substitute_wrong_type_flagged(client, auth_headers):
    loafer = P.wardrobe_item("WF1", category="footwear", type_="loafer", colour="black")
    a1 = P.agent1_output(
        required=["footwear"], item_types={"footwear": "heel"}, wardrobe=[loafer]
    )
    top = P.product("TP1", category="top")
    req = P.decision_request(
        options=[
            P.option(
                "OPT-BUY-NOTHING",
                products=[],
                wardrobe_items=[P.repurposed("WF1", category="footwear", type_="loafer")],
            )
        ],
        a1=a1,
        products_by_category={"top": [top]},
    )
    body = _recommend(client, auth_headers, req)
    codes = {i["code"] for i in body["validation_issues"]}
    assert "type_mismatch" in codes


def test_no_types_extracted_keeps_old_behaviour(client, auth_headers):
    # User only named categories: nothing to type-check against.
    prod = P.product("P1", category="footwear", name="Random Footwear Thing")
    a1 = P.agent1_output(required=["footwear"])
    req = P.decision_request(
        options=[P.option("OPT-1", products=[P.candidate(prod)])],
        a1=a1,
        products_by_category={"footwear": [prod]},
    )
    body = _recommend(client, auth_headers, req)
    codes = {i["code"] for i in body["validation_issues"]}
    assert "type_mismatch" not in codes
    assert body["decision"]["status"] == "complete"
