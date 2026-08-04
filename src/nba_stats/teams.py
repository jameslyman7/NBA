"""Team name and tricode helpers aligned with the legacy NBA scraper project."""

from __future__ import annotations

from nba_api.stats.static import teams as nba_teams

# Matches special cases in C:/Users/crgly/PythonProjects/NBA/Injuries/combined_injuries.py
SPECIAL_TRICODES = {
    "Los Angeles Clippers": "LAC",
    "Los Angeles Lakers": "LAL",
    "New York Knicks": "NYK",
    "New Orleans Pelicans": "NOP",
    "Brooklyn Nets": "BKN",
    "San Antonio Spurs": "SAS",
    "Oklahoma City Thunder": "OKC",
    "Golden State Warriors": "GSW",
}

# ESPN scoreboard abbreviations that differ from nba_api tricodes.
ESPN_TRICODE_MAP = {
    "NY": "NYK",
    "NO": "NOP",
    "SA": "SAS",
    "GS": "GSW",
    "UTAH": "UTA",
    "WSH": "WAS",
    "PHO": "PHX",
    "BRO": "BKN",
    "BK": "BKN",
}


def team_tricode(team_name: str) -> str:
    """Return a 3-letter team code from a full or partial team name."""
    if team_name in SPECIAL_TRICODES:
        return SPECIAL_TRICODES[team_name]

    normalized = team_name.strip()
    for team in nba_teams.get_teams():
        full_name = team["full_name"]
        if normalized.lower() in {full_name.lower(), team["nickname"].lower(), team["abbreviation"].lower()}:
            return team["abbreviation"]

    if len(normalized) == 3 and normalized.isupper():
        return normalized

    return normalized[:3].upper()


def normalize_espn_tricode(abbreviation: str) -> str:
    """Map ESPN team abbreviations onto nba_api tricodes."""
    abbr = (abbreviation or "").strip().upper()
    return ESPN_TRICODE_MAP.get(abbr, abbr)


def tricode_from_team_id(team_id: int | str | None) -> str:
    """Return a tricode for an NBA team ID, or empty string if unknown."""
    if team_id is None:
        return ""
    try:
        tid = int(team_id)
    except (TypeError, ValueError):
        return ""
    for team in nba_teams.get_teams():
        if team["id"] == tid:
            return team["abbreviation"]
    return ""


def tricode_from_filename(filename: str) -> str:
    """Map a legacy results/injuries filename stem to a tricode."""
    stem = filename.replace("_injuries.csv", "").replace("_results.csv", "")
    return team_tricode(stem)
