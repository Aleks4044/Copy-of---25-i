"""Јавен HTML извор со предвидувања од Mutating.com.

Страницата https://www.mutating.com/soccer-predictions/ е јавна и не бара
никакви клучеви или креденцијали. Од неа се читаат САМО реални вредности:
fixture id, имена на домашниот и гостинскиот тим, предвидувањето (1, X, 2,
1X, X2, 12), времето или статусот, тековниот резултат и контекстот
земја/лига од заглавјето на секцијата.

Mutating.com НЕ објавува квоти ниту сигурност за своите предвидувања, па
такви вредности не се измислуваат никаде во апликацијата.
"""

import html
import logging
import re
import time
from typing import TypedDict

import requests

PREDICTIONS_URL = "https://www.mutating.com/soccer-predictions/"
TIMEOUT = 12
# Страницата за детали на секој натпревар (match preview) е јавна и се чита
# само за мал број редови, со кеш, за да не се оптоварува изворот.
DETAIL_TIMEOUT = 10
MAX_DETAIL_PAGES = 12
DETAIL_CACHE_TTL = 1800.0
HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (compatible; BSD-Football/1.0)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en",
}

_PCT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")

# Точните ознаки како што се објавени на страницата за детали.
MARKET_LABELS: dict[str, str] = {
    "btts": "Both Teams to Score",
    "over15": "Over 1.5 goals",
    "under15": "Under 1.5 goals",
    "over25": "Over 2.5 goals",
    "under25": "Under 2.5 goals",
}

_MARKET_CACHE: dict[str, tuple[float, "MutatingMarkets"]] = {}

# Само вредностите што Mutating.com навистина објавува како предвидување.
VALID_PICKS: frozenset[str] = frozenset({"1", "X", "2", "1X", "X2", "12"})

PICK_DESCRIPTIONS: dict[str, str] = {
    "1": "Домашна победа",
    "X": "Реми",
    "2": "Гостинска победа",
    "1X": "Домашен или реми",
    "X2": "Реми или гостин",
    "12": "Без реми",
}

PAGE_UNAVAILABLE_NOTE = (
    "Страницата со предвидувања на Mutating.com не одговори во дозволеното "
    "време, па имињата на тимовите и предвидувањата не се вчитани."
)
PAGE_PARSE_NOTE = (
    "Страницата со предвидувања на Mutating.com врати неочекуван формат, па "
    "имињата на тимовите не се вчитани."
)
PAGE_EMPTY_NOTE = (
    "Страницата со предвидувања на Mutating.com не објави ниту едно "
    "предвидување со имена на тимови во моментот."
)
PARSER_MISSING_NOTE = (
    "HTML парсерот не е достапен, па предвидувањата од Mutating.com не се "
    "вчитани."
)


class MutatingMarkets(TypedDict):
    """Реални проценти од страницата за детали (0.0 значи недостапно)."""

    has_markets: bool
    btts: float
    no_btts: float
    over15: float
    under15: float
    over25: float
    under25: float


def _empty_markets() -> MutatingMarkets:
    return MutatingMarkets(
        has_markets=False,
        btts=0.0,
        no_btts=0.0,
        over15=0.0,
        under15=0.0,
        over25=0.0,
        under25=0.0,
    )


class MutatingPrediction(TypedDict):
    fixture_id: str
    home: str
    away: str
    pick: str
    pick_description: str
    kickoff: str
    score: str
    country: str
    league: str
    league_label: str
    detail_url: str
    has_markets: bool
    btts: float
    no_btts: float
    over15: float
    under15: float
    over25: float
    under25: float


def _clean(value: object) -> str:
    """Отстранува HTML ентитети и празни знаци од текстуална вредност."""
    if not isinstance(value, str):
        return ""
    text = html.unescape(value).replace("\xa0", " ")
    return " ".join(text.split())


def _node_text(node: object) -> str:
    if node is None:
        return ""
    getter = getattr(node, "get_text", None)
    if getter is None:
        return _clean(node)
    return _clean(getter(" ", strip=True))


def _score_label(home: str, away: str) -> str:
    if home.isdigit() and away.isdigit():
        return f"{home} - {away}"
    return ""


def _league_context(node: object, soup: object) -> tuple[str, str]:
    """Земја и лига од заглавјето на секцијата што го содржи натпреварот."""
    holder = getattr(node, "find_parent", lambda *_: None)("section")
    if holder is None:
        holder = getattr(node, "parent", None)
    for _ in range(6):
        if holder is None:
            break
        finder = getattr(holder, "find", None)
        if finder is not None:
            block = finder("div", class_="leaguediv")
            if block is not None:
                return (
                    _node_text(block.find("a", class_="countrieslist")),
                    _node_text(block.find("a", class_="leagueslist")),
                )
        holder = getattr(holder, "parent", None)
    return "", ""


def _league_label(country: str, league: str) -> str:
    if country and league:
        return f"{country} / {league}"
    return league or country or ""


def _detail_url(node: object) -> str:
    """Линкот до јавната страница со детали за натпреварот."""
    finder = getattr(node, "find_parent", None)
    if finder is None:
        return ""
    anchor = finder("a")
    if anchor is None:
        return ""
    href = _clean(anchor.get("href"))
    return href if href.startswith("http") else ""


def _row_average(soup: object, label: str) -> float:
    """Просек од двете објавени колони (дома/гости) за дадена ознака.

    Се чита САМО она што страницата навистина го објавува. Ако ознаката или
    процентите не постојат, се враќа 0.0 (недостапно).
    """
    needle = label.lower()
    try:
        nodes = soup.find_all(
            string=lambda text: (
                isinstance(text, str) and _clean(text).lower() == needle
            )
        )
    except Exception as error:
        logging.exception("Unexpected error")
        logging.info(f"Ознаката {label} не може да се прочита: {error}")
        return 0.0
    for text_node in nodes:
        holder = getattr(text_node, "parent", None)
        for _ in range(4):
            if holder is None:
                break
            values = [
                float(value) for value in _PCT_RE.findall(_node_text(holder))
            ]
            usable = [v for v in values if 0.0 <= v <= 100.0]
            if 2 <= len(usable) <= 3:
                return round(sum(usable[:2]) / 2.0, 1)
            if len(usable) == 1:
                return round(usable[0], 1)
            holder = getattr(holder, "parent", None)
    return 0.0


def _markets_from_detail(markup: str) -> MutatingMarkets:
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(markup, "html.parser")
    except Exception as error:
        logging.exception("Unexpected error")
        logging.info(f"Страницата за детали не може да се парсира: {error}")
        return _empty_markets()

    values = {
        key: _row_average(soup, label) for key, label in MARKET_LABELS.items()
    }
    btts = values["btts"]
    over15 = values["over15"]
    over25 = values["over25"]
    under15 = values["under15"] or (
        round(100.0 - over15, 1) if over15 > 0.0 else 0.0
    )
    under25 = values["under25"] or (
        round(100.0 - over25, 1) if over25 > 0.0 else 0.0
    )
    no_btts = round(100.0 - btts, 1) if btts > 0.0 else 0.0
    has_markets = any(
        value > 0.0 for value in (btts, over15, over25, under15, under25)
    )
    return MutatingMarkets(
        has_markets=has_markets,
        btts=btts,
        no_btts=no_btts,
        over15=over15,
        under15=under15,
        over25=over25,
        under25=under25,
    )


def _fetch_markets(url: str) -> MutatingMarkets:
    """Ги чита реалните проценти од страницата за детали (со кеш)."""
    now = time.monotonic()
    cached = _MARKET_CACHE.get(url)
    if cached is not None and now - cached[0] < DETAIL_CACHE_TTL:
        return cached[1]
    try:
        response = requests.get(url, headers=HEADERS, timeout=DETAIL_TIMEOUT)
        response.raise_for_status()
        markup = response.text
    except requests.RequestException as error:
        logging.exception("Unexpected error")
        logging.info(
            "Страницата за детали на Mutating.com не одговори: "
            f"{type(error).__name__}"
        )
        return _empty_markets()
    markets = _markets_from_detail(markup)
    if markets["has_markets"]:
        _MARKET_CACHE[url] = (now, markets)
    return markets


def _enrich_markets(rows: dict[str, MutatingPrediction], limit: int) -> None:
    """Дополнува проценти за ГГ и Над/Под 1.5 и 2.5 за мал број редови."""
    enriched = 0
    for row in rows.values():
        if enriched >= limit:
            break
        url = row["detail_url"]
        if not url:
            continue
        markets = _fetch_markets(url)
        if not markets["has_markets"]:
            continue
        row.update(
            has_markets=True,
            btts=markets["btts"],
            no_btts=markets["no_btts"],
            over15=markets["over15"],
            under15=markets["under15"],
            over25=markets["over25"],
            under25=markets["under25"],
        )
        enriched += 1


def fetch_predictions(
    detail_limit: int = MAX_DETAIL_PAGES,
) -> tuple[dict[str, MutatingPrediction], str]:
    """Ги вчитува денешните предвидувања од јавната HTML страница.

    Враќа (мапа по fixture_id, кратка забелешка на македонски). Никогаш не
    крева исклучок и не логира stack trace за очекувани мрежни грешки.
    """
    try:
        from bs4 import BeautifulSoup
    except Exception as error:
        logging.exception("Unexpected error")
        logging.info(f"BeautifulSoup не е достапен: {error}")
        return {}, PARSER_MISSING_NOTE

    try:
        response = requests.get(
            PREDICTIONS_URL, headers=HEADERS, timeout=TIMEOUT
        )
        response.raise_for_status()
        markup = response.text
    except requests.RequestException as error:
        logging.exception("Unexpected error")
        logging.info(
            "Страницата со предвидувања на Mutating.com е недостапна: "
            f"{type(error).__name__}"
        )
        return {}, PAGE_UNAVAILABLE_NOTE

    try:
        soup = BeautifulSoup(markup, "html.parser")
        nodes = soup.select('[id^="calcresult-"]')
    except Exception as error:
        logging.exception("Unexpected error")
        logging.info(f"Mutating.com HTML не може да се парсира: {error}")
        return {}, PAGE_PARSE_NOTE

    rows: dict[str, MutatingPrediction] = {}
    for node in nodes:
        raw_id = _clean(node.get("id"))
        fixture_id = raw_id.replace("calcresult-", "").strip()
        if not fixture_id or fixture_id in rows:
            continue
        pick = _node_text(node).upper().replace(" ", "")
        if pick not in VALID_PICKS:
            continue
        home = _node_text(soup.find(id=f"winclasshome-{fixture_id}"))
        away = _node_text(soup.find(id=f"winclassaway-{fixture_id}"))
        if not home or not away:
            continue
        score = _score_label(
            _node_text(soup.find(id=f"scorehome-{fixture_id}")),
            _node_text(soup.find(id=f"scoreaway-{fixture_id}")),
        )
        kickoff = _node_text(soup.find(id=fixture_id))
        country, league = _league_context(node, soup)
        rows[fixture_id] = MutatingPrediction(
            fixture_id=fixture_id,
            home=home,
            away=away,
            pick=pick,
            pick_description=PICK_DESCRIPTIONS.get(pick, ""),
            kickoff=kickoff,
            score=score,
            country=country,
            league=league,
            league_label=_league_label(country, league),
            detail_url=_detail_url(node),
            has_markets=False,
            btts=0.0,
            no_btts=0.0,
            over15=0.0,
            under15=0.0,
            over25=0.0,
            under25=0.0,
        )

    if not rows:
        return {}, PAGE_EMPTY_NOTE
    if detail_limit > 0:
        _enrich_markets(rows, detail_limit)
    return rows, ""
