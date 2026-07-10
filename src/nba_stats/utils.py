"""Shared helpers for nba_api responses."""

from __future__ import annotations

import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd

DEFAULT_EXPORT_DIR = Path("data/exports")
API_REQUEST_DELAY = 0.6


def to_dataframe(data_set) -> pd.DataFrame:
    """Convert an nba_api DataSet to a pandas DataFrame."""
    if data_set is None:
        return pd.DataFrame()
    return data_set.get_data_frame()


def normalize_game_id(game_id: str | int) -> str:
    """Return a zero-padded 10-digit game ID string."""
    return str(game_id).zfill(10)


def current_season(today: date | None = None) -> str:
    """Return the NBA season string (e.g. '2025-26') for a given date."""
    today = today or date.today()
    if today.month >= 10:
        start_year = today.year
    else:
        start_year = today.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def format_game_date(value: date | datetime | str) -> str:
    """Format a date for nba_api ScoreboardV3 (YYYY-MM-DD)."""
    if isinstance(value, str):
        if "/" in value:
            month, day, year = value.split("/")
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        return value
    if isinstance(value, datetime):
        value = value.date()
    return value.isoformat()


def parse_game_date(value: date | datetime | str | None = None) -> date:
    """Coerce supported date inputs to a date object."""
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def is_game_final(game_status) -> bool:
    """Return True when a scoreboard gameStatus indicates a final game."""
    if game_status is None or (isinstance(game_status, float) and pd.isna(game_status)):
        return False
    if isinstance(game_status, str):
        return game_status.strip().lower() in {"3", "final"}
    return int(game_status) == 3


def api_pause(seconds: float = API_REQUEST_DELAY) -> None:
    """Sleep between API calls to reduce throttling."""
    if seconds > 0:
        time.sleep(seconds)

