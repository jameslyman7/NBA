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
        default=date.today().strftime("%Y-%m-%d"),
        help="Date in YYYY-MM-DD format",
    )
    export_parser.add_argument(
        "--output-dir",
        default=None,
        help=f"Output directory (default: {DEFAULT_EXPORT_DIR}/YYYY-MM-DD)",
    )
    export_parser.add_argument(
        "--no-espn-injuries",
        action="store_true",
        help="Skip ESPN league injury report",
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
        year, month, day = map(int, args.date.split("-"))
        export, paths = run_daily_export(
            game_date=date(year, month, day),
            output_dir=Path(args.output_dir) if args.output_dir else None,
            include_espn_injuries=not args.no_espn_injuries,
        )
        print(f"Exported daily data for {export.export_date.isoformat()}:")
        for name, path in paths.items():
            print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
