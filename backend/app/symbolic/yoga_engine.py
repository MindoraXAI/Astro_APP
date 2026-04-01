"""
AIS Yoga Detection Engine
Evaluates all yoga rules against a computed ChartState.
Returns ranked list of ActiveYoga with strength scores.
"""
from __future__ import annotations

from typing import List
from loguru import logger

from app.core.models import ChartState, ActiveYoga
from app.symbolic.yoga_rules import YOGA_RULESET, YogaRule


class YogaEngine:
    """Evaluates all yoga rules against a chart and returns active yogas."""

    def detect_yogas(self, chart: ChartState) -> List[ActiveYoga]:
        """
        Evaluate all registered yoga rules.
        Returns list of ActiveYoga, sorted by strength descending.
        """
        active: List[ActiveYoga] = []

        for rule in YOGA_RULESET:
            try:
                if not rule.predicate(chart):
                    continue
                if rule.cancellation(chart):
                    logger.debug(f"Yoga {rule.name!r} cancelled")
                    continue

                strength = rule.strength_fn(chart)
                strength = round(min(max(strength, 0.0), 1.0), 3)

                # Determine activation dasha
                activation = self._suggest_activation_dasha(rule, chart)

                yoga = ActiveYoga(
                    name=rule.name,
                    category=rule.category,
                    tradition=rule.tradition,
                    strength=strength,
                    planets_involved=rule.planets_required,
                    houses_involved=rule.houses_required,
                    effect_career=rule.effects.get("career"),
                    effect_personality=rule.effects.get("personality"),
                    effect_health=rule.effects.get("health"),
                    activation_dasha=activation,
                    source_ref=rule.source_ref,
                )
                active.append(yoga)
                logger.debug(f"Yoga detected: {rule.name!r} strength={strength:.3f}")

            except Exception as e:
                logger.warning(f"Error evaluating yoga {rule.name!r}: {e}")
                continue

        # Sort by strength descending
        active.sort(key=lambda y: y.strength, reverse=True)
        logger.info(f"Yoga detection complete: {len(active)} active yogas found")
        return active

    def _suggest_activation_dasha(self, rule: YogaRule, chart: ChartState) -> str:
        """
        Suggest the dasha period most likely to activate this yoga.
        Heuristic: yogas activate during dashas of involved planets.
        """
        cd = chart.current_dasha
        involved = rule.planets_required or []
        if cd.mahadasha in involved or cd.antardasha in involved:
            return f"{cd.mahadasha}-{cd.antardasha} (ACTIVE NOW)"
        # Check upcoming dashas
        for future in chart.next_dashas[:5]:
            if future.mahadasha in involved or future.antardasha in involved:
                return f"{future.mahadasha}-{future.antardasha} ({future.start_date})"
        # Default: first planet in list
        if involved:
            return f"{involved[0]} dasha (timing varies)"
        return "Context-dependent"


# Module-level singleton
_engine: YogaEngine | None = None


def get_yoga_engine() -> YogaEngine:
    global _engine
    if _engine is None:
        _engine = YogaEngine()
    return _engine
