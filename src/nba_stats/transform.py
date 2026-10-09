"""Transform nba_api DataFrames into legacy scraper CSV schemas."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from nba_stats.teams import team_tricode

PLAYER_BOXSCORE_COLUMNS = [
    "Player",
    "Player ID",
    "Pos",
    "Team",
    "Match up",
    "Date",
    "W/L",
    "Min",
    "Pts",
    "FGM",
    "FGA",
    "FG%",
    "3PM",
    "3PA",
    "3P%",
    "FTM",
    "FTA",
    "FT%",
    "OREB",
    "DREB",
    "REB",
    "AST",
    "STL",
    "BLK",
    "TOV",
    "PF",
    "+/-",
    "FP",
]

TEAM_BOXSCORE_COLUMNS = [
    "Team",
    "Match up",
    "Date",
    "W/L",
    "Min",
    "Pts",
    "Opp Pts",
    "FGM",
    "FGA",
    "FG%",
    "3PM",
    "3PA",
    "3P%",
    "FTM",
    "FTA",
    "FT%",
    "OREB",
    "DREB",
    "REB",
    "AST",
    "STL",
    "BLK",
    "TOV",
    "PF",
    "+/-",
]

INJURY_COLUMNS = ["Identifier", "Pos", "Player", "Status"]

LEAGUE_RESULTS_COLUMNS = ["Identifier", "Date", "OPP", "RESULT", "ATS/OU", "Spread", "Total"]

SCHEDULE_COLUMNS = ["Identifier", "Date", "OPP", "Time", "Location", "Game Type"]


def _format_boxscore_date(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, (date, datetime)):
        return value.strftime("%m/%d/%Y")
    text = str(value).strip()
    if "T" in text:
        text = text.split("T", maxsplit=1)[0]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%Y %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).strftime("%m/%d/%Y")
        except ValueError:
            continue
    return text


def _format_league_date(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, (date, datetime)):
        return value.strftime("%b %d, %Y")
    text = str(value).strip()
    if "T" in text:
        text = text.split("T", maxsplit=1)[0]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%Y %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).strftime("%b %d, %Y")
        except ValueError:
            continue
    return text


def _pct(value) -> str | float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "-"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return value
    if numeric <= 1:
        numeric *= 100
    return round(numeric, 1)


def _matchup_label(matchup: str) -> str:
    """Convert API matchup strings to legacy 'ATL @ MIA' / 'BOS vs. ORL' style."""
    text = str(matchup).strip()
    if " vs. " in text or " @ " in text:
        return text
    if " vs " in text:
        return text.replace(" vs ", " vs. ", 1)
    if " @ " not in text and " vs. " not in text:
        parts = text.split()
        if len(parts) >= 3 and parts[1].upper() == "VS":
            return f"{parts[0]} vs. {parts[2]}"
        if len(parts) >= 3 and parts[1] == "@":
            return f"{parts[0]} @ {parts[2]}"
    return text


def player_logs_to_boxscores(df: pd.DataFrame) -> pd.DataFrame:
    """Map PlayerGameLogs rows to the legacy player boxscores.csv schema."""
    if df.empty:
        return pd.DataFrame(columns=PLAYER_BOXSCORE_COLUMNS)

    positions = (
        df["POSITION"].fillna("").astype(str)
        if "POSITION" in df.columns
        else pd.Series([""] * len(df), index=df.index)
    )
    player_ids = (
        df["PLAYER_ID"]
        if "PLAYER_ID" in df.columns
        else pd.Series([""] * len(df), index=df.index)
    )

    out = pd.DataFrame(
        {
            "Player": df.get("PLAYER_NAME", ""),
            "Player ID": player_ids,
            "Pos": positions,
            "Team": df.get("TEAM_ABBREVIATION", ""),
            "Match up": df.get("MATCHUP", "").map(_matchup_label),
            "Date": df.get("GAME_DATE", "").map(_format_boxscore_date),
            "W/L": df.get("WL", ""),
            "Min": df.get("MIN", ""),
            "Pts": df.get("PTS", ""),
            "FGM": df.get("FGM", ""),
            "FGA": df.get("FGA", ""),
            "FG%": df.get("FG_PCT", "").map(_pct),
            "3PM": df.get("FG3M", ""),
            "3PA": df.get("FG3A", ""),
            "3P%": df.get("FG3_PCT", "").map(_pct),
            "FTM": df.get("FTM", ""),
            "FTA": df.get("FTA", ""),
            "FT%": df.get("FT_PCT", "").map(_pct),
            "OREB": df.get("OREB", ""),
            "DREB": df.get("DREB", ""),
            "REB": df.get("REB", ""),
            "AST": df.get("AST", ""),
            "STL": df.get("STL", ""),
            "BLK": df.get("BLK", ""),
            "TOV": df.get("TOV", ""),
            "PF": df.get("PF", ""),
            "+/-": df.get("PLUS_MINUS", ""),
            "FP": df.get("NBA_FANTASY_PTS", ""),
        }
    )
    return out[PLAYER_BOXSCORE_COLUMNS]


def _opponent_pts(df: pd.DataFrame) -> pd.Series:
    """Opponent points for each team row, paired by GAME_ID when available."""
    if "GAME_ID" in df.columns and "PTS" in df.columns and not df["GAME_ID"].isna().all():
        game_totals = df.groupby("GAME_ID", sort=False)["PTS"].transform("sum")
        return game_totals - df["PTS"]

    # Fallback: Pts - (+/-) when both sides of a game are not in the frame.
    if "PTS" in df.columns and "PLUS_MINUS" in df.columns:
        pts = pd.to_numeric(df["PTS"], errors="coerce")
        plus_minus = pd.to_numeric(df["PLUS_MINUS"], errors="coerce")
        return pts - plus_minus

    return pd.Series([""] * len(df), index=df.index)


def team_logs_to_boxscores(df: pd.DataFrame) -> pd.DataFrame:
    """Map LeagueGameLog team rows to the legacy team_boxscores.csv schema."""
    if df.empty:
        return pd.DataFrame(columns=TEAM_BOXSCORE_COLUMNS)

    out = pd.DataFrame(
        {
            "Team": df.get("TEAM_ABBREVIATION", ""),
            "Match up": df.get("MATCHUP", "").map(_matchup_label),
            "Date": df.get("GAME_DATE", "").map(_format_boxscore_date),
            "W/L": df.get("WL", ""),
            "Min": df.get("MIN", ""),
            "Pts": df.get("PTS", ""),
            "Opp Pts": _opponent_pts(df),
            "FGM": df.get("FGM", ""),
            "FGA": df.get("FGA", ""),
            "FG%": df.get("FG_PCT", "").map(_pct),
            "3PM": df.get("FG3M", ""),
            "3PA": df.get("FG3A", ""),
            "3P%": df.get("FG3_PCT", "").map(_pct),
            "FTM": df.get("FTM", ""),
            "FTA": df.get("FTA", ""),
            "FT%": df.get("FT_PCT", "").map(_pct),
            "OREB": df.get("OREB", ""),
            "DREB": df.get("DREB", ""),
            "REB": df.get("REB", ""),
            "AST": df.get("AST", ""),
            "STL": df.get("STL", ""),
            "BLK": df.get("BLK", ""),
            "TOV": df.get("TOV", ""),
            "PF": df.get("PF", ""),
            "+/-": df.get("PLUS_MINUS", ""),
        }
    )
    return out[TEAM_BOXSCORE_COLUMNS]


def injuries_to_legacy(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure injury rows use Identifier, Pos, Player, Status columns."""
    if df.empty:
        return pd.DataFrame(columns=INJURY_COLUMNS)

    out = df.copy()
    if "Identifier" not in out.columns and "team_tricode" in out.columns:
        out["Identifier"] = out["team_tricode"]
    if "Identifier" not in out.columns and "team" in out.columns:
        out["Identifier"] = out["team"].map(team_tricode)

    rename_map = {
        "position": "Pos",
        "POSITION": "Pos",
        "player": "Player",
        "PLAYER": "Player",
        "status": "Status",
        "STATUS": "Status",
    }
    out = out.rename(columns=rename_map)

    for column in INJURY_COLUMNS:
        if column not in out.columns:
            out[column] = ""

    return out[INJURY_COLUMNS]


def _parse_opponent(matchup: str, team_tricode_value: str) -> str:
    text = _matchup_label(matchup)
    if " @ " in text:
        away, home = text.split(" @ ", maxsplit=1)
        if team_tricode_value == away.strip():
            return f"@{home.strip()}"
        return home.strip()
    if " vs. " in text:
        home, away = text.split(" vs. ", maxsplit=1)
        if team_tricode_value == home.strip():
            return away.strip()
        return f"@{home.strip()}"
    return text


def _result_label(wl: str, team_pts, opp_pts) -> str:
    try:
        team_pts = int(float(team_pts))
        opp_pts = int(float(opp_pts))
    except (TypeError, ValueError):
        return ""

    if wl == "W":
        return f"Won {team_pts}-{opp_pts}"
    if wl == "L":
        return f"Lost {team_pts}-{opp_pts}"
    if team_pts > opp_pts:
        return f"Won {team_pts}-{opp_pts}"
    if team_pts < opp_pts:
        return f"Lost {team_pts}-{opp_pts}"
    return f"Tied {team_pts}-{opp_pts}"


def _ats_ou_label(team_pts, opp_pts, spread, total) -> str:
    try:
        team_pts = float(team_pts)
        opp_pts = float(opp_pts)
    except (TypeError, ValueError):
        return ""

    ats = ""
    ou = ""

    if spread is not None and spread != "" and not pd.isna(spread):
        try:
            spread_value = float(str(spread).strip())
            adjusted = team_pts + spread_value - opp_pts
            ats = "Won" if adjusted > 0 else "Lost" if adjusted < 0 else "Push"
        except ValueError:
            ats = ""

    if total is not None and total != "" and not pd.isna(total):
        try:
            total_value = float(str(total).strip())
            combined = team_pts + opp_pts
            ou = "Over" if combined > total_value else "Under" if combined < total_value else "Push"
        except ValueError:
            ou = ""

    if ats and ou:
        return f"{ats} /\n {ou}"
    return ats or ou


def schedule_rows_to_league_results(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert merged schedule/odds/result rows to league_results.csv schema.

    Expected input columns (snake_case):
    team_tricode, game_date, matchup, wl, team_pts, opp_pts, spread, total
    """
    if df.empty:
        return pd.DataFrame(columns=LEAGUE_RESULTS_COLUMNS)

    rows = []
    for _, row in df.iterrows():
        tricode = row.get("team_tricode") or row.get("Team") or row.get("TEAM_ABBREVIATION")
        matchup = row.get("matchup") or row.get("MATCHUP") or row.get("Match up", "")
        spread = row.get("spread") if "spread" in row else row.get("Spread")
        total = row.get("total") if "total" in row else row.get("Total")

        rows.append(
            {
                "Identifier": tricode,
                "Date": _format_league_date(row.get("game_date") or row.get("Date") or row.get("GAME_DATE")),
                "OPP": _parse_opponent(str(matchup), str(tricode)),
                "RESULT": _result_label(
                    row.get("wl") or row.get("W/L") or row.get("WL", ""),
                    row.get("team_pts"),
                    row.get("opp_pts"),
                ),
                "ATS/OU": _ats_ou_label(
                    row.get("team_pts"),
                    row.get("opp_pts"),
                    spread,
                    total,
                ),
                "Spread": spread,
                "Total": total,
            }
        )

    return pd.DataFrame(rows, columns=LEAGUE_RESULTS_COLUMNS)


def season_schedule_to_team_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Expand ScheduleLeagueV2 games into one row per team (home + away).

    Output schema matches a concatenated team-schedule file:
    Identifier, Date, OPP, Time, Location, Game Type
    """
    if df.empty:
        return pd.DataFrame(columns=SCHEDULE_COLUMNS)

    working = df.copy()
    if "gameDate" in working.columns:
        working["_sort_date"] = pd.to_datetime(working["gameDate"], errors="coerce")
        working = working.sort_values("_sort_date", kind="stable")

    rows: list[dict] = []
    for _, game in working.iterrows():
        home = game.get("homeTeam_teamTricode")
        away = game.get("awayTeam_teamTricode")
        if home is None or away is None or (isinstance(home, float) and pd.isna(home)):
            continue
        if isinstance(away, float) and pd.isna(away):
            continue

        home = str(home).strip()
        away = str(away).strip()
        if not home or not away:
            continue

        game_date = _format_league_date(game.get("gameDate") or game.get("gameDateEst"))
        tip_time = str(game.get("gameStatusText") or "").strip()
        if tip_time.lower() in {"final", "ppd", "postponed"}:
            tip_time = ""
        game_type = str(game.get("gameLabel") or "").strip() or "Regular Season"

        rows.append(
            {
                "Identifier": home,
                "Date": game_date,
                "OPP": away,
                "Time": tip_time,
                "Location": "Home",
                "Game Type": game_type,
            }
        )
        rows.append(
            {
                "Identifier": away,
                "Date": game_date,
                "OPP": f"@{home}",
                "Time": tip_time,
                "Location": "Away",
                "Game Type": game_type,
            }
        )

    return pd.DataFrame(rows, columns=SCHEDULE_COLUMNS)
