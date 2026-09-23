"""
AnalysisRecord model — Agent 1 re-export from shared layer.
Import path stays the same for Agent 1 internals: from app.models.analysis import AnalysisRecord
"""

from shared.models.analysis_record import AnalysisRecord  # noqa: F401

__all__ = ["AnalysisRecord"]
