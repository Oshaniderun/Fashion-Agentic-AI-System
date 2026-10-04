"""
Feature 5 — decision audit log.

A local SQLite record of every decision Agent 4 made, for post-hoc
accountability and bias review. It stores the SHA-256 of the canonical request
instead of the request itself: no raw user text, no item descriptions, no PII.

Writes are best-effort — an audit failure must never change or break the
decision a user is waiting for.
"""

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("decision_audit")

_TABLE = "decision_audit"

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {_TABLE} (
    decision_id            TEXT PRIMARY KEY,
    recorded_at            TEXT NOT NULL,
    request_id             TEXT,
    input_sha256           TEXT NOT NULL,
    candidate_ids          TEXT NOT NULL,
    score_breakdowns       TEXT NOT NULL,
    weights_version        TEXT NOT NULL,
    chosen_combination_id  TEXT,
    decision_status        TEXT NOT NULL,
    reject_reason_codes    TEXT NOT NULL,
    confidence_score       REAL,
    confidence_level       TEXT,
    explanation_source     TEXT,
    explanation_verified   INTEGER,
    reoptimization_round   INTEGER NOT NULL DEFAULT 0
)
"""

_JSON_COLUMNS = ("candidate_ids", "score_breakdowns", "reject_reason_codes")


class AuditUnavailable(RuntimeError):
    """The audit store could not be read; the caller gets a masked 503."""


def canonical_json(payload: Any) -> str:
    """Stable serialisation: the hash must not depend on dict ordering."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def input_hash(request) -> str:
    return hashlib.sha256(canonical_json(request.model_dump(mode="json")).encode()).hexdigest()


def decision_id_for(request) -> str:
    """Deterministic id derived from the input hash.

    The same request therefore maps to the same audit row, which keeps the
    response body deterministic (callers compare it) while still recording that
    the decision happened and exactly how it was made.
    """
    return "dec_" + input_hash(request)[:16]


def _db_path() -> Path:
    return Path(settings.AUDIT_DB_PATH)


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=settings.AUDIT_LOCK_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    return conn


def record(request, response) -> Optional[str]:
    """Store one decision row; return its id, or None when disabled/failed."""
    if not settings.AUDIT_ENABLED:
        return None
    decision_id = decision_id_for(request)
    row = {
        "decision_id": decision_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "request_id": request.request_id,
        "input_sha256": input_hash(request),
        "candidate_ids": canonical_json(
            [o.combination_id for o in request.budget_response.options]
        ),
        "score_breakdowns": canonical_json(
            [b.model_dump(mode="json") for b in getattr(response, "score_breakdown", [])]
        ),
        "weights_version": settings.SCORE_WEIGHTS_VERSION,
        "chosen_combination_id": response.selected_combination_id,
        "decision_status": response.decision.status.value,
        "reject_reason_codes": canonical_json(
            [c.value for c in getattr(response, "reason_codes", [])]
        ),
        "confidence_score": response.decision.confidence_score,
        "confidence_level": response.decision.confidence_level.value,
        "explanation_source": getattr(response, "explanation_source", None),
        "explanation_verified": _as_flag(getattr(response, "explanation_verified", None)),
        "reoptimization_round": getattr(response, "reoptimization_round", 0),
    }
    try:
        with _connect() as conn:
            conn.execute(
                f"INSERT OR IGNORE INTO {_TABLE} "
                "(" + ", ".join(row) + ") VALUES ("
                + ", ".join(f":{key}" for key in row)
                + ")",
                row,
            )
        return decision_id
    except sqlite3.Error as exc:  # never fail the decision over the log
        logger.error("Audit write failed: %s", type(exc).__name__)
        return None


def _as_flag(value: Optional[bool]) -> Optional[int]:
    return None if value is None else int(bool(value))


def _decode(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    for column in _JSON_COLUMNS:
        try:
            data[column] = json.loads(data.get(column) or "[]")
        except json.JSONDecodeError:
            data[column] = []
    data["explanation_verified"] = bool(data["explanation_verified"]) if data.get(
        "explanation_verified"
    ) is not None else None
    return data


def fetch(decision_id: str) -> Optional[Dict[str, Any]]:
    if not _db_path().exists():
        return None
    try:
        with _connect() as conn:
            row = conn.execute(
                f"SELECT * FROM {_TABLE} WHERE decision_id = ?", (decision_id,)
            ).fetchone()
    except sqlite3.Error:
        logger.error("Audit read failed")
        return None
    return _decode(row) if row else None


def list_entries(limit: int, offset: int) -> Dict[str, Any]:
    """Most recent first. Returns an empty page when nothing has been logged."""
    if not _db_path().exists():
        return {"total": 0, "limit": limit, "offset": offset, "items": []}
    try:
        with _connect() as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM {_TABLE}").fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM {_TABLE} ORDER BY recorded_at DESC, rowid DESC"
                " LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
    except sqlite3.Error as exc:
        logger.error("Audit list failed: %s", type(exc).__name__)
        raise AuditUnavailable() from exc
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_decode(r) for r in rows],
    }
