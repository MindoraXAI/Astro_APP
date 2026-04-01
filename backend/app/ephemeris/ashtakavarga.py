"""
AIS Ashtakavarga Engine
Computes Prashtarashtakavarga (individual planet scores in each sign)
and Sarvashtakavarga (total score per sign).

Ashtakavarga assigns benefic points (0 or 1) for each of 8 reference points
(7 planets + Lagna) transiting each of the 12 signs.

Source: Brihat Parashara Hora Shastra, Chapter on Ashtakavarga.
"""
from __future__ import annotations

from typing import Dict, List
from app.core.models import PlanetState


# ─── Benefic position tables ────────────────────────────────────────────────
# For each planet, this table gives the 12 house positions (from the reference planet)
# where a benefic point is contributed.
# Format: planet_name → {reference_planet: [benefic houses from that reference]}
# Houses are 1-indexed, relative to the reference planet's sign.

ASHTAKA_TABLE: Dict[str, Dict[str, List[int]]] = {
    "Sun": {
        "Sun":     [1, 2, 4, 7, 8, 9, 10, 11],
        "Moon":    [3, 6, 10, 11],
        "Mars":    [1, 2, 4, 7, 8, 9, 10, 11],
        "Mercury": [3, 5, 6, 9, 10, 11, 12],
        "Jupiter": [5, 6, 9, 11],
        "Venus":   [6, 7, 12],
        "Saturn":  [1, 2, 4, 7, 8, 9, 10, 11],
        "Lagna":   [3, 4, 6, 10, 11, 12],
    },
    "Moon": {
        "Sun":     [3, 6, 7, 8, 10, 11],
        "Moon":    [1, 3, 6, 7, 10, 11],
        "Mars":    [2, 3, 5, 6, 9, 10, 11],
        "Mercury": [1, 3, 4, 5, 7, 8, 10, 11],
        "Jupiter": [1, 4, 7, 8, 10, 11, 12],
        "Venus":   [3, 4, 5, 7, 9, 10, 11],
        "Saturn":  [3, 5, 6, 11],
        "Lagna":   [3, 6, 10, 11],
    },
    "Mars": {
        "Sun":     [3, 5, 6, 10, 11],
        "Moon":    [3, 6, 11],
        "Mars":    [1, 2, 4, 7, 8, 10, 11],
        "Mercury": [3, 5, 6, 11],
        "Jupiter": [6, 10, 11, 12],
        "Venus":   [6, 8, 11, 12],
        "Saturn":  [1, 4, 7, 8, 9, 10, 11],
        "Lagna":   [1, 3, 6, 10, 11],
    },
    "Mercury": {
        "Sun":     [5, 6, 9, 11, 12],
        "Moon":    [2, 4, 6, 8, 10, 11],
        "Mars":    [1, 2, 4, 7, 8, 9, 10, 11],
        "Mercury": [1, 3, 5, 6, 9, 10, 11, 12],
        "Jupiter": [6, 8, 11, 12],
        "Venus":   [1, 2, 3, 4, 5, 8, 9, 11],
        "Saturn":  [1, 2, 4, 7, 8, 9, 10, 11],
        "Lagna":   [1, 2, 4, 6, 8, 10, 11],
    },
    "Jupiter": {
        "Sun":     [1, 2, 3, 4, 7, 8, 9, 10, 11],
        "Moon":    [2, 5, 7, 9, 11],
        "Mars":    [1, 2, 4, 7, 8, 10, 11],
        "Mercury": [1, 2, 4, 5, 6, 9, 10, 11],
        "Jupiter": [1, 2, 3, 4, 7, 8, 10, 11],
        "Venus":   [2, 5, 6, 9, 10, 11],
        "Saturn":  [3, 5, 6, 12],
        "Lagna":   [1, 2, 4, 5, 6, 7, 9, 10, 11],
    },
    "Venus": {
        "Sun":     [8, 11, 12],
        "Moon":    [1, 2, 3, 4, 5, 8, 9, 11, 12],
        "Mars":    [3, 4, 6, 9, 11, 12],
        "Mercury": [3, 5, 6, 9, 11],
        "Jupiter": [5, 8, 9, 10, 11],
        "Venus":   [1, 2, 3, 4, 5, 8, 9, 10, 11],
        "Saturn":  [3, 4, 5, 8, 9, 10, 11],
        "Lagna":   [1, 2, 3, 4, 5, 8, 9, 11],
    },
    "Saturn": {
        "Sun":     [1, 2, 4, 7, 8, 10, 11],
        "Moon":    [3, 6, 11],
        "Mars":    [3, 5, 6, 10, 11, 12],
        "Mercury": [6, 8, 9, 10, 11, 12],
        "Jupiter": [5, 6, 11, 12],
        "Venus":   [6, 11, 12],
        "Saturn":  [3, 5, 6, 11],
        "Lagna":   [1, 3, 4, 6, 10, 11],
    },
}

REFERENCE_ORDER = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Lagna"]


class AshtakavargaEngine:
    """
    Computes Ashtakavarga scores for all planets across all 12 signs.
    """

    def compute(
        self,
        planets: Dict[str, PlanetState],
        lagna_sign_number: int,
    ) -> Dict[str, List[int]]:
        """
        Compute Prashtarashtakavarga for each planet.

        Returns: {planet_name: [score_sign1, score_sign2, ... score_sign12]}
        Score per sign = count of benefic points from all 8 reference positions.
        """
        results: Dict[str, List[int]] = {}

        for target_planet, table in ASHTAKA_TABLE.items():
            scores = [0] * 12  # Index 0 = Aries, index 11 = Pisces

            for ref_name, benefic_houses in table.items():
                if ref_name == "Lagna":
                    ref_sign_num = lagna_sign_number
                else:
                    ref_planet = planets.get(ref_name)
                    if not ref_planet:
                        continue
                    ref_sign_num = ref_planet.sign_number

                for benefic_house in benefic_houses:
                    # House X from reference = sign number (1-indexed)
                    target_sign_idx = (ref_sign_num - 1 + benefic_house - 1) % 12
                    scores[target_sign_idx] += 1

            results[target_planet] = scores

        return results

    def sarvashtakavarga(self, prastara: Dict[str, List[int]]) -> List[int]:
        """
        Sum all planet Ashtakavarga scores per sign.
        Returns 12-element list (total bindus per sign, max = 56).
        """
        total = [0] * 12
        for scores in prastara.values():
            for i, score in enumerate(scores):
                total[i] += score
        return total

    def planet_transit_score(
        self,
        planet_name: str,
        transit_sign_number: int,
        prastara: Dict[str, List[int]],
    ) -> int:
        """
        Get Ashtakavarga score for a planet transiting a specific sign (1-indexed).
        Score >= 4: auspicious transit. Score < 4: inauspicious.
        """
        scores = prastara.get(planet_name, [0] * 12)
        return scores[(transit_sign_number - 1) % 12]

    def house_strength(
        self,
        house_number: int,
        lagna_sign_number: int,
        sarva: List[int],
    ) -> int:
        """Get Sarvashtakavarga score for a given house (1-indexed)."""
        sign_idx = (lagna_sign_number - 1 + house_number - 1) % 12
        return sarva[sign_idx]
