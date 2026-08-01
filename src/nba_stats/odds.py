"""Betting lines and odds from the NBA live odds feed."""

from __future__ import annotations

from typing import Any

import pandas as pd
from nba_api.live.nba.endpoints.odds import Odds

from nba_stats.utils import normalize_game_id


def _pick_book(books: list[dict[str, Any]], preferred_book: str | None) -> dict[str, Any] | None:
    if not books:
        return None
    if preferred_book:
        for book in books:
            if book.get("name", "").lower() == preferred_book.lower():
                return book
    return books[0]


def _extract_market_lines(
    markets: list[dict[str, Any]],
    preferred_book: str | None,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "home_spread": None,
        "away_spread": None,
        "home_spread_odds": None,
        "away_spread_odds": None,
        "over_total": None,
        "under_total": None,
        "over_odds": None,
        "under_odds": None,
        "home_moneyline": None,
        "away_moneyline": None,
        "sportsbook": None,
    }

    for market in markets:
        market_name = (market.get("name") or market.get("group_name") or "").lower()
        book = _pick_book(market.get("books", []), preferred_book)
        if book is None:
            continue

        summary["sportsbook"] = summary["sportsbook"] or book.get("name")
        outcomes = book.get("outcomes", [])

        if "spread" in market_name:
            for outcome in outcomes:
                side = (outcome.get("type") or "").lower()
                if side == "home":
                    summary["home_spread"] = outcome.get("spread")
                    summary["home_spread_odds"] = outcome.get("odds")
                elif side == "away":
                    summary["away_spread"] = outcome.get("spread")
                    summary["away_spread_odds"] = outcome.get("odds")

        elif "total" in market_name or "over/under" in market_name:
            for outcome in outcomes:
                side = (outcome.get("type") or "").lower()
                if side == "over":
                    summary["over_total"] = outcome.get("odds_field_id") or outcome.get("spread")
                    # NBA odds feed stores the total line on spread for totals
                    summary["over_total"] = outcome.get("spread") or summary["over_total"]
                    summary["over_odds"] = outcome.get("odds")
                elif side == "under":
                    summary["under_total"] = outcome.get("spread") or summary["under_total"]
                    summary["under_odds"] = outcome.get("odds")

        elif "moneyline" in market_name or market_name == "2way":
            for outcome in outcomes:
                side = (outcome.get("type") or "").lower()
                if side == "home":
                    summary["home_moneyline"] = outcome.get("odds")
                elif side == "away":
                    summary["away_moneyline"] = outcome.get("odds")

    if summary["over_total"] is None and summary["under_total"] is not None:
        summary["over_total"] = summary["under_total"]
    if summary["under_total"] is None and summary["over_total"] is not None:
        summary["under_total"] = summary["over_total"]

    return summary


def get_odds_lines(preferred_book: str | None = "DraftKings") -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Fetch betting lines from the NBA live odds feed.

    Returns:
        Tuple of (detailed_lines, summary_lines) DataFrames.
        summary_lines has one row per game with spread, total, and moneyline.

    Empty DataFrames are returned when the live feed is unavailable (offseason,
    CDN blocks, or empty/non-JSON responses).
    """
    try:
        endpoint = Odds()
        games_data = endpoint.get_games()
    except (ValueError, TypeError, KeyError, OSError) as exc:
        # nba_api raises JSONDecodeError (a ValueError) when the CDN returns
        # HTML/"Access Denied" or an empty body — common offseason / blocks.
        print(f"Warning: live odds unavailable ({exc}); continuing with empty odds.")
        return pd.DataFrame(), pd.DataFrame()

    if games_data is None:
        return pd.DataFrame(), pd.DataFrame()

    raw_games = games_data.get_dict()
    if isinstance(raw_games, dict):
        raw_games = raw_games.get("games", [])

    detail_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for game in raw_games or []:
        game_id = normalize_game_id(game.get("gameId", ""))
        home_team_id = game.get("homeTeamId")
        away_team_id = game.get("awayTeamId")
        markets = game.get("markets", [])

        for market in markets:
            market_name = market.get("name") or market.get("group_name")
            for book in market.get("books", []):
                for outcome in book.get("outcomes", []):
                    detail_rows.append(
                        {
                            "game_id": game_id,
                            "home_team_id": home_team_id,
                            "away_team_id": away_team_id,
                            "market": market_name,
                            "sportsbook": book.get("name"),
                            "outcome_type": outcome.get("type"),
                            "odds": outcome.get("odds"),
                            "opening_odds": outcome.get("opening_odds"),
                            "odds_trend": outcome.get("odds_trend"),
                            "spread": outcome.get("spread"),
                            "opening_spread": outcome.get("opening_spread"),
                        }
                    )

        market_lines = _extract_market_lines(markets, preferred_book)
        summary_rows.append(
            {
                "game_id": game_id,
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                **market_lines,
            }
        )

    return pd.DataFrame(detail_rows), pd.DataFrame(summary_rows)
