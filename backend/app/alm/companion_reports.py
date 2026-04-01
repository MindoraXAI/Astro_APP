"""
Companion report builders for the ASL experience.

These outputs are inspired by public astrology product patterns such as
multi-mode reports, remedies, and western snapshots, while remaining original
and grounded in the local rule engine.
"""
from __future__ import annotations

from typing import Dict, List

from app.core.models import (
    ASLReport,
    ChartState,
    LalKitabInsight,
    LalKitabReport,
    PlanetDigest,
    QueryRequest,
    WesternPlacement,
    WesternSnapshot,
)
from app.ephemeris.engine import get_engine


HOUSE_LABELS: Dict[int, str] = {
    1: "self, vitality, identity",
    2: "family, voice, stored wealth",
    3: "initiative, courage, communication",
    4: "home, inner stability, mother",
    5: "creativity, children, intelligence",
    6: "health routines, obstacles, service",
    7: "partnerships and agreements",
    8: "transformation, inheritance, uncertainty",
    9: "fortune, dharma, teachers",
    10: "career, work, public standing",
    11: "gains, networks, long-term goals",
    12: "loss, retreat, foreign links, sleep",
}

WESTERN_SIGN_THEMES: Dict[str, str] = {
    "Aries": "direct, initiating, fast-moving",
    "Taurus": "steady, sensual, grounded",
    "Gemini": "curious, conversational, adaptive",
    "Cancer": "protective, emotional, home-oriented",
    "Leo": "expressive, proud, creative",
    "Virgo": "analytical, precise, improvement-focused",
    "Libra": "relational, balancing, aesthetic",
    "Scorpio": "intense, strategic, transformative",
    "Sagittarius": "visionary, exploratory, meaning-seeking",
    "Capricorn": "disciplined, ambitious, structured",
    "Aquarius": "independent, reformist, future-minded",
    "Pisces": "sensitive, imaginative, porous",
}

PLANET_REMEDY_LIBRARY: Dict[str, str] = {
    "Sun": "Strengthen consistency, sunrise routines, gratitude to fatherly mentors, and clear ethical leadership.",
    "Moon": "Protect sleep, hydration, emotional regulation, and regular contact with nurturing spaces or caregivers.",
    "Mars": "Channel pressure into exercise, disciplined action, and conflict handled without haste.",
    "Mercury": "Use journaling, study, precise speech, and cleaner daily planning to stabilize Mercury themes.",
    "Jupiter": "Support teachers, charitable learning, and a weekly wisdom practice before making major judgments.",
    "Venus": "Refine relationships, beauty, and money habits with moderation instead of overindulgence.",
    "Saturn": "Honor time, duty, elders, and repetition. Small disciplined acts work better than dramatic fixes.",
    "Rahu": "Reduce noise, avoid obsession, and use fact-checking before large risks or compulsive decisions.",
    "Ketu": "Ground spiritual drift through practical rituals, reflection, and completion of unfinished matters.",
}

PLANET_PRIORITY = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]


def build_asl_report(chart: ChartState, request: QueryRequest) -> ASLReport:
    return ASLReport(
        overview=_build_overview(chart, request),
        advanced_signatures=_build_advanced_signatures(chart),
        lal_kitab=_build_lal_kitab_report(chart),
        western_snapshot=_build_western_snapshot(request),
        suggested_questions=_build_suggested_questions(chart, request),
        planetary_matrix=_build_planetary_matrix(chart),
    )


def _build_overview(chart: ChartState, request: QueryRequest) -> str:
    lagna_lord = chart.houses[1].lord
    lagna_lord_state = chart.planets[lagna_lord]
    top_yoga = chart.active_yogas[0].name if chart.active_yogas else "house-lord dynamics"
    return (
        f"ASL reads this chart through a Vedic core, timing logic, remedy logic, and a companion western snapshot. "
        f"The native rises in {chart.lagna}, with Lagna lord {lagna_lord} placed in house {lagna_lord_state.house}. "
        f"The emotional filter is {chart.moon_sign} Moon, and the present timing is {chart.current_dasha.mahadasha}-"
        f"{chart.current_dasha.antardasha}. Right now the chart is especially shaped by {top_yoga}."
    )


def _build_advanced_signatures(chart: ChartState) -> List[str]:
    lagna_lord = chart.houses[1].lord
    lagna_lord_state = chart.planets[lagna_lord]
    strongest = max(chart.planets.values(), key=lambda planet: planet.shadbala_strength)
    weakest = min(chart.planets.values(), key=lambda planet: planet.shadbala_strength)
    moon = chart.planets["Moon"]

    signatures = [
        f"Lagna lord {lagna_lord} sits in house {lagna_lord_state.house} in {lagna_lord_state.sign}, shaping the life path.",
        f"Moon is in {moon.nakshatra} pada {moon.nakshatra_pada}, which colors instinctive reactions and timing sensitivity.",
        f"Strongest planet: {strongest.name} in house {strongest.house} with {round(strongest.shadbala_strength * 100)}% relative strength.",
        f"Most sensitive planet: {weakest.name} in house {weakest.house}; this area needs slower, steadier handling.",
        f"Navamsa Lagna is {chart.d9_lagna} and Dasamsa Lagna is {chart.d10_lagna}.",
        f"Current dasha runs through {chart.current_dasha.end_date}; the next major sequence starts with {chart.next_dashas[0].mahadasha}."
        if chart.next_dashas
        else f"Current dasha runs through {chart.current_dasha.end_date}.",
    ]
    return signatures[:6]


def _build_lal_kitab_report(chart: ChartState) -> LalKitabReport:
    difficult_houses = [house for house in (6, 8, 12) if chart.houses[house].occupants]
    difficult_planets = sorted(chart.planets.values(), key=_lal_kitab_weight, reverse=True)

    remedies: List[LalKitabInsight] = []
    for planet in difficult_planets[:4]:
        remedies.append(
            LalKitabInsight(
                planet=planet.name,
                focus_area=HOUSE_LABELS.get(planet.house, "life themes"),
                interpretation=(
                    f"{planet.name} in house {planet.house} in {planet.sign} is treated as a practical adjustment point. "
                    f"Its dignity is {planet.dignity} and the relative strength is {round(planet.shadbala_strength * 100)}%."
                ),
                remedy=_planet_remedy_text(planet.name, planet.house),
            )
        )

    if difficult_houses:
        alerts = [
            f"House {house} is active through {', '.join(chart.houses[house].occupants)}, so {HOUSE_LABELS[house]} deserves extra practical care."
            for house in difficult_houses
        ]
    else:
        weakest = min(chart.planets.values(), key=lambda planet: planet.shadbala_strength)
        alerts = [
            f"The chart is not dominated by dusthana occupancy, so the main correction point is {weakest.name} in house {weakest.house}."
        ]

    summary = (
        "This Lal Kitab-inspired layer stays symbolic and non-harmful: it highlights planets that need correction through discipline, "
        "service, simplicity, and behavior changes rather than superstition."
    )

    return LalKitabReport(
        summary=summary,
        house_alerts=alerts[:3],
        remedies=remedies,
        note="These are reflective, tradition-inspired remedies and not guarantees or substitutes for professional advice.",
    )


def _build_western_snapshot(request: QueryRequest) -> WesternSnapshot:
    tropical = get_engine().compute_tropical_snapshot(request.birth_data)
    placements = []
    for body_name in ["Sun", "Moon", "Mercury", "Venus", "Mars"]:
        body = tropical["placements"][body_name]
        placements.append(
            WesternPlacement(
                body=body_name,
                sign=body["sign"],
                degree=round(body["degree_in_sign"], 2),
                meaning=_western_body_meaning(body_name, body["sign"]),
            )
        )

    themes = [
        f"Tropical Ascendant in {tropical['ascendant']} reads as {WESTERN_SIGN_THEMES.get(tropical['ascendant'], 'distinctive and personal')}.",
        f"Sun in {tropical['sun_sign']} centers identity around {WESTERN_SIGN_THEMES.get(tropical['sun_sign'], 'purpose and self-expression')}.",
        f"Moon in {tropical['moon_sign']} processes emotion through {WESTERN_SIGN_THEMES.get(tropical['moon_sign'], 'feeling and instinct')}.",
    ]

    return WesternSnapshot(
        ascendant=tropical["ascendant"],
        sun_sign=tropical["sun_sign"],
        moon_sign=tropical["moon_sign"],
        placements=placements,
        themes=themes,
    )


def _build_suggested_questions(chart: ChartState, request: QueryRequest) -> List[str]:
    lagna_lord = chart.houses[1].lord
    first_questions = [
        f"What does the {chart.current_dasha.mahadasha}-{chart.current_dasha.antardasha} period mean for my {request.life_domain} path?",
        f"How should I use {lagna_lord} in house {chart.planets[lagna_lord].house} more consciously?",
        f"Which yoga in my chart activates most strongly over the next {request.time_horizon}?",
        f"What practical remedy should I follow for {min(chart.planets.values(), key=lambda planet: planet.shadbala_strength).name}?",
        "What kind of relationships, work style, and spiritual habits suit this chart best?",
    ]

    deduped: List[str] = []
    for question in first_questions:
        if question not in deduped:
            deduped.append(question)
    return deduped[:5]


def _build_planetary_matrix(chart: ChartState) -> List[PlanetDigest]:
    ordered_planets = sorted(
        chart.planets.values(),
        key=lambda planet: PLANET_PRIORITY.index(planet.name) if planet.name in PLANET_PRIORITY else 99,
    )
    return [
        PlanetDigest(
            name=planet.name,
            sign=planet.sign,
            house=planet.house,
            nakshatra=planet.nakshatra,
            dignity=planet.dignity,
            strength=round(planet.shadbala_strength, 2),
        )
        for planet in ordered_planets
    ]


def _lal_kitab_weight(planet) -> float:
    score = 1.0 - planet.shadbala_strength
    if planet.house in {6, 8, 12}:
        score += 0.25
    if planet.dignity in {"debilitated", "enemy"}:
        score += 0.2
    if planet.is_combust:
        score += 0.1
    return score


def _planet_remedy_text(planet_name: str, house: int) -> str:
    house_theme = HOUSE_LABELS.get(house, "daily life")
    base = PLANET_REMEDY_LIBRARY.get(planet_name, "Choose simple, consistent corrective habits.")
    return f"{base} Direct the effort toward {house_theme}."


def _western_body_meaning(body_name: str, sign: str) -> str:
    sign_tone = WESTERN_SIGN_THEMES.get(sign, "distinctive expression")
    body_meanings = {
        "Sun": "identity and will",
        "Moon": "emotion and instinct",
        "Mercury": "thinking and communication",
        "Venus": "relating and taste",
        "Mars": "drive and assertion",
    }
    return f"{body_name} in {sign} emphasizes {body_meanings.get(body_name, 'expression')} through a {sign_tone} style."
