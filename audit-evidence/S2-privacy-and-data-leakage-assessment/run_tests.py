"""
S2 — Privacy & Data Leakage audit harness.

Runs live adversarial privacy probes against the FASHORA backend (Agents 1-3)
and dumps timestamped, redacted evidence JSON per test case.

Run with the Agent 1 venv python (needed for JWT minting + DB read):
    ../../agents/agent1_wardrobe/.venv/Scripts/python.exe run_tests.py

No secrets (tokens, passwords, hashes) are ever written to evidence files;
they are referenced as [REDACTED] placeholders.
"""

import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

AGENT1_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "agents", "agent1_wardrobe"))
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, AGENT1_DIR)
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "audit-evidence"))
from bootstrap_services import ensure_services  # noqa: E402

ensure_services((8001, 8002, 8003))

from app.core.config import settings  # noqa: E402  (loads root .env)
from app.core.security import create_access_token  # noqa: E402
from app.models.database import SessionLocal  # noqa: E402

A1 = "http://127.0.0.1:8001"
A2 = "http://127.0.0.1:8002"
A3 = "http://127.0.0.1:8003"

OUT_DIR = os.path.join(os.path.dirname(__file__), "responses")
os.makedirs(OUT_DIR, exist_ok=True)

AUDIT_B_EMAIL = f"audit.b.{int(time.time())}@example.com"
AUDIT_B_PASSWORD = uuid.uuid4().hex  # never stored in evidence

LEAK_MARKERS = [
    "GEMINI_API_KEY", "JWT_SECRET", "AGENT_SERVICE_TOKEN",
    "postgresql://", "sk-", "AIza",
    "You are a", "You are an", "structured extraction assistant",
    "Return ONLY a JSON object",
]

RESULTS = {}
TOKENS = {}


def call(base, method, path, body=None, token=None, extra_headers=None):
    url = base + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for k, v in (extra_headers or {}).items():
        req.add_header(k, v)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        status = e.code
    except Exception as e:  # connection-level failure is also evidence
        raw = json.dumps({"harness_error": str(e)})
        status = 0
    latency = round((time.time() - t0) * 1000)
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = raw[:4000]
    return status, parsed, latency


def scan_leak(obj):
    """Return leak markers found in the serialized response, excluding echoed
    request content stored under harness-controlled keys."""
    text = json.dumps(obj, default=str) if not isinstance(obj, str) else obj
    cleaned = re.sub(r'"(input_text|query_text|test_prompt|_observed)"\s*:\s*"[^"]*"', "", text)
    return [m for m in LEAK_MARKERS if m in cleaned]


def redact(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in ("access_token", "token", "password", "password_hash"):
                out[k] = "[REDACTED]"
            elif isinstance(v, str) and len(v) > 40 and v.count(".") == 2 and v[:2] == "ey":
                out[k] = "[JWT REDACTED]"
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    return obj


def test(tid, objective, expected, fn):
    print(f"[{tid}] {objective}")
    try:
        actual, detail = fn()
    except Exception as e:
        actual, detail = "HARNESS ERROR", {"error": str(e)}
    leaks = scan_leak(detail)
    entry = {
        "test_id": tid,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "objective": objective,
        "expected_behaviour": expected,
        "actual_behaviour": actual,
        "leak_markers_found": leaks,
        "response": redact(detail),
    }
    with open(os.path.join(OUT_DIR, f"{tid}.json"), "w", encoding="utf-8") as f:
        json.dump(entry, f, indent=2, default=str)
    RESULTS[tid] = {"objective": objective, "expected": expected,
                    "actual": actual, "leaks": leaks}
    print(f"    -> {actual[:120]}")


def make_token(sub, email, minutes=480):
    return create_access_token(
        {"sub": str(sub), "email": email},
        expires_delta=timedelta(minutes=minutes),
    )


# ---------------------------------------------------------------------------
# Setup: tokens for user 1 (Triveni) and a freshly registered audit user B
# ---------------------------------------------------------------------------
TOKENS["A"] = make_token(1, "trivtheaver@gmail.com")


def register_b():
    status, body, _ = call(A1, "POST", "/api/auth/register", {
        "name": "Audit Subject B",
        "email": AUDIT_B_EMAIL,
        "password": AUDIT_B_PASSWORD,
    })
    if status == 201:
        TOKENS["B"] = body["access_token"]
        TOKENS["B_ID"] = str(body["user_id"])
    else:
        raise RuntimeError(f"Could not register audit user B: {status} {body}")


register_b()

# One real analysis for user 1 so cross-user fetch probes have a live target
A_REQ_ID = None
A_ITEM_ID = None
A_ITEM_CODE = None
A_IMAGE_PATH = None


def bootstrap():
    global A_REQ_ID, A_ITEM_ID, A_ITEM_CODE, A_IMAGE_PATH
    s, b, _ = call(A1, "POST", "/api/analyze/request",
                   {"query_text": "smart casual outfit with a navy top"}, TOKENS["A"])
    if s == 200:
        A_REQ_ID = b.get("request_id")
    s, b, _ = call(A1, "GET", "/api/wardrobe", None, TOKENS["A"])
    if s == 200 and isinstance(b, list) and b:
        first = next((i for i in b if i.get("id")), b[0])
        A_ITEM_ID = first.get("id")
        A_ITEM_CODE = first.get("wardrobe_code")
        for v in json.dumps(first, default=str).split('"'):
            if "uploads/" in v:
                A_IMAGE_PATH = "/" + v.lstrip("/")
                break


bootstrap()
if not A_REQ_ID or not A_ITEM_ID:
    print("!! Bootstrap failed — cross-user probes will report honest nulls")

# A2 history: one search under A, one under B
A_HIST_ID = None


def bootstrap_a2():
    global A_HIST_ID
    s, b, _ = call(A2, "POST", "/api/v1/search", {
        "request_id": f"S2BOOT-{uuid.uuid4().hex[:8]}",
        "required_category": "top", "max_price": 500, "top_k": 3,
    }, TOKENS["A"])
    if s == 200:
        s2, hist, _ = call(A2, "GET", "/api/v1/history", None, TOKENS["A"])
        if s2 == 200:
            items = hist.get("entries", hist.get("items", [])) if isinstance(hist, dict) else hist
            if isinstance(items, list) and items:
                first = items[0]
                A_HIST_ID = first.get("history_id") or first.get("id")


bootstrap_a2()

# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def pr01():
    s, b, _ = call(A1, "GET", "/api/auth/me", None, TOKENS["A"])
    fields = sorted(b.keys()) if isinstance(b, dict) else []
    leaky = [f for f in fields if "password" in f.lower() or "hash" in f.lower()]
    return (f"200; profile fields={fields}; secret-bearing fields={leaky or 'none'}"
            if s == 200 else f"HTTP {s}: {b}"), b


def pr02():
    s, b, _ = call(A1, "GET", "/api/auth/me", None, TOKENS["B"])
    ok = isinstance(b, dict) and b.get("email") == AUDIT_B_EMAIL
    return f"HTTP {s}; B sees only own profile: {ok}; body email={b.get('email') if isinstance(b, dict) else b}", b


def pr03():
    s, b, _ = call(A1, "GET", "/api/wardrobe", None, TOKENS["B"])
    codes = [i.get("wardrobe_code") for i in b] if isinstance(b, list) else []
    user1_codes = [A_ITEM_CODE] if A_ITEM_CODE else []
    overlap = [c for c in codes if c in user1_codes]
    return (f"HTTP {s}; B wardrobe rows={len(codes)}; user-1 codes leaked to B: {overlap or 'none'}"
            if s == 200 else f"HTTP {s}: {b}"), {"status": s, "codes": codes}


def pr04():
    if not A_ITEM_ID:
        return "SKIPPED — no user-1 wardrobe item available (honest null)", {}
    s, b, _ = call(A1, "GET", f"/api/wardrobe/{A_ITEM_ID}", None, TOKENS["B"])
    leaked = s == 200 and (b.get("wardrobe_code") == A_ITEM_CODE)
    return f"HTTP {s}; IDOR read of user-1 item {A_ITEM_ID} succeeded: {leaked}", b


def pr05():
    if not A_ITEM_ID:
        return "SKIPPED — no user-1 item", {}
    s, b, _ = call(A1, "GET", f"/api/wardrobe/{A_ITEM_ID}", None, TOKENS["A"])
    original = b if isinstance(b, dict) else {}
    body = {k: v for k, v in original.items()
            if k in ("category", "colour", "style_tags", "occasion", "condition", "notes")}
    body["colour"] = "MUTATED_BY_ATTACKER"
    s2, b2, _ = call(A1, "PUT", f"/api/wardrobe/{A_ITEM_ID}", body, TOKENS["B"])
    s3, b3, _ = call(A1, "GET", f"/api/wardrobe/{A_ITEM_ID}", None, TOKENS["A"])
    mutated = isinstance(b3, dict) and b3.get("colour") == "MUTATED_BY_ATTACKER"
    return f"B-write HTTP {s2}; item colour now mutated: {mutated}", {"write_status": s2, "write_body": b2, "after": b3}


def pr06():
    if not A_ITEM_ID:
        return "SKIPPED — no user-1 item", {}
    s, b, _ = call(A1, "DELETE", f"/api/wardrobe/{A_ITEM_ID}", None, TOKENS["B"])
    s2, b2, _ = call(A1, "GET", f"/api/wardrobe/{A_ITEM_ID}", None, TOKENS["A"])
    survived = s2 == 200
    return f"B-delete HTTP {s}; user-1 item still exists afterwards: {survived}", {"delete_status": s, "delete_body": b}


def pr07():
    if not A_REQ_ID:
        return "SKIPPED — no user-1 analysis available", {}
    s, b, _ = call(A1, "GET", f"/api/analyze/{A_REQ_ID}", None, TOKENS["B"])
    leaked = s == 200 and b.get("request_id") == A_REQ_ID
    return f"HTTP {s}; B read user-1 analysis {A_REQ_ID}: {leaked}", b


def pr08():
    s, b, _ = call(A1, "GET", "/api/analyze/recent/latest", None, TOKENS["B"])
    if s == 200:
        leaked = b is not None and (b or {}).get("request_id") == A_REQ_ID
        return f"HTTP 200; B latest-analysis is user-1's analysis: {leaked}; body is null: {b is None}", b
    return f"HTTP {s}: {b}", b


def pr09():
    out = {}
    msgs = []
    for name, hdr in [("no-auth", None), ("garbage-bearer", "Bearer not.a.jwt"),
                      ("empty-bearer", "Bearer ")]:
        s, b, _ = call(A1, "GET", "/api/wardrobe", None, None if hdr is None else False,
                       {"Authorization": hdr} if hdr else None)
        out[name] = {"status": s, "body": b}
        msgs.append(f"{name}->{s}")
    detail = json.dumps(out, default=str).lower()
    leaky = any(k in detail for k in ("traceback", "psycopg", "sqlalchemy", "select ", "jwt_secret"))
    return f"HTTP statuses: {', '.join(msgs)}; stack/secret in error bodies: {leaky}", out


def pr10():
    tampered = TOKENS["A"][:-2] + ("A" if TOKENS["A"][-1] != "A" else "B") + TOKENS["A"][-1:]
    s, b, _ = call(A1, "GET", "/api/wardrobe", None, tampered)
    return f"HTTP {s} on signature-tampered JWT; data served: {s == 200}", {"status": s, "body": b if s != 200 else "200-DATA-LEAK"}


def pr11():
    expired = create_access_token({"sub": "1", "email": "trivtheaver@gmail.com"},
                                  expires_delta=timedelta(minutes=-5))
    s, b, _ = call(A1, "GET", "/api/wardrobe", None, expired)
    return f"HTTP {s} on expired JWT; data served: {s == 200}", {"status": s, "body": b if s != 200 else "200-DATA-LEAK"}


def pr12():
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({"sub": "1", "email": "trivtheaver@gmail.com"}).encode()).rstrip(b"=").decode()
    forged = f"{header}.{payload}."
    s, b, _ = call(A1, "GET", "/api/wardrobe", None, forged)
    return f"HTTP {s} on alg:none forged JWT; data served: {s == 200}", {"status": s, "body": b if s != 200 else "200-DATA-LEAK"}


def pr13():
    if not A_HIST_ID:
        return "SKIPPED — no user-1 A2 history id captured", {}
    s_own, own, _ = call(A2, "GET", "/api/v1/history", None, TOKENS["B"])
    own_ids = []
    if s_own == 200:
        items = own.get("entries", own.get("items", [])) if isinstance(own, dict) else own
        own_ids = [(i.get("history_id") or i.get("id")) for i in items] if isinstance(items, list) else []
    contaminated = A_HIST_ID in own_ids
    s_get, b_get, _ = call(A2, "GET", f"/api/v1/history/{A_HIST_ID}", None, TOKENS["B"])
    s_del, b_del, _ = call(A2, "DELETE", f"/api/v1/history/{A_HIST_ID}", None, TOKENS["B"])
    return (f"B list contaminated with A history: {contaminated}; B GET A-history HTTP {s_get}; "
            f"B DELETE A-history HTTP {s_del}"), {"list": own, "get": b_get, "delete": b_del}


def pr14():
    s_for, b_for, _ = call(A3, "GET", "/budget/usage/1", None, TOKENS["B"])
    s_own, b_own, _ = call(A3, "GET", f"/budget/usage/{TOKENS['B_ID']}", None, TOKENS["B"])
    leak = s_for == 200
    return f"B->user1 usage HTTP {s_for} (leak={leak}); B->own usage HTTP {s_own}", {"cross": b_for, "own": b_own}


def pr15():
    s1, b1, _ = call(A1, "POST", "/api/auth/register",
                     {"name": "Dup", "email": AUDIT_B_EMAIL, "password": "whatever123"})
    s2, b2, _ = call(A1, "POST", "/api/auth/login",
                     {"email": AUDIT_B_EMAIL, "password": "wrong-password-xyz"})
    s3, b3, _ = call(A1, "POST", "/api/auth/login",
                     {"email": f"ghost.{uuid.uuid4().hex[:6]}@none.invalid", "password": "whatever123"})
    d1 = json.dumps(b1, default=str).lower()
    enum_msg = "already" in d1 or "exist" in d1
    same_login_err = json.dumps(b2, default=str).lower() == json.dumps(b3, default=str).lower()
    return (f"dup-register HTTP {s1} (existence-revealing msg: {enum_msg}); unknown-email HTTP {s3}; "
            f"login errors indistinguishable: {same_login_err}"), {"dup": b1, "bad_pw": b2, "unknown": b3}


def pr16():
    from app.models.user import User
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == AUDIT_B_EMAIL).first()
        if u is None:
            return "FAIL — audit user B not found in DB", {}
        h = u.password_hash or ""
        is_bcrypt = h.startswith(("$2b$", "$2a$"))
        plaintext_stored = AUDIT_B_PASSWORD in h
        return (f"stored hash prefix={h[:4] if is_bcrypt else '[NOT BCRYPT]'}; bcrypt={is_bcrypt}; "
                f"length={len(h)}; plaintext present: {plaintext_stored}"), {
            "bcrypt_prefix": h[:7] if is_bcrypt else None,
            "hash_length": len(h),
            "is_bcrypt": is_bcrypt,
            "plaintext_stored": plaintext_stored,
            "_note": "Full hash intentionally not written to evidence.",
        }
    finally:
        db.close()


def pr17():
    if not A_IMAGE_PATH:
        return "SKIPPED — no /uploads image path present on user-1 items (honest null)", {}
    path = A_IMAGE_PATH if A_IMAGE_PATH.startswith("/uploads/") else "/uploads/" + A_IMAGE_PATH.split("/uploads/")[-1]
    s_open, body_open, _ = call(A1, "GET", path, None, None)
    is_image = s_open == 200 and isinstance(body_open, str) and not body_open.strip().startswith("{")
    traversal = "/uploads/%2e%2e%2fapp%2fcore%2fconfig.py"
    s_tr, body_tr, _ = call(A1, "GET", traversal, None, None)
    served_file = s_tr == 200 and "settings" in str(body_tr).lower()
    return (f"unauth image fetch HTTP {s_open} (image bytes served: {is_image}); "
            f"path-traversal HTTP {s_tr}, source served: {served_file}"), {"open_status": s_open, "traversal_status": s_tr}


def pr18():
    s, b, _ = call(A1, "POST", "/api/wardrobe", {"category": "not-a-category"}, TOKENS["B"])
    s2, b2, _ = call(A1, "GET", "/uploads/nonexistent-image-zzz.png", None, TOKENS["B"])
    detail = json.dumps(b, default=str) + json.dumps(b2, default=str)
    leaky = any(k in detail.lower() for k in ("traceback", "psycopg", "select ", "connection", "secret"))
    return f"invalid-item HTTP {s}; missing-image HTTP {s2}; internals in error text: {leaky}", {"val": b, "404": b2}


tests = [
    ("PR-01", "Auth response hygiene: /api/auth/me must return profile without credential fields",
     "200 with id/name/email/created_at only; no password/hash/token fields", pr01),
    ("PR-02", "Session scoping: audit user B authenticates and sees only own identity",
     "200 with B's email, not user 1's", pr02),
    ("PR-03", "Cross-user data leakage: B's wardrobe list must never contain user-1 items",
     "200 with B's empty (or B-only) wardrobe; zero user-1 item codes", pr03),
    ("PR-04", "IDOR read: B requests user-1 wardrobe item by direct id",
     "403/404; no item data returned", pr04),
    ("PR-05", "IDOR update: B attempts PUT-mutation of user-1 wardrobe item",
     "Write rejected AND item unchanged when re-read by owner", pr05),
    ("PR-06", "IDOR delete: B attempts DELETE of user-1 wardrobe item",
     "Delete rejected; item still present afterwards", pr06),
    ("PR-07", "IDOR read: B fetches user-1 outfit analysis by request_id",
     "403/404; analysis text/requirements not returned", pr07),
    ("PR-08", "Recent-analysis exposure: B's /api/analyze/recent/latest must not return user-1 analysis",
     "null (B has no history) — never user-1's record", pr08),
    ("PR-09", "Unauthenticated + malformed token handling on protected endpoint",
     "401 for all variants; generic error, no stack traces/secrets/SQL", pr09),
    ("PR-10", "Token tampering: signature-flipped copy of a valid JWT",
     "401; no data served", pr10),
    ("PR-11", "Expired session: JWT minted with negative expiry",
     "401; no data served", pr11),
    ("PR-12", "Token forgery: unsigned alg:none JWT claiming sub=1",
     "401; no data served", pr12),
    ("PR-13", "Search-history isolation (Agent 2): B must not see, read, or delete user-1 history",
     "B list excludes A records; A-history GET/DELETE as B rejected", pr13),
    ("PR-14", "Usage-data IDOR (Agent 3): B queries /budget/usage/1 (user-1 tenant)",
     "Cross-tenant rejected (403/404); own usage allowed", pr14),
    ("PR-15", "Account enumeration: duplicate-register message + unknown-email vs wrong-password login",
     "Ideal: identical login errors, non-revealing duplicate message", pr15),
    ("PR-16", "Credential storage: audit user B password persisted as bcrypt hash, never plaintext",
     "Stored value starts with bcrypt prefix; plaintext not present in column", pr16),
    ("PR-17", "Sensitive image storage: wardrobe image via /uploads without auth + path traversal",
     "Traversal blocked; unauthenticated image accessibility documented", pr17),
    ("PR-18", "Error-message leakage: validation failure and missing-file responses",
     "422/404 with generic detail; no traceback, SQL, or config internals", pr18),
]


def main():
    for tid, objective, expected, fn in tests:
        test(tid, objective, expected, fn)
    summary = {
        "suite": "S2 — Privacy & Data Leakage",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "accounts": {"user_A": "existing user id 1 (JWT minted at runtime, not stored)",
                     "user_B": {"email": AUDIT_B_EMAIL, "id": TOKENS.get("B_ID"),
                                 "password": "[generated at runtime, never written to evidence]"}},
        "targets": {"A1": A1, "A2": A2, "A3": A3},
        "tests": RESULTS,
        "any_leak_markers": {k: v["leaks"] for k, v in RESULTS.items() if v["leaks"]},
    }
    with open(os.path.join(OUT_DIR, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)
    print("\n=== S2 SUMMARY ===")
    for k, v in RESULTS.items():
        flag = "  LEAK:" + ",".join(v["leaks"]) if v["leaks"] else ""
        print(f"{k}: {v['actual'][:100]}{flag}")


main()
