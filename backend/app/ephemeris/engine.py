"""
AIS Ephemeris Engine
Wrapper around pyswisseph (Swiss Ephemeris) for precise astrological computation.

Features:
- Planetary positions (longitude, speed, retrograde status)
- Lagna (Ascendant) computation
- Nakshatra and Pada
- Whole Sign + Placidus house cusps
- Lahiri / Raman / Krishnamurti ayanamsa
- Divisional charts: D1, D9 (Navamsa), D10 (Dasamsa)
- Full ChartState assembly
"""
from __future__ import annotations

import swisseph as swe
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple, Optional
from loguru import logger
import pytz

from app.core.models import (
    BirthData, ChartState, PlanetState, HouseState,
    DashaPeriod, TransitEffect
)
from app.core.config import settings
from app.ephemeris.dashas import VimshottariDasha
from app.ephemeris.shadbala import ShadbalaEngine


# ─── Constants ────────────────────────────────────────────────────────────────

PLANET_MAP = {
    "Sun":     swe.SUN,
    "Moon":    swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus":   swe.VENUS,
    "Mars":    swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn":  swe.SATURN,
    "Rahu":    swe.MEAN_NODE,   # North Node (Rahu)
    "Ketu":    None,             # Computed as Rahu + 180
}

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishtha", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
]

# Planetary dignities: sign, exalt, debi, moolat, own signs
DIGNITY_TABLE = {
    "Sun":     {"exalt": 0, "debi": 6, "own": [4], "mool": [4]},     # Aries/Libra, Leo
    "Moon":    {"exalt": 1, "debi": 7, "own": [3], "mool": [3]},     # Taurus/Scorpio, Cancer
    "Mars":    {"exalt": 9, "debi": 3, "own": [0, 7], "mool": [0]},  # Cap/Can, Aries+Scorpio
    "Mercury": {"exalt": 5, "debi": 11, "own": [2, 5], "mool": [5]}, # Virgo/Pisces, Gem+Virgo
    "Jupiter": {"exalt": 3, "debi": 9, "own": [8, 11], "mool": [8]}, # Can/Cap, Sag+Pisces
    "Venus":   {"exalt": 11, "debi": 5, "own": [1, 6], "mool": [6]}, # Pisc/Vir, Tau+Lib
    "Saturn":  {"exalt": 6, "debi": 0, "own": [9, 10], "mool": [9]}, # Lib/Ari, Cap+Aqu
    "Rahu":    {"exalt": 1, "debi": 7, "own": [], "mool": []},       # Tau/Sco (Vedic)
    "Ketu":    {"exalt": 7, "debi": 1, "own": [], "mool": []},       # Sco/Tau (Vedic)
}

# Natural enemies and friends for dignity assessment
PLANETARY_FRIENDS = {
    "Sun":     {"friends": ["Moon", "Mars", "Jupiter"],    "enemies": ["Venus", "Saturn"]},
    "Moon":    {"friends": ["Sun", "Mercury"],             "enemies": []},
    "Mars":    {"friends": ["Sun", "Moon", "Jupiter"],     "enemies": ["Mercury"]},
    "Mercury": {"friends": ["Sun", "Venus"],               "enemies": ["Moon"]},
    "Jupiter": {"friends": ["Sun", "Moon", "Mars"],        "enemies": ["Mercury", "Venus"]},
    "Venus":   {"friends": ["Mercury", "Saturn"],          "enemies": ["Sun", "Moon"]},
    "Saturn":  {"friends": ["Mercury", "Venus"],           "enemies": ["Sun", "Moon", "Mars"]},
    "Rahu":    {"friends": ["Mercury", "Venus", "Saturn"], "enemies": ["Sun", "Moon", "Mars"]},
    "Ketu":    {"friends": ["Mercury", "Venus", "Saturn"], "enemies": ["Sun", "Moon", "Mars"]},
}

AYANAMSA_MAP = {1: swe.SIDM_LAHIRI, 3: swe.SIDM_RAMAN, 5: swe.SIDM_KRISHNAMURTI}
HOUSE_SYSTEM_MAP = {"W": b"W", "P": b"P", "E": b"E", "O": b"O"}


# ─── Engine ───────────────────────────────────────────────────────────────────

class EphemerisEngine:
    """
    Core astrological computation engine using Swiss Ephemeris.
    Fully stateless — each call is independent.
    """

    def __init__(self):
        if settings.SWISSEPH_PATH:
            swe.set_ephe_path(settings.SWISSEPH_PATH)
        ayanamsa_id = AYANAMSA_MAP.get(settings.DEFAULT_AYANAMSA, swe.SIDM_LAHIRI)
        swe.set_sid_mode(ayanamsa_id)
        logger.debug(f"EphemerisEngine initialized: ayanamsa={settings.DEFAULT_AYANAMSA}, house={settings.DEFAULT_HOUSE_SYSTEM}")

    # ── Birth data → Julian Day ──────────────────────────────────────────────

    def birth_data_to_jd(self, birth: BirthData) -> Tuple[float, datetime]:
        """Convert birth data to Julian Day (UT) and obliquity."""
        tz = pytz.timezone(birth.timezone)
        local_dt = datetime.strptime(f"{birth.date} {birth.time}", "%Y-%m-%d %H:%M:%S")
        local_dt = tz.localize(local_dt)
        utc_dt = local_dt.astimezone(pytz.utc)

        jd = swe.julday(
            utc_dt.year, utc_dt.month, utc_dt.day,
            utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0
        )
        return jd, utc_dt

    # ── Planetary positions ──────────────────────────────────────────────────

    def compute_planet(self, jd: float, planet_name: str) -> Dict:
        """Compute sidereal position for a single planet."""
        if planet_name == "Ketu":
            rahu_data = self.compute_planet(jd, "Rahu")
            ketu_long = (rahu_data["longitude"] + 180) % 360
            sign_num = int(ketu_long / 30)
            deg_in_sign = ketu_long % 30
            nakshatra_idx = int(ketu_long / (360 / 27))
            pada = int((ketu_long % (360 / 27)) / (360 / 108)) + 1
            return {
                "longitude": ketu_long,
                "sign": SIGNS[sign_num],
                "sign_number": sign_num + 1,
                "degree_in_sign": deg_in_sign,
                "nakshatra": NAKSHATRAS[nakshatra_idx],
                "nakshatra_pada": pada,
                "speed": -rahu_data["speed"],
                "is_retrograde": True,      # Ketu always treated as retrograde
            }

        planet_id = PLANET_MAP[planet_name]
        flags = swe.FLG_SIDEREAL | swe.FLG_SPEED
        result, _ = swe.calc_ut(jd, planet_id, flags)
        long = result[0]
        speed = result[3]

        sign_num = int(long / 30)
        deg_in_sign = long % 30
        nakshatra_idx = int(long / (360 / 27))
        pada = int((long % (360 / 27)) / (360 / 108)) + 1

        return {
            "longitude": long,
            "sign": SIGNS[sign_num],
            "sign_number": sign_num + 1,
            "degree_in_sign": deg_in_sign,
            "nakshatra": NAKSHATRAS[nakshatra_idx],
            "nakshatra_pada": max(1, min(4, pada)),
            "speed": speed,
            "is_retrograde": speed < 0 and planet_name not in ("Rahu", "Ketu"),
        }

    def compute_tropical_body(self, jd: float, body_name: str) -> Dict[str, Any]:
        """Compute tropical longitude/sign for a single body."""
        if body_name == "Ketu":
            rahu = self.compute_tropical_body(jd, "Rahu")
            longitude = (rahu["longitude"] + 180) % 360
            sign_num = int(longitude / 30)
            return {
                "longitude": longitude,
                "sign": SIGNS[sign_num],
                "sign_number": sign_num + 1,
                "degree_in_sign": longitude % 30,
            }

        planet_id = PLANET_MAP[body_name]
        flags = swe.FLG_SPEED
        result, _ = swe.calc_ut(jd, planet_id, flags)
        longitude = result[0] % 360
        sign_num = int(longitude / 30)
        return {
            "longitude": longitude,
            "sign": SIGNS[sign_num],
            "sign_number": sign_num + 1,
            "degree_in_sign": longitude % 30,
        }

    # ── House cusps ─────────────────────────────────────────────────────────

    def compute_houses(self, jd: float, lat: float, lng: float, system: str = "W") -> Dict:
        """Compute house cusps and Lagna."""
        flags = swe.FLG_SIDEREAL
        sys_byte = HOUSE_SYSTEM_MAP.get(system, b"W")
        cusps, ascmc = swe.houses_ex(jd, lat, lng, sys_byte, flags)
        lagna_long = ascmc[0]  # Ascendant
        sign_num = int(lagna_long / 30)
        return {
            "lagna_longitude": lagna_long,
            "lagna_sign": SIGNS[sign_num],
            "lagna_sign_number": sign_num + 1,
            "cusps": list(cusps),
            "mc_longitude": ascmc[1],
        }

    def compute_tropical_houses(self, jd: float, lat: float, lng: float, system: str = "P") -> Dict[str, Any]:
        """Compute tropical ascendant and cusps for a western-style snapshot."""
        sys_byte = HOUSE_SYSTEM_MAP.get(system, b"P")
        cusps, ascmc = swe.houses_ex(jd, lat, lng, sys_byte, 0)
        lagna_long = ascmc[0]
        sign_num = int(lagna_long / 30)
        return {
            "lagna_longitude": lagna_long,
            "lagna_sign": SIGNS[sign_num],
            "lagna_sign_number": sign_num + 1,
            "cusps": list(cusps),
            "mc_longitude": ascmc[1],
        }

    def compute_tropical_snapshot(self, birth: BirthData) -> Dict[str, Any]:
        """Compute a compact tropical snapshot for companion western reporting."""
        jd, _ = self.birth_data_to_jd(birth)
        house_data = self.compute_tropical_houses(jd, birth.latitude, birth.longitude, "P")
        bodies = {
            body_name: self.compute_tropical_body(jd, body_name)
            for body_name in ["Sun", "Moon", "Mercury", "Venus", "Mars"]
        }
        return {
            "ascendant": house_data["lagna_sign"],
            "sun_sign": bodies["Sun"]["sign"],
            "moon_sign": bodies["Moon"]["sign"],
            "placements": bodies,
        }

    # ── Dignity ─────────────────────────────────────────────────────────────

    def get_dignity(self, planet_name: str, sign_number: int) -> str:
        """Return dignity status of a planet in a given sign (0-indexed sign_num)."""
        sign_idx = sign_number - 1  # Convert 1-indexed to 0-indexed
        dt = DIGNITY_TABLE.get(planet_name)
        if not dt:
            return "neutral"
        if sign_idx == dt["exalt"]:
            return "exalted"
        if sign_idx == dt["debi"]:
            return "debilitated"
        if sign_idx in dt.get("mool", []):
            return "moolatrikona"
        if sign_idx in dt.get("own", []):
            return "own"
        # Determine friend/enemy/neutral based on sign lord
        sign_lord = self._sign_lord(sign_idx)
        friends = PLANETARY_FRIENDS.get(planet_name, {}).get("friends", [])
        enemies = PLANETARY_FRIENDS.get(planet_name, {}).get("enemies", [])
        if sign_lord in friends:
            return "friendly"
        if sign_lord in enemies:
            return "enemy"
        return "neutral"

    def _sign_lord(self, sign_idx: int) -> str:
        """Return the ruling planet of a sign (0-indexed)."""
        lords = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
                 "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"]
        return lords[sign_idx % 12]

    # ── House lordships ─────────────────────────────────────────────────────

    def get_house_lordships(self, lagna_sign_number: int) -> Dict[str, List[int]]:
        """Map each planet to the list of houses it rules (Whole Sign from Lagna)."""
        lords_by_sign = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
                         "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"]
        lordships: Dict[str, List[int]] = {p: [] for p in PLANET_MAP}
        for house_num in range(1, 13):
            sign_idx = (lagna_sign_number - 1 + house_num - 1) % 12
            lord = lords_by_sign[sign_idx]
            lordships[lord].append(house_num)
        return lordships

    # ── Combustion check ────────────────────────────────────────────────────

    def is_combust(self, planet_name: str, planet_long: float, sun_long: float) -> bool:
        """Check if planet is combust (too close to Sun)."""
        combustion_orbs = {
            "Moon": 12, "Mars": 17, "Mercury": 14, "Jupiter": 11,
            "Venus": 10, "Saturn": 15
        }
        orb = combustion_orbs.get(planet_name, 0)
        if orb == 0:
            return False
        diff = abs(planet_long - sun_long) % 360
        if diff > 180:
            diff = 360 - diff
        return diff < orb

    # ── Divisional chart position ────────────────────────────────────────────

    def divisional_longitude(self, longitude: float, division: int) -> Tuple[str, int]:
        """Compute position in a divisional chart (D-N)."""
        sign_idx = int(longitude / 30)
        deg = longitude % 30
        # Division within sign
        division_size = 30 / division
        div_num = int(deg / division_size)

        # D9 (Navamsa): follow fire-earth-air-water cycle from sign's element
        if division == 9:
            # Navamsa starts: moveable=Aries, fixed=Capricorn, dual=Libra
            nature = sign_idx % 3  # 0=moveable, 1=fixed, 2=dual
            navamsa_starts = [0, 9, 6]   # Aries, Cap, Libra (0-indexed)
            start = navamsa_starts[nature]
            nav_sign = (start + div_num) % 12
            return SIGNS[nav_sign], nav_sign + 1
        # D10 (Dasamsa): even signs go forward, odd signs go backward
        elif division == 10:
            if sign_idx % 2 == 0:  # even sign (Aries, Gem, Leo…)
                das_sign = (sign_idx * 1 + div_num) % 12
            else:
                das_sign = (sign_idx + 9 - div_num) % 12
            return SIGNS[das_sign], das_sign + 1

        # Generic
        div_sign = (sign_idx * division + div_num) % 12
        return SIGNS[div_sign], div_sign + 1

    # ── Ashtakavarga (simplified) ────────────────────────────────────────────

    def compute_current_transits(self, natal_chart: ChartState) -> List[TransitEffect]:
        """Compare current planetary positions to natal chart."""
        now_jd, _ = self.birth_data_to_jd(BirthData(
            date=datetime.utcnow().strftime("%Y-%m-%d"),
            time=datetime.utcnow().strftime("%H:%M:%S"),
            timezone="UTC",
            latitude=0,
            longitude=0,
        ))
        effects: List[TransitEffect] = []
        transit_windows = {
            "Jupiter": 365,
            "Saturn": 730,
            "Rahu": 540,
            "Ketu": 540,
            "Mars": 45,
            "Venus": 24,
        }
        for planet_name in ["Jupiter", "Saturn", "Rahu", "Ketu", "Mars", "Venus"]:
            current = self.compute_planet(now_jd, planet_name)
            natal = natal_chart.planets.get(planet_name)
            if not natal:
                continue
            # Compute transit house relative to natal Moon (Vedic Gochara)
            moon_sign_num = natal_chart.planets["Moon"].sign_number
            transit_sign_num = current["sign_number"]
            transit_house = (transit_sign_num - moon_sign_num) % 12 + 1
            effects.append(TransitEffect(
                planet=planet_name,
                from_sign=natal.sign,
                to_sign=current["sign"],
                natal_house=transit_house,
                effect_strength=0.65,
                description=f"{planet_name} transiting {current['sign']} (house {transit_house} from natal Moon)",
                start_date=datetime.utcnow().strftime("%Y-%m-%d"),
                end_date=(datetime.utcnow() + timedelta(days=transit_windows.get(planet_name, 30))).strftime("%Y-%m-%d"),
            ))
        return effects

    # ── Master chart computation ─────────────────────────────────────────────

    def compute_chart(self, birth: BirthData, tradition: str = "vedic") -> ChartState:
        """Compute the full chart state for given birth data."""
        jd, utc_dt = self.birth_data_to_jd(birth)
        house_system = settings.DEFAULT_HOUSE_SYSTEM

        logger.info(f"Computing chart: JD={jd:.4f}, lat={birth.latitude}, lng={birth.longitude}")

        # Ayanamsa value
        ayanamsa_val = swe.get_ayanamsa_ut(jd)

        # Houses
        house_data = self.compute_houses(jd, birth.latitude, birth.longitude, house_system)
        lagna_sign = house_data["lagna_sign"]
        lagna_sign_number = house_data["lagna_sign_number"]

        # House lordships
        lordships = self.get_house_lordships(lagna_sign_number)

        # Planetary positions
        raw_planets: Dict[str, Dict] = {}
        sun_long = 0.0
        for planet_name in PLANET_MAP:
            raw = self.compute_planet(jd, planet_name)
            raw_planets[planet_name] = raw
            if planet_name == "Sun":
                sun_long = raw["longitude"]

        # Build PlanetState objects
        planets: Dict[str, PlanetState] = {}
        for planet_name, raw in raw_planets.items():
            # Whole sign house placement
            planet_sign_num = raw["sign_number"]
            planet_house = (planet_sign_num - lagna_sign_number) % 12 + 1

            dignity = self.get_dignity(planet_name, raw["sign_number"])
            combust = self.is_combust(planet_name, raw["longitude"], sun_long)

            planets[planet_name] = PlanetState(
                name=planet_name,
                longitude=raw["longitude"],
                sign=raw["sign"],
                sign_number=raw["sign_number"],
                house=planet_house,
                degree_in_sign=raw["degree_in_sign"],
                nakshatra=raw["nakshatra"],
                nakshatra_pada=raw["nakshatra_pada"],
                is_retrograde=raw["is_retrograde"],
                is_combust=combust,
                dignity=dignity,
                shadbala_strength=0.5,  # placeholder; Shadbala fills this
                house_lord_of=lordships.get(planet_name, []),
            )

        # Build HouseState objects (Whole Sign)
        houses: Dict[int, HouseState] = {}
        lords_by_sign = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
                         "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"]
        for house_num in range(1, 13):
            sign_idx = (lagna_sign_number - 1 + house_num - 1) % 12
            sign = SIGNS[sign_idx]
            lord = lords_by_sign[sign_idx]
            occupants = [pn for pn, ps in planets.items() if ps.house == house_num]
            houses[house_num] = HouseState(
                number=house_num,
                sign=sign,
                sign_number=sign_idx + 1,
                lord=lord,
                occupants=occupants,
            )

        # Shadbala strength update
        shadbala_engine = ShadbalaEngine()
        shadbala_results = shadbala_engine.compute_all(planets, houses, jd, birth)
        for planet_name, strength in shadbala_results.items():
            if planet_name in planets:
                planets[planet_name] = planets[planet_name].model_copy(
                    update={"shadbala_strength": strength}
                )

        # Dasha sequence
        moon_long = planets["Moon"].longitude
        dasha_engine = VimshottariDasha()
        current_dasha, next_dashas = dasha_engine.get_dasha_sequence(
            moon_long=moon_long,
            birth_jd=jd,
            count=10
        )

        # Divisional charts (lagna in D9, D10)
        d9_sign, _ = self.divisional_longitude(house_data["lagna_longitude"], 9)
        d10_sign, _ = self.divisional_longitude(house_data["lagna_longitude"], 10)

        # Assemble
        chart = ChartState(
            lagna=lagna_sign,
            lagna_degree=house_data["lagna_longitude"] % 30,
            moon_sign=planets["Moon"].sign,
            sun_sign=planets["Sun"].sign,
            tradition=tradition,
            house_system=("whole_sign" if house_system == "W" else house_system.lower()),
            ayanamsa="lahiri" if settings.DEFAULT_AYANAMSA == 1 else str(settings.DEFAULT_AYANAMSA),
            ayanamsa_value=ayanamsa_val,
            planets=planets,
            houses=houses,
            current_dasha=current_dasha,
            next_dashas=next_dashas,
            active_transits=[],  # filled by yoga engine
            d9_lagna=d9_sign,
            d10_lagna=d10_sign,
            birth_julian_day=jd,
        )

        # Active transits
        chart.active_transits = self.compute_current_transits(chart)

        logger.info(f"Chart computed: Lagna={lagna_sign}, Moon={planets['Moon'].sign}, Sun={planets['Sun'].sign}")
        return chart


# ─── Module-level singleton ────────────────────────────────────────────────────

_engine: Optional[EphemerisEngine] = None


def get_engine() -> EphemerisEngine:
    global _engine
    if _engine is None:
        _engine = EphemerisEngine()
    return _engine
