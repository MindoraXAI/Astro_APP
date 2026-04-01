"""
AIS Vedic Aspect Matrix
Computes all planetary aspects in a Vedic chart.

Vedic Aspects (Drishti):
- All planets: 7th house aspect (180°, full strength)
- Mars:    4th (90°) and 8th (210°) house aspects — 3/4 strength
- Jupiter: 5th (120°) and 9th (240°) house aspects — full strength
- Saturn:  3rd (60°) and 10th (270°) house aspects — 3/4 strength
- Rahu/Ketu: 5th and 9th (similar to Jupiter, per many classical texts)
"""
from __future__ import annotations

from typing import Dict, List, Tuple
from app.core.models import ChartState, PlanetState


# ─── Aspect definitions ────────────────────────────────────────────────────────
# Format: planet → [(house_offset, strength)]
# house_offset = number of houses forward from planet's house (7th = 6 offset)
# All planets also get the 7th house (offset=6) at full strength

BASE_ASPECTS = {
    "Sun":     [(6, 1.0)],
    "Moon":    [(6, 1.0)],
    "Mercury": [(6, 1.0)],
    "Venus":   [(6, 1.0)],
    "Mars":    [(6, 1.0), (3, 0.75), (7, 0.75)],   # 4th and 8th special
    "Jupiter": [(6, 1.0), (4, 1.0), (8, 1.0)],     # 5th and 9th special
    "Saturn":  [(6, 1.0), (2, 0.75), (9, 0.75)],   # 3rd and 10th special
    "Rahu":    [(6, 1.0), (4, 0.75), (8, 0.75)],
    "Ketu":    [(6, 1.0), (4, 0.75), (8, 0.75)],
}


class AspectMatrix:
    """Computes Vedic aspect strengths between all planets."""

    def compute_all_aspects(
        self, chart: ChartState
    ) -> Dict[str, List[Tuple[str, float]]]:
        """
        Compute all aspects in the chart.

        Returns:
            {target_planet: [(aspector_planet, strength), ...]}
        """
        aspects_on: Dict[str, List[Tuple[str, float]]] = {p: [] for p in chart.planets}

        for aspector_name, aspector in chart.planets.items():
            for house_offset, strength in BASE_ASPECTS.get(aspector_name, [(6, 1.0)]):
                aspected_house = (aspector.house - 1 + house_offset) % 12 + 1
                # Find planets in aspected house
                for target_name, target in chart.planets.items():
                    if target_name == aspector_name:
                        continue
                    if target.house == aspected_house:
                        aspects_on[target_name].append((aspector_name, strength))

        return aspects_on

    def planet_receives_benefic_aspects(
        self, planet_name: str, chart: ChartState
    ) -> float:
        """Return net benefic aspect score on a planet (positive = benefic dominant)."""
        all_aspects = self.compute_all_aspects(chart)
        aspects = all_aspects.get(planet_name, [])

        benefics = {"Jupiter", "Venus", "Moon", "Mercury"}
        malefics = {"Sun", "Mars", "Saturn", "Rahu", "Ketu"}

        score = 0.0
        for aspector, strength in aspects:
            if aspector in benefics:
                score += strength * 0.1
            elif aspector in malefics:
                score -= strength * 0.08

        return round(score, 3)

    def get_house_aspects(
        self, house_number: int, chart: ChartState
    ) -> List[Tuple[str, float]]:
        """Return list of (planet, strength) for all planets aspecting a specific house."""
        result = []
        for aspector_name, aspector in chart.planets.items():
            for house_offset, strength in BASE_ASPECTS.get(aspector_name, [(6, 1.0)]):
                aspected_house = (aspector.house - 1 + house_offset) % 12 + 1
                if aspected_house == house_number:
                    result.append((aspector_name, strength))
        return result

    def mutual_aspect_exists(
        self, p1: str, p2: str, chart: ChartState
    ) -> bool:
        """Check if two planets mutually aspect each other."""
        all_aspects = self.compute_all_aspects(chart)
        p1_receives = dict(all_aspects.get(p1, []))
        p2_receives = dict(all_aspects.get(p2, []))
        return p2 in p1_receives and p1 in p2_receives
