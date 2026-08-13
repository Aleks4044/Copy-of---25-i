"""Само-читачки клиент за јавниот HTML на Fudbal91.

Изворот е јавен и не бара клуч. Се читаат САМО реални вредности:
  * дневната понуда од насловната страница (натпревари, време, натпреварување,
    просечни квоти 1/X/2 и 0-2/3+, број кладилници, линк за споредба)
  * по потреба, мал ограничен број страници за споредба
    (/soccer_clubs/compare/...) за вистински меѓусебни средби и статистики

Се почитува тековниот robots режим на изворот: патеките `quick_odds`,
`odds_changes` и `modules` НИКОГАШ не се повикуваат. Пред секое барање
патеката се проверува со `_is_allowed`.

Ниту една вредност не се измислува: сите проценти, проекции и препораки се
изведени детерминистички од објавените просечни квоти и од реално најдените
статистики, што е и јасно означено во интерфејсот.
"""

import logging
import math
import re
import time
from typing import TypedDict

import requests

BASE_URL = "https://www.fudbal91.com"
TZ_URL = f"{BASE_URL}/tz.php"
OFFER_URL = f"{BASE_URL}/"
LOCAL_ZONE = "Europe/Skopje"

TIMEOUT = 15
COMPARE_TIMEOUT = 15
MAX_COMPARE_PAGES = 6
COMPARE_DELAY = 0.35
OFFER_CACHE_TTL = 90.0
COMPARE_CACHE_TTL = 1800.0

# Патеки што се забранети за автоматски барања на изворот. Никогаш не се
# повикуваат од овој клиент.
BLOCKED_SEGMENTS: tuple[str, ...] = (
    "quick_odds",
    "odds_changes",
    "modules",
)

HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (compatible; BSD-Football/1.0)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "mk,en-US;q=0.9,en;q=0.8,sr;q=0.7",
}

OFFER_UNAVAILABLE_NOTE = (
    "Fudbal91 не одговори во дозволеното време или врати неочекуван формат, "
    "па дополнителната покриеност не е вчитана."
)
OFFER_EMPTY_NOTE = (
    "Fudbal91 не објавува натпревари со просечни квоти во моментот."
)
PARSER_MISSING_NOTE = (
    "HTML парсерот не е достапен, па Fudbal91 понудата не е вчитана."
)
COMPARE_UNAVAILABLE_NOTE = (
    "Страницата за споредба на Fudbal91 не одговори, па меѓусебните средби и "
    "статистиките не се достапни за овој натпревар."
)
COMPARE_EMPTY_NOTE = (
    "Fudbal91 не објавува меѓусебни средби ниту табела за овој натпревар."
)
ABSENCES_NOTE = (
    "Fudbal91 јавната понуда не објавува отсутни играчи, па отсуствата се "
    "означени како недостапни и не се измислуваат."
)
DERIVED_NOTE = (
    "Овие проценти и проекции се изведени од јавните просечни квоти и од "
    "реално најдените статистики на Fudbal91 — тие НЕ се официјална "
    "сигурност на Fudbal91."
)
NA_LABEL = "недостапно"

_DATE_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
_TIME_RE = re.compile(r"(\d{1,2}:\d{2})")
_COMPARE_RE = re.compile(r"/soccer_clubs/compare/")

_OFFER_CACHE: dict[str, tuple[float, list[dict]]] = {}
_COMPARE_CACHE: dict[str, tuple[float, dict]] = {}

# Ознаки на дополнителни секции што навистина постојат на страницата за
# споредба. Ако некоја не постои, воопшто не се прикажува.
COMPARE_SECTION_IDS: tuple[str, ...] = (
    "mutual",
    "form",
    "forma",
    "stats",
    "statistika",
    "table",
    "tabela",
    "h2h",
)


class MutualRow(TypedDict):
    date: str
    score: str
    goals: str
    competition: str
    season: str


class StatRow(TypedDict):
    label: str
    value: str


class OptionRow(TypedDict):
    label: str
    probability: float
    support_label: str


class Fudbal91Compare(TypedDict):
    url: str
    has_mutual: bool
    mutual_rows: list[MutualRow]
    stat_rows: list[StatRow]
    note: str


class Fudbal91Fixture(TypedDict):
    id: str
    kickoff: str
    kickoff_minutes: int
    day_label: str
    home: str
    away: str
    home_slug: str
    away_slug: str
    display_pair: str
    slug_pair: str
    competition: str
    compare_url: str
    has_odds: bool
    odd_home: float
    odd_draw: float
    odd_away: float
    odd_under25: float
    odd_over25: float
    bookmakers: int


class Fudbal91Row(Fudbal91Fixture):
    covered: bool
    match_id: str
    is_upcoming: bool
    has_context: bool
    has_source_pick: bool
    source_pick: str
    source_pick_odds: float
    support_label: str
    top_label: str
    top_probability: float
    options: list[OptionRow]
    prob_home: float
    prob_draw: float
    prob_away: float
    prob_over25: float
    prob_under25: float
    ft_projection: str
    ft_probability: float
    expected_goals: float
    ht_projection: str
    ht_probability: float
    has_mutual: bool
    mutual_rows: list[MutualRow]
    stat_rows: list[StatRow]
    has_stats: bool
    compare_note: str
    absences_label: str
    absences_note: str
    derived_note: str


def _is_allowed(path: str) -> bool:
    """Дали патеката е дозволена (без забранетите сегменти)."""
    lowered = (path or "").lower()
    return not any(segment in lowered for segment in BLOCKED_SEGMENTS)


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


def _float(value: str) -> float:
    cleaned = _clean(value).replace(",", ".")
    if not cleaned:
        return 0.0
    try:
        number = float(cleaned)
    except ValueError:
        return 0.0
    return round(number, 2) if number > 0.0 else 0.0


def _minutes(label: str) -> int:
    match = _TIME_RE.search(label or "")
    if match is None:
        return -1
    try:
        hours, minutes = match.group(1).split(":")
        return int(hours) * 60 + int(minutes)
    except ValueError:
        return -1


def _session() -> requests.Session:
    """Сесија што прво го поставува часовниот појас како самиот сајт."""
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get(
            TZ_URL,
            params={"zone": LOCAL_ZONE, "r": "/"},
            timeout=TIMEOUT,
        )
    except requests.RequestException as error:
        logging.exception("Unexpected error")
        logging.info(
            f"Fudbal91 часовниот појас не е поставен: {type(error).__name__}"
        )
    return session


def _soup(markup: str):
    from bs4 import BeautifulSoup

    return BeautifulSoup(markup, "html.parser")


def _competition_label(cell: object) -> str:
    anchor = cell.find("a") if cell is not None else None
    if anchor is None:
        return NA_LABEL
    title = _clean(anchor.get("title"))
    if title:
        cleaned = re.sub(
            r"\s*analize\s+utakmica\s*$", "", title, flags=re.IGNORECASE
        )
        if cleaned:
            return cleaned
    href = _clean(anchor.get("href"))
    parts = [part for part in href.split("/") if part]
    if len(parts) >= 2 and parts[0] == "competition":
        return parts[1].replace("_", " ")
    return NA_LABEL


def _slug_names(href: str) -> tuple[str, str]:
    parts = [part for part in href.split("/") if part]
    for part in parts:
        if "_vs_" in part:
            left, right = part.split("_vs_", 1)
            return left.replace("_", " "), right.replace("_", " ")
    return "", ""


def _display_names(label: str, fallback: tuple[str, str]) -> tuple[str, str]:
    parts = [part.strip() for part in (label or "").split("-")]
    if len(parts) == 2 and parts[0] and parts[1]:
        return parts[0], parts[1]
    return fallback


def _fixture_from_row(row: object, kickoff: str, day_label: str):
    cells = row.find_all("td")
    if len(cells) < 3:
        return None
    anchor = None
    for cell in cells:
        for link in cell.find_all("a"):
            href = _clean(link.get("href"))
            if _COMPARE_RE.search(href):
                anchor = link
                break
        if anchor is not None:
            break
    if anchor is None:
        return None
    href = _clean(anchor.get("href"))
    if not _is_allowed(href):
        return None
    home_slug, away_slug = _slug_names(href)
    home, away = _display_names(_text(anchor), (home_slug, away_slug))
    if not home or not away:
        return None
    odds = [_float(_text(cell)) for cell in row.select("td.odd-cell")]
    while len(odds) < 5:
        odds.append(0.0)
    bookmakers = 0
    match = re.search(r"\((\d+)\)", _text(cells[-1]))
    if match is not None:
        bookmakers = int(match.group(1))
    slug = f"{home_slug or home}_vs_{away_slug or away}".replace(" ", "_")
    has_odds = odds[0] > 1.0 and odds[1] > 1.0 and odds[2] > 1.0
    return Fudbal91Fixture(
        id=f"fudbal91-{slug}-{kickoff.replace(':', '')}",
        kickoff=kickoff,
        kickoff_minutes=_minutes(kickoff),
        day_label=day_label,
        home=home,
        away=away,
        home_slug=home_slug or home,
        away_slug=away_slug or away,
        display_pair=pair_key(home, away),
        slug_pair=pair_key(home_slug or home, away_slug or away),
        competition=_competition_label(cells[0]),
        compare_url=f"{BASE_URL}{href}" if href.startswith("/") else href,
        has_odds=has_odds,
        odd_home=odds[0],
        odd_draw=odds[1],
        odd_away=odds[2],
        odd_under25=odds[3],
        odd_over25=odds[4],
        bookmakers=bookmakers,
    )


def _parse_offer(markup: str) -> list[Fudbal91Fixture]:
    soup = _soup(markup)
    fixtures: list[Fudbal91Fixture] = []
    seen: set[str] = set()
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        header = _text(rows[0].find(["td", "th"]))
        match = _TIME_RE.search(header)
        if match is None:
            continue
        kickoff = match.group(1)
        if len(kickoff) == 4:
            kickoff = f"0{kickoff}"
        day_label = _clean(header.split(match.group(1))[0])
        for row in rows[1:]:
            fixture = _fixture_from_row(row, kickoff, day_label)
            if fixture is None or fixture["id"] in seen:
                continue
            seen.add(fixture["id"])
            fixtures.append(fixture)
    return fixtures


def pair_key(home: str, away: str) -> str:
    """Симетричен нормализиран клуч за спарување со другите извори."""
    from app.states.sportscore_client import pair_key as normalize

    return normalize(home, away)


def fetch_offer() -> tuple[list[Fudbal91Fixture], str]:
    """Ја вчитува денешната јавна понуда. Никогаш не крева исклучок."""
    now = time.monotonic()
    cached = _OFFER_CACHE.get(OFFER_URL)
    if cached is not None and now - cached[0] < OFFER_CACHE_TTL:
        return [Fudbal91Fixture(**row) for row in cached[1]], ""

    try:
        from bs4 import BeautifulSoup  # noqa: F401
    except Exception as error:
        logging.exception("Unexpected error")
        logging.info(f"BeautifulSoup не е достапен: {type(error).__name__}")
        return [], PARSER_MISSING_NOTE

    if not _is_allowed("/"):
        return [], OFFER_UNAVAILABLE_NOTE

    session = _session()
    try:
        response = session.get(OFFER_URL, timeout=TIMEOUT)
        response.raise_for_status()
        markup = response.text
    except requests.RequestException as error:
        logging.exception("Unexpected error")
        logging.info(f"Fudbal91 понудата е недостапна: {type(error).__name__}")
        return [], OFFER_UNAVAILABLE_NOTE
    finally:
        try:
            session.close()
        except Exception as error:
            logging.exception("Unexpected error")
            logging.info(f"Fudbal91 сесијата не е затворена: {error}")

    try:
        fixtures = _parse_offer(markup)
    except Exception as error:
        logging.exception("Unexpected error")
        logging.info(f"Fudbal91 HTML не може да се парсира: {error}")
        return [], OFFER_UNAVAILABLE_NOTE

    if not fixtures:
        return [], OFFER_EMPTY_NOTE
    _OFFER_CACHE[OFFER_URL] = (now, [dict(row) for row in fixtures])
    return fixtures, ""


def _mutual_row(cells: list[str]) -> MutualRow | None:
    if len(cells) < 2 or not _DATE_RE.match(cells[0]):
        return None
    return MutualRow(
        date=cells[0],
        score=cells[1] if len(cells) > 1 else NA_LABEL,
        goals=cells[2] if len(cells) > 2 else "",
        competition=cells[3] if len(cells) > 3 else "",
        season=cells[4] if len(cells) > 4 else "",
    )


def _stat_row(cells: list[str]) -> StatRow | None:
    usable = [cell for cell in cells if cell]
    if len(usable) < 2:
        return None
    label = usable[0]
    rest = usable[1:]
    if rest and not any(ch.isdigit() for ch in rest[0]):
        label = f"{label} · {rest[0]}"
        rest = rest[1:]
    if not rest:
        return None
    return StatRow(label=label, value=" · ".join(rest[:9]))


def _parse_compare(url: str, markup: str) -> Fudbal91Compare:
    soup = _soup(markup)
    mutual: list[MutualRow] = []
    stats: list[StatRow] = []
    for section_id in COMPARE_SECTION_IDS:
        section = soup.find(id=section_id)
        if section is None:
            continue
        for table in section.find_all("table"):
            for row in table.find_all("tr"):
                cells = [_text(cell) for cell in row.find_all(["td", "th"])]
                mutual_row = _mutual_row(cells)
                if mutual_row is not None:
                    if len(mutual) < 8:
                        mutual.append(mutual_row)
                    continue
                stat_row = _stat_row(cells)
                if stat_row is not None and len(stats) < 10:
                    stats.append(stat_row)
    note = "" if (mutual or stats) else COMPARE_EMPTY_NOTE
    return Fudbal91Compare(
        url=url,
        has_mutual=len(mutual) > 0,
        mutual_rows=mutual,
        stat_rows=stats,
        note=note,
    )


def fetch_compare(urls: list[str]) -> dict[str, Fudbal91Compare]:
    """Чита мал, ограничен број страници за споредба (со кеш и пауза)."""
    out: dict[str, Fudbal91Compare] = {}
    targets = [url for url in urls if url and _is_allowed(url)]
    if not targets:
        return out

    try:
        from bs4 import BeautifulSoup  # noqa: F401
    except Exception as error:
        logging.exception("Unexpected error")
        logging.info(f"BeautifulSoup не е достапен: {type(error).__name__}")
        return out

    now = time.monotonic()
    pending: list[str] = []
    for url in targets[:MAX_COMPARE_PAGES]:
        cached = _COMPARE_CACHE.get(url)
        if cached is not None and now - cached[0] < COMPARE_CACHE_TTL:
            out[url] = Fudbal91Compare(**cached[1])
            continue
        pending.append(url)
    if not pending:
        return out

    session = _session()
    try:
        for url in pending:
            try:
                response = session.get(url, timeout=COMPARE_TIMEOUT)
                response.raise_for_status()
                markup = response.text
            except requests.RequestException as error:
                logging.exception("Unexpected error")
                logging.info(
                    f"Fudbal91 споредбата не е достапна: {type(error).__name__}"
                )
                out[url] = Fudbal91Compare(
                    url=url,
                    has_mutual=False,
                    mutual_rows=[],
                    stat_rows=[],
                    note=COMPARE_UNAVAILABLE_NOTE,
                )
                continue
            try:
                compare = _parse_compare(url, markup)
            except Exception as error:
                logging.exception("Unexpected error")
                logging.info(f"Fudbal91 споредбата не е парсирана: {error}")
                compare = Fudbal91Compare(
                    url=url,
                    has_mutual=False,
                    mutual_rows=[],
                    stat_rows=[],
                    note=COMPARE_UNAVAILABLE_NOTE,
                )
            out[url] = compare
            if compare["has_mutual"] or compare["stat_rows"]:
                _COMPARE_CACHE[url] = (time.monotonic(), dict(compare))
            time.sleep(COMPARE_DELAY)
    finally:
        try:
            session.close()
        except Exception as error:
            logging.exception("Unexpected error")
            logging.info(f"Fudbal91 сесијата не е затворена: {error}")
    return out


def _support_label(probability: float) -> str:
    if probability >= 70.0:
        return "Силна поддршка"
    if probability >= 55.0:
        return "Умерена поддршка"
    if probability > 40.0:
        return "Слаба поддршка"
    return "Без јасна поддршка"


def _implied(values: list[float]) -> list[float]:
    inverse = [1.0 / value if value > 1.0 else 0.0 for value in values]
    total = sum(inverse)
    if total <= 0.0:
        return [0.0 for _ in values]
    return [round(item / total * 100.0, 1) for item in inverse]


def _poisson(lam: float, k: int) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


def _top_score(lam_home: float, lam_away: float, cap: int) -> tuple[str, float]:
    if lam_home <= 0.0 or lam_away <= 0.0:
        return NA_LABEL, 0.0
    home = [_poisson(lam_home, k) for k in range(cap + 1)]
    away = [_poisson(lam_away, k) for k in range(cap + 1)]
    total = 0.0
    best = 0.0
    label = NA_LABEL
    for h, ph in enumerate(home):
        for a, pa in enumerate(away):
            joint = ph * pa
            total += joint
            if joint > best:
                best, label = joint, f"{h}-{a}"
    if total <= 0.0 or best <= 0.0:
        return NA_LABEL, 0.0
    return label, round(best / total * 100.0, 1)


def _expected_goals(over25: float) -> float:
    if over25 <= 0.0:
        return 0.0
    return round(min(4.6, max(1.10, 1.35 + (over25 - 50.0) / 100.0 * 2.4)), 2)


def _lambdas(
    total: float, prob_home: float, prob_draw: float, prob_away: float
) -> tuple[float, float]:
    if total <= 0.0:
        return 0.0, 0.0
    weight_home = prob_home + prob_draw / 2.0
    weight_away = prob_away + prob_draw / 2.0
    denominator = weight_home + weight_away
    share = weight_home / denominator if denominator > 0.0 else 0.5
    share = min(0.72, max(0.28, share))
    return round(total * share, 2), round(total * (1.0 - share), 2)


def build_row(
    fixture: Fudbal91Fixture,
    compare: Fudbal91Compare | None,
    covered: bool,
    match_id: str,
    is_upcoming: bool,
) -> Fudbal91Row:
    """Го гради приказот со изведени вредности од реални квоти/статистики."""
    prob_home, prob_draw, prob_away = 0.0, 0.0, 0.0
    prob_over25, prob_under25 = 0.0, 0.0
    if fixture["has_odds"]:
        prob_home, prob_draw, prob_away = _implied(
            [fixture["odd_home"], fixture["odd_draw"], fixture["odd_away"]]
        )
    if fixture["odd_over25"] > 1.0 and fixture["odd_under25"] > 1.0:
        prob_under25, prob_over25 = _implied(
            [fixture["odd_under25"], fixture["odd_over25"]]
        )

    options: list[OptionRow] = []
    if fixture["has_odds"]:
        options.extend(
            [
                OptionRow(
                    label=f"1 · {fixture['home']}",
                    probability=prob_home,
                    support_label=_support_label(prob_home),
                ),
                OptionRow(
                    label="X · Реми",
                    probability=prob_draw,
                    support_label=_support_label(prob_draw),
                ),
                OptionRow(
                    label=f"2 · {fixture['away']}",
                    probability=prob_away,
                    support_label=_support_label(prob_away),
                ),
                OptionRow(
                    label="1X · домашен или реми",
                    probability=round(min(99.0, prob_home + prob_draw), 1),
                    support_label=_support_label(prob_home + prob_draw),
                ),
                OptionRow(
                    label="12 · без реми",
                    probability=round(min(99.0, prob_home + prob_away), 1),
                    support_label=_support_label(prob_home + prob_away),
                ),
                OptionRow(
                    label="X2 · реми или гостин",
                    probability=round(min(99.0, prob_draw + prob_away), 1),
                    support_label=_support_label(prob_draw + prob_away),
                ),
            ]
        )
    if prob_over25 > 0.0:
        options.append(
            OptionRow(
                label="Над 2.5 гола",
                probability=prob_over25,
                support_label=_support_label(prob_over25),
            )
        )
    if prob_under25 > 0.0:
        options.append(
            OptionRow(
                label="Под 2.5 гола",
                probability=prob_under25,
                support_label=_support_label(prob_under25),
            )
        )
    options.sort(key=lambda row: -row["probability"])
    top = options[0] if options else None

    source_pick = NA_LABEL
    source_pick_odds = 0.0
    has_source_pick = False
    if fixture["has_odds"]:
        candidates = [
            (fixture["odd_home"], f"1 · {fixture['home']}"),
            (fixture["odd_draw"], "X · Реми"),
            (fixture["odd_away"], f"2 · {fixture['away']}"),
        ]
        best = min(candidates, key=lambda row: row[0])
        source_pick_odds = best[0]
        source_pick = best[1]
        has_source_pick = True

    total_goals = _expected_goals(prob_over25)
    if total_goals <= 0.0 and fixture["has_odds"]:
        # Без објавена линија за 2.5 гола не се измислува вкупен број голови.
        total_goals = 0.0
    lam_home, lam_away = _lambdas(total_goals, prob_home, prob_draw, prob_away)
    ft_projection, ft_probability = _top_score(lam_home, lam_away, 7)
    ht_projection, ht_probability = _top_score(
        round(lam_home * 0.45, 2), round(lam_away * 0.45, 2), 4
    )

    stat_rows: list[StatRow] = []
    if fixture["has_odds"]:
        stat_rows.append(
            StatRow(
                label="Просечни квоти 1 / X / 2",
                value=(
                    f"{fixture['odd_home']:.2f} · {fixture['odd_draw']:.2f} · "
                    f"{fixture['odd_away']:.2f}"
                ),
            )
        )
    if fixture["odd_over25"] > 1.0 or fixture["odd_under25"] > 1.0:
        stat_rows.append(
            StatRow(
                label="Просечни квоти 0-2 / 3+",
                value=(
                    f"{fixture['odd_under25']:.2f} · "
                    f"{fixture['odd_over25']:.2f}"
                ),
            )
        )
    if fixture["bookmakers"] > 0:
        stat_rows.append(
            StatRow(
                label="Број кладилници во просекот",
                value=str(fixture["bookmakers"]),
            )
        )
    compare_note = ""
    mutual_rows: list[MutualRow] = []
    if compare is not None:
        mutual_rows = list(compare["mutual_rows"])
        stat_rows.extend(compare["stat_rows"])
        compare_note = compare["note"]
    else:
        compare_note = COMPARE_EMPTY_NOTE

    return Fudbal91Row(
        **fixture,
        covered=covered,
        match_id=match_id,
        is_upcoming=is_upcoming,
        has_context=bool(options) or bool(mutual_rows) or bool(stat_rows),
        has_source_pick=has_source_pick,
        source_pick=source_pick,
        source_pick_odds=source_pick_odds,
        support_label=(
            top["support_label"] if top is not None else "Без јасна поддршка"
        ),
        top_label=top["label"] if top is not None else NA_LABEL,
        top_probability=top["probability"] if top is not None else 0.0,
        options=options[:3],
        prob_home=prob_home,
        prob_draw=prob_draw,
        prob_away=prob_away,
        prob_over25=prob_over25,
        prob_under25=prob_under25,
        ft_projection=ft_projection,
        ft_probability=ft_probability,
        expected_goals=total_goals,
        ht_projection=ht_projection,
        ht_probability=ht_probability,
        has_mutual=len(mutual_rows) > 0,
        mutual_rows=mutual_rows,
        stat_rows=stat_rows[:12],
        has_stats=len(stat_rows) > 0,
        compare_note=compare_note,
        absences_label=NA_LABEL,
        absences_note=ABSENCES_NOTE,
        derived_note=DERIVED_NOTE,
    )
