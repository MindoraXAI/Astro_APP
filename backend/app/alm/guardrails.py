"""
AIS Output Guardrails
Multi-layer safety and hallucination prevention for ALM outputs.
"""
from __future__ import annotations

import re
from typing import Optional
from loguru import logger

from app.core.models import ChartState


# ─── Prohibited patterns ──────────────────────────────────────────────────────

DEATH_PATTERNS = [
    r"\b(death|die|dying|fatal|mortality|end of life)\b",
    r"\b(life span|longevity prediction|years to live)\b",
]

ABSOLUTE_CERTAINTY_PATTERNS = [
    r"\b(will definitely|guaranteed|100%|absolutely certain|certain to)\b",
    r"\b(you will definitely|this will happen|it is certain)\b",
]

HARMFUL_PATTERNS = [
    r"\b(stop your medication|avoid doctors|cure your cancer)\b",
    r"\b(do not seek medical|reject treatment)\b",
]


def apply_guardrails(text: str, chart: Optional[ChartState]) -> str:
    """
    Apply all guardrail layers to LLM output.

    Layer 1: Remove death/mortality claims
    Layer 2: Soften absolute certainty language
    Layer 3: Remove harmful medical advice
    Layer 4: Add uncertainty hedge if confidence language is missing
    """
    if not text:
        return text

    processed = text

    # Layer 1: Death claims → health vigilance framing
    for pattern in DEATH_PATTERNS:
        processed = re.sub(
            pattern,
            "significant life transition",
            processed,
            flags=re.IGNORECASE
        )

    # Layer 2: Soften absolute certainty
    replacements = {
        "will definitely": "shows strong tendency to",
        "is guaranteed": "has high probability of",
        "100%": "with high likelihood",
        "certainly will": "may strongly",
        "you will": "you may",
        "this will happen": "this may unfold",
    }
    for old, new in replacements.items():
        processed = processed.replace(old, new)

    # Layer 3: Remove harmful medical advice
    for pattern in HARMFUL_PATTERNS:
        processed = re.sub(pattern, "[professional advice recommended]", processed, flags=re.IGNORECASE)

    # Layer 4: Add uncertainty hedge if missing
    uncertainty_words = ["may", "tends to", "suggests", "indicates", "shows potential", "tendency"]
    if not any(word in processed.lower() for word in uncertainty_words):
        processed = (
            "Based on the astrological chart indicators (noting that these are tendencies, "
            "not certainties): " + processed
        )

    # Layer 5: Disclaimer
    if len(processed) > 100:
        processed += (
            "\n\n⚠️ *Astrological insights are for reflection and self-awareness. "
            "Consult qualified professionals for health, legal, and financial decisions.*"
        )

    logger.debug(f"Guardrails applied: output length {len(text)} → {len(processed)}")
    return processed
