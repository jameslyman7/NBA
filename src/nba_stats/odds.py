"""Betting lines and odds from NBA live feed and ESPN historical odds."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd
import requests
from nba_api.live.nba.endpoints.odds import Odds

from nba_stats.teams import normalize_espn_tricode, tricode_from_team_id
from nba_stats.utils import api_pause, normalize_game_id, parse_game_date

ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
ESPN_ODDS_URL = (
    "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba"
    "/events/{event_id}/competitions/{competition_id}/odds"
)


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


def _parse_line(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("+", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _espn_side_spread(side_odds: dict[str, Any] | None, fallback: float | None = None) -> float | None:
    if not side_odds:
        return fallback
    for key in ("close", "current", "open"):
        block = side_odds.get(key) or {}
        point_spread = block.get("pointSpread") or {}
        parsed = _parse_line(point_spread.get("american") or point_spread.get("alternateDisplayValue"))
        if parsed is not None:
            return parsed
    return fallback


def _pick_espn_provider(
    items: list[dict[str, Any]],
    preferred_book: str | None,
) -> dict[str, Any] | None:
    if not items:
        return None
    if preferred_book:
        preferred = preferred_book.lower()
        for item in items:
            name = (item.get("provider") or {}).get("name", "").lower()
            if preferred in name:
                return item
    # Prefer ESPN BET, else first provider.
    for item in items:
        name = (item.get("provider") or {}).get("name", "").lower()
        if "espn" in name:
            return item
    return items[0]


def get_espn_odds_for_date(
    game_date: date | datetime | str,
    preferred_book: str | None = "DraftKings",
    timeout: int = 30,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Fetch closing/current lines from ESPN for a specific date.

    Used when the NBA live odds feed has no data (historical dates / offseason).
    """
    export_date = parse_game_date(game_date)
    date_key = export_date.strftime("%Y%m%d")

    try:
        scoreboard = requests.get(
            ESPN_SCOREBOARD_URL,
            params={"dates": date_key},
            timeout=timeout,
        )
        scoreboard.raise_for_status()
        events = scoreboard.json().get("events", [])
    except (OSError, ValueError, requests.RequestException) as exc:
        print(f"Warning: ESPN scoreboard odds unavailable ({exc}); continuing with empty odds.")
        return pd.DataFrame(), pd.DataFrame()

    detail_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for event in events:
        competitions = event.get("competitions") or []
        if not competitions:
            continue
        competition = competitions[0]
        competitors = competition.get("competitors") or []
        try:
            home = next(c for c in competitors if c.get("homeAway") == "home")
            away = next(c for c in competitors if c.get("homeAway") == "away")
        except StopIteration:
            continue

        home_tricode = normalize_espn_tricode((home.get("team") or {}).get("abbreviation", ""))
        away_tricode = normalize_espn_tricode((away.get("team") or {}).get("abbreviation", ""))
        event_id = event.get("id")
        competition_id = competition.get("id") or event_id

        api_pause(0.35)
        try:
            odds_response = requests.get(
                ESPN_ODDS_URL.format(event_id=event_id, competition_id=competition_id),
                timeout=timeout,
            )
            odds_response.raise_for_status()
            items = odds_response.json().get("items", [])
        except (OSError, ValueError, requests.RequestException):
            continue

        book = _pick_espn_provider(items, preferred_book)
        if book is None:
            continue

        provider_name = (book.get("provider") or {}).get("name")
        home_spread = _espn_side_spread(book.get("homeTeamOdds"), _parse_line(book.get("spread")))
        away_spread = _espn_side_spread(
            book.get("awayTeamOdds"),
            None if home_spread is None else -home_spread,
        )
        total = _parse_line(book.get("overUnder"))

        summary_rows.append(
            {
                "game_id": "",
                "home_team_id": (home.get("team") or {}).get("id"),
                "away_team_id": (away.get("team") or {}).get("id"),
                "home_tricode": home_tricode,
                "away_tricode": away_tricode,
                "home_spread": home_spread,
                "away_spread": away_spread,
                "home_spread_odds": (book.get("homeTeamOdds") or {}).get("spreadOdds"),
                "away_spread_odds": (book.get("awayTeamOdds") or {}).get("spreadOdds"),
                "over_total": total,
                "under_total": total,
                "over_odds": book.get("overOdds"),
                "under_odds": book.get("underOdds"),
                "home_moneyline": (book.get("homeTeamOdds") or {}).get("moneyLine"),
                "away_moneyline": (book.get("awayTeamOdds") or {}).get("moneyLine"),
                "sportsbook": provider_name,
                "espn_event_id": event_id,
            }
        )

        detail_rows.append(
            {
                "game_id": "",
                "home_team_id": (home.get("team") or {}).get("id"),
                "away_team_id": (away.get("team") or {}).get("id"),
                "home_tricode": home_tricode,
                "away_tricode": away_tricode,
                "market": "spread",
                "sportsbook": provider_name,
                "outcome_type": "home",
                "odds": (book.get("homeTeamOdds") or {}).get("spreadOdds"),
                "spread": home_spread,
                "espn_event_id": event_id,
            }
        )
        detail_rows.append(
            {
                "game_id": "",
                "home_team_id": (home.get("team") or {}).get("id"),
                "away_team_id": (away.get("team") or {}).get("id"),
                "home_tricode": home_tricode,
                "away_tricode": away_tricode,
                "market": "total",
                "sportsbook": provider_name,
                "outcome_type": "over",
                "odds": book.get("overOdds"),
                "spread": total,
                "espn_event_id": event_id,
            }
        )

    return pd.DataFrame(detail_rows), pd.DataFrame(summary_rows)


def get_live_odds_lines(preferred_book: str | None = "DraftKings") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch betting lines from the NBA live odds feed (today's games only)."""
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
        home_tricode = tricode_from_team_id(home_team_id)
        away_tricode = tricode_from_team_id(away_team_id)
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
                            "home_tricode": home_tricode,
                            "away_tricode": away_tricode,
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
                "home_tricode": home_tricode,
                "away_tricode": away_tricode,
                **market_lines,
            }
        )

    return pd.DataFrame(detail_rows), pd.DataFrame(summary_rows)


def get_odds_lines(
    preferred_book: str | None = "DraftKings",
    game_date: date | datetime | str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Fetch betting lines for a date.

    Uses the NBA live odds feed for today's slate. Falls back to ESPN historical
    odds so past dates still get Spread / Total / ATS-OU.
    """
    export_date = parse_game_date(game_date)

    if export_date == date.today():
        live_details, live_summary = get_live_odds_lines(preferred_book=preferred_book)
        if not live_summary.empty:
            return live_details, live_summary

    espn_details, espn_summary = get_espn_odds_for_date(
        export_date,
        preferred_book=preferred_book,
    )
    if not espn_summary.empty:
        return espn_details, espn_summary

    if export_date == date.today():
        return live_details, live_summary
    return pd.DataFrame(), pd.DataFrame()
