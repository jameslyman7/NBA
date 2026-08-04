"""Schedule and scoreboard data from nba_api."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
from nba_api.stats.endpoints import scheduleleaguev2, scoreboardv3

from nba_stats.transform import schedule_rows_to_league_results
from nba_stats.utils import (
    api_pause,
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

    Merges scoreboard results with odds (NBA live or ESPN historical) when available.
    """
    daily_games = get_daily_games(game_date)
    if daily_games.empty:
        return schedule_rows_to_league_results(pd.DataFrame())

    merged = daily_games.copy()
    if odds_summary is not None and not odds_summary.empty:
        odds = odds_summary.copy()
        team_lines = _odds_summary_to_team_lines(odds)
        if not team_lines.empty:
            merged = merged.merge(team_lines, on="team_tricode", how="left")
        else:
            merged["spread"] = None
            merged["total"] = None
    else:
        merged["spread"] = None
        merged["total"] = None

    return schedule_rows_to_league_results(merged)


def _odds_summary_to_team_lines(odds: pd.DataFrame) -> pd.DataFrame:
    """
    Expand one-row-per-game odds into one-row-per-team spread/total lines.

    Prefers home_tricode/away_tricode when present (ESPN + enriched live odds).
    Falls back to NBA game_id + home/away team ids via scoreboard merge keys.
    """
    rows: list[dict] = []

    has_tricodes = {"home_tricode", "away_tricode"}.issubset(odds.columns)
    if has_tricodes:
        for _, row in odds.iterrows():
            home = row.get("home_tricode")
            away = row.get("away_tricode")
            total = row.get("over_total")
            if home:
                rows.append(
                    {
                        "team_tricode": home,
                        "spread": row.get("home_spread"),
                        "total": total,
                    }
                )
            if away:
                rows.append(
                    {
                        "team_tricode": away,
                        "spread": row.get("away_spread"),
                        "total": total,
                    }
                )
        return pd.DataFrame(rows)

    # Legacy path: require game_id and attach later via location — kept for safety.
    if "game_id" not in odds.columns:
        return pd.DataFrame(columns=["team_tricode", "spread", "total"])

    return pd.DataFrame(columns=["team_tricode", "spread", "total"])


def _parse_boxscore_date(value) -> date:
    text = str(value).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized game date: {value!r}")


def build_season_league_results(
    season: str | None = None,
    include_odds: bool = True,
) -> pd.DataFrame:
    """
    Build a full-season league_results.csv using team game logs + ESPN lines.

    One row per team per game (30 * 82 = 2460 for a full regular season).
    """
    from nba_stats.boxscores import get_season_team_boxscores
    from nba_stats.odds import get_espn_odds_for_date

    season = season or current_season()
    team_df = get_season_team_boxscores(season=season)
    if team_df.empty:
        return schedule_rows_to_league_results(pd.DataFrame())

    games = pd.DataFrame(
        {
            "team_tricode": team_df["Team"],
            "matchup": team_df["Match up"],
            "game_date": team_df["Date"],
            "wl": team_df["W/L"],
            "team_pts": team_df["Pts"],
            "opp_pts": team_df["Opp Pts"],
        }
    )
    games["_date"] = games["game_date"].map(_parse_boxscore_date)

    if include_odds:
        odds_parts: list[pd.DataFrame] = []
        unique_dates = sorted(games["_date"].unique())
        for index, game_date in enumerate(unique_dates, start=1):
            print(
                f"Fetching ESPN odds {index}/{len(unique_dates)} ({game_date.isoformat()})...",
                flush=True,
            )
            _, summary = get_espn_odds_for_date(game_date)
            lines = _odds_summary_to_team_lines(summary)
            if not lines.empty:
                lines = lines.copy()
                lines["_date"] = game_date
                odds_parts.append(lines)
            api_pause(0.2)

        if odds_parts:
            all_odds = pd.concat(odds_parts, ignore_index=True)
            games = games.merge(all_odds, on=["_date", "team_tricode"], how="left")
        else:
            games["spread"] = None
            games["total"] = None
    else:
        games["spread"] = None
        games["total"] = None

    games = games.drop(columns=["_date"])
    return schedule_rows_to_league_results(games)
