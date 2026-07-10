"""Schedule and scoreboard data from nba_api."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
from nba_api.stats.endpoints import scheduleleaguev2, scoreboardv3

from nba_stats.transform import schedule_rows_to_league_results
from nba_stats.utils import (
    current_season,
    format_game_date,
    is_game_final,
    normalize_game_id,
    to_dataframe,
)


def get_season_schedule(season: str | None = None) -> pd.DataFrame:
    """Fetch the full regular-season schedule for an NBA season."""
    season = season or current_season()
    endpoint = scheduleleaguev2.ScheduleLeagueV2(season=season)
    return to_dataframe(endpoint.season_games)


def get_scoreboard(
    game_date: date | datetime | str | None = None,
) -> dict[str, pd.DataFrame]:
    """Fetch games and line scores for a specific date."""
    if game_date is None:
        game_date = date.today()

    endpoint = scoreboardv3.ScoreboardV3(game_date=format_game_date(game_date))

    return {
        "games": to_dataframe(endpoint.game_header),
        "line_scores": to_dataframe(endpoint.line_score),
        "game_leaders": to_dataframe(endpoint.game_leaders),
        "team_leaders": to_dataframe(endpoint.team_leaders),
    }


def get_daily_games(game_date: date) -> pd.DataFrame:
    """
    Return one row per team for each game on a date with scores and metadata.

    Columns include game_id, team_tricode, matchup, wl, team_pts, opp_pts, game_status.
    """
    board = get_scoreboard(game_date)
    games = board["games"]
    line_scores = board["line_scores"]

    if games.empty or line_scores.empty:
        return pd.DataFrame()

    rows: list[dict] = []
    grouped = line_scores.groupby("gameId", sort=False)

    for _, game in games.iterrows():
        game_id = normalize_game_id(game["gameId"])
        if game_id not in grouped.groups:
            continue

        teams = grouped.get_group(game_id).reset_index(drop=True)
        if len(teams) < 2:
            continue

        home = teams.iloc[0]
        away = teams.iloc[1]
        game_status = game.get("gameStatus")
        final = is_game_final(game_status)

        for team_row, opp_row, location in (
            (home, away, "home"),
            (away, home, "away"),
        ):
            tricode = team_row.get("teamTricode", "")
            opp_tricode = opp_row.get("teamTricode", "")
            if location == "home":
                matchup = f"{tricode} vs. {opp_tricode}"
            else:
                matchup = f"{tricode} @ {opp_tricode}"

            team_pts = team_row.get("score")
            opp_pts = opp_row.get("score")
            wl = ""
            if final and pd.notna(team_pts) and pd.notna(opp_pts):
                wl = "W" if float(team_pts) > float(opp_pts) else "L"

            rows.append(
                {
                    "game_id": game_id,
                    "game_date": game_date,
                    "game_status": game_status,
                    "game_status_text": game.get("gameStatusText"),
                    "team_tricode": tricode,
                    "team_id": team_row.get("teamId"),
                    "opp_tricode": opp_tricode,
                    "matchup": matchup,
                    "wl": wl,
                    "team_pts": team_pts,
                    "opp_pts": opp_pts,
                    "location": location,
                }
            )

    return pd.DataFrame(rows)


def get_final_game_ids(game_date: date) -> list[str]:
    """Return game IDs for completed games on a date."""
    board = get_scoreboard(game_date)
    games = board["games"]
    if games.empty:
        return []

    return [
        normalize_game_id(row["gameId"])
        for _, row in games.iterrows()
        if is_game_final(row.get("gameStatus"))
    ]


def build_daily_league_results(
    game_date: date,
    odds_summary: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Build league_results.csv-style rows for a date with lines and outcomes.

    Merges scoreboard results with NBA live odds (spread/total) when available.
    """
    daily_games = get_daily_games(game_date)
    if daily_games.empty:
        return schedule_rows_to_league_results(pd.DataFrame())

    merged = daily_games.copy()
    if odds_summary is not None and not odds_summary.empty:
        odds = odds_summary.copy()
        odds["game_id"] = odds["game_id"].map(normalize_game_id)

        home_lines = odds.rename(
            columns={
                "home_spread": "home_spread_line",
                "over_total": "game_total_line",
            }
        )
        away_lines = odds.rename(
            columns={
                "away_spread": "away_spread_line",
                "over_total": "game_total_line",
            }
        )

        merged = merged.merge(
            home_lines[
                [
                    "game_id",
                    "home_spread_line",
                    "game_total_line",
                    "sportsbook",
                ]
            ],
            on="game_id",
            how="left",
        )
        merged = merged.merge(
            away_lines[["game_id", "away_spread_line"]],
            on="game_id",
            how="left",
        )

        merged["spread"] = merged.apply(
            lambda row: row["home_spread_line"]
            if row.get("location") == "home"
            else row.get("away_spread_line"),
            axis=1,
        )
        merged["total"] = merged["game_total_line"]
    else:
        merged["spread"] = None
        merged["total"] = None

    return schedule_rows_to_league_results(merged)
