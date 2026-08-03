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
    playerindex,
)
from nba_api.stats.library.parameters import PlayerOrTeamAbbreviation

from nba_stats.transform import player_logs_to_boxscores, team_logs_to_boxscores
from nba_stats.utils import api_pause, current_season, to_dataframe


def _nba_date_filter(value: date) -> str:
    return value.strftime("%m/%d/%Y")


def get_player_position_map(season: str | None = None) -> dict[int, str]:
    """Return PERSON_ID -> roster POSITION (G, F, C, G-F, ...) for a season."""
    season = season or current_season()
    # historical=1 includes players who left mid-season / prior rosters for that year.
    endpoint = playerindex.PlayerIndex(season=season, historical_nullable="1")
    index = to_dataframe(endpoint.player_index)
    if index.empty or "PERSON_ID" not in index.columns or "POSITION" not in index.columns:
        return {}

    index = index.dropna(subset=["PERSON_ID"]).copy()
    index["POSITION"] = index["POSITION"].fillna("").astype(str)
    # Prefer non-empty positions when PlayerIndex returns duplicate PERSON_IDs.
    index = index.sort_values("POSITION").drop_duplicates("PERSON_ID", keep="last")
    return dict(zip(index["PERSON_ID"].astype(int), index["POSITION"], strict=False))


def _with_positions(raw: pd.DataFrame, season: str) -> pd.DataFrame:
    """Attach roster POSITION from PlayerIndex when PLAYER_ID is present."""
    if raw.empty or "PLAYER_ID" not in raw.columns:
        return raw
    api_pause()
    positions = get_player_position_map(season)
    out = raw.copy()
    out["POSITION"] = out["PLAYER_ID"].map(positions).fillna("")
    return out


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


def get_season_player_boxscores(
    season: str | None = None,
    season_type: str = "Regular Season",
) -> pd.DataFrame:
    """
    Fetch every player box score for a season in legacy boxscores.csv format.

    One PlayerGameLogs call returns the full season; positions come from PlayerIndex.
    """
    season = season or current_season()
    endpoint = playergamelogs.PlayerGameLogs(
        season_nullable=season,
        season_type_nullable=season_type,
    )
    raw = _with_positions(to_dataframe(endpoint.player_game_logs), season)
    return player_logs_to_boxscores(raw)


def get_daily_player_boxscores(
    game_date: date,
    season: str | None = None,
) -> pd.DataFrame:
    """
    Fetch player box scores for a single date in legacy boxscores.csv format.

    Uses PlayerGameLogs with a date filter (same stats as nba.com/stats player box scores),
    enriched with roster positions from PlayerIndex.
    """
    season = season or current_season(game_date)
    date_filter = _nba_date_filter(game_date)
    endpoint = playergamelogs.PlayerGameLogs(
        season_nullable=season,
        season_type_nullable="Regular Season",
        date_from_nullable=date_filter,
        date_to_nullable=date_filter,
    )
    raw = _with_positions(to_dataframe(endpoint.player_game_logs), season)
    return player_logs_to_boxscores(raw)


def get_season_team_boxscores(
    season: str | None = None,
    season_type: str = "Regular Season",
) -> pd.DataFrame:
    """
    Fetch every team box score for a season in legacy team_boxscores.csv format.

    One LeagueGameLog call (team rows) returns the full season.
    """
    season = season or current_season()
    endpoint = leaguegamelog.LeagueGameLog(
        player_or_team_abbreviation=PlayerOrTeamAbbreviation.team,
        season=season,
        season_type_all_star=season_type,
    )
    raw = to_dataframe(endpoint.league_game_log)
    return team_logs_to_boxscores(raw)


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
