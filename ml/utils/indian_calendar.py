# ml/utils/indian_calendar.py
# Indian Railways domain: holidays cause major traffic and delay spikes.
# Used by both feature engineering and Prophet forecaster.

from datetime import date, timedelta
import pandas as pd

# Approximate dates for recurring Indian holidays.
# Format: (month, day) — year-independent.
INDIAN_HOLIDAYS: dict[str, list[tuple[int, int]]] = {
    "Republic Day":    [(1, 26)],
    "Holi":            [(3, 14), (3, 25), (3, 6)],
    "Ram Navami":      [(4, 2),  (4, 21)],
    "Eid al-Fitr":     [(4, 10), (4, 30), (3, 31)],
    "Eid al-Adha":     [(6, 17), (7, 7),  (6, 28)],
    "Independence":    [(8, 15)],
    "Onam":            [(8, 30), (9, 8)],
    "Navratri":        [(10, 3), (10, 22), (10, 13)],
    "Dussehra":        [(10, 12), (10, 24), (10, 15)],
    "Diwali":          [(11, 1), (10, 21), (11, 12)],
    "Chhath Puja":     [(11, 3), (10, 23)],
    "Guru Nanak":      [(11, 19), (11, 8)],
    "Christmas":       [(12, 25)],
    "New Year Eve":    [(12, 31)],
}
def get_holidays_for_year(year: int) -> list[dict]:
    """
    Return a list of holiday dicts for a given year.
    Format matches Prophet's holidays DataFrame.
    """
    holidays = []
    for name, occurrences in INDIAN_HOLIDAYS.items():
        for month, day in occurrences:
            try:
                d = date(year, month, day)
                holidays.append({
                    "holiday":    name,
                    "ds":         d.strftime("%Y-%m-%d"),
                    "lower_window": -3,   # Capture pre-holiday traffic surge
                    "upper_window":  3,   # And post-holiday
                })
            except ValueError:
                continue
    return holidays


def build_prophet_holidays(years: list[int]) -> "pd.DataFrame":
    """Build a Prophet-compatible holidays DataFrame for given years."""
    import pandas as pd
    rows = []
    for year in years:
        rows.extend(get_holidays_for_year(year))
    return pd.DataFrame(rows)


def is_holiday_window(d: date, window: int = 3) -> bool:
    """True if date is within `window` days of a major Indian holiday."""
    for occurrences in INDIAN_HOLIDAYS.values():
        for month, day in occurrences:
            try:
                holiday = d.replace(month=month, day=day)
                if abs((d - holiday).days) <= window:
                    return True
            except ValueError:
                continue
    return False


# Seasonal label for a given month
SEASON_MAP = {
    12: "fog", 1: "fog",
    6:  "monsoon", 7: "monsoon", 8: "monsoon", 9: "monsoon",
    10: "harvest", 11: "harvest",
    4:  "summer", 5: "summer",
}


def get_season(month: int) -> str:
    return SEASON_MAP.get(month, "normal")