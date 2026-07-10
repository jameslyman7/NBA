"""League standings from nba_api."""

from __future__ import annotations

import pandas as pd
from nba_api.stats.endpoints import leaguestandingsv3

from nba_stats.utils import current_season, to_dataframe


def get_standings(season: str | None = None) -> pd.DataFrame:
    """
    Fetch current league standings for an NBA season.

    Args:
        season: Season string like '2025-26'. Defaults to the current season.

    Returns:
        DataFrame with team records, ranks, and conference info.
    """
    season = season or current_season()
    endpoint = leaguestandingsv3.LeagueStandingsV3(season=season)
    return to_dataframe(endpoint.standings)
