"""
Deterministic rule-based interpretation layer.

This module converts chart state into structured, auditable predictions without
depending on an LLM.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from app.core.models import ChartState, Prediction, QueryRequest


DOMAIN_HOUSES: Dict[str, List[int]] = {
    "career": [1, 6, 10, 11],
    "health": [1, 6, 8],
    "relationships": [2, 5, 7, 11],
    "finance": [2, 9, 10, 11],
    "spirituality": [5, 8, 9, 12],
    "general": [1, 4, 7, 10],
}


def generate_rule_based_predictions(chart: ChartState, request: QueryRequest) -> List[Prediction]:
    houses = DOMAIN_HOUSES.get(request.life_domain, DOMAIN_HOUSES["general"])
    domain_lord_names = [chart.houses[house].lord for house in houses]
    domain_lords = [chart.planets[lord_name] for lord_name in domain_lord_names if lord_name in chart.planets]
    strong_lords = [planet for planet in domain_lords if planet.shadbala_strength >= 0.62]
    weak_lords = [planet for planet in domain_lords if planet.shadbala_strength <= 0.42]
    supportive_yogas = [
        yoga for yoga in chart.active_yogas
        if yoga.category in {"pancha_mahapurusha", "raja", "dhana", "viparita", "neecha_bhanga"}
    ]
    challenging_yogas = [yoga for yoga in chart.active_yogas if yoga.category == "duryoga"]
    relevant_transits = [
        transit for transit in chart.active_transits
        if transit.natal_house in houses or transit.planet in domain_lord_names
    ]

    domain_signal = "steady"
    if len(strong_lords) >= len(weak_lords) + 1 or supportive_yogas:
        domain_signal = "supportive"
    elif len(weak_lords) > len(strong_lords) + 1 or challenging_yogas:
        domain_signal = "challenging"

    confidence = _compute_confidence(chart, request, strong_lords, weak_lords, supportive_yogas)
    timing_start = chart.current_dasha.start_date
    timing_end = chart.current_dasha.end_date

    primary_statement = _build_primary_statement(
        chart=chart,
        request=request,
        signal=domain_signal,
        strong_lords=strong_lords,
        weak_lords=weak_lords,
        supportive_yogas=supportive_yogas,
        challenging_yogas=challenging_yogas,
    )
    timing_statement = _build_timing_statement(chart, request, relevant_transits, strong_lords, weak_lords)
    advice_statement = _build_advice_statement(request, strong_lords, weak_lords, relevant_transits)

    predictions = [
        Prediction(
            id=f"pred_{datetime.utcnow().strftime('%Y%m%d')}_{request.life_domain}_001",
            domain=request.life_domain,
            statement=primary_statement,
            confidence=confidence,
            confidence_basis=_confidence_basis(chart, strong_lords, supportive_yogas),
            activation_window={"start": timing_start, "end": timing_end},
            source_rules=_source_rules(chart, houses, supportive_yogas, relevant_transits),
            severity=_signal_to_severity(domain_signal),
            action_recommendations=_recommendations(request.life_domain, strong_lords, weak_lords, relevant_transits),
            caveat=_caveat(request),
        ),
        Prediction(
            id=f"pred_{datetime.utcnow().strftime('%Y%m%d')}_{request.life_domain}_002",
            domain=request.life_domain,
            statement=timing_statement,
            confidence=max(0.4, round(confidence - 0.05, 2)),
            confidence_basis=f"Current dasha {chart.current_dasha.mahadasha}-{chart.current_dasha.antardasha} with transit overlay",
            activation_window={"start": timing_start, "end": timing_end},
            source_rules=_source_rules(chart, houses, supportive_yogas[:1], relevant_transits),
            severity="neutral",
            action_recommendations=_recommendations(request.life_domain, strong_lords, weak_lords, relevant_transits),
            caveat=_caveat(request),
        ),
        Prediction(
            id=f"pred_{datetime.utcnow().strftime('%Y%m%d')}_{request.life_domain}_003",
            domain=request.life_domain,
            statement=advice_statement,
            confidence=max(0.38, round(confidence - 0.08, 2)),
            confidence_basis="House lord strength and transit-sensitive guidance",
            activation_window={"start": timing_start, "end": timing_end},
            source_rules=_source_rules(chart, houses, supportive_yogas[:1], relevant_transits),
            severity="positive" if domain_signal == "supportive" else "neutral",
            action_recommendations=_recommendations(request.life_domain, strong_lords, weak_lords, relevant_transits),
            caveat=_caveat(request),
        ),
    ]

    return predictions


def build_rule_based_narrative(chart: ChartState, request: QueryRequest, predictions: List[Prediction]) -> str:
    top_yogas = ", ".join(yoga.name for yoga in chart.active_yogas[:3]) or "no dominant yogas"
    return (
        f"{request.life_domain.title()} reading for {chart.lagna} lagna with {chart.moon_sign} Moon. "
        f"The chart is currently moving through {chart.current_dasha.mahadasha}-{chart.current_dasha.antardasha}, "
        f"and the strongest themes come from {top_yogas}. "
        f"{' '.join(prediction.statement for prediction in predictions[:2])}"
    )


def _build_primary_statement(
    chart: ChartState,
    request: QueryRequest,
    signal: str,
    strong_lords,
    weak_lords,
    supportive_yogas,
    challenging_yogas,
) -> str:
    domain = request.life_domain
    top_yoga = supportive_yogas[0] if supportive_yogas else None
    strong_names = ", ".join(f"{planet.name} in house {planet.house}" for planet in strong_lords[:2])
    weak_names = ", ".join(f"{planet.name} in house {planet.house}" for planet in weak_lords[:2])

    if signal == "supportive":
        yoga_fragment = f"supported by {top_yoga.name}" if top_yoga else "supported by strong house lords"
        return (
            f"The current {domain} period shows constructive momentum, {yoga_fragment}. "
            f"Strong signals come from {strong_names or 'well-placed chart factors'}, so growth is more likely when actions stay disciplined and timely."
        )
    if signal == "challenging":
        challenge = challenging_yogas[0].name if challenging_yogas else "weaker domain lords"
        return (
            f"The chart suggests a more demanding phase for {domain}, especially because of {challenge}. "
            f"{weak_names or 'Several sensitive placements'} indicate delays or pressure rather than denial, so progress depends on patience, structure, and better timing."
        )
    return (
        f"The {domain} outlook is mixed but workable. "
        f"The chart shows both support and friction, with {strong_names or 'some solid placements'} helping balance "
        f"{weak_names or 'more delicate areas that need conscious handling'}."
    )


def _build_timing_statement(chart: ChartState, request: QueryRequest, relevant_transits, strong_lords, weak_lords) -> str:
    transit_fragment = ""
    if relevant_transits:
        transit = relevant_transits[0]
        transit_fragment = (
            f" The transit of {transit.planet} through house {transit.natal_house} from the Moon adds an extra emphasis during this window."
        )
    elif strong_lords:
        transit_fragment = f" The stronger domain lord {strong_lords[0].name} helps the present dasha deliver clearer results."
    elif weak_lords:
        transit_fragment = f" Because {weak_lords[0].name} is weaker, results may mature more slowly than expected."

    return (
        f"The most active timing window runs through the current dasha period, "
        f"{chart.current_dasha.mahadasha}-{chart.current_dasha.antardasha}, ending on {chart.current_dasha.end_date}."
        f"{transit_fragment}"
    )


def _build_advice_statement(request: QueryRequest, strong_lords, weak_lords, relevant_transits) -> str:
    domain = request.life_domain
    strong_hint = strong_lords[0].name if strong_lords else "the stronger chart factors"
    weak_hint = weak_lords[0].name if weak_lords else "the more sensitive areas"
    transit_hint = relevant_transits[0].planet if relevant_transits else "current transit conditions"
    return (
        f"For {domain}, lean into {strong_hint}'s strengths while managing {weak_hint} more carefully. "
        f"Use {transit_hint} as a timing cue for deliberate action, and avoid forcing outcomes before the chart's present cycle stabilizes."
    )


def _compute_confidence(chart: ChartState, request: QueryRequest, strong_lords, weak_lords, supportive_yogas) -> float:
    confidence = 0.5
    confidence += min(len(strong_lords), 3) * 0.06
    confidence -= min(len(weak_lords), 3) * 0.04
    if supportive_yogas:
        confidence += min(supportive_yogas[0].strength * 0.18, 0.16)
    if request.birth_data.time_confidence != "exact":
        confidence -= 0.05
    return round(max(0.35, min(confidence, 0.9)), 2)


def _confidence_basis(chart: ChartState, strong_lords, supportive_yogas) -> str:
    fragments = [f"dasha {chart.current_dasha.mahadasha}-{chart.current_dasha.antardasha}"]
    if strong_lords:
        fragments.append(f"strong lord {strong_lords[0].name}")
    if supportive_yogas:
        fragments.append(f"yoga {supportive_yogas[0].name}")
    return " + ".join(fragments)


def _source_rules(chart: ChartState, houses: List[int], supportive_yogas, relevant_transits) -> List[str]:
    rules = [f"house_lord_{house}_in_{chart.planets[chart.houses[house].lord].house}" for house in houses]
    rules.append(f"dasha_{chart.current_dasha.mahadasha.lower()}_{chart.current_dasha.antardasha.lower()}")
    for yoga in supportive_yogas:
        if yoga.source_ref:
            rules.append(yoga.source_ref)
    for transit in relevant_transits:
        rules.append(f"transit_{transit.planet.lower()}_{transit.natal_house}")
    deduped: List[str] = []
    for rule in rules:
        if rule not in deduped:
            deduped.append(rule)
    return deduped[:8]


def _signal_to_severity(signal: str) -> str:
    if signal == "supportive":
        return "positive"
    if signal == "challenging":
        return "challenging"
    return "neutral"


def _recommendations(domain: str, strong_lords, weak_lords, relevant_transits) -> List[str]:
    tips = []
    if strong_lords:
        tips.append(f"Act through the strengths of {strong_lords[0].name} and prioritize areas linked to house {strong_lords[0].house}.")
    if weak_lords:
        tips.append(f"Build consistency around {weak_lords[0].name}-related themes before expecting fast results.")
    if relevant_transits:
        tips.append(f"Use the current {relevant_transits[0].planet} transit as a timing filter for important moves.")
    if domain == "health":
        tips.append("Treat health readings as reflective only and use professionals for diagnosis or treatment.")
    return tips[:3]


def _caveat(request: QueryRequest) -> str:
    if request.birth_data.time_confidence == "exact":
        return "Reading is more stable because the birth time is marked exact, but outcomes remain tendencies rather than certainties."
    return "Interpretation uses an approximate birth time, so house-level timing should be treated with extra caution."
