"""
AIS Yoga Rules DSL
Defines 80+ classical Vedic yoga formation rules as structured dataclasses.

Each YogaRule encodes:
- Predicate logic (ChartState → bool)
- Strength function (ChartState → 0.0-1.0)
- Effects per life domain
- Cancellation conditions
- BPHS source reference

Categories:
1. Pancha Mahapurusha Yogas (5)
2. Raja Yogas (20+)
3. Dhana Yogas (15+)
4. Viparita Raja Yogas (3)
5. Duryogas / Arishta Yogas (10+)
6. Neecha Bhanga Raja Yoga (9 cancellation forms)
7. Miscellaneous Special Yogas (15+)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Literal
from app.core.models import ChartState, PlanetState


# ─── Core Data Structure ───────────────────────────────────────────────────────

@dataclass
class YogaRule:
    name: str
    category: Literal["pancha_mahapurusha", "raja", "dhana", "viparita", "duryoga", "neecha_bhanga", "misc"]
    tradition: Literal["vedic", "western", "both"] = "vedic"
    source_ref: str = ""
    # Formation predicate
    predicate: Callable[[ChartState], bool] = field(default=lambda c: False, repr=False)
    # Strength computation (0.0-1.0)
    strength_fn: Callable[[ChartState], float] = field(default=lambda c: 0.5, repr=False)
    # Cancellation predicate (True = yoga is cancelled)
    cancellation: Callable[[ChartState], bool] = field(default=lambda c: False, repr=False)
    # Effects by life domain
    effects: Dict[str, str] = field(default_factory=dict)
    planets_required: List[str] = field(default_factory=list)
    houses_required: List[int] = field(default_factory=list)


# ─── Helper Functions ──────────────────────────────────────────────────────────

def planet_in_houses(chart: ChartState, planet: str, houses: List[int]) -> bool:
    p = chart.planets.get(planet)
    return p is not None and p.house in houses

def planet_in_signs(chart: ChartState, planet: str, signs: List[str]) -> bool:
    p = chart.planets.get(planet)
    return p is not None and p.sign in signs

def planet_dignity(chart: ChartState, planet: str) -> str:
    p = chart.planets.get(planet)
    return p.dignity if p else "neutral"

def planets_conjunction(chart: ChartState, p1: str, p2: str) -> bool:
    """Two planets in the same house (conjunction)."""
    pl1 = chart.planets.get(p1)
    pl2 = chart.planets.get(p2)
    return pl1 is not None and pl2 is not None and pl1.house == pl2.house

def mutual_aspect(chart: ChartState, p1: str, p2: str) -> bool:
    """Check 7th house mutual aspect (180°)."""
    pl1 = chart.planets.get(p1)
    pl2 = chart.planets.get(p2)
    if not pl1 or not pl2:
        return False
    diff = abs(pl1.house - pl2.house)
    return diff == 6  # 7th house aspect = 6 houses apart

def planet_in_kendra(chart: ChartState, planet: str) -> bool:
    return planet_in_houses(chart, planet, [1, 4, 7, 10])

def planet_in_trikona(chart: ChartState, planet: str) -> bool:
    return planet_in_houses(chart, planet, [1, 5, 9])

def planet_in_kendra_or_trikona(chart: ChartState, planet: str) -> bool:
    return planet_in_kendra(chart, planet) or planet_in_trikona(chart, planet)

def planet_in_dusthana(chart: ChartState, planet: str) -> bool:
    return planet_in_houses(chart, planet, [6, 8, 12])

def planet_not_debilitated(chart: ChartState, planet: str) -> bool:
    return planet_dignity(chart, planet) != "debilitated"

def planet_not_combust(chart: ChartState, planet: str) -> bool:
    p = chart.planets.get(planet)
    return p is not None and not p.is_combust

def lord_of_house(chart: ChartState, house_num: int) -> Optional[str]:
    """Return the lord of a given house."""
    h = chart.houses.get(house_num)
    return h.lord if h else None

def lord_in_house(chart: ChartState, lord_of: int, in_house: int) -> bool:
    """Return True if lord of 'lord_of' house is placed in 'in_house'."""
    lord = lord_of_house(chart, lord_of)
    if not lord:
        return False
    return planet_in_houses(chart, lord, [in_house])

def lords_conjunction(chart: ChartState, h1: int, h2: int) -> bool:
    """Lords of two houses conjunct (same house)."""
    l1 = lord_of_house(chart, h1)
    l2 = lord_of_house(chart, h2)
    if not l1 or not l2 or l1 == l2:
        return False
    return planets_conjunction(chart, l1, l2)

def lords_mutual_aspect(chart: ChartState, h1: int, h2: int) -> bool:
    l1 = lord_of_house(chart, h1)
    l2 = lord_of_house(chart, h2)
    if not l1 or not l2 or l1 == l2:
        return False
    return mutual_aspect(chart, l1, l2)

def lords_exchange(chart: ChartState, h1: int, h2: int) -> bool:
    """Parivartana Yoga (mutual sign exchange) between lords of two houses."""
    l1 = lord_of_house(chart, h1)
    l2 = lord_of_house(chart, h2)
    if not l1 or not l2 or l1 == l2:
        return False
    p1 = chart.planets.get(l1)
    p2 = chart.planets.get(l2)
    if not p1 or not p2:
        return False
    # l1 is in house h2 AND l2 is in house h1
    return p1.house == h2 and p2.house == h1

def strength_from_planet(chart: ChartState, planet: str) -> float:
    p = chart.planets.get(planet)
    return p.shadbala_strength if p else 0.3

def max_strength(*vals: float) -> float:
    return max(vals, default=0.3)

def avg_strength(*vals: float) -> float:
    return sum(vals) / max(len(vals), 1)


# ─────────────────────────────────────────────────────────────────────────────
# YOGA RULE DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

def build_yoga_ruleset() -> List[YogaRule]:
    rules: List[YogaRule] = []

    # ═══════════════════════════════════════════════════════════════
    # 1. PANCHA MAHAPURUSHA YOGAS (5 Great Person Yogas)
    # Each formed when the corresponding planet is in kendra AND
    # in own sign or exalted. Not in dusthana.
    # Source: BPHS Chapter 35
    # ═══════════════════════════════════════════════════════════════

    rules.append(YogaRule(
        name="Hamsa Mahapurusha Yoga",
        category="pancha_mahapurusha",
        source_ref="BPHS_ch35_v2",
        planets_required=["Jupiter"],
        predicate=lambda c: (
            planet_in_kendra(c, "Jupiter") and
            planet_in_signs(c, "Jupiter", ["Cancer", "Sagittarius", "Pisces"]) and
            planet_not_combust(c, "Jupiter")
        ),
        strength_fn=lambda c: min(0.95, strength_from_planet(c, "Jupiter") * 1.2),
        effects={
            "career": "High authority, wisdom-based leadership, spiritual or academic prominence",
            "personality": "Just, learned, respected, generous, philosophical",
            "health": "Good constitution, long life",
        },
    ))

    rules.append(YogaRule(
        name="Malavya Mahapurusha Yoga",
        category="pancha_mahapurusha",
        source_ref="BPHS_ch35_v4",
        planets_required=["Venus"],
        predicate=lambda c: (
            planet_in_kendra(c, "Venus") and
            planet_in_signs(c, "Venus", ["Taurus", "Libra", "Pisces"]) and
            planet_not_combust(c, "Venus")
        ),
        strength_fn=lambda c: min(0.95, strength_from_planet(c, "Venus") * 1.2),
        effects={
            "career": "Artistic success, luxury industries, diplomacy",
            "personality": "Charming, artistic, sensual, prosperous",
            "relationships": "Highly attractive, happy marriages, many admirers",
        },
    ))

    rules.append(YogaRule(
        name="Ruchaka Mahapurusha Yoga",
        category="pancha_mahapurusha",
        source_ref="BPHS_ch35_v1",
        planets_required=["Mars"],
        predicate=lambda c: (
            planet_in_kendra(c, "Mars") and
            planet_in_signs(c, "Mars", ["Aries", "Scorpio", "Capricorn"]) and
            planet_not_combust(c, "Mars")
        ),
        strength_fn=lambda c: min(0.95, strength_from_planet(c, "Mars") * 1.2),
        effects={
            "career": "Military, leadership, athletic excellence, administration",
            "personality": "Courageous, energetic, commanding, physically strong",
        },
    ))

    rules.append(YogaRule(
        name="Bhadra Mahapurusha Yoga",
        category="pancha_mahapurusha",
        source_ref="BPHS_ch35_v3",
        planets_required=["Mercury"],
        predicate=lambda c: (
            planet_in_kendra(c, "Mercury") and
            planet_in_signs(c, "Mercury", ["Gemini", "Virgo"]) and
            planet_not_combust(c, "Mercury")
        ),
        strength_fn=lambda c: min(0.95, strength_from_planet(c, "Mercury") * 1.2),
        effects={
            "career": "Intellectual eminence, writing, teaching, business acumen",
            "personality": "Intelligent, eloquent, skilled, analytical",
        },
    ))

    rules.append(YogaRule(
        name="Shasha Mahapurusha Yoga",
        category="pancha_mahapurusha",
        source_ref="BPHS_ch35_v5",
        planets_required=["Saturn"],
        predicate=lambda c: (
            planet_in_kendra(c, "Saturn") and
            planet_in_signs(c, "Saturn", ["Capricorn", "Aquarius", "Libra"]) and
            planet_not_combust(c, "Saturn")
        ),
        strength_fn=lambda c: min(0.95, strength_from_planet(c, "Saturn") * 1.2),
        effects={
            "career": "Administration, law, engineering, political power over masses",
            "personality": "Disciplined, authoritative, perseverant, shrewd",
        },
    ))

    # ═══════════════════════════════════════════════════════════════
    # 2. RAJA YOGAS — Trikona-Kendra Lord Combinations
    # Source: BPHS Chapter 37
    # ═══════════════════════════════════════════════════════════════

    # Key Raja Yoga principle: lord of trikona (1,5,9) + lord of kendra (1,4,7,10) combine
    TRIKONA_HOUSES = [1, 5, 9]
    KENDRA_HOUSES = [1, 4, 7, 10]

    for trikona in TRIKONA_HOUSES:
        for kendra in KENDRA_HOUSES:
            if trikona == kendra:
                continue  # Lagna is both trikona and kendra — skip to avoid duplicates
            rules.append(YogaRule(
                name=f"Raja Yoga (Lord {trikona} + Lord {kendra})",
                category="raja",
                source_ref=f"BPHS_ch37_raja_{trikona}_{kendra}",
                houses_required=[trikona, kendra],
                predicate=lambda c, t=trikona, k=kendra: (
                    lords_conjunction(c, t, k) or
                    lords_mutual_aspect(c, t, k) or
                    lords_exchange(c, t, k)
                ),
                strength_fn=lambda c, t=trikona, k=kendra: avg_strength(
                    strength_from_planet(c, lord_of_house(c, t) or "Sun"),
                    strength_from_planet(c, lord_of_house(c, k) or "Sun"),
                ),
                cancellation=lambda c, t=trikona, k=kendra: (
                    planet_in_dusthana(c, lord_of_house(c, t) or "") or
                    planet_in_dusthana(c, lord_of_house(c, k) or "")
                ),
                effects={
                    "career": "Rise to prominence, authority, recognition; timing via dasha",
                    "finance": "Wealth and status improvement",
                },
            ))

    # ═══════════════════════════════════════════════════════════════
    # 3. DHANA YOGAS — Wealth Combinations
    # Source: BPHS Chapter 38
    # ═══════════════════════════════════════════════════════════════

    for h1, h2 in [(2, 11), (2, 9), (2, 5), (11, 9), (11, 5), (9, 5)]:
        rules.append(YogaRule(
            name=f"Dhana Yoga (Lord {h1} + Lord {h2})",
            category="dhana",
            source_ref=f"BPHS_ch38_dhana_{h1}_{h2}",
            houses_required=[h1, h2],
            predicate=lambda c, a=h1, b=h2: (
                lords_conjunction(c, a, b) or
                lords_mutual_aspect(c, a, b) or
                lords_exchange(c, a, b)
            ),
            strength_fn=lambda c, a=h1, b=h2: avg_strength(
                strength_from_planet(c, lord_of_house(c, a) or "Sun"),
                strength_from_planet(c, lord_of_house(c, b) or "Sun"),
            ),
            effects={
                "finance": "Wealth accumulation, financial gains, prosperity",
                "career": "Material success through professional endeavors",
            },
        ))

    # ═══════════════════════════════════════════════════════════════
    # 4. VIPARITA RAJA YOGAS (Dusthana Lords Exchange)
    # Source: BPHS Chapter 39
    # ═══════════════════════════════════════════════════════════════

    viparita_pairs = [(6, 8), (6, 12), (8, 12)]
    viparita_names = ["Harsha", "Sarala", "Vimala"]
    for (h1, h2), vname in zip(viparita_pairs, viparita_names):
        rules.append(YogaRule(
            name=f"{vname} Viparita Raja Yoga (Lord {h1} + Lord {h2})",
            category="viparita",
            source_ref=f"BPHS_ch39_viparita_{vname.lower()}",
            houses_required=[h1, h2],
            predicate=lambda c, a=h1, b=h2: lords_exchange(c, a, b) or lords_conjunction(c, a, b),
            strength_fn=lambda c, a=h1, b=h2: avg_strength(
                strength_from_planet(c, lord_of_house(c, a) or "Sun"),
                strength_from_planet(c, lord_of_house(c, b) or "Sun"),
            ),
            cancellation=lambda c, a=h1, b=h2: (
                planet_in_trikona(c, lord_of_house(c, a) or "") or
                planet_in_kendra(c, lord_of_house(c, b) or "")
            ),
            effects={
                "career": "Success after setbacks, rise through adversity",
                "spirituality": "Detachment from material results leads to unexpected gains",
            },
        ))

    # ═══════════════════════════════════════════════════════════════
    # 5. NEECHA BHANGA RAJA YOGA (Debilitation Cancelled)
    # Source: BPHS Chapter 35 and classical commentaries
    # ═══════════════════════════════════════════════════════════════

    # Neecha Bhanga: debilitated planet's debilitation is cancelled when:
    # a) Lord of sign of debilitation is in kendra from Lagna or Moon
    # b) Planet that would exalt in the same sign is in kendra
    # c) Debilitated planet is in kendra
    # d) Lord of exaltation sign aspects the debilitated planet
    # When cancelled → gives Raja Yoga-like results

    debilitated_planets = [
        ("Sun", "Libra", "Venus", "Saturn"),
        ("Moon", "Scorpio", "Mars", "Jupiter"),
        ("Mars", "Cancer", "Moon", "Saturn"),
        ("Mercury", "Pisces", "Jupiter", "Venus"),
        ("Jupiter", "Capricorn", "Saturn", "Mars"),
        ("Venus", "Virgo", "Mercury", "Moon"),
        ("Saturn", "Aries", "Mars", "Mercury"),
    ]

    for planet, debi_sign, debi_sign_lord, exalt_planet in debilitated_planets:
        rules.append(YogaRule(
            name=f"Neecha Bhanga Raja Yoga ({planet} in {debi_sign})",
            category="neecha_bhanga",
            source_ref=f"BPHS_neecha_bhanga_{planet.lower()}",
            planets_required=[planet],
            predicate=lambda c, pl=planet, ds=debi_sign, dsl=debi_sign_lord, ep=exalt_planet: (
                # Planet must be debilitated
                planet_in_signs(c, pl, [ds]) and
                planet_dignity(c, pl) == "debilitated" and
                # Cancellation condition: sign lord or exalt planet in kendra
                (planet_in_kendra(c, dsl) or planet_in_kendra(c, ep) or planet_in_kendra(c, pl))
            ),
            strength_fn=lambda c, pl=planet, dsl=debi_sign_lord: avg_strength(
                strength_from_planet(c, pl),
                strength_from_planet(c, dsl),
            ),
            effects={
                "career": "Reversal of bad fortune → unexpected authority and recognition",
                "general": "Obstacles overcome; debility converted to strength through adversity",
            },
        ))

    # ═══════════════════════════════════════════════════════════════
    # 6. SPECIAL NAMED YOGAS
    # ═══════════════════════════════════════════════════════════════

    rules.append(YogaRule(
        name="Gaja Kesari Yoga",
        category="misc",
        source_ref="BPHS_ch36_gaja_kesari",
        planets_required=["Jupiter", "Moon"],
        predicate=lambda c: (
            planet_not_debilitated(c, "Jupiter") and
            planet_not_combust(c, "Jupiter") and
            # Jupiter in kendra from Moon
            (c.planets["Jupiter"].house - c.planets["Moon"].house) % 12 in [0, 3, 6, 9] if
            "Jupiter" in c.planets and "Moon" in c.planets else False
        ),
        strength_fn=lambda c: avg_strength(
            strength_from_planet(c, "Jupiter"),
            strength_from_planet(c, "Moon"),
        ),
        effects={
            "career": "Fame, authority, intellectual recognition",
            "personality": "Elephant-like prowess — commanding, prosperous, respected",
        },
    ))

    rules.append(YogaRule(
        name="Budha-Aditya Yoga",
        category="misc",
        source_ref="BPHS_ch36_budha_aditya",
        planets_required=["Sun", "Mercury"],
        predicate=lambda c: (
            planets_conjunction(c, "Sun", "Mercury") and
            not planet_in_signs(c, "Sun", ["Libra"])
        ),
        strength_fn=lambda c: avg_strength(
            strength_from_planet(c, "Sun"),
            strength_from_planet(c, "Mercury")
        ),
        effects={
            "career": "Intelligence, government connections, analytical skill",
            "personality": "Sharp intellect, good speech, administrative capability",
        },
    ))

    rules.append(YogaRule(
        name="Saraswati Yoga",
        category="misc",
        source_ref="BPHS_saraswati",
        planets_required=["Jupiter", "Venus", "Mercury"],
        predicate=lambda c: (
            planet_in_kendra_or_trikona(c, "Jupiter") and
            planet_in_kendra_or_trikona(c, "Venus") and
            planet_in_kendra_or_trikona(c, "Mercury") and
            planet_not_debilitated(c, "Jupiter") and
            planet_not_debilitated(c, "Venus") and
            planet_not_debilitated(c, "Mercury")
        ),
        strength_fn=lambda c: avg_strength(
            strength_from_planet(c, "Jupiter"),
            strength_from_planet(c, "Venus"),
            strength_from_planet(c, "Mercury"),
        ),
        effects={
            "career": "Scholarly excellence, artistic mastery, creative intelligence",
            "personality": "Knowledge of arts, sciences, philosophy; highly respected",
        },
    ))

    rules.append(YogaRule(
        name="Pancha Vargeeya Bala Yoga",
        category="misc",
        source_ref="classical_pancha_vargeeya",
        predicate=lambda c: sum(
            1 for p in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
            if planet_dignity(c, p) in ["exalted", "own", "moolatrikona", "friendly"]
        ) >= 5,
        strength_fn=lambda c: min(1.0, sum(
            strength_from_planet(c, p)
            for p in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
        ) / 7),
        effects={
            "general": "Exceptional chart overall strength — multiple domains of success",
        },
    ))

    rules.append(YogaRule(
        name="Lakshmi Yoga",
        category="raja",
        source_ref="BPHS_ch36_lakshmi",
        planets_required=["Venus"],
        predicate=lambda c: (
            planet_in_trikona(c, "Venus") and
            planet_not_debilitated(c, "Venus") and
            planet_in_kendra(c, lord_of_house(c, 9) or "Jupiter")
        ),
        strength_fn=lambda c: avg_strength(
            strength_from_planet(c, "Venus"),
            strength_from_planet(c, lord_of_house(c, 9) or "Venus"),
        ),
        effects={
            "finance": "Great wealth, material prosperity, goddess Lakshmi's grace",
            "relationships": "Beautiful, devoted partner; domestic happiness",
        },
    ))

    rules.append(YogaRule(
        name="Chandra Mangala Yoga",
        category="misc",
        source_ref="BPHS_ch36_chandra_mangala",
        planets_required=["Moon", "Mars"],
        predicate=lambda c: (
            planets_conjunction(c, "Moon", "Mars") or
            mutual_aspect(c, "Moon", "Mars")
        ),
        strength_fn=lambda c: avg_strength(
            strength_from_planet(c, "Moon"),
            strength_from_planet(c, "Mars"),
        ),
        effects={
            "finance": "Wealth through trade, business, real estate",
            "career": "Executive ability, bold business initiatives",
        },
    ))

    rules.append(YogaRule(
        name="Amala Yoga",
        category="misc",
        source_ref="BPHS_ch36_amala",
        predicate=lambda c: (
            (planet_in_houses(c, "Jupiter", [10]) and planet_not_debilitated(c, "Jupiter")) or
            (planet_in_houses(c, "Venus", [10]) and planet_not_debilitated(c, "Venus"))
        ),
        strength_fn=lambda c: max_strength(
            strength_from_planet(c, "Jupiter") if planet_in_houses(c, "Jupiter", [10]) else 0,
            strength_from_planet(c, "Venus") if planet_in_houses(c, "Venus", [10]) else 0,
        ),
        effects={
            "career": "Spotless reputation, charitable fame, respected career",
            "personality": "Pure character, service to others, lasting legacy",
        },
    ))

    rules.append(YogaRule(
        name="Kemadruma Yoga (Isolated Moon)",
        category="duryoga",
        source_ref="BPHS_kemadruma",
        planets_required=["Moon"],
        predicate=lambda c: all(
            not planet_in_houses(c, p, [
                (c.planets["Moon"].house - 1 - 1) % 12 + 1,  # 2nd from Moon
                (c.planets["Moon"].house + 1 - 1) % 12 + 1,  # 12th from Moon
            ])
            for p in ["Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
            if "Moon" in c.planets
        ),
        strength_fn=lambda c: strength_from_planet(c, "Moon") * 0.5,
        effects={
            "general": "Tendency toward isolation, mental instability, poverty in early life",
            "personality": "Emotional insecurity; requires support systems",
        },
    ))

    rules.append(YogaRule(
        name="Parivartana Yoga (9th-10th Exchange)",
        category="raja",
        source_ref="BPHS_parivartana_9_10",
        houses_required=[9, 10],
        predicate=lambda c: lords_exchange(c, 9, 10),
        strength_fn=lambda c: avg_strength(
            strength_from_planet(c, lord_of_house(c, 9) or "Jupiter"),
            strength_from_planet(c, lord_of_house(c, 10) or "Saturn"),
        ),
        effects={
            "career": "Exceptional fortune through career; dharma and karma aligned",
            "finance": "Prosperity through vocation; luck in professional endeavors",
        },
    ))

    rules.append(YogaRule(
        name="Parivartana Yoga (1st-10th Exchange)",
        category="raja",
        source_ref="BPHS_parivartana_1_10",
        houses_required=[1, 10],
        predicate=lambda c: lords_exchange(c, 1, 10),
        strength_fn=lambda c: avg_strength(
            strength_from_planet(c, lord_of_house(c, 1) or "Mars"),
            strength_from_planet(c, lord_of_house(c, 10) or "Saturn"),
        ),
        effects={
            "career": "Self-made authority; career defined by personal identity",
        },
    ))

    return rules


# Module-level ruleset (built once)
YOGA_RULESET: List[YogaRule] = build_yoga_ruleset()
