"""Безопасен мулти-извор слој за табот „T1x2“.

Правила што овој модул НИКОГАШ не ги нарушува:

* Не се измислуваат натпревари, статистики ниту предвидувања. Ако изворот е
  блокиран или не врати читливи редови — тоа јасно се означува.
* Не се заобиколува Cloudflare ниту друга бот-заштита, не се користи
  прелистувачка автоматизација (Playwright) и не се допираат приватни,
  админ или најавни патеки.
* Сите барања се обични, само-читачки GET барања со timeout.

Извори:
  1) SofaScore — едно обично барање кон јавниот JSON ресурс. Во нормални
     барања тој враќа HTTP 403 (Varnish), па изворот се означува како
     блокиран и НИШТО не се пресметува од него.
  2) Flashscore / Rezultati — обични барања кон јавните фудбалски страници
     на rezultati.com (без robots-забранетите /tablica/ и /zdrijeb/), а
     редовите се читаат само од реален серверски-рендериран текст со
     „домашен – гостин“ и статус/резултат.
  3) FBref — едно обично барање. Кога Cloudflare враќа 403, изворот се
     означува како недостапен, без измислување.

Предвидување се дава САМО кога изворот дава реален xG за двата тима.
"""

import logging
import re
import time
from datetime import date, datetime, timezone
from typing import TypedDict

import requests

from app.states.bsd_state import local_clock, local_today
from app.states.sportscore_client import pair_key

import asyncio

import reflex as rx

TIMEOUT = 12
CACHE_TTL = 120.0
MAX_ROWS = 40
NA_PREDICTION = "Недостапно"
NO_XG_REASON = "нема реален xG од изворот"

HEADERS: dict[str, str] = {
    "User-Agent": "BSD-Football/1.0 (read-only public pages)",
    "Accept": "text/html,application/json;q=0.9",
    "Accept-Language": "mk,hr;q=0.8,en;q=0.7",
}

# ── SofaScore ────────────────────────────────────────────────────────────
SOFASCORE_URLS: tuple[str, ...] = (
    "https://api.sofascore.com/api/v1/sport/football/scheduled-events/{day}",
    "https://www.sofascore.com/api/v1/sport/football/scheduled-events/{day}",
)
SOFASCORE_BLOCKED_NOTE = (
    "Јавниот JSON ресурс враќа HTTP 403 на обични барања. Не се користи "
    "прелистувачка автоматизација ниту заобиколување на заштитата, па не се "
    "вчитани редови и ништо не се измислува."
)
SOFASCORE_OK_NOTE = (
    "Обично само-читачко барање успеа. Прикажани се точно вратените реални "
    "настани (xG не е дел од овој ресурс)."
)

# ── Flashscore / Rezultati ──────────────────────────────────────────────
REZULTATI_BASE = "https://www.rezultati.com"
REZULTATI_PATHS: tuple[str, ...] = ("/nogomet/", "/")
REZULTATI_BLOCKED_SEGMENTS: tuple[str, ...] = (
    "/tablica/",
    "/zdrijeb/",
    "/admin",
    "/login",
    "/prijava",
)
REZULTATI_LIMITED_NOTE = (
    "Страницата одговара со HTTP 200, но списокот со натпревари се "
    "дополнува со JavaScript, па серверскиот HTML содржи малку читливи "
    "редови. Прикажани се САМО реално најдените парови „домашен – гостин“; "
    "статистики не се објавени и не се измислуваат."
)
REZULTATI_EMPTY_NOTE = (
    "Јавните страници не вратија ниту еден читлив пар „домашен – гостин“ во "
    "серверскиот HTML, па нема реални редови за приказ."
)
REZULTATI_UNAVAILABLE_NOTE = (
    "Јавните страници не одговорија во дозволеното време или вратија "
    "неочекуван формат."
)

# ── FBref ───────────────────────────────────────────────────────────────
FBREF_URL = "https://fbref.com/en/matches/"
FBREF_BLOCKED_NOTE = (
    "Cloudflare враќа HTTP 403 (challenge) на обични барања, а заштитата не "
    "се заобиколува. Затоа од FBref не се читаат ниту се измислуваат редови."
)
FBREF_UNAVAILABLE_NOTE = (
    "FBref не одговори во дозволеното време на обично барање."
)

EMPTY_NOTE = (
    "Заштитените и недостапните извори не вратија ниту еден употреблив "
    "реален ред. Наместо примерок или измислени податоци, тука не се "
    "прикажува ништо."
)
# Точниот текст за празната состојба во табот „T1x2“.
EMPTY_MATCHES_NOTE = "Нема натпревари за денес. Обиди се со копчето 'Освежи'."

_PAIR_RE = re.compile(r"^\s*(.{2,42}?)\s+(?:-|–|vs\.?|:)\s+(.{2,42}?)\s*$")
_SCORE_RE = re.compile(r"\b(\d{1,2})\s*[-:]\s*(\d{1,2})\b")
_TIME_RE = re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b")
_LIVE_RE = re.compile(r"\b(\d{1,2})['`′]|\bHT\b|\bLIVE\b", re.IGNORECASE)
_FINISHED_RE = re.compile(r"\b(FT|Završeno|Zavrseno|Kraj)\b", re.IGNORECASE)

_CACHE: dict[str, tuple[float, dict]] = {}


class TeamStats(TypedDict):
    possession: float
    shots: float
    shots_on_target: float
    xg: float
    corners: float
    yellow_cards: float


class MultiStatRow(TypedDict):
    label: str
    home: str
    away: str
    home_pct: float


class MultiMatch(TypedDict):
    id: str
    source: str
    source_label: str
    home: str
    away: str
    # Компатибилни имиња што ги очекува приказот (исти реални вредности).
    home_team: str
    away_team: str
    home_xg: float
    away_xg: float
    time: str
    kickoff: str
    day_key: str
    status: str
    status_label: str
    league: str
    score: str
    has_score: bool
    home_stats: TeamStats
    away_stats: TeamStats
    stat_rows: list[MultiStatRow]
    has_stats: bool
    form_home: str
    form_away: str
    has_form: bool
    prediction: str
    prediction_label: str
    prediction_reason: str
    confidence: float
    has_prediction: bool
    detail_url: str


class SourceStatus(TypedDict):
    key: str
    label: str
    endpoint: str
    status_code: int
    status_label: str
    kind: str
    available: bool
    rows: int
    note: str


class MultiSnapshot(TypedDict):
    matches: list[MultiMatch]
    statuses: list[SourceStatus]
    note: str


def _empty_stats() -> TeamStats:
    return TeamStats(
        possession=0.0,
        shots=0.0,
        shots_on_target=0.0,
        xg=0.0,
        corners=0.0,
        yellow_cards=0.0,
    )


def _clean(value: object) -> str:
    if isinstance(value, str):
        return " ".join(value.replace("\xa0", " ").split())
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return ""


def _text(node: object) -> str:
    if node is None:
        return ""
    getter = getattr(node, "get_text", None)
    if getter is None:
        return _clean(node)
    return _clean(getter(" ", strip=True))


def _num(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().replace(",", "."))
        except ValueError:
            return None
    return None


def _status_label(code: int) -> tuple[str, str]:
    """Читлива ознака и вид (ok / limited / blocked / error)."""
    if code == 200:
        return "200 · достапно", "ok"
    if code == 403:
        return "403 · блокирано", "blocked"
    if code == 429:
        return "429 · ограничено", "limited"
    if code == 0:
        return "мрежна грешка / timeout", "error"
    return f"HTTP {code}", "error"


def _get(url: str, accept_json: bool = False) -> tuple[str, int]:
    """Обично само-читачко GET барање. Никогаш не крева исклучок."""
    headers = dict(HEADERS)
    if accept_json:
        headers["Accept"] = "application/json"
    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as error:
        logging.exception("Unexpected error")
        logging.info(f"Изворот не е достапен: {type(error).__name__}")
        return "", 0
    if response.status_code != 200:
        logging.info(f"Изворот врати HTTP {response.status_code}.")
        return "", response.status_code
    return response.text, 200


def _predict(
    home_stats: TeamStats, away_stats: TeamStats
) -> tuple[str, str, str, float, bool]:
    """Предвидување САМО од реален xG за двата тима."""
    home_xg = float(home_stats["xg"])
    away_xg = float(away_stats["xg"])
    if home_xg <= 0.0 or away_xg <= 0.0:
        return NA_PREDICTION, NA_PREDICTION, NO_XG_REASON, 0.0, False
    diff = home_xg - away_xg
    if diff > 0.5:
        pick, label = "1", "1 · домашен"
    elif diff < -0.5:
        pick, label = "2", "2 · гостин"
    else:
        pick, label = "X", "X · реми"
    confidence = round(min(90.0, 50.0 + abs(diff) * 14.0), 1)
    reason = (
        f"реален xG {home_xg:.2f} : {away_xg:.2f} "
        f"(разлика {abs(diff):.2f} гола)"
    )
    return pick, label, reason, confidence, True


def _stat_rows(home: TeamStats, away: TeamStats) -> list[MultiStatRow]:
    """Редови само за оние показатели што изворот навистина ги дава."""
    labels: tuple[tuple[str, str, str], ...] = (
        ("possession", "Поседување", "%"),
        ("shots", "Удари", ""),
        ("shots_on_target", "Удари во гол", ""),
        ("xg", "xG", ""),
        ("corners", "Корнери", ""),
        ("yellow_cards", "Жолти картони", ""),
    )
    rows: list[MultiStatRow] = []
    for key, label, suffix in labels:
        home_value = float(home[key])
        away_value = float(away[key])
        if home_value <= 0.0 and away_value <= 0.0:
            continue
        total = home_value + away_value
        share = (home_value / total * 100.0) if total > 0.0 else 0.0
        decimals = 2 if key == "xg" else 0
        rows.append(
            MultiStatRow(
                label=label,
                home=f"{home_value:.{decimals}f}{suffix}",
                away=f"{away_value:.{decimals}f}{suffix}",
                home_pct=round(max(0.0, min(100.0, share)), 1),
            )
        )
    return rows


def _finalize(row: MultiMatch) -> MultiMatch:
    """Дополнува изведени полиња (статистички редови и предвидување)."""
    # Компатибилните полиња секогаш ги пресликуваат реалните вредности; кога
    # изворот не дава xG, тие остануваат 0.0 и ништо не се измислува.
    row["home_team"] = row["home"]
    row["away_team"] = row["away"]
    row["home_xg"] = float(row["home_stats"]["xg"])
    row["away_xg"] = float(row["away_stats"]["xg"])
    row["time"] = row["kickoff"]
    rows = _stat_rows(row["home_stats"], row["away_stats"])
    pick, label, reason, confidence, has_prediction = _predict(
        row["home_stats"], row["away_stats"]
    )
    row["stat_rows"] = rows
    row["has_stats"] = len(rows) > 0
    row["prediction"] = pick
    row["prediction_label"] = label
    row["prediction_reason"] = reason
    row["confidence"] = confidence
    row["has_prediction"] = has_prediction
    row["has_form"] = bool(row["form_home"] or row["form_away"])
    return row


def _blank_row(
    source: str,
    source_label: str,
    home: str,
    away: str,
    kickoff: str,
    day_key: str,
    status: str,
    status_label: str,
    league: str,
    score: str,
    has_score: bool,
    detail_url: str = "",
) -> MultiMatch:
    slug = pair_key(home, away).replace("|", "-").replace(" ", "_")
    return MultiMatch(
        id=f"{source}-{slug}-{kickoff.replace(':', '')}",
        source=source,
        source_label=source_label,
        home=home,
        away=away,
        home_team=home,
        away_team=away,
        home_xg=0.0,
        away_xg=0.0,
        time=kickoff,
        kickoff=kickoff,
        day_key=day_key,
        status=status,
        status_label=status_label,
        league=league or "—",
        score=score,
        has_score=has_score,
        home_stats=_empty_stats(),
        away_stats=_empty_stats(),
        stat_rows=[],
        has_stats=False,
        form_home="",
        form_away="",
        has_form=False,
        prediction=NA_PREDICTION,
        prediction_label=NA_PREDICTION,
        prediction_reason=NO_XG_REASON,
        confidence=0.0,
        has_prediction=False,
        detail_url=detail_url,
    )


# ── SofaScore ────────────────────────────────────────────────────────────


def _sofascore_status(event: dict) -> tuple[str, str]:
    status = event.get("status")
    status = status if isinstance(status, dict) else {}
    kind = _clean(status.get("type")).lower()
    description = _clean(status.get("description"))
    if "progress" in kind or "live" in kind:
        return "live", description or "Во тек"
    if "finish" in kind or kind == "ft":
        return "finished", "Завршен"
    if "postpon" in kind or "cancel" in kind:
        return "postponed", description or "Одложен/Откажан"
    return "upcoming", description or "Претстоен"


def _sofascore_kickoff(event: dict) -> str:
    stamp = _num(event.get("startTimestamp"))
    if stamp is None or stamp <= 0.0:
        return "--:--"
    try:
        moment = datetime.fromtimestamp(stamp, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        logging.exception("Unexpected error")
        return "--:--"
    from app.states.bsd_state import _to_local

    return _to_local(moment).strftime("%H:%M")


def _sofascore_rows(payload: dict, day: str) -> list[MultiMatch]:
    events = payload.get("events")
    events = events if isinstance(events, list) else []
    rows: list[MultiMatch] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        home_block = event.get("homeTeam")
        away_block = event.get("awayTeam")
        home = _clean(
            (home_block or {}).get("name")
            if isinstance(home_block, dict)
            else ""
        )
        away = _clean(
            (away_block or {}).get("name")
            if isinstance(away_block, dict)
            else ""
        )
        if not home or not away:
            continue
        status, status_label = _sofascore_status(event)
        home_score = _num((event.get("homeScore") or {}).get("current"))
        away_score = _num((event.get("awayScore") or {}).get("current"))
        has_score = home_score is not None and away_score is not None
        tournament = event.get("tournament")
        league = ""
        if isinstance(tournament, dict):
            league = _clean(tournament.get("name"))
            unique = tournament.get("uniqueTournament")
            if not league and isinstance(unique, dict):
                league = _clean(unique.get("name"))
        rows.append(
            _finalize(
                _blank_row(
                    "sofascore",
                    "SofaScore",
                    home,
                    away,
                    _sofascore_kickoff(event),
                    day,
                    status,
                    status_label,
                    league,
                    (
                        f"{int(home_score)} - {int(away_score)}"
                        if has_score
                        else "vs"
                    ),
                    has_score,
                )
            )
        )
    return rows


def fetch_sofascore(day: str) -> tuple[list[MultiMatch], SourceStatus]:
    """Едно обично барање кон јавниот SofaScore JSON ресурс."""
    import json

    last_code = 0
    endpoint = SOFASCORE_URLS[0].format(day=day)
    for template in SOFASCORE_URLS:
        endpoint = template.format(day=day)
        body, code = _get(endpoint, accept_json=True)
        last_code = code
        if code != 200 or not body:
            continue
        try:
            payload = json.loads(body)
        except ValueError:
            logging.info("SofaScore врати невалиден JSON.")
            continue
        if not isinstance(payload, dict):
            continue
        rows = _sofascore_rows(payload, day)
        label, kind = _status_label(200)
        return rows, SourceStatus(
            key="sofascore",
            label="SofaScore",
            endpoint=endpoint,
            status_code=200,
            status_label=label,
            kind="ok" if rows else "limited",
            available=len(rows) > 0,
            rows=len(rows),
            note=SOFASCORE_OK_NOTE if rows else SOFASCORE_BLOCKED_NOTE,
        )

    label, kind = _status_label(last_code)
    note = (
        SOFASCORE_BLOCKED_NOTE
        if last_code in (401, 403)
        else "Ресурсот не врати употреблив JSON на обично барање."
    )
    return [], SourceStatus(
        key="sofascore",
        label="SofaScore",
        endpoint=endpoint,
        status_code=last_code,
        status_label=label,
        kind=kind if last_code else "error",
        available=False,
        rows=0,
        note=note,
    )


# ── Flashscore / Rezultati ──────────────────────────────────────────────


def _rezultati_status(context: str) -> tuple[str, str, str, bool]:
    """Статус, ознака, резултат и дали има резултат — од реален текст."""
    score = _SCORE_RE.search(context)
    if _FINISHED_RE.search(context):
        if score is not None:
            return (
                "finished",
                "Завршен",
                f"{score.group(1)} - {score.group(2)}",
                True,
            )
        return "finished", "Завршен", "vs", False
    if _LIVE_RE.search(context):
        if score is not None:
            return (
                "live",
                "Во тек",
                f"{score.group(1)} - {score.group(2)}",
                True,
            )
        return "live", "Во тек", "vs", False
    return "upcoming", "Претстоен", "vs", False


def _rezultati_kickoff(context: str) -> str:
    found = _TIME_RE.search(context)
    if found is None:
        return "--:--"
    return f"{int(found.group(1)):02d}:{found.group(2)}"


def _plausible_team(name: str) -> bool:
    if len(name) < 2 or len(name) > 42:
        return False
    if not any(ch.isalpha() for ch in name):
        return False
    lowered = name.lower()
    banned = (
        "cookie",
        "privatnost",
        "uslovi",
        "prijava",
        "registracija",
        "kladionic",
        "http",
        "www.",
        "tablica",
        "zdrijeb",
    )
    return not any(word in lowered for word in banned)


def _rezultati_rows(markup: str, day: str, url: str) -> list[MultiMatch]:
    """Читање само од реален серверски-рендериран текст."""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(markup, "html.parser")
    except Exception as error:
        logging.exception("Unexpected error")
        logging.info(f"Rezultati HTML не е парсиран: {type(error).__name__}")
        return []

    rows: list[MultiMatch] = []
    seen: set[str] = set()
    candidates: list[tuple[str, str]] = []

    for node in soup.find_all(["a", "div", "span", "li", "h2", "h3"]):
        text = _text(node)
        if not text or len(text) > 160:
            continue
        title = _clean(node.get("title")) if hasattr(node, "get") else ""
        for candidate in (title, text):
            found = _PAIR_RE.match(candidate)
            if found is None:
                continue
            home = _clean(found.group(1))
            away = _clean(found.group(2))
            if not _plausible_team(home) or not _plausible_team(away):
                continue
            parent_text = _text(getattr(node, "parent", None)) or text
            candidates.append((f"{home}|{away}", parent_text[:200]))
            key = pair_key(home, away)
            if key in seen:
                continue
            seen.add(key)
            status, status_label, score, has_score = _rezultati_status(
                parent_text
            )
            rows.append(
                _finalize(
                    _blank_row(
                        "rezultati",
                        "Flashscore / Rezultati",
                        home,
                        away,
                        _rezultati_kickoff(parent_text),
                        day,
                        status,
                        status_label,
                        "",
                        score,
                        has_score,
                        url,
                    )
                )
            )
            break
        if len(rows) >= MAX_ROWS:
            break
    return rows


def fetch_rezultati(day: str) -> tuple[list[MultiMatch], SourceStatus]:
    """Јавни фудбалски страници на rezultati.com (без забранетите патеки)."""
    rows: list[MultiMatch] = []
    last_code = 0
    endpoint = f"{REZULTATI_BASE}{REZULTATI_PATHS[0]}"
    for path in REZULTATI_PATHS:
        if any(segment in path for segment in REZULTATI_BLOCKED_SEGMENTS):
            continue
        endpoint = f"{REZULTATI_BASE}{path}"
        markup, code = _get(endpoint)
        last_code = code
        if code != 200 or not markup:
            continue
        rows.extend(_rezultati_rows(markup, day, endpoint))
        if rows:
            break
        time.sleep(0.4)

    if last_code != 200:
        label, kind = _status_label(last_code)
        return [], SourceStatus(
            key="rezultati",
            label="Flashscore / Rezultati",
            endpoint=endpoint,
            status_code=last_code,
            status_label=label,
            kind=kind if last_code else "error",
            available=False,
            rows=0,
            note=REZULTATI_UNAVAILABLE_NOTE,
        )

    label, _kind = _status_label(200)
    return rows, SourceStatus(
        key="rezultati",
        label="Flashscore / Rezultati",
        endpoint=endpoint,
        status_code=200,
        status_label=label,
        kind="ok" if rows else "limited",
        available=len(rows) > 0,
        rows=len(rows),
        note=REZULTATI_LIMITED_NOTE if rows else REZULTATI_EMPTY_NOTE,
    )


# ── FBref ───────────────────────────────────────────────────────────────


def fetch_fbref() -> tuple[list[MultiMatch], SourceStatus]:
    """Само едно обично барање; Cloudflare 403 значи недостапно."""
    _markup, code = _get(FBREF_URL)
    label, kind = _status_label(code)
    note = FBREF_BLOCKED_NOTE if code == 403 else FBREF_UNAVAILABLE_NOTE
    if code == 200:
        note = (
            "Страницата одговори со HTTP 200, но табелите со натпревари не се "
            "читаат автоматски од овој слој, па не се прикажуваат редови и "
            "ништо не се измислува."
        )
        kind = "limited"
    return [], SourceStatus(
        key="fbref",
        label="FBref",
        endpoint=FBREF_URL,
        status_code=code,
        status_label=label,
        kind=kind if code else "error",
        available=False,
        rows=0,
        note=note,
    )


# ── Собирање ────────────────────────────────────────────────────────────


def _dedupe(rows: list[MultiMatch]) -> list[MultiMatch]:
    """Де-дупликација по нормализиран пар тимови + почеток/ден."""
    out: list[MultiMatch] = []
    seen: set[str] = set()
    for row in rows:
        key = (
            f"{pair_key(row['home'], row['away'])}|"
            f"{row['day_key']}|{row['kickoff']}"
        )
        loose = f"{pair_key(row['home'], row['away'])}|{row['day_key']}"
        if key in seen or loose in seen:
            continue
        seen.add(key)
        seen.add(loose)
        out.append(row)
    return out


def collect_multi_source(day: str) -> MultiSnapshot:
    """Ги чита сите безопасни извори. Никогаш не крева исклучок."""
    now = time.monotonic()
    cached = _CACHE.get(day)
    if cached is not None and now - cached[0] < CACHE_TTL:
        return MultiSnapshot(**cached[1])

    rows: list[MultiMatch] = []
    statuses: list[SourceStatus] = []

    try:
        sofa_rows, sofa_status = fetch_sofascore(day)
        rows.extend(sofa_rows)
        statuses.append(sofa_status)
    except Exception as error:
        logging.exception(f"Error: SofaScore слојот падна: {error}")
        statuses.append(
            SourceStatus(
                key="sofascore",
                label="SofaScore",
                endpoint=SOFASCORE_URLS[0].format(day=day),
                status_code=0,
                status_label="неочекувана грешка",
                kind="error",
                available=False,
                rows=0,
                note=SOFASCORE_BLOCKED_NOTE,
            )
        )

    try:
        rez_rows, rez_status = fetch_rezultati(day)
        rows.extend(rez_rows)
        statuses.append(rez_status)
    except Exception as error:
        logging.exception(f"Error: Rezultati слојот падна: {error}")
        statuses.append(
            SourceStatus(
                key="rezultati",
                label="Flashscore / Rezultati",
                endpoint=f"{REZULTATI_BASE}{REZULTATI_PATHS[0]}",
                status_code=0,
                status_label="неочекувана грешка",
                kind="error",
                available=False,
                rows=0,
                note=REZULTATI_UNAVAILABLE_NOTE,
            )
        )

    try:
        fb_rows, fb_status = fetch_fbref()
        rows.extend(fb_rows)
        statuses.append(fb_status)
    except Exception as error:
        logging.exception(f"Error: FBref слојот падна: {error}")
        statuses.append(
            SourceStatus(
                key="fbref",
                label="FBref",
                endpoint=FBREF_URL,
                status_code=0,
                status_label="неочекувана грешка",
                kind="error",
                available=False,
                rows=0,
                note=FBREF_UNAVAILABLE_NOTE,
            )
        )

    order = {"live": 0, "upcoming": 1, "finished": 2, "postponed": 3}
    unique = _dedupe(rows)
    unique.sort(
        key=lambda row: (
            order.get(row["status"], 4),
            row["kickoff"],
            row["home"],
        )
    )
    unique = unique[:MAX_ROWS]

    snapshot = MultiSnapshot(
        matches=unique,
        statuses=statuses,
        note="" if unique else EMPTY_NOTE,
    )
    if unique:
        _CACHE[day] = (time.monotonic(), dict(snapshot))
    return snapshot


class MultiSourceState(rx.State):
    """Реални редови од безопасните извори; без примерок и без измислување."""

    matches: list[MultiMatch] = []
    source_statuses: list[SourceStatus] = []
    selected_day: str = ""
    fetched_at: str = "--:--:--"
    note: str
    is_loading: bool = False
    has_loaded: bool = False

    @rx.var
    def loading(self) -> bool:
        return self.is_loading

    @rx.var
    def selected_day_value(self) -> str:
        return self.selected_day or local_today().isoformat()

    @rx.var
    def selected_day_label(self) -> str:
        value = self.selected_day_value
        try:
            return date.fromisoformat(value[:10]).strftime("%d.%m.%Y")
        except ValueError:
            return value

    @rx.var
    def total_count(self) -> int:
        return len(self.matches)

    @rx.var
    def prediction_rows(self) -> list[MultiMatch]:
        return [row for row in self.matches if row["has_prediction"]]

    @rx.var
    def predictions(self) -> list[MultiMatch]:
        """Само редовите со реално изведено предвидување (од xG)."""
        return self.prediction_rows

    @rx.var
    def prediction_count(self) -> int:
        return len(self.prediction_rows)

    @rx.var
    def stats_count(self) -> int:
        return len([row for row in self.matches if row["has_stats"]])

    @rx.var
    def available_source_count(self) -> int:
        return len([row for row in self.source_statuses if row["available"]])

    @rx.var
    def source_count(self) -> int:
        return len(self.source_statuses)

    @rx.var
    def source_row_counts(self) -> list[dict[str, str]]:
        """Колку реални редови даде секој прочитан извор."""
        rows: list[dict[str, str]] = []
        for status in self.source_statuses:
            count = len(
                [row for row in self.matches if row["source"] == status["key"]]
            )
            rows.append(
                {
                    "key": status["key"],
                    "label": status["label"],
                    "count": str(count),
                }
            )
        return rows

    @rx.var
    def has_data(self) -> bool:
        return len(self.matches) > 0

    @rx.var
    def empty_label(self) -> str:
        return EMPTY_MATCHES_NOTE

    @rx.var
    def source_note(self) -> str:
        return self.note or EMPTY_NOTE

    @rx.var
    def summary_label(self) -> str:
        return (
            f"{self.total_count} реални редови · "
            f"{self.prediction_count} со предвидување од xG · "
            f"{self.available_source_count} од {self.source_count} извори "
            "вратија употребливи редови"
        )

    @rx.event(background=True)
    async def fetch_all_matches(self):
        """Ги чита сите безопасни извори без да падне при 403 или празен HTML."""
        async with self:
            if self.is_loading:
                return
            self.is_loading = True
            day = self.selected_day_value
        try:
            snapshot = await asyncio.to_thread(collect_multi_source, day)
        except Exception as error:
            logging.exception(f"Error: мулти-извор читањето не успеа: {error}")
            async with self:
                self.note = EMPTY_NOTE
                self.fetched_at = local_clock()
                self.has_loaded = True
                self.is_loading = False
            return
        async with self:
            # Сите собрани и де-дупликирани реални редови (вклучувајќи ги
            # Flashscore/Rezultati) секогаш се доделуваат тука. Кога ниту
            # еден извор не врати употреблив ред, листата останува празна —
            # никогаш не се додава примерок или измислен натпревар.
            rows = [row for row in snapshot["matches"] if row]
            self.matches = rows if rows else []
            self.source_statuses = snapshot["statuses"]
            self.note = snapshot["note"]
            self.fetched_at = local_clock()
            self.has_loaded = True
            self.is_loading = False
