"""
Plain-language personal reading builder.

Transforms deterministic chart outputs into a human-facing reading with richer,
chart-specific sections and follow-up answers that avoid repetitive wording.
"""
from __future__ import annotations

from typing import Dict, List

from app.core.models import ChartState, HumanReading, PersonalityProfile, Prediction, QueryRequest


SIGN_STYLE: Dict[str, str] = {
    "Aries": "direct, brave, and fast-moving",
    "Taurus": "steady, loyal, and hard to shake once committed",
    "Gemini": "curious, quick-thinking, and socially alert",
    "Cancer": "protective, emotionally tuned in, and family-minded",
    "Leo": "warm, expressive, and naturally visible",
    "Virgo": "careful, observant, and improvement-focused",
    "Libra": "balanced, graceful, and deeply aware of other people",
    "Scorpio": "intense, private, and highly perceptive",
    "Sagittarius": "optimistic, freedom-seeking, and growth-oriented",
    "Capricorn": "disciplined, ambitious, and quietly strong",
    "Aquarius": "independent, unusual, and future-minded",
    "Pisces": "sensitive, imaginative, and compassionate",
}

MOON_STYLE: Dict[str, str] = {
    "Aries": "feel quickly and prefer honesty over emotional guessing games",
    "Taurus": "need steadiness, loyalty, and a sense of safety before opening fully",
    "Gemini": "process emotions through conversation, ideas, and mental movement",
    "Cancer": "carry strong emotional memory and bond deeply with people and places",
    "Leo": "need warmth, appreciation, and heartfelt connection",
    "Virgo": "notice subtle details and can carry hidden inner pressure",
    "Libra": "seek harmony and can be deeply affected by imbalance around you",
    "Scorpio": "feel everything intensely and do not connect superficially",
    "Sagittarius": "need space, truth, and a sense of possibility to feel emotionally alive",
    "Capricorn": "guard feelings carefully and reveal them slowly over time",
    "Aquarius": "need emotional honesty without clinginess or drama",
    "Pisces": "absorb atmospheres strongly and need both softness and boundaries",
}

PLANET_FOCUS: Dict[str, str] = {
    "Sun": "identity, pride, and purpose",
    "Moon": "emotions, comfort, and instinct",
    "Mercury": "thinking, communication, and decision-making",
    "Venus": "love, attraction, and harmony",
    "Mars": "drive, courage, and initiative",
    "Jupiter": "growth, meaning, and wisdom",
    "Saturn": "responsibility, patience, and life lessons",
    "Rahu": "desire, appetite, and restless ambition",
    "Ketu": "detachment, past familiarity, and inner release",
}

HOUSE_MEANINGS: Dict[int, str] = {
    1: "identity and self-confidence",
    2: "money, voice, family, and stability",
    3: "communication, courage, and self-expression",
    4: "home, roots, emotional security, and private life",
    5: "creativity, romance, joy, and self-expression",
    6: "work pressure, health routines, and everyday effort",
    7: "love, partnership, and long-term commitment",
    8: "deep change, trust, fear, and emotional intensity",
    9: "belief, growth, learning, and life direction",
    10: "career, reputation, work, and responsibility",
    11: "income, friendships, support, and long-range goals",
    12: "rest, isolation, healing, sleep, and inner life",
}

DOMAIN_KEYWORDS: Dict[str, tuple[str, ...]] = {
    "relationships": ("love", "relationship", "marriage", "partner", "dating", "romance", "husband", "wife"),
    "career": ("career", "job", "work", "profession", "promotion", "office", "boss"),
    "finance": ("money", "finance", "income", "wealth", "business", "salary", "earning"),
    "health": ("health", "body", "illness", "stress", "sleep", "energy", "healing"),
    "spirituality": ("spiritual", "faith", "purpose", "karma", "growth", "travel", "meaning"),
}


def infer_life_domain(query: str | None, explicit_domain: str = "general") -> str:
    if explicit_domain != "general":
        return explicit_domain

    normalized_query = (query or "").strip().lower()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(keyword in normalized_query for keyword in keywords):
            return domain
    return explicit_domain


def build_human_reading(
    chart: ChartState,
    request: QueryRequest,
    predictions: List[Prediction],
    personality: PersonalityProfile,
) -> HumanReading:
    first_name = _first_name(request.birth_data.full_name)
    strongest = max(chart.planets.values(), key=lambda planet: planet.shadbala_strength)
    weakest = min(chart.planets.values(), key=lambda planet: planet.shadbala_strength)
    effective_domain = infer_life_domain(request.query, request.life_domain)

    title = f"{first_name}, your personal reading"
    intro = (
        f"You come through as {SIGN_STYLE.get(chart.lagna, 'distinctive and layered')}, while emotionally you often "
        f"{MOON_STYLE.get(chart.moon_sign, 'respond very strongly to what happens around you')}. "
        f"One of the strongest repeating themes in your chart is {HOUSE_MEANINGS.get(strongest.house, 'personal growth')}."
    )

    return HumanReading(
        title=title,
        intro=intro,
        personality_traits=_build_personality_traits(chart, personality, strongest.name),
        emotional_patterns=_build_emotional_patterns(chart),
        relationship_patterns=_build_relationship_patterns(chart),
        career_and_money=_build_career_and_money(chart),
        past_patterns=_build_past_patterns(chart),
        current_phase=_build_current_phase(chart, predictions, effective_domain),
        future_guidance=_build_future_guidance(chart, predictions, effective_domain),
        strengths_to_use=_build_strengths_to_use(chart, personality),
        areas_to_watch=_build_areas_to_watch(chart, predictions, weakest.name),
        life_highlights=_build_life_highlights(chart, effective_domain),
        chat_starters=_build_chat_starters(first_name, effective_domain),
    )


def build_chat_response(
    chart: ChartState,
    request: QueryRequest,
    reading: HumanReading,
    predictions: List[Prediction],
) -> str:
    query = (request.query or "").strip()
    normalized_query = query.lower()
    effective_domain = infer_life_domain(query, request.life_domain)

    if any(token in normalized_query for token in ("who am i", "personality", "nature", "trait")):
        parts = reading.personality_traits[:2] + reading.emotional_patterns[:1]
        return _join_sentences(parts)

    if effective_domain == "relationships":
        parts = reading.relationship_patterns[:2] + reading.future_guidance[:1]
        return _join_sentences(parts)

    if effective_domain in {"career", "finance"}:
        parts = reading.career_and_money[:2] + reading.future_guidance[:1]
        return _join_sentences(parts)

    if effective_domain == "health":
        parts = reading.areas_to_watch[:2] + reading.current_phase[:1]
        return _join_sentences(parts)

    if any(token in normalized_query for token in ("past", "before", "childhood", "earlier")):
        parts = reading.past_patterns[:2] + reading.life_highlights[:1]
        return _join_sentences(parts)

    if any(token in normalized_query for token in ("future", "ahead", "next", "coming")):
        parts = reading.future_guidance[:2] + _prediction_fragments(predictions, "positive")
        return _join_sentences(parts)

    if any(token in normalized_query for token in ("current", "now", "present", "phase")):
        parts = reading.current_phase[:2] + reading.areas_to_watch[:1]
        return _join_sentences(parts)

    if any(token in normalized_query for token in ("strength", "gift", "talent", "best")):
        parts = reading.strengths_to_use[:2] + reading.life_highlights[:1]
        return _join_sentences(parts)

    if any(token in normalized_query for token in ("problem", "challenge", "weakness", "struggle", "watch")):
        parts = reading.areas_to_watch[:2] + reading.future_guidance[:1]
        return _join_sentences(parts)

    direct_answer = _answer_from_predictions(predictions, effective_domain)
    parts = [direct_answer] + reading.current_phase[:1] + reading.future_guidance[:1]
    return _join_sentences(parts)


def _build_personality_traits(chart: ChartState, personality: PersonalityProfile, strongest_name: str) -> List[str]:
    mercury = chart.planets["Mercury"]
    mars = chart.planets["Mars"]
    traits = [
        f"You tend to present yourself as {SIGN_STYLE.get(chart.lagna, 'steady and memorable')}.",
        f"Your emotional world suggests you {MOON_STYLE.get(chart.moon_sign, 'feel deeply and respond quickly to your surroundings')}.",
        f"Your mind is often drawn toward {HOUSE_MEANINGS.get(mercury.house, 'clearer thinking and better decisions')}, so you think best when life has movement and purpose.",
        f"A strong engine in your personality comes from {strongest_name.lower()}, which gives extra force around {HOUSE_MEANINGS.get(chart.planets[strongest_name].house, 'an important part of life')}.",
    ]
    if personality.archetypes:
        traits.append(f"People may experience you as {personality.archetypes[0].replace('The ', '').lower()} energy: noticeable, distinct, and not easy to ignore.")
    return _dedupe(traits, limit=5)


def _build_emotional_patterns(chart: ChartState) -> List[str]:
    moon = chart.planets["Moon"]
    venus = chart.planets["Venus"]
    fourth_house = chart.houses[4]
    patterns = [
        f"Emotionally, you keep returning to themes of {HOUSE_MEANINGS.get(moon.house, 'inner stability')}.",
        f"In close connection, you are drawn toward {HOUSE_MEANINGS.get(venus.house, 'love and harmony')} and tend to value sincerity over shallow attention.",
    ]
    if fourth_house.occupants:
        patterns.append(
            f"Your private life can feel especially charged because home and emotional security are linked with {', '.join(fourth_house.occupants)} in your chart."
        )
    else:
        patterns.append("You may not always show everything on the surface, but your inner world needs real safety before it fully relaxes.")
    return _dedupe(patterns, limit=4)


def _build_relationship_patterns(chart: ChartState) -> List[str]:
    venus = chart.planets["Venus"]
    seventh_house = chart.houses[7]
    seventh_lord = chart.planets[seventh_house.lord]
    fifth_house = chart.houses[5]

    items = [
        f"Relationships are a serious growth area in your life, with long-term themes tied to {HOUSE_MEANINGS.get(seventh_lord.house, 'commitment and emotional maturity')}.",
        f"In love, you are usually looking for more than surface chemistry. You want connection that supports {HOUSE_MEANINGS.get(venus.house, 'real harmony and meaningful shared life')}.",
    ]
    if seventh_house.occupants:
        items.append(
            f"You are likely to attract strong personalities or meaningful mirrors through partnership because {', '.join(seventh_house.occupants)} shape your relationship zone."
        )
    if fifth_house.occupants:
        items.append(
            f"Romance and attraction are colored by {', '.join(fifth_house.occupants)}, so desire and emotional expression may feel especially vivid at certain times."
        )
    if len(items) < 4:
        items.append("You tend to do best in relationships that combine emotional honesty, shared direction, and enough room to remain yourself.")
    return _dedupe(items, limit=4)


def _build_career_and_money(chart: ChartState) -> List[str]:
    tenth_house = chart.houses[10]
    tenth_lord = chart.planets[tenth_house.lord]
    second_house = chart.houses[2]
    eleventh_house = chart.houses[11]
    sun = chart.planets["Sun"]
    saturn = chart.planets["Saturn"]

    items = [
        f"Career growth is tied to {HOUSE_MEANINGS.get(tenth_lord.house, 'responsibility and visible results')}, so your work path tends to reward patience and a long view.",
        f"Money patterns are closely linked to {HOUSE_MEANINGS.get(chart.planets[second_house.lord].house, 'how you build stability')}, which means income improves most when your choices are consistent rather than impulsive.",
        f"You are likely to take work seriously because both pride and responsibility are connected to {HOUSE_MEANINGS.get(sun.house, 'what you build in the world')} and {HOUSE_MEANINGS.get(saturn.house, 'where discipline is required')}.",
    ]
    if eleventh_house.occupants:
        items.append(
            f"Support, networks, and gains are influenced by {', '.join(eleventh_house.occupants)}, so the right people matter more than random speed."
        )
    else:
        items.append("Steady effort, the right circle, and reputation-building matter more for you than shortcuts.")
    return _dedupe(items, limit=4)


def _build_past_patterns(chart: ChartState) -> List[str]:
    saturn = chart.planets["Saturn"]
    ketu = chart.planets["Ketu"]
    items = [
        f"Your earlier life seems to have taught you lessons around {HOUSE_MEANINGS.get(saturn.house, 'patience and emotional maturity')} sooner than average.",
        f"There is also a strong pattern of letting go, resetting, or outgrowing old situations connected to {HOUSE_MEANINGS.get(ketu.house, 'a sensitive life area')}.",
    ]
    if saturn.house in {1, 4, 7, 10}:
        items.append("You may have felt pressure to become responsible early, which can make you strong but also harder on yourself than others realize.")
    if ketu.house in {8, 12}:
        items.append("Some of your deepest growth seems to come through periods of withdrawal, inner change, or learning to trust life after uncertainty.")
    if len(items) < 4:
        items.append("A repeating past theme is becoming wiser through experience rather than getting easy answers immediately.")
    return _dedupe(items, limit=4)


def _build_current_phase(chart: ChartState, predictions: List[Prediction], effective_domain: str) -> List[str]:
    dasha = chart.current_dasha
    strongest = max(chart.planets.values(), key=lambda planet: planet.shadbala_strength)
    supportive = [item for item in predictions if item.severity == "positive"]
    challenging = [item for item in predictions if item.severity == "challenging"]

    opening = (
        "Your present cycle looks more supportive than restrictive, especially if you move with discipline instead of rushing."
        if len(supportive) >= len(challenging)
        else "Your present cycle asks for patience, cleaner boundaries, and fewer forced decisions."
    )
    items = [
        opening,
        f"The strongest activity right now is around {HOUSE_MEANINGS.get(strongest.house, 'a major part of your life story')}.",
        f"This current period runs through {dasha.end_date}, so the next several months are better for steady shaping than sudden extremes.",
    ]
    if effective_domain != "general":
        items.append(f"You may feel this most clearly in your {effective_domain} life.")
    return _dedupe(items, limit=4)


def _build_future_guidance(chart: ChartState, predictions: List[Prediction], effective_domain: str) -> List[str]:
    weakest = min(chart.planets.values(), key=lambda planet: planet.shadbala_strength)
    positive = [item for item in predictions if item.severity == "positive"]
    challenging = [item for item in predictions if item.severity == "challenging"]

    items = []
    if len(positive) >= len(challenging):
        items.append("What is ahead looks more constructive than blocked, especially if you stay consistent with the choices you already know are right.")
        items.append("The next stretch favors long-term decisions, calmer momentum, and building something real instead of chasing quick reassurance.")
    else:
        items.append("The road ahead still has openings, but it improves when you become more selective with your time, energy, and trust.")
        items.append("Future progress may come in steps rather than one dramatic break, so patience matters more than speed.")

    items.append(
        f"One place to be especially thoughtful is {HOUSE_MEANINGS.get(weakest.house, 'the more sensitive side of life')}, because wiser handling there improves everything else."
    )
    if effective_domain != "general":
        items.append(f"This future story is especially active in your {effective_domain} path.")
    return _dedupe(items, limit=4)


def _build_strengths_to_use(chart: ChartState, personality: PersonalityProfile) -> List[str]:
    strongest = sorted(chart.planets.values(), key=lambda planet: planet.shadbala_strength, reverse=True)[:2]
    items = [
        f"One of your biggest strengths is the ability to grow through {HOUSE_MEANINGS.get(strongest[0].house, 'important life experience')} instead of staying stuck.",
        f"You also carry extra resilience around {HOUSE_MEANINGS.get(strongest[1].house, 'a key part of life')}, which helps you recover and keep moving.",
    ]
    if personality.strengths:
        items.append(_sanitize_personality_hint(personality.strengths[0]))
    if chart.active_yogas:
        items.append("Your chart shows built-in support for rising after pressure, which is why effort often pays off after a slower start.")
    return _dedupe(items, limit=4)


def _build_areas_to_watch(chart: ChartState, predictions: List[Prediction], weakest_name: str) -> List[str]:
    weakest = chart.planets[weakest_name]
    items = [
        f"One recurring challenge is around {HOUSE_MEANINGS.get(weakest.house, 'a sensitive life area')}, where you may need more patience and self-awareness than average.",
        f"{PLANET_FOCUS.get(weakest.name, weakest.name)} can feel more sensitive in your chart, so forcing outcomes there usually backfires.",
    ]
    if any(item.severity == "challenging" for item in predictions):
        items.append("When life feels delayed, the chart suggests that slower structure will serve you better than pushing harder in frustration.")
    else:
        items.append("Even in stronger periods, the chart still rewards steadiness, emotional honesty, and better pacing.")
    return _dedupe(items, limit=4)


def _build_life_highlights(chart: ChartState, effective_domain: str) -> List[str]:
    moon = chart.planets["Moon"]
    sun = chart.planets["Sun"]
    highlights = [
        f"A major thread in your life is learning how to balance {HOUSE_MEANINGS.get(moon.house, 'inner life')} with {HOUSE_MEANINGS.get(sun.house, 'outer responsibility')}.",
        "You are not built for a flat life path. Growth seems to happen when you choose honesty over image and depth over noise.",
        f"One of your long-term breakthroughs comes from becoming more confident around {HOUSE_MEANINGS.get(chart.houses[1].number, 'who you are')}.",
    ]
    if effective_domain != "general":
        highlights.append(f"Your current questions about {effective_domain} are not random. They connect to a real active thread in your chart.")
    return _dedupe(highlights, limit=4)


def _build_chat_starters(first_name: str, effective_domain: str) -> List[str]:
    starters = [
        f"What is {first_name}'s strongest gift according to this chart?",
        "What relationship pattern keeps repeating in my life?",
        "What part of my career path looks strongest right now?",
        "What should I be careful about over the next year?",
    ]
    if effective_domain == "relationships":
        starters.insert(1, "Why do I attract the kind of relationships I do?")
    if effective_domain in {"career", "finance"}:
        starters.insert(1, "What kind of work suits my natural strengths best?")
    return _dedupe(starters, limit=5)


def _answer_from_predictions(predictions: List[Prediction], effective_domain: str) -> str:
    for prediction in predictions:
        if prediction.domain == effective_domain:
            return _strip_technical_language(prediction.statement)
    if predictions:
        return _strip_technical_language(predictions[0].statement)
    return "Your chart suggests a meaningful period of growth, but the most useful results will come from moving steadily instead of looking for instant certainty."


def _prediction_fragments(predictions: List[Prediction], severity: str) -> List[str]:
    items = [
        _strip_technical_language(prediction.statement)
        for prediction in predictions
        if prediction.severity == severity
    ]
    return _dedupe(items, limit=1)


def _strip_technical_language(text: str) -> str:
    cleaned = text
    replacements = {
        "dasha": "current cycle",
        "transit": "current timing",
        "house lord": "key life area",
        "house lords": "key life areas",
        "yoga": "supportive chart pattern",
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new).replace(old.title(), new.capitalize())
    return cleaned


def _first_name(full_name: str | None) -> str:
    if not full_name:
        return "Friend"
    return full_name.strip().split()[0]


def _sanitize_personality_hint(text: str) -> str:
    sanitized = text.replace("house", "part of life").replace("planet", "inner pattern")
    if ":" in sanitized:
        sanitized = sanitized.split(":", 1)[-1].strip()
    if not sanitized.endswith("."):
        sanitized += "."
    return sanitized


def _join_sentences(items: List[str]) -> str:
    sentences = _dedupe(items, limit=3)
    text = " ".join(item.strip() for item in sentences if item.strip())
    if not text.endswith("."):
        text += "."
    return text


def _dedupe(items: List[str], limit: int) -> List[str]:
    deduped: List[str] = []
    for item in items:
        normalized = item.strip()
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped[:limit]
