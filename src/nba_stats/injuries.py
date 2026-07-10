"""Injury and inactive-player data."""

from __future__ import annotations

from datetime import date

import pandas as pd
import requests
from nba_api.stats.endpoints import boxscoresummaryv2, playergamelog

from nba_stats.teams import team_tricode
from nba_stats.transform import injuries_to_legacy
from nba_stats.utils import api_pause, current_season, normalize_game_id, to_dataframe

ESPN_INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"


def get_game_inactives(game_id: str) -> pd.DataFrame:
    """Fetch inactive/out players for a specific game."""
    summary = boxscoresummaryv2.BoxScoreSummaryV2(game_id=game_id)
    return to_dataframe(summary.inactive_players)


def get_player_dnp_comments(
    player_id: int,
    season: str | None = None,
) -> pd.DataFrame:
    """Fetch a player's game log rows with DNP/injury comments."""
    season = season or current_season()
    log = playergamelog.PlayerGameLog(player_id=player_id, season=season)
    df = to_dataframe(log.player_game_log)

    if df.empty or "COMMENT" not in df.columns:
        return df

    comments = df["COMMENT"].fillna("").astype(str).str.strip()
    return df.loc[comments != ""].copy()


def get_espn_injury_report(timeout: int = 30) -> pd.DataFrame:
    """
    Fetch the league-wide injury report from ESPN's public API.

    Returns a DataFrame compatible with the legacy combined_injuries.csv schema.
    """
    response = requests.get(ESPN_INJURIES_URL, timeout=timeout)
    response.raise_for_status()
    payload = response.json()

    rows: list[dict[str, str]] = []
    for team_block in payload.get("injuries", []):
        team_info = team_block.get("team", {})
        team_name = team_info.get("displayName") or team_info.get("name") or ""
        identifier = team_tricode(team_name)

        for injury in team_block.get("injuries", []):
            athlete = injury.get("athlete", {})
            player_name = athlete.get("displayName") or athlete.get("shortName") or ""
            position = athlete.get("position", {}).get("abbreviation", "")
            status = injury.get("status") or injury.get("type", {}).get("description", "")

            details = injury.get("details") or {}
            detail_type = details.get("type") or details.get("detail") or ""
            side = details.get("side") or ""
            injury_note = " ".join(part for part in [side, detail_type] if part).strip()
            if injury_note:
                player_label = f"{player_name} ({injury_note})"
            else:
                player_label = player_name

            rows.append(
                {
                    "Identifier": identifier,
                    "Pos": position,
                    "Player": player_label,
                    "Status": status,
                }
            )

    return injuries_to_legacy(pd.DataFrame(rows))


def get_daily_injuries(
    game_ids: list[str] | None = None,
    include_espn: bool = True,
    export_date: date | None = None,
) -> pd.DataFrame:
    """
    Build a daily injury report.

    Uses ESPN league-wide injuries by default (closest to the legacy Vegas Insider
    scraper). Optionally merges game inactive lists when game_ids are provided.
    """
    frames: list[pd.DataFrame] = []

    if include_espn:
        try:
            frames.append(get_espn_injury_report())
        except requests.RequestException:
            pass

    if game_ids:
        inactive_rows: list[pd.DataFrame] = []
        for game_id in game_ids:
            try:
                inactives = get_game_inactives(game_id)
                if inactives.empty:
                    continue
                inactives = inactives.copy()
                inactives["game_id"] = normalize_game_id(game_id)
                if export_date is not None:
                    inactives["export_date"] = export_date.isoformat()
                inactive_rows.append(inactives)
            finally:
                api_pause()

        if inactive_rows:
            raw = pd.concat(inactive_rows, ignore_index=True)
            mapped = pd.DataFrame(
                {
                    "Identifier": raw.get("TEAM_ABBREVIATION", raw.get("TEAM_CITY", "")),
                    "Pos": raw.get("POSITION", ""),
                    "Player": raw.get("PLAYER_NAME", ""),
                    "Status": "Out",
                }
            )
            frames.append(injuries_to_legacy(mapped))

    if not frames:
        return injuries_to_legacy(pd.DataFrame())

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["Identifier", "Player", "Status"], keep="last")
    return injuries_to_legacy(combined)
