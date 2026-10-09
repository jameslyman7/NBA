"""NBA data utilities built on top of the nba_api package."""

import nba_stats._ssl  # noqa: F401  # OS cert store before any HTTPS

from nba_stats.boxscores import (
    get_boxscore,
    get_daily_player_boxscores,
    get_daily_team_boxscores,
    get_live_boxscore,
    get_season_player_boxscores,
    get_season_team_boxscores,
)
from nba_stats.daily import DailyExport, collect_daily_export
from nba_stats.export import (
    export_daily_csv,
    run_daily_export,
    run_daily_export_range,
    run_season_boxscores_export,
    run_season_league_results_export,
    run_season_schedules_export,
)
from nba_stats.injuries import get_daily_injuries, get_espn_injury_report, get_game_inactives
from nba_stats.odds import get_odds_lines
from nba_stats.schedules import (
    build_daily_league_results,
    build_season_league_results,
    build_season_schedules,
    get_daily_games,
    get_scoreboard,
    get_season_schedule,
)
from nba_stats.standings import get_standings

__all__ = [
    "DailyExport",
    "build_daily_league_results",
    "build_season_league_results",
    "build_season_schedules",
    "collect_daily_export",
    "export_daily_csv",
    "get_boxscore",
    "get_daily_games",
    "get_daily_injuries",
    "get_daily_player_boxscores",
    "get_daily_team_boxscores",
    "get_espn_injury_report",
    "get_game_inactives",
    "get_live_boxscore",
    "get_odds_lines",
    "get_scoreboard",
    "get_season_player_boxscores",
    "get_season_schedule",
    "get_season_team_boxscores",
    "get_standings",
    "run_daily_export",
    "run_daily_export_range",
    "run_season_boxscores_export",
    "run_season_league_results_export",
    "run_season_schedules_export",
]
