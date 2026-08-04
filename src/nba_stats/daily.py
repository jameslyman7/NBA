"""Daily data collection for NBA exports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from nba_stats.boxscores import get_daily_player_boxscores, get_daily_team_boxscores
from nba_stats.injuries import get_daily_injuries
from nba_stats.odds import get_odds_lines
from nba_stats.schedules import build_daily_league_results, get_final_game_ids, get_scoreboard
from nba_stats.utils import parse_game_date


@dataclass
class DailyExport:
    """All daily DataFrames ready for CSV export."""

    export_date: date
    player_boxscores: pd.DataFrame
    team_boxscores: pd.DataFrame
    injuries: pd.DataFrame
    league_results: pd.DataFrame
    odds_lines: pd.DataFrame
    odds_summary: pd.DataFrame
    scoreboard: pd.DataFrame


def collect_daily_export(
    game_date: date | str | None = None,
    include_espn_injuries: bool = True,
) -> DailyExport:
    """
    Collect daily NBA data in legacy CSV-compatible DataFrames.

    Mirrors the outputs from C:/Users/crgly/PythonProjects/NBA:
    - Boxscores/boxscores.csv
    - Boxscores/team_boxscores.csv
    - Injuries/combined_injuries.csv
    - Results/league_results.csv
    """
    export_date = parse_game_date(game_date)
    odds_lines, odds_summary = get_odds_lines(game_date=export_date)
    scoreboard = get_scoreboard(export_date)["games"]
    final_game_ids = get_final_game_ids(export_date)

    return DailyExport(
        export_date=export_date,
        player_boxscores=get_daily_player_boxscores(export_date),
        team_boxscores=get_daily_team_boxscores(export_date),
        injuries=get_daily_injuries(
            game_ids=final_game_ids,
            include_espn=include_espn_injuries,
            export_date=export_date,
        ),
        league_results=build_daily_league_results(export_date, odds_summary=odds_summary),
        odds_lines=odds_lines,
        odds_summary=odds_summary,
        scoreboard=scoreboard,
    )
