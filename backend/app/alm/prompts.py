"""
AIS ALM Prompt Templates
System and user prompt construction for Ollama LLM.
"""
from __future__ import annotations

from app.core.models import ChartState, QueryRequest


def build_system_prompt(chart: ChartState, request: QueryRequest) -> str:
    """Build the system prompt with chart state context."""
    yogas_text = "\n".join(
        f"  - {y.name} (strength: {y.strength:.2f}): {y.effect_career or y.effect_personality or 'see classical texts'}"
        for y in chart.active_yogas[:5]
    ) or "  - No significant yogas detected"

    planet_text = "\n".join(
        f"  - {name}: {p.sign} ({p.dignity}), House {p.house}, {'Retrograde' if p.is_retrograde else 'Direct'}, Shadbala: {p.shadbala_strength:.2f}"
        for name, p in chart.planets.items()
    )

    transit_text = "\n".join(
        f"  - {t.planet} in {t.to_sign} (House {t.natal_house} from Moon): {t.description}"
        for t in chart.active_transits[:4]
    ) or "  - No significant current transits"

    return f"""You are the Astro Language Model (ALM) — a world-class expert in Vedic astrology (Jyotisha) trained on the Brihat Parashara Hora Shastra, Saravali, Phaladeepika, and thousands of classical interpretations.

CRITICAL RULES:
1. You may ONLY make astrological claims that are supported by the chart data below and the retrieved knowledge base passages.
2. Do NOT invent planetary positions, yogas, or combinations not present in the chart data.
3. Express ALL predictions as tendencies and potentials, NOT certainties.
4. Always include appropriate uncertainty language.
5. Do NOT make predictions about death, severe illness timelines, or irreversible negative outcomes.
6. Be specific, evidence-grounded, and compassionate.

═══ CHART DATA ═══
Tradition: {chart.tradition.upper()} | House System: {chart.house_system} | Ayanamsa: {chart.ayanamsa}
Lagna (Ascendant): {chart.lagna} ({chart.lagna_degree:.1f}°)
Moon Sign: {chart.moon_sign}
Sun Sign: {chart.sun_sign}
D9 (Navamsa) Lagna: {chart.d9_lagna or 'Not computed'}
D10 (Dasamsa) Lagna: {chart.d10_lagna or 'Not computed'}

Current Dasha: {chart.current_dasha.mahadasha}-{chart.current_dasha.antardasha}
  Period: {chart.current_dasha.start_date} → {chart.current_dasha.end_date}
  Elapsed: {chart.current_dasha.elapsed_fraction:.1%} of this antardasha

PLANETARY POSITIONS:
{planet_text}

ACTIVE YOGAS (top 5 by strength):
{yogas_text}

CURRENT TRANSITS:
{transit_text}

Query Domain: {request.life_domain.upper()}
Time Horizon: {request.time_horizon}
═══════════════════"""


def build_user_prompt(query: str, chart: ChartState, retrieved_context: str) -> str:
    """Build the user-side prompt with RAG context."""
    return f"""USER QUERY: {query}

{retrieved_context}

Based on the chart data in your system context and the classical references above, provide:

1. A specific, evidence-grounded prediction for the {query} domain
2. The timing window this applies to (reference the current dasha)
3. Key chart factors driving this prediction (cite specific planetary placements or yogas)
4. 2-3 practical recommendations aligned with the chart's energies
5. An honest confidence assessment (acknowledge what's uncertain)

Remember: every claim must trace back to a specific chart factor or classical reference. Be warm, specific, and precise."""
