"""Box score data from nba_api."""

from __future__ import annotations

from datetime import date

import pandas as pd
from nba_api.live.nba.endpoints import boxscore as live_boxscore
from nba_api.stats.endpoints import (
    boxscoretraditionalv3,
    boxscoresummaryv2,
    leaguegamelog,
    playergamelogs,
)
from nba_api.stats.library.parameters import PlayerOrTeamAbbreviation

from nba_stats.transform import player_logs_to_boxscores, team_logs_to_boxscores
from nba_stats.utils import current_season, to_dataframe


def _nba_date_filter(value: date) -> str:
    return value.strftime("%m/%d/%Y")


def get_boxscore(game_id: str) -> dict[str, pd.DataFrame]:
    """Fetch traditional box score stats for a single game."""
    traditional = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=game_id)
    summary = boxscoresummaryv2.BoxScoreSummaryV2(game_id=game_id)

    return {
        "player_stats": to_dataframe(traditional.player_stats),
        "team_stats": to_dataframe(traditional.team_stats),
        "summary": to_dataframe(summary.game_summary),
    }


def get_live_boxscore(game_id: str) -> dict:
    """Fetch live box score JSON from NBA CDN."""
    return live_boxscore.BoxScore(game_id=game_id).get_dict()


def get_daily_player_boxscores(
    game_date: date,
    season: str | None = None,
) -> pd.DataFrame:
    """
    Fetch player box scores for a single date in legacy boxscores.csv format.

    Uses PlayerGameLogs with a date filter (same stats as nba.com/stats player box scores).
    """
    season = season or current_season(game_date)
    date_filter = _nba_date_filter(game_date)
    endpoint = playergamelogs.PlayerGameLogs(
        season_nullable=season,
        season_type_nullable="Regular Season",
        date_from_nullable=date_filter,
        date_to_nullable=date_filter,
    )
    raw = to_dataframe(endpoint.player_game_logs)
    return player_logs_to_boxscores(raw)


def get_daily_team_boxscores(
    game_date: date,
    season: str | None = None,
) -> pd.DataFrame:
    """
    Fetch team box scores for a single date in legacy team_boxscores.csv format.

    Uses LeagueGameLog filtered to team rows for the date.
    """
    season = season or current_season(game_date)
    date_filter = _nba_date_filter(game_date)
    endpoint = leaguegamelog.LeagueGameLog(
        player_or_team_abbreviation=PlayerOrTeamAbbreviation.team,
        season=season,
        season_type_all_star="Regular Season",
        date_from_nullable=date_filter,
        date_to_nullable=date_filter,
    )
    raw = to_dataframe(endpoint.league_game_log)
    return team_logs_to_boxscores(raw)
