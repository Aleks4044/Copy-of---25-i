"""Само-читачки ESPN Football клиент (јавни endpoints, без клуч).

Се користат ИСКЛУЧИВО јавните патеки:
  * /apis/site/v2/sports/soccer/{league}/scoreboard?dates=YYYYMMDD
  * /apis/site/v2/sports/soccer/{league}/summary?event={event_id}

Не се маскира прелистувач (ESPN блокира browser User-Agent), не се користат
приватни ресурси и не се измислуваат натпревари, статистики ниту квоти.
Предвидување се изведува САМО ако постојат реални boxscore статистики или
реални објавени квоти; во спротивно натпреварот е видлив како реален фикстур
со ознака „недостапно“.
"""

import logging
import time
from datetime import date, datetime, timezone
from typing import TypedDict
from zoneinfo import ZoneInfo

import requests

BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer"
TIMEOUT = 12
SCOREBOARD_CACHE_TTL = 60.0
SUMMARY_CACHE_TTL = 180.0
DETAIL_LIMIT = 8
DETAIL_DELAY = 0.15
LOCAL_TZ_NAME = "Europe/Skopje"

# Само заглавје за формат — БЕЗ User-Agent маскирање.
HEADERS: dict[str, str] = {"Accept": "application/json"}

LEAGUES: tuple[tuple[str, str], ...] = (
    ("eng.1", "Премиер лига"),
    ("esp.1", "Ла Лига"),
    ("ita.1", "Серија А"),
    ("ger.1", "Бундеслига"),
    ("fra.1", "Лига 1"),
    ("usa.1", "MLS"),
    ("bra.1", "Бразил Серија А"),
    ("uefa.champions", "Лига на шампиони"),
    ("uefa.europa", "Лига Европа"),
)

LEAGUE_LABELS: dict[str, str] = {key: label for key, label in LEAGUES}

UNAVAILABLE_NOTE = (
    "ESPN не одговори во дозволеното време или врати неочекуван формат."
)
EMPTY_NOTE = "ESPN не врати натпревари за избраниот датум и лиги."
NO_STATS_NOTE = (
    "ESPN сè уште не објавува статистики ниту квоти за овој натпревар, па "
    "предвидување не е достапно."
)

STAT_WEIGHTS: dict[str, float] = {
    "shotsontarget": 0.40,
    "totalshots": 0.25,
    "possessionpct": 0.20,
    "woncorners": 0.15,
}

STAT_LABELS_MK: dict[str, str] = {
    "possessionpct": "Поседување",
    "totalshots": "Удари",
    "shotsontarget": "Удари во гол",
    "shotsofftarget": "Удари надвор",
    "woncorners": "Корнери",
    "foulscommitted": "Прекршоци",
    "offsides": "Офсајди",
    "yellowcards": "Жолти картони",
    "redcards": "Црвени картони",
    "saves": "Одбранки",
    "accuratepasses": "Точни пасови",
    "totalpasses": "Пасови",
    "effectiveclearance": "Расчистувања",
}


class ESPNStat(TypedDict):
    label: str
    home: str
    away: str
    home_pct: float


class ESPNRow(TypedDict):
    id: str
    event_id: str
    league_key: str
    league: str
    home: str
    away: str
    home_logo: str
    away_logo: str
    score: str
    has_score: bool
    status: str
    status_text: str
    clock: str
    kickoff: str
    day_key: str
    venue: str
    pair_key: str
    covered: bool
    detail_url: str
    has_stats: bool
    stats: list[ESPNStat]
    has_odds: bool
    odds_label: str
    odd_home: float
    odd_draw: float
    odd_away: float
    over_under: float
    has_prediction: bool
    prediction_note: str
    basis_label: str
    market: str
    pick: str
    pick_side: str
    confidence: float
    prob_home: float
    prob_draw: float
    prob_away: float
    goals_market: str
    goals_pick: str
    goals_confidence: float


_SCOREBOARD_CACHE: dict[str, tuple[float, list[dict]]] = {}
_SUMMARY_CACHE: dict[str, tuple[float, dict]] = {}


def _local_zone() -> ZoneInfo | timezone:
    try:
        return ZoneInfo(LOCAL_TZ_NAME)
    except Exception as error:
        logging.exception("Unexpected error")
        logging.info(
            f"Локалната зона не е достапна ({type(error).__name__}); UTC."
        )
        return timezone.utc


def _clean(value: object) -> str:
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return ""


def _num(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace("%", "").replace(",", "").strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def pair_key(home: str, away: str) -> str:
    """Симетричен клуч, ист како кај останатите извори."""
    from app.states.sportscore_client import pair_key as normalize

    return normalize(home, away)


def _get_json(url: str, params: dict[str, str], label: str) -> dict | None:
    """Тивко GET барање; никогаш не крева исклучок."""
    try:
        response = requests.get(
            url, params=params, headers=HEADERS, timeout=TIMEOUT
        )
    except requests.RequestException as error:
        logging.exception("Unexpected error")
        logging.info(f"{label} не е достапно: {type(error).__name__}.")
        return None
    if response.status_code != 200:
        logging.info(f"{label} врати HTTP {response.status_code}.")
        return None
    try:
        payload = response.json()
    except ValueError:
        logging.info(f"{label} врати невалиден JSON.")
        return None
    return payload if isinstance(payload, dict) else None


def _espn_date(day: str) -> str:
    """ISO датум (YYYY-MM-DD) во ESPN формат YYYYMMDD."""
    if not day:
        return ""
    try:
        return date.fromisoformat(day[:10]).strftime("%Y%m%d")
    except ValueError:
        return ""


def _kickoff_label(raw: str) -> str:
    if not isinstance(raw, str) or len(raw) < 10:
        return "--:--"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return "--:--"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(_local_zone()).strftime("%H:%M")


def _day_key(raw: str) -> str:
    if not isinstance(raw, str) or len(raw) < 10:
        return ""
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw[:10]
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(_local_zone()).date().isoformat()


def _status(block: dict) -> tuple[str, str, str]:
    """Враќа (статус, читлив текст, часовник)."""
    type_block = block.get("type") if isinstance(block, dict) else None
    type_block = type_block if isinstance(type_block, dict) else {}
    name = _clean(type_block.get("name")).upper()
    state = _clean(type_block.get("state")).lower()
    detail = _clean(type_block.get("shortDetail")) or _clean(
        type_block.get("description")
    )
    clock = _clean(block.get("displayClock")) if isinstance(block, dict) else ""
    if "POSTPON" in name or "DELAY" in name:
        return "postponed", "Одложен", ""
    if "CANCEL" in name or "ABANDON" in name:
        return "cancelled", "Откажан", ""
    if state == "in" or "IN_PROGRESS" in name or "HALFTIME" in name:
        return "live", detail or "Во тек", clock
    if state == "post" or bool(type_block.get("completed")):
        return "finished", "Завршен", ""
    return "upcoming", detail or "Претстоен", ""


def _team(side: dict) -> tuple[str, str, str]:
    block = side.get("team") if isinstance(side, dict) else None
    block = block if isinstance(block, dict) else {}
    name = (
        _clean(block.get("displayName"))
        or _clean(block.get("name"))
        or _clean(block.get("shortDisplayName"))
    )
    return name, _clean(block.get("logo")), _clean(block.get("id"))


def _empty_row(
    event: dict, league_key: str, league_label: str
) -> ESPNRow | None:
    competitions = event.get("competitions")
    competitions = competitions if isinstance(competitions, list) else []
    comp = (
        competitions[0]
        if competitions and isinstance(competitions[0], dict)
        else {}
    )
    competitors = comp.get("competitors")
    competitors = competitors if isinstance(competitors, list) else []
    home_side: dict = {}
    away_side: dict = {}
    for side in competitors:
        if not isinstance(side, dict):
            continue
        if _clean(side.get("homeAway")) == "home":
            home_side = side
        elif _clean(side.get("homeAway")) == "away":
            away_side = side
    if not home_side or not away_side:
        return None
    home, home_logo, _hid = _team(home_side)
    away, away_logo, _aid = _team(away_side)
    if not home or not away:
        return None

    event_id = _clean(comp.get("id")) or _clean(event.get("id"))
    status, status_text, clock = _status(
        comp.get("status") or event.get("status") or {}
    )
    home_score = _num(home_side.get("score"))
    away_score = _num(away_side.get("score"))
    has_score = (
        status in ("live", "finished")
        and home_score is not None
        and away_score is not None
    )
    venue = comp.get("venue") if isinstance(comp.get("venue"), dict) else {}
    raw_date = _clean(comp.get("date")) or _clean(event.get("date"))

    return ESPNRow(
        id=f"espn-{league_key}-{event_id}",
        event_id=event_id,
        league_key=league_key,
        league=league_label,
        home=home,
        away=away,
        home_logo=home_logo,
        away_logo=away_logo,
        score=(f"{int(home_score)} - {int(away_score)}" if has_score else "vs"),
        has_score=has_score,
        status=status,
        status_text=status_text,
        clock=clock,
        kickoff=_kickoff_label(raw_date),
        day_key=_day_key(raw_date),
        venue=_clean(venue.get("fullName")) or "—",
        pair_key=pair_key(home, away),
        covered=False,
        detail_url=(
            f"https://www.espn.com/soccer/match/_/gameId/{event_id}"
            if event_id
            else ""
        ),
        has_stats=False,
        stats=[],
        has_odds=False,
        odds_label="",
        odd_home=0.0,
        odd_draw=0.0,
        odd_away=0.0,
        over_under=0.0,
        has_prediction=False,
        prediction_note=NO_STATS_NOTE,
        basis_label="",
        market="",
        pick="",
        pick_side="",
        confidence=0.0,
        prob_home=0.0,
        prob_draw=0.0,
        prob_away=0.0,
        goals_market="",
        goals_pick="",
        goals_confidence=0.0,
    )


def _fetch_scoreboard(league_key: str, day: str) -> list[dict]:
    cache_key = f"{league_key}|{day}"
    now = time.monotonic()
    cached = _SCOREBOARD_CACHE.get(cache_key)
    if cached is not None and now - cached[0] < SCOREBOARD_CACHE_TTL:
        return cached[1]
    params: dict[str, str] = {}
    espn_day = _espn_date(day)
    if espn_day:
        params["dates"] = espn_day
    payload = _get_json(
        f"{BASE_URL}/{league_key}/scoreboard",
        params,
        f"ESPN scoreboard {league_key}",
    )
    if payload is None:
        return []
    events = payload.get("events")
    rows = (
        [row for row in events if isinstance(row, dict)]
        if isinstance(events, list)
        else []
    )
    _SCOREBOARD_CACHE[cache_key] = (now, rows)
    return rows


def fetch_rows(
    day: str, leagues: tuple[str, ...] | None = None
) -> tuple[list[ESPNRow], str]:
    """Вчитува реални ESPN настани за избраниот датум и лиги."""
    keys = leagues or tuple(key for key, _label in LEAGUES)
    rows: list[ESPNRow] = []
    reachable = 0
    for league_key in keys:
        label = LEAGUE_LABELS.get(league_key, league_key)
        events = _fetch_scoreboard(league_key, day)
        if events:
            reachable += 1
        for event in events:
            row = _empty_row(event, league_key, label)
            if row is None:
                continue
            if any(item["id"] == row["id"] for item in rows):
                continue
            rows.append(row)
    if not rows:
        return [], UNAVAILABLE_NOTE if reachable == 0 else EMPTY_NOTE
    matching = [row for row in rows if not day or row["day_key"] == day[:10]]
    if matching:
        return matching, ""
    return rows, (
        "ESPN не врати настани точно за избраниот датум, па прикажани се "
        "точно вратените реални настани."
    )


def _fetch_summary(league_key: str, event_id: str) -> dict:
    cache_key = f"{league_key}|{event_id}"
    now = time.monotonic()
    cached = _SUMMARY_CACHE.get(cache_key)
    if cached is not None and now - cached[0] < SUMMARY_CACHE_TTL:
        return cached[1]
    payload = _get_json(
        f"{BASE_URL}/{league_key}/summary",
        {"event": event_id},
        f"ESPN summary {event_id}",
    )
    if payload is None:
        return {}
    _SUMMARY_CACHE[cache_key] = (now, payload)
    return payload


def _stat_key(name: str) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def _stat_pairs(payload: dict) -> list[tuple[str, float, float, str, str]]:
    """Реални парови статистики (клуч, дома, гости, приказ дома, приказ гости)."""
    boxscore = payload.get("boxscore")
    boxscore = boxscore if isinstance(boxscore, dict) else {}
    teams = boxscore.get("teams")
    teams = teams if isinstance(teams, list) else []
    home_stats: dict[str, tuple[float, str]] = {}
    away_stats: dict[str, tuple[float, str]] = {}
    for block in teams:
        if not isinstance(block, dict):
            continue
        side = _clean(block.get("homeAway"))
        target = home_stats if side == "home" else away_stats
        rows = block.get("statistics")
        rows = rows if isinstance(rows, list) else []
        for stat in rows:
            if not isinstance(stat, dict):
                continue
            key = _stat_key(
                _clean(stat.get("name")) or _clean(stat.get("label"))
            )
            if not key:
                continue
            value = _num(stat.get("value"))
            display = _clean(stat.get("displayValue"))
            if value is None:
                value = _num(display)
            if value is None:
                continue
            target[key] = (value, display or f"{value:g}")
    pairs: list[tuple[str, float, float, str, str]] = []
    for key, (home_value, home_display) in home_stats.items():
        if key not in away_stats:
            continue
        away_value, away_display = away_stats[key]
        pairs.append((key, home_value, away_value, home_display, away_display))
    return pairs


def _build_stats(
    pairs: list[tuple[str, float, float, str, str]],
) -> list[ESPNStat]:
    stats: list[ESPNStat] = []
    for key, home, away, home_display, away_display in pairs[:12]:
        total = home + away
        share = (home / total * 100.0) if total > 0 else 0.0
        stats.append(
            ESPNStat(
                label=STAT_LABELS_MK.get(key, key),
                home=home_display,
                away=away_display,
                home_pct=round(max(0.0, min(100.0, share)), 1),
            )
        )
    return stats


def _weighted_share(
    pairs: list[tuple[str, float, float, str, str]],
) -> tuple[float, float, bool]:
    """Дел на домашниот тим (0-100) и вкупни удари од реални статистики."""
    weight_total = 0.0
    accumulated = 0.0
    shots_total = 0.0
    for key, home, away, _hd, _ad in pairs:
        total = home + away
        if total <= 0.0:
            continue
        if key in ("shotsontarget", "totalshots") and shots_total <= 0.0:
            shots_total = total
        weight = STAT_WEIGHTS.get(key)
        if weight is None:
            continue
        accumulated += weight * (home / total * 100.0)
        weight_total += weight
    if weight_total <= 0.0:
        return 0.0, shots_total, False
    return round(accumulated / weight_total, 1), shots_total, True


def _american_decimal(value: float) -> float:
    if value < 0.0:
        return round(1.0 + 100.0 / abs(value), 2)
    if value > 0.0:
        return round(1.0 + value / 100.0, 2)
    return 0.0


def _odds_from_summary(payload: dict) -> dict[str, float | str]:
    """Реални квоти од ESPN (само ако постојат moneyline вредности)."""
    blocks = payload.get("odds")
    blocks = blocks if isinstance(blocks, list) else []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        home = block.get("homeTeamOdds")
        away = block.get("awayTeamOdds")
        draw = block.get("drawOdds")
        home_ml = (
            _num((home or {}).get("moneyLine"))
            if isinstance(home, dict)
            else None
        )
        away_ml = (
            _num((away or {}).get("moneyLine"))
            if isinstance(away, dict)
            else None
        )
        draw_ml = (
            _num((draw or {}).get("moneyLine"))
            if isinstance(draw, dict)
            else None
        )
        if home_ml is None or away_ml is None or draw_ml is None:
            continue
        provider = block.get("provider")
        provider = provider if isinstance(provider, dict) else {}
        out: dict[str, float | str] = {
            "provider": _clean(provider.get("displayName"))
            or _clean(provider.get("name"))
            or "ESPN",
            "odd_home": _american_decimal(home_ml),
            "odd_draw": _american_decimal(draw_ml),
            "odd_away": _american_decimal(away_ml),
        }
        over_under = _num(block.get("overUnder"))
        if over_under is not None and over_under > 0.0:
            out["over_under"] = round(over_under, 1)
        over_odds = _num(block.get("overOdds"))
        under_odds = _num(block.get("underOdds"))
        if over_odds is not None:
            out["odd_over"] = _american_decimal(over_odds)
        if under_odds is not None:
            out["odd_under"] = _american_decimal(under_odds)
        return out
    return {}


def _normalize3(
    values: tuple[float, float, float],
) -> tuple[float, float, float]:
    total = sum(max(0.0001, value) for value in values)
    home = round(max(0.0001, values[0]) / total * 100.0, 1)
    draw = round(max(0.0001, values[1]) / total * 100.0, 1)
    away = round(max(0.5, 100.0 - home - draw), 1)
    return home, draw, away


def _apply_prediction_from_stats(
    row: ESPNRow, pairs: list[tuple[str, float, float, str, str]]
) -> bool:
    share, shots_total, usable = _weighted_share(pairs)
    if not usable:
        return False
    adjusted = share
    parts = row["score"].split("-")
    goals_now = 0.0
    if row["has_score"] and len(parts) == 2:
        try:
            home_goals = int(parts[0].strip())
            away_goals = int(parts[1].strip())
            adjusted = share + (home_goals - away_goals) * 6.0
            goals_now = float(home_goals + away_goals)
        except ValueError:
            adjusted = share
    adjusted = max(3.0, min(97.0, adjusted))
    draw = max(6.0, 26.0 - abs(adjusted - 50.0) * 0.35)
    rest = max(2.0, 100.0 - draw)
    prob_home = round(rest * (adjusted / 100.0), 1)
    prob_away = round(max(1.0, rest - prob_home), 1)
    prob_draw = round(max(1.0, 100.0 - prob_home - prob_away), 1)
    _set_prediction(
        row,
        prob_home,
        prob_draw,
        prob_away,
        "Изведено од реални ESPN статистики",
        "ESPN boxscore",
    )
    if shots_total > 0.0 or row["has_score"]:
        expected = goals_now + shots_total * 0.12
        if expected >= 2.5:
            row["goals_pick"] = "Над 2.5 гола"
            row["goals_confidence"] = round(
                min(95.0, 50.0 + (expected - 2.5) * 18.0), 1
            )
        else:
            row["goals_pick"] = "Под 2.5 гола"
            row["goals_confidence"] = round(
                min(95.0, 50.0 + (2.5 - expected) * 18.0), 1
            )
        row["goals_market"] = "Голови · од реални удари и резултат"
    return True


def _apply_prediction_from_odds(
    row: ESPNRow, odds: dict[str, float | str]
) -> bool:
    odd_home = float(odds.get("odd_home") or 0.0)
    odd_draw = float(odds.get("odd_draw") or 0.0)
    odd_away = float(odds.get("odd_away") or 0.0)
    if odd_home <= 1.0 or odd_draw <= 1.0 or odd_away <= 1.0:
        return False
    prob_home, prob_draw, prob_away = _normalize3(
        (1.0 / odd_home, 1.0 / odd_draw, 1.0 / odd_away)
    )
    _set_prediction(
        row,
        prob_home,
        prob_draw,
        prob_away,
        "Изведено од реални ESPN квоти",
        f"квоти · {odds.get('provider')}",
    )
    over_odds = float(odds.get("odd_over") or 0.0)
    under_odds = float(odds.get("odd_under") or 0.0)
    line = float(odds.get("over_under") or 0.0)
    if line > 0.0 and over_odds > 1.0 and under_odds > 1.0:
        total = 1.0 / over_odds + 1.0 / under_odds
        over_pct = round(1.0 / over_odds / total * 100.0, 1)
        if over_pct >= 50.0:
            row["goals_pick"] = f"Над {line:g} гола"
            row["goals_confidence"] = over_pct
        else:
            row["goals_pick"] = f"Под {line:g} гола"
            row["goals_confidence"] = round(100.0 - over_pct, 1)
        row["goals_market"] = "Голови · имплицирано од реални квоти"
    return True


def _set_prediction(
    row: ESPNRow,
    prob_home: float,
    prob_draw: float,
    prob_away: float,
    market: str,
    basis: str,
) -> None:
    options = [
        (prob_home, f"1 · {row['home']}", "home"),
        (prob_draw, "X · Реми", "draw"),
        (prob_away, f"2 · {row['away']}", "away"),
    ]
    best = max(options, key=lambda item: item[0])
    row["prob_home"] = prob_home
    row["prob_draw"] = prob_draw
    row["prob_away"] = prob_away
    row["pick"] = best[1]
    row["pick_side"] = best[2]
    row["confidence"] = round(min(97.0, best[0]), 1)
    row["market"] = market
    row["basis_label"] = basis
    row["has_prediction"] = True
    row["prediction_note"] = ""


def enrich_rows(rows: list[ESPNRow], limit: int = DETAIL_LIMIT) -> int:
    """Чита summary за ограничен број настани (live/завршени имаат приоритет)."""
    order = {"live": 0, "finished": 1, "upcoming": 2}
    targets = sorted(rows, key=lambda r: order.get(r["status"], 3))
    done = 0
    for row in targets:
        if done >= limit:
            break
        if not row["event_id"]:
            continue
        payload = _fetch_summary(row["league_key"], row["event_id"])
        if not payload:
            continue
        try:
            pairs = _stat_pairs(payload)
            if pairs:
                row["stats"] = _build_stats(pairs)
                row["has_stats"] = len(row["stats"]) > 0
            odds = _odds_from_summary(payload)
            if odds:
                row["has_odds"] = True
                row["odds_label"] = str(odds.get("provider") or "ESPN")
                row["odd_home"] = float(odds.get("odd_home") or 0.0)
                row["odd_draw"] = float(odds.get("odd_draw") or 0.0)
                row["odd_away"] = float(odds.get("odd_away") or 0.0)
                row["over_under"] = float(odds.get("over_under") or 0.0)
            applied = False
            if pairs:
                applied = _apply_prediction_from_stats(row, pairs)
            if not applied and odds:
                applied = _apply_prediction_from_odds(row, odds)
            if not applied:
                row["prediction_note"] = NO_STATS_NOTE
        except Exception as error:
            logging.exception("Unexpected error")
            logging.info(
                f"ESPN деталите не се применети: {type(error).__name__}"
            )
            continue
        done += 1
        time.sleep(DETAIL_DELAY)
    return done
