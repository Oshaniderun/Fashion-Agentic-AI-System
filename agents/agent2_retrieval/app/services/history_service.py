"""
Server-side search history for Agent 2 (user-scoped).

Records one row per retrieval performed for an authenticated USER (calls made
with the inter-agent service token are not attributed to anyone and are not
recorded). Writes are best-effort: a history failure must never break
retrieval. Product payloads are NOT duplicated here — we store the ranked
product IDs and re-resolve them against the catalogue on read.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, desc
from sqlalchemy.orm import Session

from app.models.search_history import SearchHistory
from shared.schemas.agent2_schemas import RetrievalRequest, RetrievalResponse

logger = logging.getLogger("agent2_retrieval.history")

MAX_STORED_PRODUCT_IDS = 20


def user_id_from_auth(auth: Optional[dict]) -> Optional[str]:
    if not auth or auth.get("auth_type") != "user":
        return None
    sub = auth.get("payload", {}).get("sub")
    return str(sub) if sub else None


def _json_list(raw: Optional[str]) -> List[Any]:
    try:
        val = json.loads(raw or "[]")
        return val if isinstance(val, list) else []
    except (ValueError, TypeError):
        return []


def record_search(
    db: Session,
    auth: Optional[dict],
    request: RetrievalRequest,
    response: RetrievalResponse,
    source: str,
) -> None:
    user_id = user_id_from_auth(auth)
    if not user_id:
        return
    try:
        category = getattr(request.required_category, "value", request.required_category)
        db.add(
            SearchHistory(
                user_id=user_id,
                source=source,
                request_id=str(request.request_id)[:200],
                query_text=(request.query_text or "")[:2000] or None,
                category=str(category)[:100],
                preferred_colour=request.preferred_colour,
                style=(request.style or "")[:100] or None,
                occasion=(request.occasion or "")[:100] or None,
                max_price=request.max_price,
                status=response.status.value,
                result_count=len(response.results),
                relaxed_constraints=json.dumps(response.relaxed_constraints)[:2000],
                product_ids=json.dumps(
                    [r.product_id for r in response.results][:MAX_STORED_PRODUCT_IDS]
                ),
            )
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning(f"search history write failed (retrieval unaffected): {exc}")


def _entry_dict(row: SearchHistory) -> dict:
    return {
        "id": row.id,
        "source": row.source,
        "request_id": row.request_id,
        "query_text": row.query_text,
        "category": row.category,
        "preferred_colour": row.preferred_colour,
        "style": row.style,
        "occasion": row.occasion,
        "max_price": row.max_price,
        "status": row.status,
        "result_count": row.result_count,
        "relaxed_constraints": _json_list(row.relaxed_constraints),
        "product_ids": _json_list(row.product_ids),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def list_history(db: Session, user_id: str, limit: int = 50) -> List[dict]:
    rows = (
        db.query(SearchHistory)
        .filter(SearchHistory.user_id == user_id)
        .order_by(desc(SearchHistory.created_at), desc(SearchHistory.id))
        .limit(limit)
        .all()
    )
    return [_entry_dict(r) for r in rows]


def get_history_entry(db: Session, user_id: str, history_id: int) -> Optional[dict]:
    row = (
        db.query(SearchHistory)
        .filter(SearchHistory.id == history_id, SearchHistory.user_id == user_id)
        .first()
    )
    return _entry_dict(row) if row else None


def delete_history_entry(db: Session, user_id: str, history_id: int) -> bool:
    deleted = (
        db.query(SearchHistory)
        .filter(SearchHistory.id == history_id, SearchHistory.user_id == user_id)
        .delete()
    )
    db.commit()
    return bool(deleted)


def clear_history(db: Session, user_id: str) -> int:
    deleted = db.execute(
        delete(SearchHistory).where(SearchHistory.user_id == user_id)
    ).rowcount
    db.commit()
    return deleted or 0
