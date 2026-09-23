"""
Coordinator service for Natural-Language Fashion Requirement Extraction.
Integrates prompt injection protection with structured extraction and confidence calculation.
"""

from typing import Tuple
from app.services.nlp.prompt_guard import prompt_guard, SecurityThreatReport
from app.services.llm.structured_extractor import structured_extractor
from shared.schemas.agent1_schemas import UserRequirements
from app.core.logging import logger


class FashionRequirementService:
    """End-to-end NLP service for Agent 1."""

    def process_request(self, raw_user_text: str) -> Tuple[UserRequirements, float, SecurityThreatReport]:
        """
        1. Evaluates security threats and sanitizes input.
        2. Extracts structured fashion requirements.
        3. Computes NLP extraction confidence score.
        """
        # Step 1: Security inspection
        threat_report = prompt_guard.evaluate_input(raw_user_text)

        # Step 2: Extraction on sanitized text
        requirements = structured_extractor.extract_requirements(threat_report.sanitized_input)

        # Step 3: Calibrated NLP confidence
        # Confidence is higher when specific key entities (occasion, style, color) are present
        conf = 0.50
        if requirements.occasion:
            conf += 0.20
        if requirements.style and requirements.style != ["casual"]:
            conf += 0.15
        if requirements.colour_preferences or requirements.excluded_colours:
            conf += 0.10
        if requirements.budget is not None:
            conf += 0.05

        if not threat_report.is_safe:
            conf = max(0.2, conf - 0.3)

        return requirements, round(min(1.0, conf), 2), threat_report


fashion_requirement_service = FashionRequirementService()
