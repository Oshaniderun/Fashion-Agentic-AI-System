"""
Abstract Base Class for LLM Structured Extraction Providers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from shared.schemas.agent1_schemas import UserRequirements


class BaseLLMProvider(ABC):
    """Abstract interface for LLM calls."""

    @abstractmethod
    def extract_requirements(self, sanitized_text: str) -> UserRequirements:
        """Extract structured user requirements from natural language fashion request."""
        pass
