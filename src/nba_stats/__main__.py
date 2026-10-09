"""CLI entry point for exploring and exporting NBA data."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import nba_stats._ssl  # noqa: F401  # OS cert store before any HTTPS

from nba_stats import (
    get_boxscore,
    get_game_inactives,
    get_scoreboard,
    get_season_schedule,
    get_standings,
    run_daily_export,
    run_daily_export_range,
    run_season_boxscores_export,
    run_season_league_results_export,
    run_season_schedules_export,
)
from nba_stats.utils import DEFAULT_EXPORT_DIR, current_season


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch and export NBA data (schedules, box scores, injuries, lines)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    schedule_parser = subparsers.add_parser("schedule", help="Season schedule")
    schedule_parser.add_argument(
        "--season",
        default=current_season(),
        help="Season string, e.g. 2025-26",
    )

    scoreboard_parser = subparsers.add_parser("scoreboard", help="Daily scoreboard")
    scoreboard_parser.add_argument(
        "--date",
        default=date.today().strftime("%Y-%m-%d"),
        help="Date in YYYY-MM-DD format",
    )

    boxscore_parser = subparsers.add_parser("boxscore", help="Game box score")
    boxscore_parser.add_argument("game_id", help="10-digit NBA game ID")

    inactives_parser = subparsers.add_parser(
        "inactives", help="Inactive players for a game"
    )
    inactives_parser.add_argument("game_id", help="10-digit NBA game ID")

    standings_parser = subparsers.add_parser("standings", help="League standings")
    standings_parser.add_argument(
        "--season",
        default=current_season(),
        help="Season string, e.g. 2025-26",
    )

    export_parser = subparsers.add_parser(
        "export-daily",
        help="Export daily CSVs (boxscores, injuries, lines, results)",
    )
    export_parser.add_argument(
        "--date",
        default=None,
        help="Single date in YYYY-MM-DD format (default: today)",
    )
    export_parser.add_argument(
        "--from",
        dest="date_from",
        default=None,
        help="Start date for a range export (YYYY-MM-DD); requires --to",
    )
    export_parser.add_argument(
        "--to",
        dest="date_to",
        default=None,
        help="End date for a range export (YYYY-MM-DD); requires --from",
    )
    export_parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            f"For a single date: output directory "
            f"(default: {DEFAULT_EXPORT_DIR}/YYYY-MM-DD). "
            f"For a range: base directory that will contain dated subfolders."
        ),
    )
    export_parser.add_argument(
        "--no-espn-injuries",
        action="store_true",
        help="Skip ESPN league injury report",
    )

    season_box_parser = subparsers.add_parser(
        "export-season-boxscores",
        help="Export full-season boxscores.csv and team_boxscores.csv",
    )
    season_box_parser.add_argument(
        "--season",
        default=current_season(),
        help="Season string, e.g. 2024-25",
    )
    season_box_parser.add_argument(
        "--output-dir",
        default=None,
        help=f"Output directory (default: {DEFAULT_EXPORT_DIR}/{{season}})",
    )

    season_results_parser = subparsers.add_parser(
        "export-season-league-results",
        help="Export full-season league_results.csv (results + ESPN lines)",
    )
    season_results_parser.add_argument(
        "--season",
        default=current_season(),
        help="Season string, e.g. 2024-25",
    )
    season_results_parser.add_argument(
        "--output-dir",
        default=None,
        help=f"Output directory (default: {DEFAULT_EXPORT_DIR}/{{season}})",
    )
    season_results_parser.add_argument(
        "--no-odds",
        action="store_true",
        help="Skip ESPN odds (Spread / Total / ATS-OU will be blank)",
    )

    season_schedules_parser = subparsers.add_parser(
        "export-season-schedules",
        help="Export concatenated team schedules.csv for a season",
    )
    season_schedules_parser.add_argument(
        "--season",
        default=current_season(),
        help="Season string, e.g. 2026-27",
    )
    season_schedules_parser.add_argument(
        "--output-dir",
        default=None,
        help=f"Output directory (default: {DEFAULT_EXPORT_DIR}/{{season}})",
    )
    season_schedules_parser.add_argument(
        "--game-type",
        action="append",
        dest="game_types",
        default=None,
        help="Optional gameLabel filter; repeatable (e.g. --game-type Preseason)",
    )

    args = parser.parse_args()

    if args.command == "schedule":
        df = get_season_schedule(season=args.season)
        print(df.head(10).to_string(index=False))
        print(f"\n({len(df)} games total)")

    elif args.command == "scoreboard":
        year, month, day = map(int, args.date.split("-"))
        data = get_scoreboard(date(year, month, day))
        games = data["games"]
        if games.empty:
            print("No games scheduled.")
        else:
            cols = [
                c
                for c in ("gameId", "gameStatusText", "GAME_ID", "GAME_STATUS_TEXT")
                if c in games.columns
            ]
            print(games[cols].to_string(index=False) if cols else games.to_string(index=False))

    elif args.command == "boxscore":
        data = get_boxscore(args.game_id)
        print(data["player_stats"].to_string(index=False))

    elif args.command == "inactives":
        df = get_game_inactives(args.game_id)
        print(df.to_string(index=False) if not df.empty else "No inactive players listed.")

    elif args.command == "standings":
        df = get_standings(season=args.season)
        print(df.to_string(index=False))

    elif args.command == "export-daily":
        if args.date_from or args.date_to:
            if not args.date_from or not args.date_to:
                parser.error("export-daily range requires both --from and --to")
            if args.date:
                parser.error("use either --date or --from/--to, not both")
            results = run_daily_export_range(
                start_date=args.date_from,
                end_date=args.date_to,
                output_base=Path(args.output_dir) if args.output_dir else None,
                include_espn_injuries=not args.no_espn_injuries,
            )
            print(f"Exported {len(results)} day(s) from {args.date_from} through {args.date_to}:")
            for export_date, paths in results.items():
                print(f"  {export_date.isoformat()}: {paths['player_boxscores'].parent}")
        else:
            game_date = args.date or date.today().strftime("%Y-%m-%d")
            year, month, day = map(int, game_date.split("-"))
            export, paths = run_daily_export(
                game_date=date(year, month, day),
                output_dir=Path(args.output_dir) if args.output_dir else None,
                include_espn_injuries=not args.no_espn_injuries,
            )
            print(f"Exported daily data for {export.export_date.isoformat()}:")
            for name, path in paths.items():
                print(f"  {name}: {path}")

    elif args.command == "export-season-boxscores":
        paths = run_season_boxscores_export(
            season=args.season,
            output_dir=Path(args.output_dir) if args.output_dir else None,
        )
        print(f"Exported season box scores for {args.season}:")
        for name, path in paths.items():
            print(f"  {name}: {path}")

    elif args.command == "export-season-league-results":
        df, path = run_season_league_results_export(
            season=args.season,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            include_odds=not args.no_odds,
        )
        print(f"Exported {len(df)} league results for {args.season}:")
        print(f"  {path}")

    elif args.command == "export-season-schedules":
        df, path = run_season_schedules_export(
            season=args.season,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            game_types=args.game_types,
        )
        print(f"Exported {len(df)} schedule rows for {args.season}:")
        print(f"  {path}")


if __name__ == "__main__":
    main()
