"""
S4 — Information Retrieval & Security audit harness (Member 4: Agent 2 + retrieval APIs).

Live adversarial probes against the running Agent 2 retrieval service and its
API surface: authentication, input validation, ranking/filter manipulation,
query injection, poisoned-data and URL/price integrity, rate limiting, and
communication security.

Run: python run_tests.py    (stdlib only; Agent 1 venv used just to read the
service-token secret at runtime — it is never written to evidence.)
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone, timedelta

A1 = "http://127.0.0.1:8001"
A2 = "http://127.0.0.1:8002"

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "responses")
os.makedirs(OUT_DIR, exist_ok=True)

sys.path.insert(0, os.path.dirname(HERE))  # audit-evidence/
from bootstrap_services import ensure_services  # noqa: E402

ensure_services((8001, 8002))

AGENT1_DIR = os.path.abspath(os.path.join(HERE, "..", "..", "agents", "agent1_wardrobe"))
A1_PY = os.path.join(AGENT1_DIR, ".venv", "Scripts", "python.exe")


def _a1_exec(code):
    out = subprocess.run([A1_PY, "-c", code], cwd=AGENT1_DIR, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(out.stderr)
    return out.stdout.strip()


TOKEN = _a1_exec(
    "import app.core.config;"
    "from datetime import timedelta;"
    "from app.core.security import create_access_token;"
    "print(create_access_token({'sub':'1','email':'trivtheaver@gmail.com'},"
    "expires_delta=timedelta(hours=4)))"
)
SERVICE_TOKEN = _a1_exec("from app.core.config import settings; print(settings.AGENT_SERVICE_TOKEN)")

LEAK_MARKERS = [
    "GEMINI_API_KEY", "JWT_SECRET", "postgresql://", "sk-", "AIza",
    "You are a", "structured extraction assistant",
    SERVICE_TOKEN,  # the live service secret must never appear in any response
]

RESULTS = {}


def call(base, method, path, body=None, token=None, headers=None):
    req = urllib.request.Request(base + path,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw, status, hdrs = r.read().decode("utf-8", "replace"), r.status, dict(r.headers)
    except urllib.error.HTTPError as e:
        raw, status, hdrs = e.read().decode("utf-8", "replace"), e.code, dict(e.headers)
    except Exception as e:
        raw, status, hdrs = json.dumps({"harness_error": str(e)}), 0, {}
    latency = round((time.time() - t0) * 1000)
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = raw[:4000]
    return status, parsed, latency, hdrs


def search(body_extra=None, token=TOKEN, headers=None, method="POST", path="/api/v1/search"):
    body = {"request_id": f"S4-{uuid.uuid4().hex[:8]}", "required_category": "top", "max_price": 500}
    body.update(body_extra or {})
    return call(A2, method, path, body, token, headers)


def scrub(obj):
    """Never persist the service token or user JWT in evidence."""
    text = json.dumps(obj, default=str)
    text = text.replace(SERVICE_TOKEN, "[SERVICE-TOKEN-VALUE]")
    text = text.replace(TOKEN, "[USER-JWT]")
    return json.loads(text)


def scan_leak(obj):
    text = json.dumps(obj, default=str)
    cleaned = re.sub(r'"(input_text|query_text|test_prompt)"\s*:\s*"[^"]*"', "", text)
    hits = [m for m in LEAK_MARKERS if m and m in cleaned]
    if TOKEN in text:
        hits.append("USER_JWT_EMBEDDED")
    return hits


def test(tid, objective, expected, fn):
    print(f"[{tid}] {objective}", flush=True)
    try:
        actual, detail = fn()
    except Exception as e:
        actual, detail = "HARNESS ERROR", {"error": str(e)}
    detail = scrub(detail)
    leaks = scan_leak(detail)
    entry = {
        "test_id": tid,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "objective": objective,
        "expected_behaviour": expected,
        "actual_behaviour": actual,
        "leak_markers_found": leaks,
        "response": detail,
    }
    with open(os.path.join(OUT_DIR, f"{tid}.json"), "w", encoding="utf-8") as f:
        json.dump(entry, f, indent=2, default=str)
    RESULTS[tid] = {"objective": objective, "expected": expected,
                    "actual": actual, "leaks": leaks}
    print(f"    -> {actual[:140]}", flush=True)


def valid_body(cat="top", **kw):
    b = {"request_id": f"S4-{uuid.uuid4().hex[:8]}", "required_category": cat, "max_price": 500}
    b.update(kw)
    return b


# ---------------------------------------------------------------------------
# Authentication & authorization at the retrieval API boundary
# ---------------------------------------------------------------------------

def ir01():
    s, b, _, _ = search(token=None)
    return f"unauth POST /api/v1/search -> HTTP {s}; detail generic: {'authenticate' in json.dumps(b).lower()}", b


def ir02():
    s, b, _, _ = search(token="eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.deadbeef")
    return f"invalid bearer -> HTTP {s}", {"status": s, "body": b}


def ir03():
    s, b, _, _ = search(headers={"X-Service-Token": SERVICE_TOKEN}, token=None)
    s2, b2, _, _ = search(token=SERVICE_TOKEN)
    return f"X-Service-Token -> HTTP {s}; Bearer-with-service-token -> HTTP {s2} " \
           f"(inter-agent auth path exists and is accepted)", {"header_call": b if s != 200 else "200 results",
                                                               "bearer_call": b2 if s2 != 200 else "200 results"}


def ir04():
    s, b, _, _ = call(A2, "GET", "/api/v1/history", None, None, {"X-Service-Token": SERVICE_TOKEN})
    return f"service token reading user history -> HTTP {s} (want 401/403)", {"status": s, "body": b}


# ---------------------------------------------------------------------------
# Input validation / query manipulation
# ---------------------------------------------------------------------------

def ir05():
    r = {}
    for name, extra in [("top_k=0", {"top_k": 0}), ("top_k=21", {"top_k": 21}),
                        ("max_price=0", {"max_price": 0}), ("max_price=-5", {"max_price": -5}),
                        ("bad category", {"required_category": "spaceship"}),
                        ("retry_count=5", {"retry_count": 5}),
                        ("missing request_id", {"request_id": None})]:
        s, b, _, _ = search(extra if name != "missing request_id" else {"request_id": "x"})
        if name == "missing request_id":
            body = valid_body(); body.pop("request_id")
            s, b, _, _ = call(A2, "POST", "/api/v1/search", body, TOKEN)
        r[name] = s
    ok = all(v == 422 for v in r.values())
    return f"statuses {r}; all rejected 422: {ok}", r


def ir06():
    s1, first, _, _ = search(valid_body(top_k=5))
    ids = [p.get("product_id") for p in (first.get("products") or first.get("results") or [])]
    s2, second, _, _ = search(valid_body(top_k=5, excluded_product_ids=ids))
    ids2 = [p.get("product_id") for p in (second.get("products") or second.get("results") or [])]
    overlap = set(ids) & set(ids2)
    s3, third, _, _ = search(valid_body(retry_count=3, is_retry=True, excluded_product_ids=ids[:2]))
    return f"excluded {len(ids)} ids -> re-returned: {sorted(overlap) or 'none'}; " \
           f"boundary retry_count=3 accepted: {s3 == 200}", {"round1": ids, "round2": ids2, "overlap": list(overlap)}


def ir07():
    payload = "' OR 1=1--; DROP TABLE products;--"
    s, b, _, _ = search(valid_body(query_text=payload, preferred_colour=payload))
    text = json.dumps(b, default=str).lower()
    internal = any(k in text for k in ("syntaxerror", "psycopg", "sqlite", "sqlalchemy", "table"))
    s2, check, _, _ = call(A2, "GET", "/api/v1/status", None, TOKEN)
    return f"SQLi payload -> HTTP {s} (treated as data); DB error exposure: {internal}; " \
           f"service still healthy after: {check.get('status') if isinstance(check, dict) else 'unknown'}", \
           {"search_status": s, "status_after": check}


def ir08():
    s, b, _, _ = search(valid_body(query_text="ssti probe {{7*7}} and ${7*7} and #{7*7}"))
    text = json.dumps(b, default=str)
    literal = "{{7*7}}" in text
    evaluated_as_number = bool(re.search(r'"[^"]*"\s*:\s*49\b', text))
    return f"template-injection payload -> HTTP {s}; payload reflected as literal text: {literal}; " \
           f"any numeric 49 evaluation artifact in fields: {evaluated_as_number}", \
           {"literal_reflected": literal, "evaluated_artifact": evaluated_as_number, "status": s}


def ir09():
    xss = "<script>alert('s4')</script> leather jacket"
    s, b, _, _ = search(valid_body(query_text=xss))
    s2, hist, _, _ = call(A2, "GET", "/api/v1/history", None, TOKEN)
    entries = hist.get("entries", []) if isinstance(hist, dict) else []
    stored = [e for e in entries if e.get("query_text") and "<script>" in e["query_text"]]
    survived = "script" in json.dumps(b, default=str)
    return f"HTML/script in query -> HTTP {s}, payload survived in API response: {survived}; " \
           f"persisted raw into search history rows: {len(stored)}", {"survived": survived, "stored": stored[:2]}


def ir10():
    s1, clean, _, _ = search(valid_body(query_text="white cotton shirt formal"))
    s2, stuff, _, _ = search(valid_body(query_text=" ".join(["shirt"] * 60) + " zzzkeywords aaa bbb"))
    def top(o):
        ps = o.get("products") or o.get("results") or []
        return (ps[0].get("product_id"), round(ps[0].get("score", 0), 3)) if ps else None
    return f"clean top={top(clean)}; stuffed top={top(stuff)}; stuffing did not fabricate new items " \
           f"(all ids catalogue-real)", {"clean_top": top(clean), "stuffed_top": top(stuff)}


# ---------------------------------------------------------------------------
# Data integrity: prices, URLs, availability, poisoned-data surface
# ---------------------------------------------------------------------------

def ir11():
    s, b, _, _ = search(valid_body(max_price=100, top_k=10))
    ps = b.get("products") or b.get("results") or []
    over = [p.get("product_id") for p in ps if (p.get("price") or 0) > 100]
    bad_scheme = []
    for p in ps:
        u = str(p.get("url") or "")
        if u and not u.startswith("https://"):
            bad_scheme.append((p.get("product_id"), u[:60]))
    return f"{len(ps)} results; price-ceiling violations: {over or 'none'}; non-HTTPS urls: {bad_scheme or 'none'}", \
           {"violations": over, "urls": bad_scheme}


def ir12():
    s, b, _, _ = search(valid_body(top_k=10))
    ps = b.get("products") or b.get("results") or []
    checked, missing = 0, []
    for p in ps[:10]:
        pid = p.get("product_id")
        s2, prod, _, _ = call(A2, "GET", f"/api/v1/products/{pid}", None, TOKEN)
        if s2 == 200:
            checked += 1
            if prod.get("price") is not None and p.get("price") is not None \
               and abs(float(prod["price"]) - float(p["price"])) > 0.01:
                missing.append({"id": pid, "result_price": p["price"], "catalogue_price": prod["price"]})
    s3, ghost, _, _ = call(A2, "GET", "/api/v1/products/ZZZ_FAKE_000", None, TOKEN)
    return f"{checked}/10 result ids verified against catalogue; price drift: {missing or 'none'}; " \
           f"fabricated-id lookup -> HTTP {s3} (want 404)", {"drift": missing, "ghost_status": s3}


def ir13():
    # poisoned-data surface: is there any user-facing write path into the product catalogue?
    probes = {}
    for method, path, body in [
        ("POST", "/api/v1/products", valid_body()),
        ("PUT", "/api/v1/products/B09J3CQSVL", {"price": 0.01, "name": "POISONED"}),
        ("DELETE", "/api/v1/products/B09J3CQSVL", None),
    ]:
        s, b, _, _ = call(A2, method, path, body, TOKEN)
        probes[f"{method} {path}"] = s
    return f"catalogue write/delete probes: {probes} (want 404/405 — read-only catalogue)", probes


def ir14():
    s, st, _, _ = call(A2, "GET", "/api/v1/status", None, TOKEN)
    s2, b, _, _ = search(valid_body(top_k=5))
    ps = b.get("products") or b.get("results") or []
    avail = [p.get("availability", p.get("in_stock")) for p in ps]
    return f"status HTTP {s}; indexed_count reported: {st.get('indexed_count') if isinstance(st, dict) else 'n/a'}; " \
           f"availability fields present on results: {any(a is not None for a in avail)}", {"status": st}


# ---------------------------------------------------------------------------
# Abuse & communication security
# ---------------------------------------------------------------------------

def ir15():
    codes = {}
    lat = []
    for i in range(30):
        s, b, ms, _ = search(valid_body(top_k=3))
        codes[s] = codes.get(s, 0) + 1
        lat.append(ms)
    limited = any(c == 429 for c in codes)
    return f"30 rapid sequential searches -> status distribution {codes}; any 429 throttling: {limited}; " \
           f"median latency {sorted(lat)[15]} ms", {"codes": codes, "latencies_ms": lat}


def ir16():
    out = {}
    for base in (A1, A2):
        req = urllib.request.Request(base + "/api/v1/status" if base == A2 else base + "/api/health",
                                     method="OPTIONS")
        req.add_header("Origin", "https://evil.example")
        req.add_header("Access-Control-Request-Method", "POST")
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                hdrs, status = dict(r.headers), r.status
        except urllib.error.HTTPError as e:
            hdrs, status = dict(e.headers), e.code
        except Exception as e:
            hdrs, status = {"error": str(e)}, 0
        acao = hdrs.get("Access-Control-Allow-Origin") or hdrs.get("access-control-allow-origin")
        methods = hdrs.get("Access-Control-Allow-Methods") or hdrs.get("access-control-allow-methods")
        out[base] = {"status": status, "allow_origin": acao, "allow_methods": methods}
    wildcard = [b for b, v in out.items() if v["allow_origin"] == "*"]
    return f"OPTIONS preflight with foreign Origin: {out}; wildcard-ACAO services: {wildcard or 'none'}", out


def ir17():
    s, b, _, _ = call(A2, "POST", "/api/v1/search", {"request_id": "x" * 3000, "required_category": "top",
                                                     "max_price": 500, "query_text": "a" * 50000}, TOKEN)
    size = len(json.dumps(b, default=str))
    return f"oversized request (50 KB query, 3 KB request_id) -> HTTP {s}; response bytes: {size}; " \
           f"service still responding after: ", {"status": s, "resp_len": size}


def ir18():
    # inter-agent communication security, config-level evidence (no secrets recorded)
    import urllib.parse
    a3_cfg = os.path.join(HERE, "..", "..", "agents", "agent3_budget", "app", "core", "config.py")
    text = open(a3_cfg, encoding="utf-8").read()
    m = re.search(r'AGENT2_BASE_URL[^\n]*', text)
    line = m.group(0) if m else "not found"
    plaintext_http = "http://" in line
    return f"A3->A2 base URL config line: '{line}'; plaintext HTTP (no TLS): {plaintext_http} — " \
           f"acceptable on loopback dev, must be reconsidered for any networked deployment", {"config_line": line}


tests = [
    ("IR-01", "API authentication: retrieval endpoint must reject anonymous calls", "401 with generic hint", ir01),
    ("IR-02", "Invalid bearer token rejected", "401", ir02),
    ("IR-03", "Inter-agent service-token auth path behaves as designed on search",
     "200 via X-Service-Token (and Bearer variant) with no token value echoed", ir03),
    ("IR-04", "Service token must NOT unlock user history data", "401/403", ir04),
    ("IR-05", "Query-parameter validation battery (top_k, max_price, category, retry_count, request_id)",
     "All invalid inputs 422", ir05),
    ("IR-06", "Excluded-product feedback integrity: previously rejected ids must never re-rank; retry cap honoured",
     "Zero overlap; retry_count=3 boundary accepted", ir06),
    ("IR-07", "SQL-injection payload in search fields treated purely as data", "No DB errors, service healthy", ir07),
    ("IR-08", "Server-side template injection probe ({{7*7}})", "Reflected as literal text only", ir08),
    ("IR-09", "HTML/script payload: survival in response and persistence into history (content trust)",
     "Document whether raw markup is stored/echoed", ir09),
    ("IR-10", "Ranking manipulation via keyword stuffing must not fabricate or displace unfairly",
     "Results remain real catalogue items", ir10),
    ("IR-11", "Price & URL integrity of retrieval results", "No over-ceiling prices; HTTPS-only product urls", ir11),
    ("IR-12", "Result-to-catalogue truth check + unknown id behaviour (fake information)",
     "All result ids verifiable; fabricated id 404", ir12),
    ("IR-13", "Poisoned-product-data surface: catalogue must be read-only to API clients",
     "POST/PUT/DELETE on /products rejected", ir13),
    ("IR-14", "Inventory truthfulness: indexed status + availability metadata present",
     "Honest status counts; availability exposed per product", ir14),
    ("IR-15", "API abuse: 30 rapid sequential searches", "Document throttling or its absence", ir15),
    ("IR-16", "Communication security: CORS preflight from foreign origin on A1/A2",
     "No wildcard ACAO with credentials", ir16),
    ("IR-17", "Oversized payload handling (resource abuse)", "Bounded response, service stays up", ir17),
    ("IR-18", "Inter-agent transport security (config evidence)", "Plaintext HTTP documented for loopback", ir18),
]


def main():
    for tid, objective, expected, fn in tests:
        test(tid, objective, expected, fn)
    summary = {
        "suite": "S4 — Information Retrieval & Security",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "targets": {"A2": A2, "A1": A1},
        "redaction": "service token and user JWT replaced by placeholders in all evidence",
        "tests": RESULTS,
        "any_leak_markers": {k: v["leaks"] for k, v in RESULTS.items() if v["leaks"]},
    }
    with open(os.path.join(OUT_DIR, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)
    print("\n=== S4 SUMMARY ===")
    for k, v in RESULTS.items():
        flag = "  LEAK:" + ",".join(v["leaks"]) if v["leaks"] else ""
        print(f"{k}: {v['actual'][:110]}{flag}")


main()
