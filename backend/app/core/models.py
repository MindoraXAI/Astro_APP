"""
AIS Shared Pydantic Models
All request/response schemas used across the API.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field, model_validator


# ─────────────────────────────────────────────────────────────────────────────
# INPUT SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class BirthData(BaseModel):
    full_name: Optional[str] = Field(
        None,
        description="Person's full name for personalization and saved readings",
        json_schema_extra={"example": "Aarav Sharma"},
    )
    date: str = Field(
        ...,
        description="ISO date: YYYY-MM-DD",
        json_schema_extra={"example": "1990-01-15"},
    )
    time: str = Field(
        ...,
        description="Local time: HH:MM:SS",
        json_schema_extra={"example": "06:30:00"},
    )
    birth_place: Optional[str] = Field(
        None,
        description="Human-readable place of birth; resolved to coordinates and timezone when needed",
        json_schema_extra={"example": "New Delhi, India"},
    )
    timezone: Optional[str] = Field(
        None,
        description="IANA timezone",
        json_schema_extra={"example": "Asia/Kolkata"},
    )
    latitude: Optional[float] = Field(
        None,
        ge=-90,
        le=90,
        json_schema_extra={"example": 28.6139},
    )
    longitude: Optional[float] = Field(
        None,
        ge=-180,
        le=180,
        json_schema_extra={"example": 77.2090},
    )
    time_confidence: Literal["exact", "approximate", "unknown"] = "approximate"

    @model_validator(mode="before")
    @classmethod
    def normalize_string_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for key in ("full_name", "date", "time", "birth_place", "timezone"):
                value = data.get(key)
                if isinstance(value, str):
                    value = value.strip()
                    data[key] = value or None
        return data

    @model_validator(mode="after")
    def validate_location_inputs(self) -> "BirthData":
        has_resolved_location = (
            self.latitude is not None and
            self.longitude is not None and
            bool(self.timezone)
        )
        if not self.birth_place and not has_resolved_location:
            raise ValueError(
                "Provide either birth_place or the combination of latitude, longitude, and timezone."
            )
        return self


class QueryRequest(BaseModel):
    birth_data: BirthData
    query: Optional[str] = Field(None, description="Free-text question", example="What does my career look like in 2026?")
    life_domain: Literal["career", "health", "relationships", "finance", "spirituality", "general"] = "general"
    tradition: Literal["vedic", "western", "both"] = "vedic"
    time_horizon: Literal["current", "3months", "1year", "3years"] = "1year"
    query_type: Literal["natal", "transit", "dasha", "compatibility", "general"] = "natal"
    known_facts: List[str] = Field(default_factory=list, example=["software engineer", "married"])

    @model_validator(mode="before")
    @classmethod
    def normalize_query_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            query = data.get("query")
            if isinstance(query, str):
                query = query.strip()
                data["query"] = query or None
        return data


# ─────────────────────────────────────────────────────────────────────────────
# CHART STATE SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class PlanetState(BaseModel):
    name: str                           # "Sun", "Moon", "Mars" etc.
    longitude: float                    # absolute ecliptic longitude 0-360
    sign: str                           # "Aries", "Taurus", etc.
    sign_number: int                    # 1-12
    house: int                          # 1-12 (Whole Sign)
    degree_in_sign: float               # 0-30
    nakshatra: str                      # e.g. "Rohini"
    nakshatra_pada: int                 # 1-4
    is_retrograde: bool = False
    is_combust: bool = False
    dignity: Literal["exalted", "own", "moolatrikona", "friendly", "neutral", "enemy", "debilitated"]
    shadbala_strength: float = 0.0      # 0.0 - 1.0 normalized
    house_lord_of: List[int] = []       # which houses this planet rules


class HouseState(BaseModel):
    number: int                         # 1-12
    sign: str
    sign_number: int
    lord: str                           # planet name
    occupants: List[str] = []           # planets in this house
    significations: List[str] = []


class DashaPeriod(BaseModel):
    mahadasha: str
    antardasha: str
    pratyantardasha: Optional[str] = None
    start_date: str                     # ISO date
    end_date: str
    elapsed_fraction: float             # 0.0-1.0


class ActiveYoga(BaseModel):
    name: str
    category: Literal["pancha_mahapurusha", "raja", "dhana", "viparita", "duryoga", "neecha_bhanga", "misc"]
    tradition: Literal["vedic", "western", "both"]
    strength: float                     # 0.0-1.0
    planets_involved: List[str]
    houses_involved: List[int]
    effect_career: Optional[str] = None
    effect_personality: Optional[str] = None
    effect_health: Optional[str] = None
    activation_dasha: Optional[str] = None
    source_ref: str = ""


class TransitEffect(BaseModel):
    planet: str
    from_sign: str
    to_sign: str
    natal_house: int
    effect_strength: float
    description: str
    start_date: str
    end_date: str


class ChartState(BaseModel):
    """Complete computed astrological chart state."""
    # Identity
    lagna: str                          # Ascendant sign
    lagna_degree: float
    moon_sign: str
    sun_sign: str
    tradition: str = "vedic"
    house_system: str = "whole_sign"
    ayanamsa: str = "lahiri"
    ayanamsa_value: float = 0.0

    # Planetary positions
    planets: Dict[str, PlanetState]    # key = planet name

    # House data
    houses: Dict[int, HouseState]      # key = house number 1-12

    # Active yogas (sorted by strength desc)
    active_yogas: List[ActiveYoga] = []

    # Dasha state
    current_dasha: DashaPeriod
    next_dashas: List[DashaPeriod] = []

    # Transit effects (current)
    active_transits: List[TransitEffect] = []

    # Divisional charts (simplified)
    d9_lagna: Optional[str] = None     # Navamsa
    d10_lagna: Optional[str] = None    # Dasamsa

    # Computation metadata
    computed_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    birth_julian_day: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# PREDICTION OUTPUT SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class Prediction(BaseModel):
    id: str
    domain: str
    statement: str
    confidence: float                   # 0.0-1.0
    confidence_basis: str
    activation_window: Dict[str, str]  # {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
    source_rules: List[str]
    severity: Literal["positive", "neutral", "challenging"]
    action_recommendations: List[str] = []
    caveat: Optional[str] = None


class PersonalityProfile(BaseModel):
    archetypes: List[str]
    strengths: List[str]
    growth_areas: List[str]
    shadow_themes: List[str]


class PlanetDigest(BaseModel):
    name: str
    sign: str
    house: int
    nakshatra: str
    dignity: str
    strength: float


class LalKitabInsight(BaseModel):
    planet: str
    focus_area: str
    interpretation: str
    remedy: str


class LalKitabReport(BaseModel):
    summary: str
    house_alerts: List[str]
    remedies: List[LalKitabInsight]
    note: str


class WesternPlacement(BaseModel):
    body: str
    sign: str
    degree: float
    meaning: str


class WesternSnapshot(BaseModel):
    ascendant: str
    sun_sign: str
    moon_sign: str
    placements: List[WesternPlacement]
    themes: List[str]


class ASLReport(BaseModel):
    overview: str
    advanced_signatures: List[str]
    lal_kitab: LalKitabReport
    western_snapshot: WesternSnapshot
    suggested_questions: List[str]
    planetary_matrix: List[PlanetDigest]


class HumanReading(BaseModel):
    title: str
    intro: str
    personality_traits: List[str]
    emotional_patterns: List[str]
    relationship_patterns: List[str]
    career_and_money: List[str]
    past_patterns: List[str]
    current_phase: List[str]
    future_guidance: List[str]
    strengths_to_use: List[str]
    areas_to_watch: List[str]
    life_highlights: List[str]
    chat_starters: List[str]


class PredictionOutput(BaseModel):
    """Full ALM prediction response."""
    chart_state: ChartState
    predictions: List[Prediction]
    personality_profile: PersonalityProfile
    evidence_chain: str
    asl_report: Optional[ASLReport] = None
    human_reading: Optional[HumanReading] = None
    chat_response: Optional[str] = None
    meta: Dict[str, Any] = {}


class LocationResolutionResponse(BaseModel):
    query: str
    latitude: float
    longitude: float
    timezone: str
    display_name: str
    confidence: Optional[float] = None
    candidates_count: Optional[int] = None
