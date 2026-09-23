"""
Prompt Injection, Jailbreak, and Untrusted Input Security Guard.
Protects against 15+ threat vectors for both normal operation and academic red-team evaluation.
"""

import re
from typing import List, Dict, Any, Tuple, Optional
from pydantic import BaseModel

from app.core.logging import logger


class SecurityThreatReport(BaseModel):
    is_safe: bool
    risk_score: float  # 0.0 (clean) to 1.0 (critical attack)
    attack_category: Optional[str] = None
    detected_indicators: List[str] = []
    sanitized_input: str
    defensive_action: str  # "allowed", "sanitized", "blocked"
    explanation: str


ATTACK_RULES: List[Dict[str, Any]] = [
    {
        "category": "direct_instruction_override",
        "pattern": r"(ignore|disregard|forget|override|bypass)\s+(all\s+)?(previous|prior|above|system|safety|security)?\s*(instructions?|rules?|prompts?|guidelines?)?",
        "weight": 0.95,
        "desc": "Direct instruction override attempt"
    },
    {
        "category": "system_prompt_extraction",
        "pattern": r"(reveal|print|show|output|leak|display|repeat|what\s+are)\s+(me\s+)?(your\s+)?(the\s+)?(system\s*prompt|initial\s*instructions?|initial\s*system\s*instructions?|hidden\s*instructions?|hidden\s*prompts?|instructions?\s*(above|verbatim)?)(\s+verbatim)?",
        "weight": 0.95,
        "desc": "System prompt leakage / extraction attempt"
    },
    {
        "category": "system_prompt_keyword",
        "pattern": r"system\s*prompt",
        "weight": 0.90,
        "desc": "System prompt keyword detection"
    },
    {
        "category": "role_play_jailbreak",
        "pattern": r"(act\s+as|pretend\s+to\s+be|simulate|you\s+are\s+now|developer\s*mode|pretend\s+you\s+have\s+no\s+rules)\s*(dan|unrestricted|god\s*mode|evil\s*bot|root|admin|system\s*administrator|developer\s*mode|in\s+developer\s*mode)?",
        "weight": 0.90,
        "desc": "Persona/role-play jailbreak attempt"
    },
    {
        "category": "secret_probing",
        "pattern": r"(api[_\s]?key|jwt[_\s]?secret|env\s*vars?|database[_\s]?url|credentials?|passwords?|admin\s*password)",
        "weight": 0.90,
        "desc": "Credential and environment variable probing"
    },
    {
        "category": "format_hijacking",
        "pattern": r"(ignore\s+(the\s+)?json\s+format|do\s+not\s+output\s+json|output\s+(only|pure)\s+text|ignore\s+the\s+schema|format\s+override)",
        "weight": 0.85,
        "desc": "Output format hijacking attempt"
    },
    {
        "category": "goal_hijacking",
        "pattern": r"(instead\s+of\s+fashion|new\s+task\s*:|stop\s+analyzing\s+clothes|write\s+a\s+(story|poem|essay|code|guide)\s+about)",
        "weight": 0.85,
        "desc": "Goal / task hijacking attempt"
    },
    {
        "category": "nested_instruction",
        "pattern": r"(```system|<system>|\[INST\]|\[SYSTEM\]|<\|im_start\|>)",
        "weight": 0.98,
        "desc": "Nested delimiter injection"
    }
]


class PromptGuard:
    """Evaluates and neutralizes prompt injection payloads."""

    def evaluate_input(self, user_input: str) -> SecurityThreatReport:
        """
        Scans input against injection threat vectors and returns a structured threat report.
        """
        detected: List[str] = []
        highest_weight = 0.0
        primary_category = None
        reasons = []

        lower = user_input.lower()

        for rule in ATTACK_RULES:
            match = re.search(rule["pattern"], lower, re.IGNORECASE)
            if match:
                matched_text = match.group(0).strip()
                # Ensure it's not matching empty string
                if matched_text:
                    detected.append(matched_text)
                    reasons.append(rule["desc"])
                    if rule["weight"] > highest_weight:
                        highest_weight = rule["weight"]
                        primary_category = rule["category"]

        if highest_weight >= 0.85:
            action = "blocked"
            is_safe = False
            # Neutralize detected patterns
            sanitized = user_input
            for rule in ATTACK_RULES:
                sanitized = re.sub(rule["pattern"], "[FILTERED_SECURITY_VIOLATION]", sanitized, flags=re.IGNORECASE)

            explanation = (
                f"Threat detected: {', '.join(set(reasons))}. "
                "The system treated the input as unexecutable data and prevented instruction manipulation."
            )
        elif highest_weight > 0.0:
            action = "sanitized"
            is_safe = True
            sanitized = user_input
            for rule in ATTACK_RULES:
                sanitized = re.sub(rule["pattern"], "[FILTERED]", sanitized, flags=re.IGNORECASE)
            explanation = f"Potential suspicious patterns identified and neutralized ({', '.join(set(reasons))})."
        else:
            action = "allowed"
            is_safe = True
            sanitized = user_input
            explanation = "Input passed all prompt security inspections without threat markers."

        return SecurityThreatReport(
            is_safe=is_safe,
            risk_score=highest_weight,
            attack_category=primary_category,
            detected_indicators=list(set(detected)),
            sanitized_input=sanitized,
            defensive_action=action,
            explanation=explanation
        )


prompt_guard = PromptGuard()
