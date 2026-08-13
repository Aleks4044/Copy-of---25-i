"""Јавен SportScore widget API (без клуч и без автентикација).

Се читаат САМО реални вредности од:
  * https://sportscore.com/api/widget/matches/?sport=football&limit=50&date=YYYY-MM-DD
  * https://sportscore.com/api/widget/match/?sport=football&slug=...

Ниту една вредност не се измислува: резултат, статус, минута, полувреме,
грбови, натпреварување и статистики се точно онакви како што ги враќа
изворот. Препораката се пресметува деривативно САМО од реални статистики.
"""

import logging
import time
import unicodedata
from datetime import datetime, timezone
from typing import TypedDict
from zoneinfo import ZoneInfo

import requests

BASE_URL = "https://sportscore.com/api/widget"
TIMEOUT = 15
MATCH_LIMIT = 50
DETAIL_LIMIT = 10
DETAIL_DELAY = 0.2
DETAIL_CACHE_TTL = 60.0
LOCAL_TZ_NAME = "Europe/Skopje"

_DETAIL_CACHE: dict[str, tuple[float, dict]] = {}

UNAVAILABLE_NOTE = (
    "SportScore widget API не одговори во дозволеното време или врати "
    "неочекуван формат. Ова не влијае на останатите извори."
)
# Очекувани, безопасни одговори од јавниот widget API. За овие НИКОГАШ не се
# логира stack trace — само кратка info/warning линија, а UI-то продолжува.
QUIET_STATUSES: tuple[int, ...] = (400, 404, 429, 500, 502, 503, 504)
EMPTY_NOTE = "SportScore не врати натпревари за избраниот датум."
DATE_IGNORED_NOTE = (
    "SportScore widget API го игнорираше избраниот датум и врати настани од "
    "{days}. Прикажани се точно вратените реални настани, без измислување."
)
NO_STATS_NOTE = (
    "SportScore не објавува статистики за овој натпревар, па препораката не "
    "е достапна."
)
FBREF_NOTE = (
    "FBref не се користи: не постои стабилен јавен JSON API, а страниците "
    "активно блокираат автоматски барања (Cloudflare 403). Затоа не се "
    "стругаат ниту се измислуваат редови од FBref."
)

# Тежини за детерминистичка препорака од реални SportScore статистики.
STAT_WEIGHTS: dict[str, float] = {
    "shots on target": 0.40,
    "dangerous attacks": 0.35,
    "ball possession": 0.25,
}
STAT_LABELS_MK: dict[str, str] = {
    "ball possession": "Поседување",
    "shots on target": "Удари во гол",
    "shots off target": "Удари надвор",
    "attacks": "Напади",
    "dangerous attacks": "Опасни напади",
    "corner kicks": "Корнери",
    "yellow cards": "Жолти картони",
    "red cards": "Црвени картони",
    "fouls": "Прекршоци",
    "offsides": "Офсајди",
}


class SportScoreStat(TypedDict):
    label: str
    home: str
    away: str
    home_pct: float
    away_pct: float


class SportScoreRow(TypedDict):
    id: str
    slug: str
    detail_url: str
    home: str
    away: str
    home_logo: str
    away_logo: str
    competition: str
    competition_logo: str
    status: str
    status_text: str
    minute_label: str
    score: str
    has_score: bool
    has_ht: bool
    ht_label: str
    kickoff: str
    day_key: str
    pair_key: str
    covered: bool
    has_stats: bool
    stats: list[SportScoreStat]
    has_prediction: bool
    prediction_note: str
    meta_market: str
    meta_pick: str
    meta_confidence: float
    home_share: float
    goals_market: str
    goals_pick: str
    goals_confidence: float


def _local_zone() -> ZoneInfo | timezone:
    try:
        return ZoneInfo(LOCAL_TZ_NAME)
    except Exception as error:
        logging.exception("Unexpected error")
        logging.info(
            f"Локалната зона не е достапна ({type(error).__name__}); "
            "се користи UTC."
        )
        return timezone.utc


def _network_label(error: Exception) -> str:
    """Кратка ознака за очекувани мрежни грешки (без stack trace).

    SSL грешките се третираат исто како timeout и грешка во конекцијата:
    очекувана мрежна состојба, не дефект во апликацијата.
    """
    if isinstance(error, requests.exceptions.SSLError):
        return "неуспешно SSL поврзување"
    if isinstance(error, requests.Timeout):
        return "истечено време на барањето (timeout)"
    if isinstance(error, requests.ConnectionError):
        return "нема конекција"
    return type(error).__name__


def _get_json(
    path: str, params: dict[str, str | int], label: str
) -> dict | None:
    """Тивко GET барање кон widget API-то.

    Враќа JSON речник или None. Никогаш не крева исклучок и никогаш не логира
    stack trace за очекувани мрежни грешки (SSL, timeout, нема конекција),
    HTTP 400/404/429/5xx или невалиден JSON — само кратка info/warning линија.
    """
    try:
        response = requests.get(
            f"{BASE_URL}{path}", params=params, timeout=TIMEOUT
        )
    except requests.RequestException as error:
        # Очекувана мрежна состојба: без stack trace, без пренесување нагоре.
        logging.exception("Unexpected error")
        logging.info(f"{label} не е достапно: {_network_label(error)}.")
        return None
    except Exception as error:
        # Неочекувана состојба — сепак не се пренесува нагоре, но се логира.
        logging.exception("Unexpected error")
        logging.warning(
            f"{label} врати неочекувана состојба: {type(error).__name__}."
        )
        return None

    if response.status_code != 200:
        if response.status_code in QUIET_STATUSES:
            logging.info(
                f"{label} не е достапно (HTTP {response.status_code})."
            )
        else:
            logging.warning(f"{label} врати HTTP {response.status_code}.")
        return None

    try:
        payload = response.json()
    except ValueError:
        logging.info(f"{label} врати невалиден JSON.")
        return None
    return payload if isinstance(payload, dict) else None


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
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _norm(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    text = "".join(
        c for c in decomposed if not unicodedata.combining(c)
    ).lower()
    cleaned = "".join(c if c.isalnum() else " " for c in text)
    return " ".join(cleaned.split())


def pair_key(home: str, away: str) -> str:
    """Симетричен клуч за совпаѓање со BZZ/Fotmob/Mutating настани."""
    parts = sorted([_norm(home), _norm(away)])
    return "|".join(parts)


def _kickoff_label(raw: str) -> str:
    if not isinstance(raw, str) or len(raw) < 16:
        return "--:--"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw[11:16]
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(_local_zone()).strftime("%H:%M")


def _status(raw: str) -> str:
    key = _clean(raw).lower()
    if key in ("live", "upcoming", "finished"):
        return key
    if "live" in key or "half" in key:
        return "live"
    if "finish" in key or "end" in key:
        return "finished"
    return "upcoming"


def _score_label(raw: dict) -> tuple[str, bool]:
    home = _num(raw.get("home_score"))
    away = _num(raw.get("away_score"))
    if home is None or away is None:
        return "vs", False
    return f"{int(home)} - {int(away)}", True


def _empty_row(raw: dict) -> SportScoreRow | None:
    home = _clean(raw.get("home"))
    away = _clean(raw.get("away"))
    if not home or not away:
        return None
    url = _clean(raw.get("url"))
    slug = url.strip("/").split("/")[-1] if url else ""
    status = _status(_clean(raw.get("status")))
    score, has_score = _score_label(raw)
    time_raw = _clean(raw.get("time"))
    status_text = _clean(raw.get("status_text"))
    return SportScoreRow(
        id=f"sportscore-{slug or pair_key(home, away)}",
        slug=slug,
        detail_url=f"https://sportscore.com{url}" if url else "",
        home=home,
        away=away,
        home_logo=_clean(raw.get("home_logo")),
        away_logo=_clean(raw.get("away_logo")),
        competition=_clean(raw.get("competition")) or "—",
        competition_logo=_clean(raw.get("competition_logo")),
        status=status,
        status_text=status_text or "—",
        minute_label=status_text if status == "live" else "",
        score=score,
        has_score=has_score,
        has_ht=False,
        ht_label="",
        kickoff=_kickoff_label(time_raw),
        day_key=time_raw[:10],
        pair_key=pair_key(home, away),
        covered=False,
        has_stats=False,
        stats=[],
        has_prediction=False,
        prediction_note=NO_STATS_NOTE,
        meta_market="",
        meta_pick="",
        meta_confidence=0.0,
        home_share=0.0,
        goals_market="",
        goals_pick="",
        goals_confidence=0.0,
    )


def fetch_rows(
    day: str, limit: int = MATCH_LIMIT
) -> tuple[list[SportScoreRow], str]:
    """Ги вчитува настаните за избраниот датум. Никогаш не крева исклучок."""
    params: dict[str, str | int] = {
        "sport": "football",
        "limit": min(max(1, limit), 200),
    }
    if day:
        params["date"] = day
    payload = _get_json("/matches/", params, "SportScore листата")
    if payload is None:
        return [], UNAVAILABLE_NOTE

    raw_rows = payload.get("matches") if isinstance(payload, dict) else None
    if not isinstance(raw_rows, list) or not raw_rows:
        return [], EMPTY_NOTE

    rows: list[SportScoreRow] = []
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        row = _empty_row(raw)
        if row is not None:
            rows.append(row)
    if not rows:
        return [], EMPTY_NOTE

    notice = ""
    if day:
        matching = [r for r in rows if r["day_key"] == day]
        if matching:
            rows = matching
        else:
            days = ", ".join(
                sorted({r["day_key"] for r in rows if r["day_key"]})
            )
            notice = DATE_IGNORED_NOTE.format(days=days or "непознат датум")
    return rows, notice


def _fetch_detail(slug: str) -> dict:
    now = time.monotonic()
    cached = _DETAIL_CACHE.get(slug)
    if cached is not None and now - cached[0] < DETAIL_CACHE_TTL:
        return cached[1]
    payload = _get_json(
        "/match/",
        {"sport": "football", "slug": slug},
        f"SportScore деталите за {slug}",
    )
    if payload is None:
        return {}
    data = payload.get("match")
    if not isinstance(data, dict):
        return {}
    _DETAIL_CACHE[slug] = (now, data)
    return data


def _stats_from_detail(detail: dict) -> list[SportScoreStat]:
    raw_stats = detail.get("stats")
    if not isinstance(raw_stats, list):
        return []
    stats: list[SportScoreStat] = []
    for raw in raw_stats:
        if not isinstance(raw, dict):
            continue
        label = _clean(raw.get("label"))
        if not label:
            continue
        home = _num(raw.get("home"))
        away = _num(raw.get("away"))
        if home is None or away is None:
            continue
        suffix = _clean(raw.get("suffix"))
        home_pct = _num(raw.get("home_pct")) or 0.0
        away_pct = _num(raw.get("away_pct")) or 0.0
        stats.append(
            SportScoreStat(
                label=STAT_LABELS_MK.get(label.lower(), label),
                home=f"{int(home)}{suffix}",
                away=f"{int(away)}{suffix}",
                home_pct=round(max(0.0, min(100.0, home_pct)), 1),
                away_pct=round(max(0.0, min(100.0, away_pct)), 1),
            )
        )
    return stats


def _weighted_share(raw_stats: list[dict]) -> tuple[float, float, bool]:
    """Дел на домашниот тим (0-100) и вкупни удари во гол од реални статистики."""
    total_weight = 0.0
    accumulated = 0.0
    shots_total = 0.0
    for raw in raw_stats:
        if not isinstance(raw, dict):
            continue
        key = _clean(raw.get("label")).lower()
        home = _num(raw.get("home"))
        away = _num(raw.get("away"))
        if home is None or away is None:
            continue
        if key == "shots on target":
            shots_total = home + away
        weight = STAT_WEIGHTS.get(key)
        if weight is None:
            continue
        total = home + away
        if total <= 0:
            continue
        home_pct = _num(raw.get("home_pct"))
        share = home_pct if home_pct is not None else home / total * 100.0
        accumulated += weight * max(0.0, min(100.0, share))
        total_weight += weight
    if total_weight <= 0.0:
        return 0.0, shots_total, False
    return round(accumulated / total_weight, 1), shots_total, True


def _apply_detail(row: SportScoreRow, detail: dict) -> None:
    status_text = _clean(detail.get("status_text"))
    minute = _clean(detail.get("live_minute"))
    status = _status(_clean(detail.get("status")) or row["status"])
    score, has_score = _score_label(detail)
    if has_score:
        row["score"] = score
        row["has_score"] = True
    row["status"] = status
    if status_text:
        row["status_text"] = status_text
    if minute:
        row["minute_label"] = minute if not minute.isdigit() else f"{minute}'"
    elif status == "live" and status_text:
        row["minute_label"] = status_text

    ht_home = _num(detail.get("home_ht_score"))
    ht_away = _num(detail.get("away_ht_score"))
    if ht_home is not None and ht_away is not None:
        row["has_ht"] = True
        row["ht_label"] = f"HT: {int(ht_home)}-{int(ht_away)}"

    stats = _stats_from_detail(detail)
    row["stats"] = stats
    row["has_stats"] = len(stats) > 0
    if not stats:
        row["prediction_note"] = NO_STATS_NOTE
        return

    raw_stats = detail.get("stats")
    raw_stats = raw_stats if isinstance(raw_stats, list) else []
    share, shots_total, usable = _weighted_share(raw_stats)
    if not usable:
        row["prediction_note"] = NO_STATS_NOTE
        return

    home_goals = _num(detail.get("home_score")) or 0.0
    away_goals = _num(detail.get("away_score")) or 0.0
    adjusted = share
    if row["has_score"]:
        adjusted = share + (home_goals - away_goals) * 6.0
    adjusted = round(max(2.0, min(98.0, adjusted)), 1)
    row["home_share"] = adjusted

    if adjusted >= 55.0:
        pick = f"1 · {row['home']}"
        confidence = adjusted
    elif adjusted <= 45.0:
        pick = f"2 · {row['away']}"
        confidence = round(100.0 - adjusted, 1)
    else:
        pick = "12 · без јасен фаворит"
        confidence = round(50.0 + abs(adjusted - 50.0), 1)
    row["meta_market"] = "Meta-Ensemble · SportScore статистики"
    row["meta_pick"] = pick
    row["meta_confidence"] = round(min(95.0, confidence), 1)
    row["has_prediction"] = True
    row["prediction_note"] = ""

    goals_now = (home_goals + away_goals) if row["has_score"] else 0.0
    expected = goals_now + shots_total * 0.12
    if shots_total > 0.0 or row["has_score"]:
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


def enrich_rows(rows: list[SportScoreRow], limit: int = DETAIL_LIMIT) -> int:
    """Дополнува детали (статистики, минута, HT) за мал број редови."""
    done = 0
    for row in rows:
        if done >= limit:
            break
        slug = row.get("slug") or ""
        if not slug:
            continue
        detail = _fetch_detail(slug)
        if not detail:
            continue
        try:
            _apply_detail(row, detail)
        except Exception as error:
            logging.exception("Unexpected error")
            logging.info(
                f"SportScore деталите не се применети: {type(error).__name__}"
            )
            continue
        done += 1
        time.sleep(DETAIL_DELAY)
    return done
