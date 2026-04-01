"""
AIS Vimshottari Dasha Engine
Computes the planetary period sequence from birth Moon nakshatra.

Vimshottari System (120-year cycle):
Ketu(7) → Venus(20) → Sun(6) → Moon(10) → Mars(7) →
Rahu(18) → Jupiter(16) → Saturn(19) → Mercury(17)

Total = 120 years
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Tuple
import swisseph as swe
import pytz

from app.core.models import DashaPeriod


# ─── Dasha Sequences & Durations ───────────────────────────────────────────────

MAHADASHA_ORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars",
                   "Rahu", "Jupiter", "Saturn", "Mercury"]

MAHADASHA_YEARS = {
    "Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
    "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17
}

# Which nakshatra (0-26) starts which Mahadasha lord
NAKSHATRA_LORDS = [
    "Ketu", "Venus", "Sun", "Moon", "Mars",     # Ashwini-Mrigashira
    "Rahu", "Jupiter", "Saturn", "Mercury",       # Ardra-Ashlesha
    "Ketu", "Venus", "Sun", "Moon", "Mars",       # Magha-Chitra
    "Rahu", "Jupiter", "Saturn", "Mercury",       # Swati-Jyeshtha
    "Ketu", "Venus", "Sun", "Moon", "Mars",       # Mula-Sravana
    "Rahu", "Jupiter", "Saturn", "Mercury",       # Dhanishtha-Revati
]

ANTARDASHA_ORDER_RELATIVE = {
    # Antardasha starts with same planet as Mahadasha
    lord: MAHADASHA_ORDER[MAHADASHA_ORDER.index(lord):] + MAHADASHA_ORDER[:MAHADASHA_ORDER.index(lord)]
    for lord in MAHADASHA_ORDER
}

DAYS_PER_YEAR = 365.25


class VimshottariDasha:
    """
    Computes Vimshottari Mahadasha + Antardasha sequence from birth Moon nakshatra.
    """

    def get_dasha_sequence(
        self,
        moon_long: float,
        birth_jd: float,
        count: int = 10,
    ) -> Tuple[DashaPeriod, List[DashaPeriod]]:
        """
        Compute current and upcoming Dasha periods.

        Args:
            moon_long: Moon's sidereal longitude (0-360)
            birth_jd: Birth Julian Day
            count: Number of future periods to return

        Returns: (current_dasha, list of next dashas)
        """
        nakshatra_idx = int(moon_long / (360.0 / 27))
        nakshatra_idx = min(nakshatra_idx, 26)

        # Fraction elapsed in birth nakshatra
        nakshatra_span = 360.0 / 27
        fraction_elapsed = (moon_long % nakshatra_span) / nakshatra_span

        # Starting Mahadasha
        start_lord = NAKSHATRA_LORDS[nakshatra_idx]
        start_lord_idx = MAHADASHA_ORDER.index(start_lord)

        # Elapsed portion of first Mahadasha
        first_md_years = MAHADASHA_YEARS[start_lord]
        elapsed_years = fraction_elapsed * first_md_years

        # Birth datetime from JD
        birth_utc = self._jd_to_datetime(birth_jd)

        # Build full sequence of Mahadashas from birth
        all_periods: List[DashaPeriod] = []
        current_start = birth_utc - timedelta(days=elapsed_years * DAYS_PER_YEAR)

        # Generate enough Mahadashas to cover now + future
        for cycle in range(3):  # 3 full 120-year cycles
            for md_offset in range(9):
                md_idx = (start_lord_idx + md_offset + cycle * 9) % 9
                md_lord = MAHADASHA_ORDER[md_idx]
                md_years = MAHADASHA_YEARS[md_lord]
                md_end = current_start + timedelta(days=md_years * DAYS_PER_YEAR)

                # Generate Antardashas within this Mahadasha
                antardasha_order = ANTARDASHA_ORDER_RELATIVE[md_lord]
                ad_start = current_start
                for ad_lord in antardasha_order:
                    ad_years = (md_years * MAHADASHA_YEARS[ad_lord]) / 120.0
                    ad_end = ad_start + timedelta(days=ad_years * DAYS_PER_YEAR)
                    all_periods.append(DashaPeriod(
                        mahadasha=md_lord,
                        antardasha=ad_lord,
                        start_date=ad_start.strftime("%Y-%m-%d"),
                        end_date=ad_end.strftime("%Y-%m-%d"),
                        elapsed_fraction=0.0,  # filled below
                    ))
                    ad_start = ad_end

                current_start = md_end

        # Find current period
        now = datetime.utcnow()
        current_idx = 0
        for i, period in enumerate(all_periods):
            pd_start = datetime.strptime(period.start_date, "%Y-%m-%d")
            pd_end = datetime.strptime(period.end_date, "%Y-%m-%d")
            if pd_start <= now < pd_end:
                current_idx = i
                total_days = (pd_end - pd_start).days or 1
                elapsed_days = (now - pd_start).days
                all_periods[i] = all_periods[i].model_copy(
                    update={"elapsed_fraction": elapsed_days / total_days}
                )
                break

        current = all_periods[current_idx]
        future = all_periods[current_idx + 1: current_idx + count + 1]
        return current, future

    def _jd_to_datetime(self, jd: float) -> datetime:
        """Convert Julian Day to Python datetime (UTC)."""
        year, month, day, hour = swe.revjul(jd)
        h = int(hour)
        m = int((hour - h) * 60)
        s = int(((hour - h) * 60 - m) * 60)
        return datetime(int(year), int(month), int(day), h, m, s, tzinfo=pytz.utc)
