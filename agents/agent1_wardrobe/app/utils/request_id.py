"""
Correlation Request ID generator.
Formats: REQ-YYYY-XXXXXX
"""

import uuid
from datetime import datetime, timezone


def generate_request_id() -> str:
    """Generates a unique request ID carried throughout the multi-agent pipeline."""
    year = datetime.now(timezone.utc).year
    short_uuid = uuid.uuid4().hex[:6].upper()
    return f"REQ-{year}-{short_uuid}"
