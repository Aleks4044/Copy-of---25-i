"""Два јавни Mutating.com извори, споени по fixture_id.

1) /soccer-predictions/ (HTML) — реални имена на тимови, предвидување
   (1, X, 2, 1X, X2, 12), време/статус и контекст земја/лига.
2) /updatepredictions/ (JSON) — статус, резултат и ознака за исход
   (green/red) без имена на тимови.

Прикажани се само редовите со вистинско Mutating предвидување И реални
имена на домаќинот и гостинот, и тоа само кога настанот не е покриен
од BZZ или Fotmob. Квоти и сигурност не се објавени од изворот и НЕ се
измислуваат. Изворот не бара никакви клучеви или креденциали.
"""

import asyncio
import html
import logging
import re
from typing import TypedDict

import reflex as rx
import requests

from app.states import mutating_scrape
from app.states.bsd_state import local_clock, local_now

ENDPOINT = "https://www.mutating.com/updatepredictions/"
TIMEOUT = 8
MAX_ROWS = 40

TODAY_NOTE = (
    "Имената на тимовите, предвидувањето и лигата се читаат од јавната "
    "страница /soccer-predictions/, а статусот, резултатот и ознаката за "
    "исход од /updatepredictions/, споени по fixture_id. Прикажани се САМО "
    "редови со реални имена на двата тима и вистинско предвидување "
    "(1, X, 2, 1X, X2, 12). Квота и сигурност не се објавени од Mutating.com "
    "и не се измислуваат."
)
ODDS_NOTE = (
    "Mutating.com не објавува квота ниту сигурност за овие предвидувања — "
    "прикажан е само изборот како што го дава изворот."
)
NA_LABEL = "недостапно"
MARKETS_NOTE = (
    "Процентите за ГГ/НГ и Над/Под 1.5 и 2.5 се читаат од јавната страница "
    "за детали на самиот натпревар на Mutating.com. Прикажани се САМО "
    "настани со реални проценти од таа страница; ако изворот не ги "
    "објавува, настанот воопшто не се прикажува и не се пресметува ништо."
)

STATUS_KIND_LABELS: dict[str, str] = {
    "upcoming": "Претстоен",
    "live": "Во тек",
    "finished": "Завршен",
    "postponed": "Одложен",
}

COVERAGE_NOTE = (
    "Редовите со реални имена и предвидување од Mutating.com се "
    "синхронизирани со веќе вчитаната покриеност од BZZ и Fotmob преку "
    "fixture_id / event_id / fotmob_id. Прикажани се САМО непокриените "
    "настани."
)
UNMATCHED_EMPTY_NOTE = (
    "Сите настани со предвидување од Mutating.com се веќе покриени од BZZ "
    "или Fotmob, па нема непокриени резервни настани за приказ."
)
NO_NAMED_ROWS_NOTE = (
    "Mutating.com во моментот не обезбедува настан со реални имена на "
    "двата тима и вистинско предвидување, па нема што да се прикаже — "
    "историските редови без имена се третираат како недостапни."
)
UNNAMED_EXCLUDED_NOTE = (
    "{count} историски редови без имена на тимови или без предвидување се "
    "исклучени како недостапни."
)
NO_MARKET_ROWS_NOTE = (
    "Mutating.com во моментот не објавува проценти за ГГ/НГ и Над/Под "
    "1.5 и 2.5 на страниците за детали, па нема настан со реални маркети "
    "за приказ."
)
WITHOUT_MARKETS_EXCLUDED_NOTE = (
    "{count} настани со предвидување се скриени бидејќи страницата за детали "
    "не објавува проценти за маркетите."
)
PENDING_EXCLUDED_NOTE = (
    "{count} настани се без ознака за исход (сеуште нерешени)."
)
NO_COVERAGE_NOTE = (
    "Покриеноста од BZZ/Fotmob сè уште не е вчитана, па сите редови од "
    "Mutating.com се сметаат за непокриени."
)

LIMITATION_NOTE = (
    "Овој извор е јавен и недокументиран. Имената на тимовите, "
    "предвидувањето (1, X, 2, 1X, X2, 12), времето и лигата се читаат од "
    "јавната HTML страница /soccer-predictions/, а статусот, резултатот и "
    "ознаката за исход од /updatepredictions/. Процентите за ГГ/НГ и "
    "Над/Под 1.5 и 2.5 се читаат само кога јавната страница за детали "
    "на натпреварот навистина ги објавува; во спротивно стојат како "
    "“недостапно”. Сите HTML ознаки се "
    "отстрануваат пред приказ. Настаните без реални проценти од страницата "
    "за детали воопшто не се прикажуваат. Изворот НЕ објавува квоти ниту сигурност, "
    "па такви вредности не се прикажуваат. Историските редови без имена на "
    "тимови или без предвидување се третираат како недостапни и не се "
    "прикажуваат како предвидувања. Предвидувањата не се спојуваат со BZZ "
    "или Fotmob моделите — служат само како резервен показател."
)
UNAVAILABLE_NOTE = (
    "Mutating.com не одговори во дозволеното време или врати неочекуван "
    "формат. Ова не влијае на останатите податоци во апликацијата."
)
MAKEYOURSTATS_NOTE = (
    "MakeYourStats: недостапен — нема документиран јавен API, а страниците "
    "ограничуваат автоматски барања. Ќе биде додаден САМО кога ќе постои "
    "официјален/јавен пристап или изречна дозвола. До тогаш не се преземаат, "
    "не се стругаат и не се измислуваат редови од MakeYourStats."
)


class MutatingRow(TypedDict):
    fixture_id: str
    home: str
    away: str
    match_label: str
    pick: str
    pick_description: str
    detail_url: str
    # Реални проценти од страницата за детали (“недостапно” ако нема).
    has_markets: bool
    btts_label: str
    ng_label: str
    over15_label: str
    under15_label: str
    over25_label: str
    under25_label: str
    country: str
    league: str
    league_label: str
    has_names: bool
    has_pick: bool
    # True само кога изворот врати вистински сигнал за исход на
    # предвидување (green/red). Полето е ЗАДОЛЖИТЕЛНО и секогаш присутно.
    has_prediction_result: bool
    status: str
    status_kind: str
    status_label: str
    kickoff: str
    score: str
    result: str
    result_label: str
    winner: str
    winner_label: str


_TAG_RE = re.compile(r"<[^>]*>")


def _strip_html(value: object) -> str:
    """Отстранува HTML ознаки и ентитети од вредност на изворот."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return ""
    text = html.unescape(value)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    return " ".join(text.split())


def _clean(value: object) -> str:
    return _strip_html(value)


def _pct_label(value: object) -> str:
    """Форматира процент од изворот или враќа “недостапно”."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return NA_LABEL
    number = float(value)
    if number <= 0.0 or number > 100.0:
        return NA_LABEL
    return f"{number:.1f}%"


def _status_kind(status: str, score: str) -> str:
    upper = status.upper().strip()
    if upper in ("FT", "AET", "PEN", "AWD"):
        return "finished"
    if upper in ("PST", "POSTP", "CANC", "ABD", "SUSP"):
        return "postponed"
    # Минута во тек ("45", "90+3") или полувреме.
    if upper in ("HT", "ET", "BT", "P", "LIVE"):
        return "live"
    digits = upper.replace("+", "").replace("'", "")
    if digits.isdigit() and ":" not in upper:
        return "live"
    if score:
        return "live"
    return "upcoming"


STATUS_ORDER: dict[str, int] = {
    "live": 0,
    "upcoming": 1,
    "finished": 2,
    "postponed": 3,
}
MAX_TODAY_CARDS = 12


def _sort_key(row: MutatingRow) -> tuple[int, str]:
    return (STATUS_ORDER.get(row["status_kind"], 4), row["status"])


def _fetch_rows() -> list[dict]:
    response = requests.post(ENDPOINT, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict)]


def _prediction_result(calc: str) -> tuple[str, str, bool]:
    """Ознака за исход на предвидување од `calcresult` (green/red).

    Враќа (клуч, етикета, дали изворот врати вистински сигнал).
    """
    value = calc.lower()
    if "green" in value:
        return "correct", "Точно", True
    if "red" in value:
        return "wrong", "Погрешно", True
    return "pending", "Нерешено", False


def _to_row(
    raw: dict,
    enriched: dict[str, mutating_scrape.MutatingPrediction] | None = None,
) -> MutatingRow | None:
    fixture_id = _clean(raw.get("fixture_id"))
    if not fixture_id:
        return None
    info = (enriched or {}).get(fixture_id) or {}
    home_name = _clean(info.get("home"))
    away_name = _clean(info.get("away"))
    pick = _clean(info.get("pick")).upper().replace(" ", "")
    has_names = bool(home_name) and bool(away_name)
    has_pick = pick in mutating_scrape.VALID_PICKS
    country = _clean(info.get("country"))
    league = _clean(info.get("league"))
    league_label = _clean(info.get("league_label")) or "—"
    status = _clean(raw.get("value")) or _clean(info.get("kickoff")) or "—"
    home = _clean(raw.get("scorehome"))
    away = _clean(raw.get("scoreaway"))
    score = f"{home} - {away}" if home and away else "—"
    if score == "—":
        score = _clean(info.get("score")) or "—"
    result, result_label, has_prediction_result = _prediction_result(
        _clean(raw.get("calcresult"))
    )
    home_win = "homewin" in _clean(raw.get("winclasshome")).lower()
    away_win = "awaywin" in _clean(raw.get("winclassaway")).lower()
    winner = "home" if home_win else ("away" if away_win else "")
    winner_label = (
        "Домашен"
        if winner == "home"
        else ("Гостин" if winner == "away" else "Без победник")
    )
    kind = _status_kind(status, score if score != "—" else "")
    kickoff = status if kind == "upcoming" and ":" in status else "—"
    btts_label = _pct_label(info.get("btts"))
    ng_label = _pct_label(info.get("no_btts"))
    over15_label = _pct_label(info.get("over15"))
    under15_label = _pct_label(info.get("under15"))
    over25_label = _pct_label(info.get("over25"))
    under25_label = _pct_label(info.get("under25"))
    has_markets = bool(info.get("has_markets")) and any(
        label != NA_LABEL
        for label in (
            btts_label,
            over15_label,
            over25_label,
        )
    )
    return MutatingRow(
        fixture_id=fixture_id,
        home=home_name,
        away=away_name,
        match_label=(
            f"{home_name} — {away_name}"
            if has_names
            else f"Настан #{fixture_id}"
        ),
        pick=pick if has_pick else "—",
        pick_description=_clean(info.get("pick_description")),
        detail_url=_clean(info.get("detail_url")),
        has_markets=has_markets,
        btts_label=btts_label,
        ng_label=ng_label,
        over15_label=over15_label,
        under15_label=under15_label,
        over25_label=over25_label,
        under25_label=under25_label,
        country=country,
        league=league,
        league_label=league_label,
        has_names=has_names,
        has_pick=has_pick,
        has_prediction_result=has_prediction_result,
        status=status,
        status_kind=kind,
        status_label=STATUS_KIND_LABELS.get(kind, "Претстоен"),
        kickoff=kickoff,
        score=score,
        result=result,
        result_label=result_label,
        winner=winner,
        winner_label=winner_label,
    )


class MutatingState(rx.State):
    """Само-читачки статус панел за Mutating.com ажурирањата."""

    rows: list[MutatingRow] = []
    fetched_at: str = "--:--:--"
    error: str = ""
    page_notice: str = ""
    enriched_count: int = 0
    is_loading: bool = False
    has_loaded: bool = False
    filter_mode: str = "all"
    # Идентификатори (fixture_id / event_id / fotmob_id) што се веќе
    # покриени од BZZ или Fotmob податоците.
    covered_keys: list[str] = []
    coverage_source_count: int = 0
    coverage_synced_at: str = "--:--:--"

    @rx.var
    def limitation_note(self) -> str:
        return LIMITATION_NOTE

    @rx.var
    def makeyourstats_note(self) -> str:
        return MAKEYOURSTATS_NOTE

    @rx.var
    def odds_note(self) -> str:
        return ODDS_NOTE

    @rx.var
    def markets_note(self) -> str:
        return MARKETS_NOTE

    @rx.var
    def coverage_note(self) -> str:
        if not self.raw_named_rows:
            return self.page_notice or NO_NAMED_ROWS_NOTE
        if not self.named_rows:
            return NO_MARKET_ROWS_NOTE
        if self.coverage_source_count == 0:
            return NO_COVERAGE_NOTE
        if not self.unmatched_rows:
            return UNMATCHED_EMPTY_NOTE
        return COVERAGE_NOTE

    @rx.var
    def pending_note(self) -> str:
        parts: list[str] = []
        if self.without_markets_count > 0:
            parts.append(
                WITHOUT_MARKETS_EXCLUDED_NOTE.format(
                    count=self.without_markets_count
                )
            )
        if self.unnamed_count > 0:
            parts.append(UNNAMED_EXCLUDED_NOTE.format(count=self.unnamed_count))
        if self.pending_count > 0:
            parts.append(PENDING_EXCLUDED_NOTE.format(count=self.pending_count))
        return " ".join(parts)

    @rx.var
    def raw_named_rows(self) -> list[MutatingRow]:
        """Редови со реални имена И вистинско предвидување (без филтер на маркети)."""
        return [r for r in self.rows if r["has_names"] and r["has_pick"]]

    @rx.var
    def named_rows(self) -> list[MutatingRow]:
        """Приказливи редови: имена, предвидување И реални маркети."""
        return [
            r
            for r in self.rows
            if r["has_names"] and r["has_pick"] and r["has_markets"]
        ]

    @rx.var
    def named_count(self) -> int:
        return len(self.named_rows)

    @rx.var
    def without_markets_count(self) -> int:
        """Именувани редови без реални маркети — никогаш не се прикажуваат."""
        return len(self.raw_named_rows) - len(self.named_rows)

    @rx.var
    def unnamed_count(self) -> int:
        """Историски редови без имена/предвидување — никогаш не се прикажуваат."""
        return len(self.rows) - len(self.raw_named_rows)

    @rx.var
    def result_rows(self) -> list[MutatingRow]:
        """Именувани редови со вистински сигнал за исход (green/red)."""
        return [r for r in self.named_rows if r["has_prediction_result"]]

    @rx.var
    def pending_rows(self) -> list[MutatingRow]:
        """Именувани редови без сеуште означен исход."""
        return [r for r in self.named_rows if not r["has_prediction_result"]]

    @rx.var
    def result_count(self) -> int:
        return len(self.result_rows)

    @rx.var
    def pending_count(self) -> int:
        return len(self.pending_rows)

    @rx.var
    def unmatched_rows(self) -> list[MutatingRow]:
        covered = set(self.covered_keys)
        return [r for r in self.named_rows if r["fixture_id"] not in covered]

    @rx.var
    def matched_rows(self) -> list[MutatingRow]:
        covered = set(self.covered_keys)
        return [r for r in self.named_rows if r["fixture_id"] in covered]

    @rx.var
    def unmatched_count(self) -> int:
        return len(self.unmatched_rows)

    @rx.var
    def matched_count(self) -> int:
        return len(self.matched_rows)

    @rx.var
    def has_unmatched(self) -> bool:
        return len(self.unmatched_rows) > 0

    @rx.var
    def today_note(self) -> str:
        return TODAY_NOTE

    @rx.var
    def today_label(self) -> str:
        return local_now().strftime("%d.%m.%Y")

    @rx.var
    def total_count(self) -> int:
        return len(self.rows)

    @rx.var
    def finished_count(self) -> int:
        return len(
            [r for r in self.unmatched_rows if r["status_kind"] == "finished"]
        )

    @rx.var
    def upcoming_count(self) -> int:
        return len(
            [r for r in self.unmatched_rows if r["status_kind"] == "upcoming"]
        )

    @rx.var
    def live_count(self) -> int:
        return len(
            [r for r in self.unmatched_rows if r["status_kind"] == "live"]
        )

    @rx.var
    def postponed_count(self) -> int:
        return len(
            [r for r in self.unmatched_rows if r["status_kind"] == "postponed"]
        )

    @rx.var
    def correct_count(self) -> int:
        return len([r for r in self.unmatched_rows if r["result"] == "correct"])

    @rx.var
    def wrong_count(self) -> int:
        return len([r for r in self.unmatched_rows if r["result"] == "wrong"])

    @rx.var
    def today_rows(self) -> list[MutatingRow]:
        """Најрелевантните денешни настани: во тек, потоа претстојни.

        Секогаш се пресметува од целата вчитана листа (не од скратената
        табела), а филтерот се применува само ако остава редови. Така
        картичките никогаш не се празни кога има валидни редови.
        """
        unmatched = self.unmatched_rows
        filtered = self._filtered(unmatched)
        pool = filtered if filtered else unmatched
        return sorted(pool, key=_sort_key)[:MAX_TODAY_CARDS]

    @rx.var
    def accuracy_rate(self) -> float:
        settled = self.correct_count + self.wrong_count
        if settled == 0:
            return 0.0
        return round(self.correct_count / settled * 100, 1)

    @rx.var
    def settled_count(self) -> int:
        return self.correct_count + self.wrong_count

    @rx.var
    def filter_tabs(self) -> list[dict[str, str]]:
        return [
            {"key": "all", "label": "Сите", "count": str(self.unmatched_count)},
            {
                "key": "finished",
                "label": "Завршени",
                "count": str(self.finished_count),
            },
            {
                "key": "upcoming",
                "label": "Претстојни",
                "count": str(self.upcoming_count),
            },
            {
                "key": "live",
                "label": "Во тек",
                "count": str(self.live_count),
            },
            {
                "key": "correct",
                "label": "Точни",
                "count": str(self.correct_count),
            },
            {
                "key": "wrong",
                "label": "Погрешни",
                "count": str(self.wrong_count),
            },
        ]

    def _filtered(self, rows: list[MutatingRow]) -> list[MutatingRow]:
        if self.filter_mode == "finished":
            return [r for r in rows if r["status_kind"] == "finished"]
        if self.filter_mode == "upcoming":
            return [r for r in rows if r["status_kind"] == "upcoming"]
        if self.filter_mode == "live":
            return [r for r in rows if r["status_kind"] == "live"]
        if self.filter_mode == "correct":
            return [r for r in rows if r["result"] == "correct"]
        if self.filter_mode == "wrong":
            return [r for r in rows if r["result"] == "wrong"]
        return list(rows)

    @rx.var
    def visible_rows(self) -> list[MutatingRow]:
        return self._filtered(self.unmatched_rows)[:MAX_ROWS]

    @rx.var
    def visible_count(self) -> int:
        return len(self.visible_rows)

    @rx.var
    def has_data(self) -> bool:
        return len(self.named_rows) > 0

    @rx.var
    def has_result_rows(self) -> bool:
        return len(self.named_rows) > 0

    async def _load(self) -> None:
        if self.is_loading:
            return
        self.is_loading = True
        try:
            try:
                raw_rows = await asyncio.to_thread(_fetch_rows)
            except Exception as error:
                logging.exception("Unexpected error")
                logging.info(
                    f"Mutating.com статусот не е достапен: "
                    f"{type(error).__name__}"
                )
                self.error = UNAVAILABLE_NOTE
                return
            try:
                enriched, page_notice = await asyncio.to_thread(
                    mutating_scrape.fetch_predictions
                )
            except Exception as error:
                logging.exception("Unexpected error")
                logging.info(
                    f"Mutating.com предвидувањата не се вчитани: "
                    f"{type(error).__name__}"
                )
                enriched, page_notice = {}, UNAVAILABLE_NOTE
            self.page_notice = page_notice
            self.enriched_count = len(enriched)
            rows: list[MutatingRow] = []
            for raw in raw_rows:
                row = _to_row(raw, enriched)
                if row is not None:
                    rows.append(row)
            if not rows:
                self.error = UNAVAILABLE_NOTE
                return
            rows.sort(key=_sort_key)
            self.rows = rows
            self.fetched_at = local_clock()
            self.error = ""
            self.has_loaded = True
        finally:
            self.is_loading = False

    @rx.event
    async def sync_coverage(self):
        """Ја синхронизира покриеноста од BZZ/Fotmob по идентификатори."""
        from app.states.bsd_state import BSDState

        bsd = await self.get_state(BSDState)
        keys: list[str] = []
        for match in bsd.matches:
            for value in (match["event_id"], match["fotmob_id"]):
                key = str(value or "").strip()
                if key and key != "0" and key not in keys:
                    keys.append(key)
        self.covered_keys = keys
        self.coverage_source_count = len(bsd.matches)
        self.coverage_synced_at = local_clock()

    @rx.event
    async def load(self):
        if self.has_loaded or self.is_loading:
            yield MutatingState.sync_coverage
            return
        yield
        await self._load()
        yield MutatingState.sync_coverage

    @rx.event
    async def refresh(self):
        if self.is_loading:
            yield MutatingState.sync_coverage
            return
        yield
        await self._load()
        yield MutatingState.sync_coverage

    @rx.event
    def set_filter_mode(self, mode: str):
        self.filter_mode = mode
