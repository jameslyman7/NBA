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


def tricode_from_filename(filename: str) -> str:
    """Map a legacy results/injuries filename stem to a tricode."""
    stem = filename.replace("_injuries.csv", "").replace("_results.csv", "")
    return team_tricode(stem)
