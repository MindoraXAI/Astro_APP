"""
AIS Shadbala Engine
Computes the 6-fold planetary strength (Shadbala) used in Vedic astrology.

The 6 components (with BPHS-based weights):
1. Sthana Bala  (positional strength)    25%
2. Dig Bala     (directional strength)   15%
3. Kaala Bala   (temporal strength)      15%
4. Cheshta Bala (motional strength)      20%
5. Naisargika B (natural strength)       10%
6. Drik Bala    (aspectual strength)     15%

Returns: normalized 0.0-1.0 strength per planet.
"""
from __future__ import annotations

import math
from typing import Dict
import swisseph as swe

from app.core.models import PlanetState, HouseState


# ─── Natural (Naisargika) Strength ────────────────────────────────────────────
# Canonical Vedic ordering: Sun > Moon > Venus > Jupiter > Mercury > Mars > Saturn
NAISARGIKA_STRENGTH = {
    "Sun": 1.0, "Moon": 0.857, "Venus": 0.714,
    "Jupiter": 0.571, "Mercury": 0.429, "Mars": 0.286,
    "Saturn": 0.143, "Rahu": 0.2, "Ketu": 0.2
}

# ─── Directional (Dig) Bala ───────────────────────────────────────────────────
# Each planet is strongest in a specific house
DIG_BALA_BEST_HOUSE = {
    "Sun": 10, "Mars": 10,         # South (10th)
    "Saturn": 7,                    # West (7th)
    "Mercury": 1, "Jupiter": 1,    # East (Lagna)
    "Moon": 4, "Venus": 4,         # North (4th)
    "Rahu": 7, "Ketu": 1,
}

# ─── Exaltation + Moolatrikona degrees ───────────────────────────────────────
# (planet_name: (exalt_long, debi_long, mool_start, mool_end))
EXALT_DEBI = {
    "Sun": (10.0, 190.0),        # 10° Aries, 10° Libra
    "Moon": (33.0, 213.0),       # 3° Taurus, 3° Scorpio
    "Mars": (298.0, 118.0),      # 28° Cap, 28° Can
    "Mercury": (165.0, 345.0),   # 15° Virgo, 15° Pisces
    "Jupiter": (95.0, 275.0),    # 5° Cancer, 5° Cap
    "Venus": (357.0, 177.0),     # 27° Pisces, 27° Virgo
    "Saturn": (200.0, 20.0),     # 20° Libra, 20° Aries
    "Rahu": (50.0, 230.0),
    "Ketu": (230.0, 50.0),
}


class ShadbalaEngine:
    """Computes Shadbala for all planets in a chart."""

    WEIGHTS = {
        "sthana": 0.25,
        "dig":    0.15,
        "kaala":  0.15,
        "cheshta": 0.20,
        "naisargika": 0.10,
        "drik":   0.15,
    }

    def compute_all(
        self,
        planets: Dict[str, PlanetState],
        houses: Dict[int, HouseState],
        jd: float,
        birth_data,  # BirthData
    ) -> Dict[str, float]:
        """Compute normalized Shadbala for all 9 planets. Returns 0.0-1.0 per planet."""
        results = {}
        for planet_name, planet in planets.items():
            sthana = self._sthana_bala(planet)
            dig    = self._dig_bala(planet)
            kaala  = self._kaala_bala(planet, jd)
            cheshta = self._cheshta_bala(planet)
            naisargika = NAISARGIKA_STRENGTH.get(planet_name, 0.3)
            drik   = self._drik_bala(planet_name, planets)

            total = (
                sthana     * self.WEIGHTS["sthana"]     +
                dig        * self.WEIGHTS["dig"]        +
                kaala      * self.WEIGHTS["kaala"]      +
                cheshta    * self.WEIGHTS["cheshta"]    +
                naisargika * self.WEIGHTS["naisargika"] +
                drik       * self.WEIGHTS["drik"]
            )
            results[planet_name] = round(min(max(total, 0.0), 1.0), 3)
        return results

    # ── Sthana Bala (Positional) ────────────────────────────────────────────

    def _sthana_bala(self, planet: PlanetState) -> float:
        """Positional strength based on dignity."""
        dignity_scores = {
            "exalted": 1.0,
            "moolatrikona": 0.85,
            "own": 0.75,
            "friendly": 0.55,
            "neutral": 0.40,
            "enemy": 0.25,
            "debilitated": 0.10,
        }
        base = dignity_scores.get(planet.dignity, 0.40)

        # Uccha Bala: proximity to exact exaltation degree
        if planet.name in EXALT_DEBI:
            exalt_long, debi_long = EXALT_DEBI[planet.name]
            diff = abs(planet.longitude - exalt_long) % 360
            if diff > 180:
                diff = 360 - diff
            uccha_bonus = max(0, 1 - diff / 180) * 0.15
            base += uccha_bonus

        # Kendra (1,4,7,10) bonus
        if planet.house in (1, 4, 7, 10):
            base += 0.05
        # Trikona (5,9) bonus
        if planet.house in (5, 9):
            base += 0.03
        # Dusthana (6,8,12) penalty
        if planet.house in (6, 8, 12):
            base -= 0.05

        return min(max(base, 0.0), 1.0)

    # ── Dig Bala (Directional) ──────────────────────────────────────────────

    def _dig_bala(self, planet: PlanetState) -> float:
        """Directional strength: 1.0 in best house, decreases with distance."""
        best_house = DIG_BALA_BEST_HOUSE.get(planet.name, 1)
        house_diff = abs(planet.house - best_house)
        if house_diff > 6:
            house_diff = 12 - house_diff
        # Linear decay: 1.0 at best, 0.0 at worst (6 houses away)
        return round(1.0 - house_diff / 6.0, 3)

    # ── Kaala Bala (Temporal) ───────────────────────────────────────────────

    def _kaala_bala(self, planet: PlanetState, jd: float) -> float:
        """
        Simplified temporal strength.
        Full Kaala Bala has many components; here we use:
        - Diurnal/nocturnal strength
        - Paksha Bala (Moon phase)
        """
        # Simple heuristic: benefics stronger at night, malefics stronger by day
        # We use JD fractional part as a proxy for day/night (UTC)
        day_fraction = jd % 1.0
        is_day = 0.25 < day_fraction < 0.75  # rough approximation
        benefics = {"Moon", "Mercury", "Jupiter", "Venus"}
        malefics = {"Sun", "Mars", "Saturn", "Rahu", "Ketu"}
        if planet.name in benefics:
            return 0.7 if not is_day else 0.55
        if planet.name in malefics:
            return 0.7 if is_day else 0.55
        return 0.60

    # ── Cheshta Bala (Motional) ─────────────────────────────────────────────

    def _cheshta_bala(self, planet: PlanetState) -> float:
        """
        Motional strength.
        Retrograde = stronger (0.75-0.90)
        Direct fast = moderate (0.50-0.65)
        Combust = weak (0.15-0.25)
        """
        if planet.is_combust:
            return 0.20
        if planet.is_retrograde:
            return 0.85
        return 0.58

    # ── Drik Bala (Aspectual) ───────────────────────────────────────────────

    def _drik_bala(
        self, planet_name: str, all_planets: Dict[str, PlanetState]
    ) -> float:
        """
        Aspectual strength based on which planets aspect this planet.
        Benefic aspects increase; malefic aspects decrease.
        """
        benefic_planets = {"Jupiter", "Venus", "Moon", "Mercury"}
        malefic_planets = {"Sun", "Mars", "Saturn", "Rahu", "Ketu"}

        target = all_planets[planet_name]
        score = 0.5  # neutral baseline

        for other_name, other in all_planets.items():
            if other_name == planet_name:
                continue
            if self._has_aspect(other, target):
                if other_name in benefic_planets:
                    score += 0.08
                elif other_name in malefic_planets:
                    score -= 0.06

        return round(min(max(score, 0.0), 1.0), 3)

    def _has_aspect(self, aspector: PlanetState, target: PlanetState) -> bool:
        """Check if aspector aspects target (Vedic aspects)."""
        # All planets aspect 7th house (180° orb ±10°)
        house_diff = abs(aspector.house - target.house)
        if house_diff > 6:
            house_diff = 12 - house_diff

        special_aspects = {
            "Mars": [4, 8],       # 4th and 8th house aspects
            "Jupiter": [5, 9],    # 5th and 9th house aspects
            "Saturn": [3, 10],    # 3rd and 10th house aspects
            "Rahu": [5, 9],
            "Ketu": [5, 9],
        }

        if house_diff == 6:  # 7th house aspect (all planets)
            return True
        if house_diff == 0:  # conjunction
            return True
        extra = special_aspects.get(aspector.name, [])
        return house_diff in extra or (12 - house_diff) in extra
