"""Само-читачки клиент за јавните страници на t1x2.net.

Се читаат ИСКЛУЧИВО јавни страници со нормални GET барања:

  /tip-dana.html      · дневен јавен избор („Tip dana“)
  /tiket-dana.html    · дневен јавен тикет („Tiket dana“)
  /statistika.html    · јавни низови и резултати
  /                   · насловна (опционално)

Приватни, најавни и администраторски патеки НИКОГАШ не се повикуваат, ниту
се обидува заобиколување на Cloudflare. Ниту една вредност не се измислува:
се прикажува точно она што страницата навистина го врати (наслов, извадок,
најдени квоти, најдени ознаки за исход) со атрибуција кон заедницата на
t1x2.net. Ниту еден клуч или чувствителен податок не се логира.
"""

import logging
import re
import time
from typing import TypedDict

import requests

BASE_URL = "https://www.t1x2.net"
ATTRIBUTION = "Извор: јавни страници на заедницата t1x2.net"
TIMEOUT = 15
REQUEST_DELAY = 2.0
CACHE_TTL = 600.0
MAX_SNIPPETS_PER_PAGE = 6
EXCERPT_LIMIT = 220

HEADERS: dict[str, str] = {
    "User-Agent": "BSD-Football/1.0 (read-only public pages)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "sr,mk,en;q=0.8",
}

# Патеки што НИКОГАШ не се повикуваат (приватно, најава, админ, кеш).
BLOCKED_SEGMENTS: tuple[str, ...] = (
    "admin",
    "includes",
    "tmp",
    "cache",
    "login",
    "prijava",
    "register",
    "tipbook",
    "user.php",
    "poruke",
)

PUBLIC_PAGES: tuple[tuple[str, str, str], ...] = (
    ("tip", "Tip dana", "/tip-dana.html"),
    ("tiket", "Tiket dana", "/tiket-dana.html"),
    ("stat", "Statistika", "/statistika.html"),
    ("home", "Насловна", "/"),
)

CAPABILITY_LABELS: dict[str, str] = {
    "tip": "Tip dana · јавни наслови, извадоци и квоти со ознака „@“",
    "tiket": "Tiket dana · јавни редови со квоти и ознаки ✔ ✘ ◌",
    "stat": "Statistika · јавни низови, резултати и одиграни натпревари",
    "home": "Насловна · јавни истакнати блокови и линкови",
}
TIPSTER_CAPABILITY = (
    "Јавни tipster метрики · име, биланс, процент, ROI и профит од табелата"
)
NOT_EXTRACTABLE = (
    "Не се читаат: приватни пораки, најавени профили, премиум содржина, "
    "/admin/, /includes/, /tmp/ и /cache/"
)

PARSER_MISSING_NOTE = (
    "HTML парсерот не е достапен, па јавните извадоци од t1x2.net не се "
    "вчитани."
)
UNAVAILABLE_NOTE = (
    "t1x2.net не одговори во дозволеното време или врати неочекуван формат. "
    "Останатите извори не се засегнати."
)
EMPTY_NOTE = (
    "Јавните страници на t1x2.net не вратија извадок што може безбедно да се "
    "прочита во моментот."
)
SNIPPET_NOTE = (
    "Јавен извадок од страницата · не е предвидување на моделите на "
    "апликацијата"
)

_ODDS_RE = re.compile(r"@\s*(\d{1,3}[.,]\d{2})")
_BRACKET_ODDS_RE = re.compile(r"\((\d{1,2}[.,]\d{2})\)")
_PICK_RE = re.compile(r"Tip:\s*([^@]{1,32}?)\s*@\s*(\d{1,3}[.,]\d{2})")
_RECORD_RE = re.compile(r"\((\d+)\s*/\s*(\d+)\)")
_PCT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
_PROFIT_RE = re.compile(r"(-?\d{1,5}[.,]\d{2})\s*€")
_MARKER_HIT = "✔"
_MARKER_MISS = "✘"
_MARKER_PENDING = "◌"

_CACHE: dict[str, tuple[float, dict]] = {}


class T1x2Snippet(TypedDict):
    id: str
    category_key: str
    category: str
    title: str
    excerpt: str
    url: str
    odds: list[str]
    odds_count: int
    odds_label: str
    has_odds: bool
    hit_count: int
    miss_count: int
    pending_count: int
    marker_label: str
    has_markers: bool
    match_label: str
    pick: str
    top_odd: float
    has_triple: bool
    note: str


class T1x2Tipster(TypedDict):
    name: str
    record: str
    accuracy: str
    roi: str
    profit: str
    source_url: str


class T1x2Page(TypedDict):
    key: str
    category: str
    url: str
    status_code: int
    status_label: str
    ok: bool
    length: int
    odds_count: int
    marker_count: int
    snippet_count: int


class T1x2Snapshot(TypedDict):
    snippets: list[T1x2Snippet]
    tipsters: list[T1x2Tipster]
    pages: list[T1x2Page]
    capabilities: list[str]
    note: str
    error: str


def _is_allowed(path: str) -> bool:
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


def _soup(markup: str):
    from bs4 import BeautifulSoup

    return BeautifulSoup(markup, "html.parser")


def _odds_values(text: str) -> list[str]:
    found: list[str] = []
    for match in _ODDS_RE.finditer(text or ""):
        value = match.group(1).replace(",", ".")
        if value not in found:
            found.append(value)
    if not found:
        for match in _BRACKET_ODDS_RE.finditer(text or ""):
            value = match.group(1).replace(",", ".")
            if value not in found:
                found.append(value)
    return found[:6]


def _marker_counts(text: str) -> tuple[int, int, int]:
    body = text or ""
    return (
        body.count(_MARKER_HIT),
        body.count(_MARKER_MISS),
        body.count(_MARKER_PENDING),
    )


def _marker_label(hit: int, miss: int, pending: int) -> str:
    if hit == 0 and miss == 0 and pending == 0:
        return ""
    parts: list[str] = []
    if hit:
        parts.append(f"{_MARKER_HIT} {hit}")
    if miss:
        parts.append(f"{_MARKER_MISS} {miss}")
    if pending:
        parts.append(f"{_MARKER_PENDING} {pending}")
    return " · ".join(parts)


def _match_label(title: str) -> str:
    """Ознака на натпревар од јавниот наслов, ако постои во таа форма."""
    head = title
    for separator in (
        "- Tip Dana",
        "- Tip dana",
        "Tip Dana za",
        "- Tiket Dana",
        "- Tiket dana",
    ):
        if separator in head:
            head = head.split(separator)[0]
            break
    head = head.strip(" -·⚽🎾🏀")
    if " - " in head and 6 <= len(head) <= 70:
        return _clean(head)
    return ""


def _snippet(
    key: str,
    category: str,
    url: str,
    index: int,
    title: str,
    excerpt: str,
) -> T1x2Snippet:
    odds = _odds_values(excerpt) or _odds_values(title)
    hit, miss, pending = _marker_counts(excerpt)
    match_label = _match_label(title)
    pick = ""
    top_odd = 0.0
    found = _PICK_RE.search(excerpt) or _PICK_RE.search(title)
    if found is not None:
        pick = _clean(found.group(1))
        try:
            top_odd = round(float(found.group(2).replace(",", ".")), 2)
        except ValueError:
            top_odd = 0.0
    elif odds:
        try:
            top_odd = round(float(odds[0]), 2)
        except ValueError:
            top_odd = 0.0
    return T1x2Snippet(
        id=f"t1x2-{key}-{index}",
        category_key=key,
        category=category,
        title=title[:120],
        excerpt=excerpt[:EXCERPT_LIMIT],
        url=url,
        odds=odds,
        odds_count=len(odds),
        odds_label=" · ".join(odds) if odds else "",
        has_odds=len(odds) > 0,
        hit_count=hit,
        miss_count=miss,
        pending_count=pending,
        marker_label=_marker_label(hit, miss, pending),
        has_markers=(hit + miss + pending) > 0,
        match_label=match_label,
        pick=pick,
        top_odd=top_odd,
        has_triple=bool(match_label and pick and top_odd > 1.0),
        note=SNIPPET_NOTE,
    )


def _usable(title: str, excerpt: str) -> bool:
    if len(title) < 8:
        return False
    body = f"{title} {excerpt}"
    if _odds_values(body):
        return True
    if any(marker in body for marker in (_MARKER_HIT, _MARKER_MISS)):
        return True
    return any(char.isdigit() for char in body)


def _snippets(
    markup: str, key: str, category: str, url: str
) -> list[T1x2Snippet]:
    """Извадоци од јавната страница; празна листа кога нема безбеден текст."""
    try:
        soup = _soup(markup)
    except Exception as error:
        logging.exception("Unexpected error")
        logging.info(f"t1x2 страницата не е парсирана: {type(error).__name__}")
        return []

    rows: list[T1x2Snippet] = []
    seen: set[str] = set()
    for node in soup.find_all(["h1", "h2", "h3"]):
        if len(rows) >= MAX_SNIPPETS_PER_PAGE:
            break
        title = _text(node)
        holder = getattr(node, "parent", None)
        excerpt = _text(holder) or title
        if not _usable(title, excerpt):
            continue
        if title in seen:
            continue
        seen.add(title)
        rows.append(_snippet(key, category, url, len(rows), title, excerpt))

    if rows:
        return rows

    for table in soup.find_all("table")[:3]:
        for row in table.find_all("tr")[:14]:
            if len(rows) >= MAX_SNIPPETS_PER_PAGE:
                break
            text = _text(row)
            if len(text) < 14 or text in seen:
                continue
            if not _usable(text, text):
                continue
            seen.add(text)
            rows.append(
                _snippet(key, category, url, len(rows), text[:90], text)
            )
        if len(rows) >= MAX_SNIPPETS_PER_PAGE:
            break
    return rows


def _tipsters(markup: str, url: str) -> list[T1x2Tipster]:
    """Јавни tipster метрики од табелата, ако страницата ги објавува."""
    try:
        soup = _soup(markup)
    except Exception as error:
        logging.exception("Unexpected error")
        logging.info(f"t1x2 табелата не е парсирана: {type(error).__name__}")
        return []

    rows: list[T1x2Tipster] = []
    seen: set[str] = set()
    for table in soup.find_all("table")[:4]:
        for row in table.find_all("tr"):
            if len(rows) >= 10:
                break
            cells = [_text(cell) for cell in row.find_all(["td", "th"])]
            if len(cells) < 4:
                continue
            joined = " ".join(cells)
            record = _RECORD_RE.search(joined)
            percent = _PCT_RE.search(joined)
            if record is None or percent is None:
                continue
            name = _clean(cells[0])
            if not name or name in seen:
                continue
            profit = _PROFIT_RE.search(joined)
            roi = ""
            for cell in cells[1:]:
                value = cell.replace(",", ".")
                if (
                    value
                    and "%" not in value
                    and "€" not in value
                    and "/" not in value
                ):
                    try:
                        roi = f"{float(value):.2f}"
                    except ValueError:
                        continue
                    break
            seen.add(name)
            rows.append(
                T1x2Tipster(
                    name=name[:40],
                    record=f"{record.group(1)}/{record.group(2)}",
                    accuracy=f"{percent.group(1)}%",
                    roi=roi or "недостапно",
                    profit=(
                        f"{profit.group(1).replace(',', '.')}€"
                        if profit is not None
                        else "недостапно"
                    ),
                    source_url=url,
                )
            )
    return rows


def _status_label(code: int) -> str:
    if code == 200:
        return "200 · достапно"
    if code == 0:
        return "мрежна грешка / timeout"
    if code == 429:
        return "429 · ограничено"
    return f"HTTP {code}"


def _get(session: requests.Session, path: str) -> tuple[str, int]:
    """Тивко GET барање кон јавна страница. Никогаш не крева исклучок."""
    if not _is_allowed(path):
        logging.info("t1x2 патеката е прескокната како непублична.")
        return "", 0
    try:
        response = session.get(f"{BASE_URL}{path}", timeout=TIMEOUT)
    except requests.RequestException as error:
        logging.exception("Unexpected error")
        logging.info(f"t1x2 {path} не е достапно: {type(error).__name__}")
        return "", 0
    if response.status_code != 200:
        logging.info(f"t1x2 {path} врати HTTP {response.status_code}.")
        return "", response.status_code
    return response.text, 200


def fetch_snapshot(include_home: bool = True) -> T1x2Snapshot:
    """Ги чита јавните страници и враќа само реално извлечени извадоци."""
    now = time.monotonic()
    cached = _CACHE.get("snapshot")
    if cached is not None and now - cached[0] < CACHE_TTL:
        return T1x2Snapshot(**cached[1])

    empty = T1x2Snapshot(
        snippets=[],
        tipsters=[],
        pages=[],
        capabilities=[],
        note="",
        error=UNAVAILABLE_NOTE,
    )

    try:
        from bs4 import BeautifulSoup  # noqa: F401
    except Exception as error:
        logging.exception("Unexpected error")
        logging.info(f"BeautifulSoup не е достапен: {type(error).__name__}")
        empty["error"] = PARSER_MISSING_NOTE
        return empty

    session = requests.Session()
    session.headers.update(HEADERS)
    pages: list[T1x2Page] = []
    snippets: list[T1x2Snippet] = []
    tipsters: list[T1x2Tipster] = []
    capabilities: list[str] = []
    targets = [row for row in PUBLIC_PAGES if include_home or row[0] != "home"]
    try:
        for index, (key, category, path) in enumerate(targets):
            if index > 0:
                time.sleep(REQUEST_DELAY)
            markup, status = _get(session, path)
            url = f"{BASE_URL}{path}"
            page_snippets: list[T1x2Snippet] = []
            if status == 200 and markup:
                page_snippets = _snippets(markup, key, category, url)
                if key in ("tip", "tiket"):
                    for row in _tipsters(markup, url):
                        if all(
                            row["name"] != item["name"] for item in tipsters
                        ):
                            tipsters.append(row)
                label = CAPABILITY_LABELS.get(key)
                if label and label not in capabilities:
                    capabilities.append(label)
            snippets.extend(page_snippets)
            odds_total = sum(row["odds_count"] for row in page_snippets)
            marker_total = sum(
                row["hit_count"] + row["miss_count"] + row["pending_count"]
                for row in page_snippets
            )
            pages.append(
                T1x2Page(
                    key=key,
                    category=category,
                    url=url,
                    status_code=status,
                    status_label=_status_label(status),
                    ok=status == 200 and bool(markup),
                    length=len(markup),
                    odds_count=odds_total,
                    marker_count=marker_total,
                    snippet_count=len(page_snippets),
                )
            )
    finally:
        try:
            session.close()
        except Exception as error:
            logging.exception("Unexpected error")
            logging.info(f"t1x2 сесијата не е затворена: {error}")

    if tipsters and TIPSTER_CAPABILITY not in capabilities:
        capabilities.append(TIPSTER_CAPABILITY)
    if capabilities:
        capabilities.append(NOT_EXTRACTABLE)

    reachable = [page for page in pages if page["ok"]]
    snapshot = T1x2Snapshot(
        snippets=snippets,
        tipsters=tipsters,
        pages=pages,
        capabilities=capabilities,
        note=ATTRIBUTION,
        error=(
            ""
            if snippets
            else (UNAVAILABLE_NOTE if not reachable else EMPTY_NOTE)
        ),
    )
    if snippets:
        _CACHE["snapshot"] = (time.monotonic(), dict(snapshot))
    return snapshot
