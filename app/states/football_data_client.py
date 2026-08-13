"""Само-читачки клиент за football-data.co.uk CSV фајлови.

Се користи ИСКЛУЧИВО директен HTTP GET кон јавните CSV патеки:

    https://www.football-data.co.uk/mmz4281/{SEASON}/{LEAGUE}.csv

Не се стругаат HTML страници, не се заобиколува ниту една заштита и ниту
една вредност не се измислува. Се читаат САМО реални колони:

    Date, Time, HomeTeam, AwayTeam, FTHG, FTAG, FTR, HTHG, HTAG, HTR,
    HS, AS, HST, AST, HC, AC, HY, AY, HR, AR и квоти кога се објавени.

Овој извор НЕ обезбедува xG, па xG никаде не се прикажува ниту се
претставува како постоечки. Предвидувањето е ЈАСНО означена хеуристика
изведена од реалната форма пред натпреварот (голови, удари во гол, поени,
корнери) и од реалните објавени квоти кога ги има.
"""

import csv
import logging
import math
import time
from datetime import datetime
from io import StringIO
from typing import TypedDict

import requests

BASE_URL = "https://www.football-data.co.uk/mmz4281"
TIMEOUT = 15
CACHE_TTL = 1800.0
REQUEST_DELAY = 0.2
MAX_ROWS_PER_LEAGUE = 8
MIN_HISTORY = 3

HEADERS: dict[str, str] = {
    "User-Agent": "BSD-Football/1.0 (read-only CSV download)",
    "Accept": "text/csv,text/plain",
}

ATTRIBUTION = (
    "Извор: football-data.co.uk · директно преземање на јавни CSV фајлови "
    "(без стругање на HTML)"
)
NO_XG_NOTE = (
    "football-data.co.uk НЕ објавува xG, па xG никаде не се прикажува и не "
    "се измислува. Предвидувањето е хеуристика од реални бројки."
)
UNAVAILABLE_NOTE = (
    "football-data.co.uk не одговори во дозволеното време или врати "
    "неочекуван формат за овие лиги."
)
EMPTY_NOTE = (
    "Ниту еден CSV фајл на football-data.co.uk не врати натпревари со реални "
    "имена на тимови."
)
NO_HISTORY_NOTE = (
    "Нема доволно претходни натпревари во сезоната ниту објавени квоти за "
    "овој ред, па предвидување не се пресметува."
)

# Лиги што вообичаено носат целосни статистички колони (HS/HST/HC/HY/HR).
LEAGUES: tuple[tuple[str, str], ...] = (
    ("E0", "Англија · Премиер лига"),
    ("E1", "Англија · Чемпионшип"),
    ("D1", "Германија · Бундеслига"),
    ("I1", "Италија · Серија А"),
    ("SP1", "Шпанија · Ла Лига"),
    ("F1", "Франција · Лига 1"),
    ("N1", "Холандија · Ередивизие"),
    ("P1", "Португалија · Прва лига"),
)

# Прво тековната, потоа претходната сезона (се користи првата достапна).
SEASONS: tuple[str, ...] = ("2526", "2425")

# Групи квоти по приоритет. Pinnacle (PS*) намерно НЕ се користи бидејќи
# изворот го означува како нестабилен од јули 2025.
ODDS_SETS: tuple[tuple[str, str, str, str], ...] = (
    ("Пазарен просек (Avg)", "AvgH", "AvgD", "AvgA"),
    ("Пазарен просек (BbAv)", "BbAvH", "BbAvD", "BbAvA"),
    ("Bet365", "B365H", "B365D", "B365A"),
    ("Bet&Win", "BWH", "BWD", "BWA"),
    ("Максимални квоти (Max)", "MaxH", "MaxD", "MaxA"),
)

STAT_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("Удари", "HS", "AS"),
    ("Удари во гол", "HST", "AST"),
    ("Корнери", "HC", "AC"),
    ("Жолти картони", "HY", "AY"),
    ("Црвени картони", "HR", "AR"),
)

_CACHE: dict[str, tuple[float, dict]] = {}


class FDStat(TypedDict):
    label: str
    home: str
    away: str
    home_pct: float


class FootballDataRow(TypedDict):
    id: str
    league_key: str
    league: str
    season: str
    season_label: str
    date_key: str
    date_label: str
    kickoff: str
    home: str
    away: str
    pair_key: str
    has_ft: bool
    ft_home: int
    ft_away: int
    ft_score: str
    has_ht: bool
    ht_home: int
    ht_away: int
    ht_score: str
    has_stats: bool
    stats: list[FDStat]
    has_odds: bool
    odds_label: str
    odd_home: float
    odd_draw: float
    odd_away: float
    has_prediction: bool
    prediction_note: str
    market: str
    basis_label: str
    history_label: str
    pick: str
    pick_side: str
    confidence: float
    prob_home: float
    prob_draw: float
    prob_away: float
    settled: bool
    actual_side: str
    actual_label: str
    is_correct: bool


class FDStatus(TypedDict):
    key: str
    label: str
    url: str
    season_label: str
    status_code: int
    status_label: str
    kind: str
    rows: int
    used_rows: int
    available: bool
    note: str


class FootballDataSnapshot(TypedDict):
    rows: list[FootballDataRow]
    statuses: list[FDStatus]
    note: str
    error: str


def pair_key(home: str, away: str) -> str:
    """Симетричен клуч, идентичен со останатите извори во апликацијата."""
    from app.states.sportscore_client import pair_key as normalize

    return normalize(home, away)


def _clean(value: object) -> str:
    if isinstance(value, str):
        return " ".join(value.replace("\xa0", " ").split())
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return ""


def _num(value: object) -> float | None:
    text = _clean(value).replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _int(value: object) -> int | None:
    number = _num(value)
    if number is None:
        return None
    return int(round(number))


def _season_label(code: str) -> str:
    if len(code) != 4 or not code.isdigit():
        return code
    return f"20{code[:2]}/{code[2:]}"


def _parse_date(raw: str) -> tuple[str, str]:
    """Враќа (ISO клуч за сортирање, читлива ознака)."""
    text = _clean(raw)
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text, fmt).date()
        except ValueError:
            continue
        return parsed.isoformat(), parsed.strftime("%d.%m.%Y")
    return "", text or "—"


def _status_label(code: int) -> tuple[str, str]:
    if code == 200:
        return "200 · достапно", "ok"
    if code == 0:
        return "мрежна грешка / timeout", "error"
    if code == 404:
        return "404 · недостапно", "limited"
    if code == 429:
        return "429 · ограничено", "limited"
    return f"HTTP {code}", "error"


def _fetch_csv(season: str, league: str) -> tuple[list[dict], int, str]:
    """Едно обично GET барање за еден CSV фајл. Никогаш не крева исклучок."""
    url = f"{BASE_URL}/{season}/{league}.csv"
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as error:
        logging.exception("Unexpected error")
        logging.info(
            f"football-data {league} {season} не е достапно: "
            f"{type(error).__name__}"
        )
        return [], 0, url
    if response.status_code != 200:
        logging.info(
            f"football-data {league} {season} врати HTTP "
            f"{response.status_code}."
        )
        return [], response.status_code, url
    try:
        body = response.content.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(StringIO(body))
        rows: list[dict] = []
        for raw in reader:
            if not isinstance(raw, dict):
                continue
            item = {
                _clean(key): value
                for key, value in raw.items()
                if key is not None
            }
            if _clean(item.get("HomeTeam")) and _clean(item.get("AwayTeam")):
                rows.append(item)
    except Exception as error:
        logging.exception("Unexpected error")
        logging.info(f"football-data CSV не е парсиран: {error}")
        return [], 200, url
    return rows, 200, url


def _empty_form() -> dict[str, float]:
    return {
        "played": 0.0,
        "points": 0.0,
        "gf": 0.0,
        "ga": 0.0,
        "sot": 0.0,
        "shots": 0.0,
        "corners": 0.0,
    }


def _update_form(forms: dict[str, dict[str, float]], raw: dict) -> None:
    """Ја ажурира формата САМО од реални, одиграни редови."""
    home = _clean(raw.get("HomeTeam"))
    away = _clean(raw.get("AwayTeam"))
    ft_home = _int(raw.get("FTHG"))
    ft_away = _int(raw.get("FTAG"))
    if not home or not away or ft_home is None or ft_away is None:
        return
    home_form = forms.setdefault(home, _empty_form())
    away_form = forms.setdefault(away, _empty_form())
    home_form["played"] += 1.0
    away_form["played"] += 1.0
    home_form["gf"] += float(ft_home)
    home_form["ga"] += float(ft_away)
    away_form["gf"] += float(ft_away)
    away_form["ga"] += float(ft_home)
    if ft_home > ft_away:
        home_form["points"] += 3.0
    elif ft_home == ft_away:
        home_form["points"] += 1.0
        away_form["points"] += 1.0
    else:
        away_form["points"] += 3.0
    for key, home_field, away_field in (
        ("sot", "HST", "AST"),
        ("shots", "HS", "AS"),
        ("corners", "HC", "AC"),
    ):
        home_value = _num(raw.get(home_field))
        away_value = _num(raw.get(away_field))
        if home_value is not None:
            home_form[key] += home_value
        if away_value is not None:
            away_form[key] += away_value


def _per_game(form: dict[str, float], key: str) -> float:
    played = form.get("played", 0.0)
    if played <= 0.0:
        return 0.0
    return form.get(key, 0.0) / played


def _form_probs(
    home_form: dict[str, float], away_form: dict[str, float]
) -> tuple[float, float, float] | None:
    """1X2 веројатности од реалната форма пред натпреварот."""
    if (
        home_form.get("played", 0.0) < MIN_HISTORY
        or away_form.get("played", 0.0) < MIN_HISTORY
    ):
        return None
    goal_edge = (
        _per_game(home_form, "gf")
        - _per_game(home_form, "ga")
        - (_per_game(away_form, "gf") - _per_game(away_form, "ga"))
    )
    sot_edge = (_per_game(home_form, "sot") - _per_game(away_form, "sot")) / 2.0
    corner_edge = (
        _per_game(home_form, "corners") - _per_game(away_form, "corners")
    ) / 4.0
    point_edge = _per_game(home_form, "points") - _per_game(away_form, "points")
    edge = (
        0.55 * goal_edge
        + 0.22 * sot_edge
        + 0.05 * corner_edge
        + 0.18 * point_edge
        + 0.35
    )
    edge = max(-3.5, min(3.5, edge))
    draw = max(14.0, 30.0 - abs(edge) * 5.5)
    rest = 100.0 - draw
    share = 1.0 / (1.0 + math.exp(-edge * 0.95))
    home = rest * share
    away = rest - home
    return round(home, 1), round(draw, 1), round(max(1.0, away), 1)


def _implied_probs(raw: dict) -> tuple[str, float, float, float] | None:
    """Имплицирани веројатности од реални објавени квоти (без маржа)."""
    for label, home_key, draw_key, away_key in ODDS_SETS:
        odd_home = _num(raw.get(home_key))
        odd_draw = _num(raw.get(draw_key))
        odd_away = _num(raw.get(away_key))
        if (
            odd_home is None
            or odd_draw is None
            or odd_away is None
            or odd_home <= 1.0
            or odd_draw <= 1.0
            or odd_away <= 1.0
        ):
            continue
        inverse = (1.0 / odd_home, 1.0 / odd_draw, 1.0 / odd_away)
        total = sum(inverse)
        if total <= 0.0:
            continue
        return (
            label,
            round(inverse[0] / total * 100.0, 1),
            round(inverse[1] / total * 100.0, 1),
            round(inverse[2] / total * 100.0, 1),
        )
    return None


def _odds_values(raw: dict) -> tuple[str, float, float, float] | None:
    for label, home_key, draw_key, away_key in ODDS_SETS:
        odd_home = _num(raw.get(home_key))
        odd_draw = _num(raw.get(draw_key))
        odd_away = _num(raw.get(away_key))
        if (
            odd_home is not None
            and odd_draw is not None
            and odd_away is not None
            and odd_home > 1.0
            and odd_draw > 1.0
            and odd_away > 1.0
        ):
            return (
                label,
                round(odd_home, 2),
                round(odd_draw, 2),
                round(odd_away, 2),
            )
    return None


def _stats(raw: dict) -> list[FDStat]:
    rows: list[FDStat] = []
    for label, home_key, away_key in STAT_FIELDS:
        home = _num(raw.get(home_key))
        away = _num(raw.get(away_key))
        if home is None or away is None:
            continue
        total = home + away
        share = (home / total * 100.0) if total > 0.0 else 0.0
        rows.append(
            FDStat(
                label=label,
                home=f"{home:g}",
                away=f"{away:g}",
                home_pct=round(max(0.0, min(100.0, share)), 1),
            )
        )
    return rows


def _actual_side(ft_home: int, ft_away: int) -> tuple[str, str]:
    if ft_home > ft_away:
        return "home", "1 · домашен"
    if ft_home == ft_away:
        return "draw", "X · реми"
    return "away", "2 · гостин"


def _row_from_raw(
    raw: dict,
    league_key: str,
    league_label: str,
    season: str,
    forms: dict[str, dict[str, float]],
) -> FootballDataRow | None:
    home = _clean(raw.get("HomeTeam"))
    away = _clean(raw.get("AwayTeam"))
    if not home or not away:
        return None
    date_key, date_label = _parse_date(_clean(raw.get("Date")))
    kickoff = _clean(raw.get("Time")) or "--:--"
    ft_home = _int(raw.get("FTHG"))
    ft_away = _int(raw.get("FTAG"))
    has_ft = ft_home is not None and ft_away is not None
    ht_home = _int(raw.get("HTHG"))
    ht_away = _int(raw.get("HTAG"))
    has_ht = ht_home is not None and ht_away is not None
    stats = _stats(raw)

    odds = _odds_values(raw)
    implied = _implied_probs(raw)
    home_form = forms.get(home, _empty_form())
    away_form = forms.get(away, _empty_form())
    form_probs = _form_probs(home_form, away_form)

    prob_home = prob_draw = prob_away = 0.0
    basis = ""
    market = ""
    note = NO_HISTORY_NOTE
    has_prediction = False
    if form_probs is not None and implied is not None:
        prob_home = round(0.5 * implied[1] + 0.5 * form_probs[0], 1)
        prob_draw = round(0.5 * implied[2] + 0.5 * form_probs[1], 1)
        prob_away = round(max(1.0, 100.0 - prob_home - prob_draw), 1)
        basis = (
            f"реални квоти ({implied[0]}) + форма пред натпреварот "
            "(голови, удари во гол, поени, корнери)"
        )
        has_prediction = True
    elif implied is not None:
        prob_home, prob_draw, prob_away = implied[1], implied[2], implied[3]
        basis = f"имплицирано САМО од реални квоти ({implied[0]})"
        has_prediction = True
    elif form_probs is not None:
        prob_home, prob_draw, prob_away = form_probs
        basis = (
            "форма пред натпреварот (реални голови, удари во гол, поени, "
            "корнери) · без објавени квоти"
        )
        has_prediction = True

    pick = ""
    pick_side = ""
    confidence = 0.0
    if has_prediction:
        options = [
            (prob_home, f"1 · {home}", "home"),
            (prob_draw, "X · Реми", "draw"),
            (prob_away, f"2 · {away}", "away"),
        ]
        best = max(options, key=lambda item: item[0])
        pick, pick_side = best[1], best[2]
        confidence = round(best[0], 1)
        market = "1X2 · хеуристика од football-data.co.uk (без xG)"
        note = ""

    actual_side = ""
    actual_label = ""
    if has_ft:
        actual_side, actual_label = _actual_side(int(ft_home), int(ft_away))

    return FootballDataRow(
        id=f"fd-{league_key}-{season}-{date_key or 'na'}-"
        f"{pair_key(home, away).replace('|', '-').replace(' ', '_')}",
        league_key=league_key,
        league=league_label,
        season=season,
        season_label=_season_label(season),
        date_key=date_key,
        date_label=date_label,
        kickoff=kickoff,
        home=home,
        away=away,
        pair_key=pair_key(home, away),
        has_ft=has_ft,
        ft_home=int(ft_home) if has_ft else 0,
        ft_away=int(ft_away) if has_ft else 0,
        ft_score=(f"{int(ft_home)} - {int(ft_away)}" if has_ft else "vs"),
        has_ht=has_ht,
        ht_home=int(ht_home) if has_ht else 0,
        ht_away=int(ht_away) if has_ht else 0,
        ht_score=(f"HT: {int(ht_home)}-{int(ht_away)}" if has_ht else ""),
        has_stats=len(stats) > 0,
        stats=stats,
        has_odds=odds is not None,
        odds_label=odds[0] if odds is not None else "",
        odd_home=odds[1] if odds is not None else 0.0,
        odd_draw=odds[2] if odds is not None else 0.0,
        odd_away=odds[3] if odds is not None else 0.0,
        has_prediction=has_prediction,
        prediction_note=note,
        market=market,
        basis_label=basis,
        history_label=(
            f"форма од {int(home_form.get('played', 0.0))} / "
            f"{int(away_form.get('played', 0.0))} претходни натпревари"
        ),
        pick=pick,
        pick_side=pick_side,
        confidence=confidence,
        prob_home=prob_home,
        prob_draw=prob_draw,
        prob_away=prob_away,
        settled=has_ft and has_prediction,
        actual_side=actual_side,
        actual_label=actual_label,
        is_correct=bool(has_ft and has_prediction and actual_side == pick_side),
    )


def _build_league_rows(
    raw_rows: list[dict],
    league_key: str,
    league_label: str,
    season: str,
    limit: int,
) -> list[FootballDataRow]:
    """Ги гради редовите хронолошки, така што формата е строго пред-натпревар."""
    ordered = sorted(
        raw_rows, key=lambda raw: _parse_date(_clean(raw.get("Date")))[0]
    )
    forms: dict[str, dict[str, float]] = {}
    built: list[FootballDataRow] = []
    for raw in ordered:
        row = _row_from_raw(raw, league_key, league_label, season, forms)
        if row is not None:
            built.append(row)
        _update_form(forms, raw)
    tail = built[-limit:] if limit > 0 else built
    return list(reversed(tail))


def fetch_snapshot(
    limit_per_league: int = MAX_ROWS_PER_LEAGUE,
) -> FootballDataSnapshot:
    """Ги чита CSV фајловите и враќа само реални редови. Не крева исклучок."""
    cache_key = f"snapshot-{limit_per_league}"
    now = time.monotonic()
    cached = _CACHE.get(cache_key)
    if cached is not None and now - cached[0] < CACHE_TTL:
        return FootballDataSnapshot(**cached[1])

    rows: list[FootballDataRow] = []
    statuses: list[FDStatus] = []
    for index, (league_key, league_label) in enumerate(LEAGUES):
        if index > 0:
            time.sleep(REQUEST_DELAY)
        raw_rows: list[dict] = []
        status_code = 0
        url = f"{BASE_URL}/{SEASONS[0]}/{league_key}.csv"
        season_used = SEASONS[0]
        for season in SEASONS:
            candidate, code, candidate_url = _fetch_csv(season, league_key)
            status_code = code
            url = candidate_url
            season_used = season
            if candidate:
                raw_rows = candidate
                break
        league_rows: list[FootballDataRow] = []
        if raw_rows:
            try:
                league_rows = _build_league_rows(
                    raw_rows,
                    league_key,
                    league_label,
                    season_used,
                    limit_per_league,
                )
            except Exception as error:
                logging.exception(
                    f"Error: football-data редовите не се изградени: {error}"
                )
                league_rows = []
        rows.extend(league_rows)
        label, kind = _status_label(status_code)
        if league_rows:
            note = (
                f"Прочитани {len(raw_rows)} реални редови; прикажани "
                f"{len(league_rows)} најнови. Без xG — само реални голови, "
                "удари, корнери, картони и квоти."
            )
        elif raw_rows:
            note = (
                "CSV фајлот е достапен, но не даде ред со употребливи имена "
                "и бројки за приказ."
            )
        else:
            note = UNAVAILABLE_NOTE
        statuses.append(
            FDStatus(
                key=league_key,
                label=league_label,
                url=url,
                season_label=_season_label(season_used),
                status_code=status_code,
                status_label=label,
                kind=kind if league_rows else ("limited" if raw_rows else kind),
                rows=len(raw_rows),
                used_rows=len(league_rows),
                available=len(league_rows) > 0,
                note=note,
            )
        )

    rows.sort(key=lambda row: (row["date_key"], row["kickoff"]), reverse=True)
    snapshot = FootballDataSnapshot(
        rows=rows,
        statuses=statuses,
        note=ATTRIBUTION,
        error="" if rows else EMPTY_NOTE,
    )
    if rows:
        _CACHE[cache_key] = (time.monotonic(), dict(snapshot))
    return snapshot
