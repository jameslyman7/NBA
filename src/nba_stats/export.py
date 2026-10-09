"""CSV export utilities for daily NBA data."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from nba_stats.boxscores import get_season_player_boxscores, get_season_team_boxscores
from nba_stats.daily import DailyExport, collect_daily_export
from nba_stats.schedules import build_season_league_results, build_season_schedules
from nba_stats.utils import DEFAULT_EXPORT_DIR, api_pause, current_season, parse_game_date

DAILY_FILES = {
    "player_boxscores": "boxscores.csv",
    "team_boxscores": "team_boxscores.csv",
    "injuries": "combined_injuries.csv",
    "league_results": "league_results.csv",
    "odds_lines": "odds_lines.csv",
    "odds_summary": "odds_summary.csv",
    "scoreboard": "scoreboard.csv",
}


def export_dir_for_date(game_date: date, base_dir: Path | str = DEFAULT_EXPORT_DIR) -> Path:
    """Return the dated export directory path."""
    return Path(base_dir) / game_date.isoformat()


def export_dir_for_season(season: str, base_dir: Path | str = DEFAULT_EXPORT_DIR) -> Path:
    """Return the season export directory path (e.g. data/exports/2024-25)."""
    return Path(base_dir) / season


def export_daily_csv(
    export: DailyExport,
    output_dir: Path | str | None = None,
) -> dict[str, Path]:
    """
    Write daily export DataFrames to CSV files.

    Default layout:
        data/exports/YYYY-MM-DD/boxscores.csv
        data/exports/YYYY-MM-DD/team_boxscores.csv
        data/exports/YYYY-MM-DD/combined_injuries.csv
        data/exports/YYYY-MM-DD/league_results.csv
        data/exports/YYYY-MM-DD/odds_lines.csv
    """
    output_dir = Path(output_dir) if output_dir else export_dir_for_date(export.export_date)
    output_dir.mkdir(parents=True, exist_ok=True)

    written: dict[str, Path] = {}
    payload = {
        "player_boxscores": export.player_boxscores,
        "team_boxscores": export.team_boxscores,
        "injuries": export.injuries,
        "league_results": export.league_results,
        "odds_lines": export.odds_lines,
        "odds_summary": export.odds_summary,
        "scoreboard": export.scoreboard,
    }

    for key, filename in DAILY_FILES.items():
        df = payload[key]
        path = output_dir / filename
        df.to_csv(path, index=False)
        written[key] = path

    return written


def run_daily_export(
    game_date: date | str | None = None,
    output_dir: Path | str | None = None,
    include_espn_injuries: bool = True,
) -> tuple[DailyExport, dict[str, Path]]:
    """Collect and export daily NBA data in one call."""
    export_date = parse_game_date(game_date)
    target_dir = output_dir or export_dir_for_date(export_date)
    export = collect_daily_export(
        game_date=export_date,
        include_espn_injuries=include_espn_injuries,
    )
    paths = export_daily_csv(export, output_dir=target_dir)
    return export, paths


def run_daily_export_range(
    start_date: date | str,
    end_date: date | str,
    output_base: Path | str | None = None,
    include_espn_injuries: bool = True,
) -> dict[date, dict[str, Path]]:
    """
    Export daily CSVs for each date from start_date through end_date (inclusive).

    Each day writes to {output_base or data/exports}/YYYY-MM-DD/.
    """
    start = parse_game_date(start_date)
    end = parse_game_date(end_date)
    if end < start:
        raise ValueError(f"end_date {end.isoformat()} is before start_date {start.isoformat()}")

    base = Path(output_base) if output_base else DEFAULT_EXPORT_DIR
    results: dict[date, dict[str, Path]] = {}
    current = start
    while current <= end:
        print(f"Exporting {current.isoformat()}...", flush=True)
        target_dir = base / current.isoformat()
        _, paths = run_daily_export(
            game_date=current,
            output_dir=target_dir,
            include_espn_injuries=include_espn_injuries,
        )
        results[current] = paths
        if current < end:
            api_pause()
        current += timedelta(days=1)
    return results


def run_season_boxscores_export(
    season: str | None = None,
    output_dir: Path | str | None = None,
    season_type: str = "Regular Season",
) -> dict[str, Path]:
    """
    Write full-season player and team box score CSVs in the daily schemas.

    Default paths:
        data/exports/{season}/boxscores.csv
        data/exports/{season}/team_boxscores.csv
    """
    season = season or current_season()
    target_dir = Path(output_dir) if output_dir else export_dir_for_season(season)
    target_dir.mkdir(parents=True, exist_ok=True)

    player_df = get_season_player_boxscores(season=season, season_type=season_type)
    api_pause()
    team_df = get_season_team_boxscores(season=season, season_type=season_type)

    paths = {
        "player_boxscores": target_dir / "boxscores.csv",
        "team_boxscores": target_dir / "team_boxscores.csv",
    }
    player_df.to_csv(paths["player_boxscores"], index=False)
    team_df.to_csv(paths["team_boxscores"], index=False)
    return paths


def run_season_league_results_export(
    season: str | None = None,
    output_dir: Path | str | None = None,
    include_odds: bool = True,
) -> tuple[pd.DataFrame, Path]:
    """
    Write a full-season league_results.csv in the daily schema.

    Default path: data/exports/{season}/league_results.csv
    """
    season = season or current_season()
    target_dir = Path(output_dir) if output_dir else export_dir_for_season(season)
    target_dir.mkdir(parents=True, exist_ok=True)

    df = build_season_league_results(season=season, include_odds=include_odds)
    path = target_dir / "league_results.csv"
    df.to_csv(path, index=False)
    return df, path


def run_season_schedules_export(
    season: str | None = None,
    output_dir: Path | str | None = None,
    game_types: list[str] | None = None,
) -> tuple[pd.DataFrame, Path]:
    """
    Write a concatenated team schedules.csv for a season.

    Default path: data/exports/{season}/schedules.csv
    """
    season = season or current_season()
    target_dir = Path(output_dir) if output_dir else export_dir_for_season(season)
    target_dir.mkdir(parents=True, exist_ok=True)

    df = build_season_schedules(season=season, game_types=game_types)
    path = target_dir / "schedules.csv"
    df.to_csv(path, index=False)
    return df, path
