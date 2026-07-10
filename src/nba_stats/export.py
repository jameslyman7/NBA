"""CSV export utilities for daily NBA data."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from nba_stats.daily import DailyExport, collect_daily_export
from nba_stats.utils import DEFAULT_EXPORT_DIR, parse_game_date

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
