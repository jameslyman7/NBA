# NBA Stats

Fetch NBA data — box scores, schedules, injuries, betting lines, and results — using the [nba_api](https://github.com/swar/nba_api) Python library.

This project replaces the Selenium scrapers in `C:\Users\crgly\PythonProjects\NBA` with API-based daily exports that produce the same CSV column layouts for Excel, PostgreSQL, and pgvector ingestion.

## Setup

This project uses [uv](https://docs.astral.sh/uv/). From the project root:

```bash
uv sync --system-certs
```

> **Note:** The project is named `nba-stats` (not `nba-api`) to avoid a naming conflict with the PyPI `nba_api` package.

## Daily export (primary workflow)

Once the season starts, run this each day to produce CSVs aligned with your legacy project:

```bash
uv run python -m nba_stats export-daily --date 2025-10-22
```

Output goes to `data/exports/YYYY-MM-DD/`:

| File | Legacy equivalent | Columns |
|------|-------------------|---------|
| `boxscores.csv` | `NBA/Boxscores/boxscores.csv` | Player, Team, Match up, Date, W/L, Min, Pts, ... FP |
| `team_boxscores.csv` | `NBA/Boxscores/team_boxscores.csv` | Team, Match up, Date, W/L, Min, Pts, Opp Pts, ... +/- |
| `combined_injuries.csv` | `NBA/Injuries/combined_injuries.csv` | Identifier, Pos, Player, Status |
| `league_results.csv` | `NBA/Results/league_results.csv` | Identifier, Date, OPP, RESULT, ATS/OU, Spread, Total |
| `odds_lines.csv` | *(new detail file)* | Full sportsbook lines by market |
| `odds_summary.csv` | *(new)* | One row per game with spread/total/moneyline |

### Python API

```python
from datetime import date
from nba_stats import run_daily_export

export, paths = run_daily_export(game_date=date(2025, 10, 22))
print(paths["player_boxscores"])
print(export.league_results.head())
```

## Other commands

```bash
# Today's scoreboard
uv run python -m nba_stats scoreboard

# Full season schedule
uv run python -m nba_stats schedule --season 2025-26

# League standings
uv run python -m nba_stats standings

# Single-game box score
uv run python -m nba_stats boxscore 0022400001
```

## Project layout

```
src/nba_stats/
├── __init__.py
├── __main__.py        # CLI
├── boxscores.py       # Daily player/team box scores
├── daily.py           # Daily collection bundle
├── export.py          # CSV export
├── injuries.py        # ESPN + game inactive lists
├── odds.py            # Spread/total/moneyline from NBA CDN
├── schedules.py       # Scoreboard + league results w/ lines
├── standings.py
├── teams.py           # Tricode mapping (LAC, NOP, etc.)
├── transform.py       # Legacy CSV schema transforms
└── utils.py

data/exports/          # Daily CSV output
```

## Data sources

| Feature | Source |
|---------|--------|
| Player box scores | `PlayerGameLogs` (date filter) |
| Team box scores | `LeagueGameLog` (team rows, date filter) |
| Daily scoreboard | `ScoreboardV3` |
| Spread / total / ML | `live.nba.endpoints.odds` |
| League injuries | ESPN public API (replaces Vegas Insider scrape) |
| Game inactives | `BoxScoreSummaryV2` |
| Season schedule | `ScheduleLeagueV2` |
| Standings | `LeagueStandingsV3` |

## Legacy project mapping

Your Selenium project at `C:\Users\crgly\PythonProjects\NBA` used:

- **nba.com/stats** player & team box score pages → now `PlayerGameLogs` + `LeagueGameLog`
- **Vegas Insider** injuries & schedule/lines → now ESPN injuries + NBA live odds + scoreboard results
- **Per-team CSV concat scripts** → single daily export with the same combined schemas

## Rate limiting

The NBA stats API can throttle requests. The export pipeline adds pauses between per-game inactive lookups. Re-run `export-daily` after games finish to refresh box scores and ATS/OU results.

## Next steps for your database pipeline

1. Run `export-daily` after games complete each night
2. Load CSVs into PostgreSQL (your existing pgvector DB)
3. Optionally append daily files into season-long master tables before Excel export
