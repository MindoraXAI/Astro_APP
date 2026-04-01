"""
AIS ALM Orchestrator
LangGraph workflow combining deterministic astrology with optional LLM synthesis.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, TypedDict
from loguru import logger

from app.alm.companion_reports import build_asl_report
from app.alm.guardrails import apply_guardrails
from app.alm.human_reading import build_chat_response, build_human_reading, infer_life_domain
from app.alm.prompts import build_system_prompt, build_user_prompt
from app.alm.rule_engine import build_rule_based_narrative, generate_rule_based_predictions
from app.core.config import settings
from app.core.models import ASLReport, ChartState, HumanReading, PersonalityProfile, Prediction, PredictionOutput, QueryRequest
from app.ephemeris.engine import get_engine
from app.rag.retriever import get_retriever
from app.services.location import resolve_birth_data
from app.symbolic.yoga_engine import get_yoga_engine


class AstroState(TypedDict):
    request: QueryRequest
    chart: Optional[ChartState]
    retrieved_context: str
    llm_raw_output: str
    predictions: List[Prediction]
    personality: Optional[PersonalityProfile]
    evidence_chain: str
    asl_report: Optional[ASLReport]
    human_reading: Optional[HumanReading]
    chat_response: str
    errors: List[str]


def node_chart_computer(state: AstroState) -> AstroState:
    try:
        effective_domain = infer_life_domain(
            state["request"].query,
            state["request"].life_domain,
        )
        if effective_domain != state["request"].life_domain:
            state["request"] = state["request"].model_copy(update={"life_domain": effective_domain})

        resolved_birth_data = resolve_birth_data(state["request"].birth_data)
        state["request"] = state["request"].model_copy(update={"birth_data": resolved_birth_data})

        chart = get_engine().compute_chart(
            resolved_birth_data,
            tradition=state["request"].tradition,
        )
        state["chart"] = chart
        logger.info(f"Chart computed: {chart.lagna} lagna, {chart.moon_sign} Moon")
    except Exception as exc:
        logger.error(f"Chart computation failed: {exc}")
        state["errors"].append(f"Ephemeris error: {exc}")
    return state


def node_yoga_detector(state: AstroState) -> AstroState:
    if not state.get("chart"):
        return state
    try:
        yogas = get_yoga_engine().detect_yogas(state["chart"])
        state["chart"] = state["chart"].model_copy(update={"active_yogas": yogas})
        logger.info(f"Yoga detection: {len(yogas)} active yogas")
    except Exception as exc:
        logger.error(f"Yoga detection failed: {exc}")
        state["errors"].append(f"Yoga engine error: {exc}")
    return state


def node_knowledge_retriever(state: AstroState) -> AstroState:
    if not state.get("chart"):
        return state
    try:
        retriever = get_retriever()
        results = retriever.retrieve(
            user_query=state["request"].query or "general chart reading",
            chart=state["chart"],
            life_domain=state["request"].life_domain,
            top_k=10,
        )
        state["retrieved_context"] = retriever.format_context(results)
        logger.info(f"RAG retrieved {len(results)} passages")
    except Exception as exc:
        logger.warning(f"RAG retrieval failed (continuing without): {exc}")
        state["retrieved_context"] = "Knowledge base retrieval unavailable for this query."
    return state


def node_synthesis_agent(state: AstroState) -> AstroState:
    if not state.get("chart"):
        state["llm_raw_output"] = "Unable to generate predictions: chart data unavailable."
        return state

    if not settings.ENABLE_LLM_SYNTHESIS:
        state["llm_raw_output"] = ""
        return state

    try:
        system_prompt = build_system_prompt(state["chart"], state["request"])
        user_prompt = build_user_prompt(
            state["request"].query or "Provide a comprehensive chart analysis",
            state["chart"],
            state["retrieved_context"],
        )

        if settings.nvidia_chat_api_key:
            from openai import OpenAI

            client = OpenAI(
                base_url=settings.NVIDIA_NIM_BASE_URL,
                api_key=settings.nvidia_chat_api_key,
            )
            response = client.chat.completions.create(
                model=settings.NVIDIA_CHAT_MODEL,
                temperature=0.25,
                max_tokens=768,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = response.choices[0].message.content or ""
        else:
            from langchain_core.messages import HumanMessage, SystemMessage
            from langchain_ollama import ChatOllama

            llm = ChatOllama(
                base_url=settings.OLLAMA_BASE_URL,
                model=settings.OLLAMA_MODEL,
                temperature=0.25,
                num_predict=768,
            )
            response = llm.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )
            content = response.content

        state["llm_raw_output"] = content
        logger.info(
            f"LLM synthesis complete via {settings.active_llm_provider}: {len(content)} chars"
        )
    except Exception as exc:
        logger.error(f"LLM synthesis failed: {exc}")
        state["llm_raw_output"] = ""
        state["errors"].append(f"LLM error: {exc}")
    return state


def node_guardrail_checker(state: AstroState) -> AstroState:
    if not state.get("llm_raw_output"):
        return state
    state["llm_raw_output"] = apply_guardrails(state["llm_raw_output"], state.get("chart"))
    return state


def node_citation_builder(state: AstroState) -> AstroState:
    chart = state.get("chart")
    if not chart:
        return state

    try:
        predictions = generate_rule_based_predictions(chart, state["request"])
        state["predictions"] = predictions

        yoga_names = ", ".join(y.name for y in chart.active_yogas[:3]) or "none detected"
        cd = chart.current_dasha
        state["evidence_chain"] = (
            f"{chart.lagna} Lagna -> {chart.moon_sign} Moon -> Active yogas: [{yoga_names}] -> "
            f"Current dasha: {cd.mahadasha}-{cd.antardasha} ({cd.start_date} to {cd.end_date}) -> "
            f"Retrieved {len(state['retrieved_context'])} chars of classical references -> "
            f"Generated {len(predictions)} deterministic predictions"
        )

        if not state.get("llm_raw_output"):
            state["llm_raw_output"] = build_rule_based_narrative(chart, state["request"], predictions)

        state["personality"] = PersonalityProfile(
            archetypes=_determine_archetypes(chart),
            strengths=_determine_strengths(chart),
            growth_areas=_determine_growth_areas(chart),
            shadow_themes=_determine_shadow_themes(chart),
        )
        state["asl_report"] = build_asl_report(chart, state["request"])
        state["human_reading"] = build_human_reading(
            chart=chart,
            request=state["request"],
            predictions=predictions,
            personality=state["personality"],
        )
        state["chat_response"] = build_chat_response(
            chart=chart,
            request=state["request"],
            reading=state["human_reading"],
            predictions=predictions,
        )
    except Exception as exc:
        logger.error(f"Citation builder failed: {exc}")
        state["errors"].append(f"Citation error: {exc}")

    return state


def _determine_archetypes(chart: ChartState) -> List[str]:
    archetype_map = {
        "Aries": "The Pioneer",
        "Taurus": "The Builder",
        "Gemini": "The Communicator",
        "Cancer": "The Nurturer",
        "Leo": "The Sovereign",
        "Virgo": "The Analyst",
        "Libra": "The Diplomat",
        "Scorpio": "The Transformer",
        "Sagittarius": "The Explorer",
        "Capricorn": "The Strategist",
        "Aquarius": "The Visionary",
        "Pisces": "The Mystic",
    }
    moon_archetypes = {
        "Aries": "The Warrior",
        "Taurus": "The Sensualist",
        "Cancer": "The Caretaker",
        "Leo": "The Creator",
        "Scorpio": "The Alchemist",
        "Capricorn": "The Elder",
        "Aquarius": "The Rebel",
        "Pisces": "The Dreamer",
    }

    archetypes = [archetype_map.get(chart.lagna, "The Seeker")]
    moon_archetype = moon_archetypes.get(chart.moon_sign)
    if moon_archetype and moon_archetype not in archetypes:
        archetypes.append(moon_archetype)
    return archetypes[:3]


def _determine_strengths(chart: ChartState) -> List[str]:
    strengths: List[str] = []
    for yoga in chart.active_yogas[:3]:
        if yoga.effect_personality and yoga.effect_personality not in strengths:
            strengths.append(yoga.effect_personality)
    if not strengths:
        strongest = max(chart.planets.values(), key=lambda planet: planet.shadbala_strength)
        strengths.append(f"{strongest.name} is comparatively strong, giving resilience through house {strongest.house}.")
    return strengths[:4]


def _determine_growth_areas(chart: ChartState) -> List[str]:
    weakest = min(chart.planets.values(), key=lambda planet: planet.shadbala_strength)
    return [
        f"{weakest.name} is the most sensitive planet in this chart, so house {weakest.house} themes need patience and conscious work.",
    ]


def _determine_shadow_themes(chart: ChartState) -> List[str]:
    themes = []
    for house in [6, 8, 12]:
        house_state = chart.houses.get(house)
        if house_state and house_state.occupants:
            themes.append(f"House {house} holds {', '.join(house_state.occupants)}, highlighting karmic work in that area.")
    return themes[:3]


async def run_alm(request: QueryRequest) -> PredictionOutput:
    initial_state: AstroState = {
        "request": request,
        "chart": None,
        "retrieved_context": "",
        "llm_raw_output": "",
        "predictions": [],
        "personality": None,
        "evidence_chain": "",
        "asl_report": None,
        "human_reading": None,
        "chat_response": "",
        "errors": [],
    }

    start = datetime.utcnow()
    result = initial_state
    for step in (
        node_chart_computer,
        node_yoga_detector,
        node_knowledge_retriever,
        node_synthesis_agent,
        node_guardrail_checker,
        node_citation_builder,
    ):
        result = step(result)
    elapsed_ms = int((datetime.utcnow() - start).total_seconds() * 1000)

    if not result.get("chart"):
        raise RuntimeError("Chart computation failed: " + "; ".join(result.get("errors", ["unknown"])))

    return PredictionOutput(
        chart_state=result["chart"],
        predictions=result.get("predictions", []),
        personality_profile=result.get("personality") or PersonalityProfile(
            archetypes=["The Seeker"],
            strengths=[],
            growth_areas=[],
            shadow_themes=[],
        ),
        evidence_chain=result.get("evidence_chain", ""),
        asl_report=result.get("asl_report"),
        human_reading=result.get("human_reading"),
        chat_response=result.get("chat_response") or None,
        meta={
            "alm_version": "2.0.0",
            "tradition": request.tradition,
            "house_system": "whole_sign",
            "ayanamsa": "lahiri",
            "processing_time_ms": elapsed_ms,
            "errors": result.get("errors", []),
            "llm_synthesis_enabled": settings.ENABLE_LLM_SYNTHESIS,
        },
    )
