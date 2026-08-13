"""BSD предвидувања базирани на вистински податоци од sports.bzzoiro.com."""

import asyncio
import logging
import math
import unicodedata
from datetime import date, datetime, timedelta, timezone
from typing import TypedDict
from zoneinfo import ZoneInfo

import reflex as rx

from app.states import api_client, bzz_derived
from app.states.api_client import ApiError

# Локалната зона на корисникот. Сите „денес“ ознаки, датумски прозорци и
# прикажани часови се пресметуваат според неа, за да не се прикаже погрешен
# ден при доцните ноќни часови (кога UTC датумот е веќе следниот).
LOCAL_TZ_NAME = "Europe/Skopje"


def _local_zone() -> timezone | ZoneInfo:
    try:
        return ZoneInfo(LOCAL_TZ_NAME)
    except Exception as error:
        logging.exception("Unexpected error")
        logging.info(
            "Локалната временска зона не е достапна "
            f"({type(error).__name__}); се користи UTC отстапка."
        )
        return timezone.utc


def _to_local(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(_local_zone())


def local_now() -> datetime:
    return datetime.now(_local_zone())


def local_today() -> date:
    return local_now().date()


def local_clock() -> str:
    """Тековен час според локалната зона (Europe/Skopje), не според серверот."""
    return local_now().strftime("%H:%M:%S")


def _parse_moment(raw: str) -> datetime | None:
    if not isinstance(raw, str) or len(raw) < 10:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _local_date(raw: str) -> date | None:
    """Локалниот (Скопје) датум на настанот од ISO ознаката на API-то."""
    parsed = _parse_moment(raw)
    if parsed is None:
        if isinstance(raw, str) and len(raw) >= 10:
            try:
                return date.fromisoformat(raw[:10])
            except ValueError:
                return None
        return None
    return _to_local(parsed).date()


# Настаните се вчитуваат за локалниот прозорец „денес и утре“ со
# документираните филтри на BZZ API-то (v2)
# (/events/?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD), со полна offset/limit
# пагинација и лимит 200 по страница — така се покриваат сите настани од
# прозорецот, не само првата страница.
EVENT_PAGE_LIMIT = 200
# Конзервативни, предвидливи лимити: едно рачно освежување или иницијално
# вчитување мора да заврши во практично време на барање, па страниците и
# подресурсите по настан се строго ограничени.
MAX_EVENT_PAGES = 3
LIVE_PAGE_LIMIT = 100
MAX_LIVE_PAGES = 2
PREDICTION_PAGE_LIMIT = 200
MAX_PREDICTION_PAGES = 3

# Јавната слика за грб на тим не бара автентикација и НИКОГАШ не смее да
# содржи API клуч во URL-то.
TEAM_IMAGE_BASE = "https://sports.bzzoiro.com/img/team"
MAX_ENRICHED = 2
# Колку натпревари од денес смеат да добијат форма од /h2h/ дури и без
# предвидување. Конзервативно, за да не се прекрши ограничувањето на API-то
# и за да не се надмине практичното време на едно освежување.
MAX_FORM_ENRICHED = 3
NA_LABEL = "Недостапно"
RATE_LIMIT_NOTE = (
    "Деталните статистики (xG и форма) не се вчитани бидејќи API-то ограничи "
    "дел од барањата (429). Листата на натпревари и предвидувањата се реални."
)
ENRICH_UNAVAILABLE_NOTE = (
    "API-то не врати детални статистики (xG и форма) за овие натпревари."
)
PREDICTIONS_RATE_LIMIT_NOTE = (
    "API-то ограничи барањата за предвидувања (429). Прикажани се само "
    "реалните натпревари; предвидувањата ќе се појават при следното "
    "успешно освежување."
)
PREDICTIONS_UNAVAILABLE_NOTE = (
    "API-то не врати предвидувања за овие натпревари во моментот."
)
# Колку настани смеат да го користат ресурсот за предвидување по настан кога
# листата /predictions/ не врати предвидување (конзервативно, за да не се
# активира ограничувањето 429).
EVENT_PREDICTION_LIMIT = 10
EVENT_PREDICTION_NOTE = (
    "{count} натпревари добија предвидување директно од ресурсот за "
    "предвидување по настан, бидејќи листата не го врати."
)
# Колку настани без официјално предвидување смеат да добијат изведено
# предвидување од реалните ресурси по настан (квоти/H2H/состави/статистики).
DERIVED_PREDICTION_LIMIT = 6
# Само за неколку настани се проверуваат и опционалните ресурси
# (/summary/ и /money/), бидејќи тие најчесто враќаат 404.
DERIVED_OPTIONAL_LIMIT = 1
DERIVED_APPLIED_NOTE = (
    "{count} натпревари без официјално BZZ предвидување добија изведено "
    "предвидување пресметано САМО од реални BZZ ресурси по ред: квоти, "
    "резиме на настанот, H2H и состави (како корекција)."
)
DERIVED_UNAVAILABLE_NOTE = (
    "BZZ не објавува ниту предвидување, ниту квоти, ниту употребливи полиња "
    "во резимето, ниту меѓусебни средби за овој натпревар, па предвидување "
    "не може да се изведе и ништо не се измислува. Деталите за секој "
    "ресурс се видливи во панелот „BZZ извори по настан“."
)
# Забелешки за настани што НЕ биле побарани поради конзервативните лимити.
# Не се пресметува ништо и не се измислува ниту една вредност за нив.
DETAIL_LIMIT_NOTE = (
    "Деталните BZZ ресурси за овој натпревар не се побарани во ова "
    "освежување поради конзервативните лимити на барања (за да остане "
    "освежувањето брзо). Затоа предвидувањето е недостапно и ништо не се "
    "измислува — ресурсите можат да се прочитаат рачно во панелот „BZZ "
    "извори по настан“ или при следното освежување."
)
DETAIL_LIMIT_NOTICE = (
    "{count} натпревари без официјално предвидување не беа побарани во ова "
    "освежување поради лимитите на барања; тие остануваат видливи со ознака "
    "за недостапност."
)
ENRICH_LIMIT_NOTICE = (
    "Деталните статистики и формата се читаат за најмногу "
    f"{MAX_ENRICHED} + {MAX_FORM_ENRICHED} натпревари по освежување; "
    "останатите остануваат без xG и форма, без измислени вредности."
)
MISSING_KEY_ERROR = (
    "Не е поставен API клуч (BZZOIRO_API_KEY), па BZZ натпреварите и "
    "предвидувањата не можат да се вчитаат. Апликацијата продолжува да "
    "работи, а Mutating.com статусот е достапен во табот „Извори“."
)
MISSING_KEY_NOTE = (
    "BZZ API клучот не е поставен, па предвидувањата од BZZ не се достапни."
)
EVENTS_RATE_LIMIT_ERROR = (
    "API-то ограничи барањата (429). Почекајте пред следно освежување."
)
EVENTS_PARTIAL_RATE_LIMIT_NOTE = (
    "API-то ограничи дел од барањата (429) при ова освежување. Прикажани се "
    "последните вчитани реални натпревари; податоците ќе се ажурираат при "
    "следното успешно освежување."
)
EVENTS_PARTIAL_SEGMENTS_NOTE = (
    "API-то ограничи барањата (429) за: {segments}. Прикажани се само "
    "денешните натпревари што се вчитани успешно; останатите ќе се појават "
    "при следното успешно освежување."
)
SEGMENT_LABELS: dict[str, str] = {
    "upcoming": "претстојни денес",
    "finished": "завршени денес",
    "live": "натпревари во тек",
}


class ModelPick(TypedDict):
    name: str
    family: str
    pick: str
    probability: float
    accuracy: float


class ShadowPick(TypedDict):
    """Fotmob предвидување пресметано само за споредба (не заменува BZZ)."""

    match_id: str
    ml_pick: str
    ml_side: str
    ml_confidence: float
    meta_market: str
    meta_pick: str
    meta_confidence: float
    meta_edge: float


class ComboMarket(TypedDict):
    key: str
    label: str
    group: str
    group_label: str
    probability: float
    odds: float
    edge: float
    recommended: bool
    recommendation: str


class BSDMatch(TypedDict):
    id: str
    event_id: int
    has_xg: bool
    kickoff: str
    sort_key: str
    date_key: str
    day_label: str
    source: str
    source_label: str
    derived_basis: str
    fotmob_id: int
    stat_facts: list[str]
    league: str
    home: str
    away: str
    home_team_id: int
    away_team_id: int
    home_logo_url: str
    away_logo_url: str
    status: str
    status_text: str
    minute: str
    has_ht: bool
    ht_home: int
    ht_away: int
    ht_label: str
    score: str
    venue: str
    form_home: str
    form_away: str
    has_prediction: bool
    prediction_note: str
    model_name: str
    # BSD ML
    ml_home: float
    ml_draw: float
    ml_away: float
    ml_pick: str
    ml_confidence: float
    pick_side: str
    # Bivariate Poisson / expected goals
    xg_home: float
    xg_away: float
    poi_home: float
    poi_draw: float
    poi_away: float
    poi_btts: float
    poi_over25: float
    poi_under25: float
    poi_over35: float
    poi_under35: float
    poi_over15: float
    poi_under15: float
    extra_label: str
    extra_pick: str
    extra_probability: float
    top_score: str
    top_score_prob: float
    expected_goals: float
    # Топ 3 модели
    top_models: list[ModelPick]
    # Комбинирани маркети
    combos: list[ComboMarket]
    top_combos: list[ComboMarket]
    combo_count: int
    combo_recommended: int
    best_combo_label: str
    best_combo_probability: float
    # Meta-Ensemble
    meta_market: str
    meta_pick: str
    meta_confidence: float
    meta_odds: float
    meta_edge: float
    meta_agreement: float
    meta_value: str


COMBO_GROUP_LABELS: dict[str, str] = {
    "outcome": "Единечен исход (1X2)",
    "double": "Двоен шанс",
    "result_goals": "Резултат + Голови",
    "result_btts": "Резултат + ГГ",
    "double_goals": "Двоен шанс + Голови",
    "double_btts": "Двоен шанс + ГГ",
    "btts_goals": "ГГ + Голови",
    "goals": "Голови и специјални",
}

LIVE_STATUSES = {
    "inprogress",
    "live",
    "1sthalf",
    "2ndhalf",
    "firsthalf",
    "secondhalf",
    "halftime",
    "ht",
    "paused",
    "extratime",
    "penalties",
    "interrupted",
}
FINISHED_STATUSES = {
    "finished",
    "ended",
    "fulltime",
    "ft",
    "aet",
    "afterextratime",
    "afterpenalties",
    "awarded",
}
UPCOMING_STATUSES = {
    "notstarted",
    "scheduled",
    "tbd",
    "timetobedefined",
}
CANCELLED_STATUSES = {
    "cancelled",
    "canceled",
    "abandoned",
    "suspended",
    "interruptedfinal",
}
POSTPONED_STATUSES = {
    "postponed",
    "postp",
    "delayed",
}


def _normalize_status(raw: str) -> str:
    """Дефанзивна нормализација на статусот од API-то.

    Освен „upcoming/live/finished“ враќа и „cancelled“ и „postponed“, за да
    можат таквите настани да се исклучат од листата на претстојни.
    """
    key = (
        (raw or "")
        .strip()
        .lower()
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
    )
    if key in LIVE_STATUSES:
        return "live"
    if key in FINISHED_STATUSES:
        return "finished"
    if key in CANCELLED_STATUSES:
        return "cancelled"
    if key in POSTPONED_STATUSES:
        return "postponed"
    if key in UPCOMING_STATUSES:
        return "upcoming"
    if "cancel" in key or "abandon" in key or "suspend" in key:
        return "cancelled"
    if "postpon" in key or "delay" in key:
        return "postponed"
    if "half" in key or "progress" in key or "live" in key:
        return "live"
    if "finish" in key or "end" in key:
        return "finished"
    return "upcoming"


def _num(value: float | int | str | None) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().replace("%", ""))
        except ValueError:
            return None
    return None


def _pct(value: float | int | str | None) -> float | None:
    number = _num(value)
    if number is None:
        return None
    if 0.0 <= number <= 1.0:
        number *= 100.0
    if number < 0.0 or number > 100.0:
        return None
    return round(number, 1)


def _pick_pct(block: dict, keys: tuple[str, ...]) -> float | None:
    if not isinstance(block, dict):
        return None
    for key in keys:
        if key in block:
            direct = _pct(block[key])
            if direct is not None:
                return direct
            sub = block[key]
            if isinstance(sub, dict):
                for inner in ("probability", "prob", "percent", "value", "pct"):
                    nested = _pct(sub.get(inner))
                    if nested is not None:
                        return nested
    probs = block.get("probabilities")
    if isinstance(probs, dict):
        return _pick_pct(probs, keys)
    return None


FAVORITE_SIDES: dict[str, str] = {
    "H": "home",
    "D": "draw",
    "A": "away",
    "1": "home",
    "X": "draw",
    "2": "away",
    "HOME": "home",
    "DRAW": "draw",
    "AWAY": "away",
}

REC_FLAG_LABELS: dict[str, str] = {
    "bet_favorite": "Фаворит",
    "winner": "Победник",
    "btts": "ГГ",
    "over_15": "Над 1.5",
    "over_25": "Над 2.5",
    "over_35": "Над 3.5",
}


def _over_line(block: dict, keys: tuple[str, ...]) -> float | None:
    direct = _pick_pct(block, keys)
    if direct is not None:
        return direct
    lines = block.get("lines") if isinstance(block, dict) else None
    if isinstance(lines, list):
        for line in lines:
            if not isinstance(line, dict):
                continue
            label = str(line.get("line"))
            if any(label.replace("_", ".") in key for key in keys):
                nested = _pick_pct(line, ("over", "over_probability", "yes"))
                if nested is not None:
                    return nested
    return None


def _over25(block: dict) -> float | None:
    direct = _pick_pct(
        block,
        (
            "prob_over_25",
            "prob_over_2_5",
            "over_2_5",
            "over25",
            "over_25",
            "over_2.5",
            "over2_5",
            "over",
        ),
    )
    if direct is not None:
        return direct
    for key in ("2.5", "2_5", "25"):
        sub = block.get(key) if isinstance(block, dict) else None
        if isinstance(sub, dict):
            nested = _pick_pct(sub, ("over", "over_probability", "yes"))
            if nested is not None:
                return nested
    lines = block.get("lines") if isinstance(block, dict) else None
    if isinstance(lines, list):
        for line in lines:
            if not isinstance(line, dict):
                continue
            if _num(line.get("line")) == 2.5 or str(line.get("line")) == "2.5":
                nested = _pick_pct(line, ("over", "over_probability", "yes"))
                if nested is not None:
                    return nested
    return None


def _poisson_pmf(lam: float, k: int) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


def _top_score_from_lambdas(
    lam_home: float, lam_away: float, max_goals: int = 7
) -> tuple[str, float]:
    """Ја гради целата матрица на точни резултати и враќа најверојатниот."""
    if lam_home <= 0.0 or lam_away <= 0.0:
        return NA_LABEL, 0.0
    home = [_poisson_pmf(lam_home, k) for k in range(max_goals + 1)]
    away = [_poisson_pmf(lam_away, k) for k in range(max_goals + 1)]
    total = 0.0
    best_prob = 0.0
    best = NA_LABEL
    for h, ph in enumerate(home):
        for a, pa in enumerate(away):
            joint = ph * pa
            total += joint
            if joint > best_prob:
                best_prob, best = joint, f"{h}-{a}"
    if total <= 0.0 or best_prob <= 0.0:
        return NA_LABEL, 0.0
    return best, round(best_prob / total * 100, 1)


def _lambdas(
    xg_home: float | None,
    xg_away: float | None,
    over25: float | None,
    ml_home: float,
    ml_draw: float,
    ml_away: float,
) -> tuple[float, float] | None:
    """Очекувани голови по тим од реални xG или од веројатностите на моделот."""
    if (
        xg_home is not None
        and xg_away is not None
        and (xg_home + xg_away) > 0.2
    ):
        return max(0.15, round(xg_home, 2)), max(0.15, round(xg_away, 2))
    if over25 is None:
        return None
    total = min(5.0, max(1.2, 1.35 + (over25 - 50.0) / 100.0 * 2.4))
    weight_home = ml_home + ml_draw / 2.0
    weight_away = ml_away + ml_draw / 2.0
    denominator = weight_home + weight_away
    share = weight_home / denominator if denominator > 0 else 0.5
    share = min(0.72, max(0.28, share))
    return round(total * share, 2), round(total * (1.0 - share), 2)


def _derive_over15(
    over15: float | None,
    over25: float | None,
    lambdas: tuple[float, float] | None,
) -> float | None:
    """Реален Над 1.5 ако постои, инаку конзервативна изведба."""
    if over15 is not None and over15 > 0.0:
        return round(over15, 1)
    if lambdas is not None:
        lam = lambdas[0] + lambdas[1]
        if lam > 0.0:
            value = 1.0 - _poisson_pmf(lam, 0) - _poisson_pmf(lam, 1)
            if value > 0.0:
                return round(min(98.0, value * 100.0), 1)
    if over25 is not None and over25 > 0.0:
        return round(min(98.0, over25 + (100.0 - over25) * 0.5), 1)
    return None


def _top_score(block: dict) -> tuple[str, float]:
    if isinstance(block, dict):
        for key in ("most_likely", "top", "correct_score", "best", "score"):
            value = block.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip(), _pct(block.get("probability")) or 0.0
            if isinstance(value, dict):
                label = value.get("score") or value.get("label")
                if isinstance(label, str) and label.strip():
                    return label.strip(), _pct(value.get("probability")) or 0.0
        home = _num(block.get("home"))
        away = _num(block.get("away"))
        if home is not None and away is not None:
            return f"{int(round(home))}-{int(round(away))}", 0.0
        scores = block.get("scores") or block.get("top_scores")
        if isinstance(scores, list) and scores:
            best = None
            best_prob = -1.0
            for row in scores:
                if not isinstance(row, dict):
                    continue
                prob = _pct(row.get("probability")) or 0.0
                label = row.get("score") or row.get("label")
                if isinstance(label, str) and prob > best_prob:
                    best, best_prob = label, prob
            if best:
                return best, max(0.0, best_prob)
    return NA_LABEL, 0.0


def _recommendation_label(probability: float) -> str:
    if probability >= 70.0:
        return "Силна препорака"
    if probability >= 55.0:
        return "Препорака"
    if probability > 40.0:
        return "Разгледај"
    return ""


def _value_label(edge: float) -> str:
    if edge >= 6.0:
        return "Висока вредност"
    if edge >= 2.0:
        return "Умерена вредност"
    return "Ниска вредност"


def _extra_recommendation(
    btts: float | None,
    over25: float | None,
    over35: float | None,
) -> tuple[str, str, float]:
    """Најсилна дополнителна препорака од реални веројатности."""
    options: list[tuple[str, str, float]] = []
    if btts is not None and btts > 0.0:
        if btts >= 50.0:
            options.append(("ГГ / НГ", "ГГ · двата тима", btts))
        else:
            options.append(("ГГ / НГ", "НГ · без ГГ", 100.0 - btts))
    if over25 is not None and over25 > 0.0:
        if over25 >= 50.0:
            options.append(("Над / Под 2.5", "Над 2.5 гола", over25))
        else:
            options.append(("Над / Под 2.5", "Под 2.5 гола", 100.0 - over25))
    if over35 is not None and over35 > 0.0:
        if over35 >= 50.0:
            options.append(("Над / Под 3.5", "Над 3.5 гола", over35))
        else:
            options.append(("Над / Под 3.5", "Под 3.5 гола", 100.0 - over35))
    if not options:
        return NA_LABEL, NA_LABEL, 0.0
    best = max(options, key=lambda row: row[2])
    return best[0], best[1], round(best[2], 1)


def _fair_odds(probability: float) -> float:
    return round(max(1.02, 100.0 / max(probability, 2.0) * 1.06), 2)


def _combo_markets(
    home: str,
    away: str,
    ml_home: float,
    ml_draw: float,
    ml_away: float,
    btts: float,
    over25: float,
    over15: float | None = None,
    over35: float | None = None,
) -> list[ComboMarket]:
    """Комбинирани маркети пресметани само од вистински API веројатности."""
    no_btts = max(0.0, 100.0 - btts)
    under25 = max(0.0, 100.0 - over25)
    over15 = (
        over15
        if over15 is not None
        else min(99.0, over25 + (100.0 - over25) * 0.55)
    )
    over35 = over35 if over35 is not None else max(1.0, over25 * 0.52)
    under35 = max(0.0, 100.0 - over35)
    dc_1x = min(99.0, ml_home + ml_draw)
    dc_12 = min(99.0, ml_home + ml_away)
    dc_x2 = min(99.0, ml_draw + ml_away)

    rows: list[ComboMarket] = []

    def add(
        key: str, label: str, group: str, probability: float, corr: float = 1.0
    ) -> None:
        value = round(min(97.5, max(1.0, probability * corr)), 1)
        odds = _fair_odds(value)
        rows.append(
            ComboMarket(
                key=key,
                label=label,
                group=group,
                group_label=COMBO_GROUP_LABELS[group],
                probability=value,
                odds=odds,
                edge=round(value - 100.0 / odds, 2),
                recommended=value > 40.0,
                recommendation=_recommendation_label(value),
            )
        )

    def mix(a: float, b: float) -> float:
        return a * b / 100.0

    # Чисти директни 1X2 исходи (за филтрите 1 · Домашен, X · Реми, 2 · Гостин).
    add("1", f"1 · {home}", "outcome", ml_home)
    add("x", "X · Реми", "outcome", ml_draw)
    add("2", f"2 · {away}", "outcome", ml_away)

    add("dc-1x", f"1X · {home} или реми", "double", dc_1x)
    add("dc-12", "12 · без реми", "double", dc_12)
    add("dc-x2", f"X2 · реми или {away}", "double", dc_x2)

    add("1-o25", "1 и Над 2.5 гола", "result_goals", mix(ml_home, over25), 1.08)
    add(
        "1-u25", "1 и Под 2.5 гола", "result_goals", mix(ml_home, under25), 0.96
    )
    add("x-o25", "X и Над 2.5 гола", "result_goals", mix(ml_draw, over25), 0.82)
    add("x-u25", "X и Под 2.5 гола", "result_goals", mix(ml_draw, under25), 1.2)
    add("2-o25", "2 и Над 2.5 гола", "result_goals", mix(ml_away, over25), 1.06)
    add(
        "2-u25", "2 и Под 2.5 гола", "result_goals", mix(ml_away, under25), 0.98
    )

    add("1-gg", "1 и ГГ", "result_btts", mix(ml_home, btts), 0.94)
    add("1-ng", "1 и НГ", "result_btts", mix(ml_home, no_btts), 1.1)
    add("x-gg", "X и ГГ", "result_btts", mix(ml_draw, btts), 0.9)
    add("x-ng", "X и НГ", "result_btts", mix(ml_draw, no_btts), 1.12)
    add("2-gg", "2 и ГГ", "result_btts", mix(ml_away, btts), 0.95)
    add("2-ng", "2 и НГ", "result_btts", mix(ml_away, no_btts), 1.08)

    add("1x-o25", "1X и Над 2.5", "double_goals", mix(dc_1x, over25), 0.97)
    add("1x-u25", "1X и Под 2.5", "double_goals", mix(dc_1x, under25), 1.05)
    add("12-o25", "12 и Над 2.5", "double_goals", mix(dc_12, over25), 1.1)
    add("12-u25", "12 и Под 2.5", "double_goals", mix(dc_12, under25), 0.9)
    add("x2-o25", "X2 и Над 2.5", "double_goals", mix(dc_x2, over25), 0.96)
    add("x2-u25", "X2 и Под 2.5", "double_goals", mix(dc_x2, under25), 1.06)

    add("1x-gg", "1X и ГГ", "double_btts", mix(dc_1x, btts), 0.93)
    add("1x-ng", "1X и НГ", "double_btts", mix(dc_1x, no_btts), 1.09)
    add("12-gg", "12 и ГГ", "double_btts", mix(dc_12, btts), 1.12)
    add("12-ng", "12 и НГ", "double_btts", mix(dc_12, no_btts), 0.92)
    add("x2-gg", "X2 и ГГ", "double_btts", mix(dc_x2, btts), 0.94)
    add("x2-ng", "X2 и НГ", "double_btts", mix(dc_x2, no_btts), 1.07)

    add("gg-o25", "ГГ и Над 2.5", "btts_goals", mix(btts, over25), 1.18)
    add("gg-u25", "ГГ и Под 2.5", "btts_goals", mix(btts, under25), 0.85)
    add("ng-o25", "НГ и Над 2.5", "btts_goals", mix(no_btts, over25), 0.7)
    add("ng-u25", "НГ и Под 2.5", "btts_goals", mix(no_btts, under25), 1.22)

    add("o15", "Над 1.5 гола", "goals", over15)
    add("o25", "Над 2.5 гола", "goals", over25)
    add("o35", "Над 3.5 гола", "goals", over35)
    add("u15", "Под 1.5 гола", "goals", max(1.0, 100.0 - over15))
    add("u25", "Под 2.5 гола", "goals", under25)
    add("u35", "Под 3.5 гола", "goals", under35)
    add("gg", "ГГ · двата тима", "goals", btts)
    add("ng", "НГ · без ГГ", "goals", no_btts)
    add("gg-1x", "ГГ или 1X", "goals", min(97.0, btts + dc_1x * 0.28))
    add("o15-12", "Над 1.5 и 12", "goals", mix(over15, dc_12), 1.06)

    return sorted(rows, key=lambda r: -r["probability"])


def _kickoff_label(raw: str) -> str:
    """Часот на почеток претворен во локално (Скопје) време."""
    parsed = _parse_moment(raw)
    if parsed is None:
        if isinstance(raw, str) and len(raw) >= 16:
            return raw[11:16]
        return "--:--"
    return _to_local(parsed).strftime("%H:%M")


def _as_date(value: str) -> date:
    """Избраниот датум од интерфејсот; локалниот ден кога нема вредност."""
    if isinstance(value, str) and len(value) >= 10:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return local_today()
    return local_today()


def _day_label(raw: str, start: date) -> str:
    """Ознака на денот во однос на избраниот датум (не на системскиот ден)."""
    local = _local_date(raw)
    if local is None:
        return ""
    today = local_today()
    if local == start:
        return "Денес" if start == today else start.strftime("%d.%m")
    if local == start + timedelta(days=1):
        following = start + timedelta(days=1)
        return "Утре" if start == today else following.strftime("%d.%m")
    return local.strftime("%d.%m")


def _sort_key(raw: str) -> str:
    """ISO временска ознака за сортирање по најблиско почетно време."""
    if not isinstance(raw, str) or not raw:
        return "9999-12-31T23:59:59+00:00"
    try:
        cleaned = raw.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(cleaned)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        return raw


def _date_window(start: date) -> tuple[str, str]:
    """UTC прозорец што го покрива избраниот ден и следниот ден.

    Локалниот ден во Скопје (UTC+2/+3) започнува претходниот UTC ден, па
    прозорецот е [избран-1, избран+1]; редовите потоа се филтрираат по
    локален датум, така што доцните ноќни часови не прикажуваат погрешен
    ден, а настаните од следниот ден се вчитуваат целосно.
    """
    return (
        (start - timedelta(days=1)).isoformat(),
        (start + timedelta(days=1)).isoformat(),
    )


def _ht_from_event(event: dict) -> tuple[int, int, bool]:
    """Резултат од првото полувреме, ако API-то го обезбедува."""
    pairs = (
        ("home_score_ht", "away_score_ht"),
        ("ht_home_score", "ht_away_score"),
        ("home_ht_score", "away_ht_score"),
        ("home_score_half_time", "away_score_half_time"),
        ("home_score_period_1", "away_score_period_1"),
        ("home_score_p1", "away_score_p1"),
    )
    for home_key, away_key in pairs:
        home = _num(event.get(home_key))
        away = _num(event.get(away_key))
        if home is not None and away is not None:
            return int(round(home)), int(round(away)), True
    for key in ("periods", "scores", "period_scores", "score_periods"):
        block = event.get(key)
        if not isinstance(block, dict):
            continue
        for inner in (
            "ht",
            "halftime",
            "half_time",
            "first_half",
            "period_1",
            "1",
        ):
            sub = block.get(inner)
            if not isinstance(sub, dict):
                continue
            home = _num(sub.get("home"))
            if home is None:
                home = _num(sub.get("home_score"))
            away = _num(sub.get("away"))
            if away is None:
                away = _num(sub.get("away_score"))
            if home is not None and away is not None:
                return int(round(home)), int(round(away)), True
    return 0, 0, False


STATUS_TEXTS: dict[str, str] = {
    "live": "Во тек",
    "finished": "Завршен",
    "cancelled": "Откажан",
    "postponed": "Одложен",
    "upcoming": "Претстоен",
}


def _status_text(event: dict, status: str) -> str:
    """Читлив текст за статусот: минута кога е во тек, инаку ознака."""
    minute = event.get("current_minute")
    raw = ""
    for key in ("status_text", "status_description", "status_more", "status"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            raw = value.strip()
            break
    if status == "live":
        if minute:
            return f"{minute}'"
        return raw or STATUS_TEXTS["live"]
    return STATUS_TEXTS.get(status, raw)


def _score_label(event: dict, status: str) -> str:
    home = event.get("home_score")
    away = event.get("away_score")
    if status == "upcoming" or home is None or away is None:
        return "vs"
    return f"{home} - {away}"


def _team_id_from(event: dict, side: str) -> int:
    """ID на тимот од листата на настани (0 кога не е достапен)."""
    direct = _num(event.get(f"{side}_team_id"))
    if direct is not None and direct > 0:
        return int(direct)
    nested = event.get(f"{side}_team_obj")
    if isinstance(nested, dict):
        value = _num(nested.get("id"))
        if value is not None and value > 0:
            return int(value)
    return 0


def _team_logo_url(team_id: int) -> str:
    """Јавен URL за грб на тим; празно кога нема ID (без никакви токени)."""
    if team_id <= 0:
        return ""
    return f"{TEAM_IMAGE_BASE}/{team_id}/?bg=transparent"


def _league_label(event: dict, league_names: dict[int, str]) -> str:
    """Име на лига: прво од предвидувањата, потоа од настанот, па фолбек."""
    raw_id = _num(event.get("league_id"))
    league_id = int(raw_id) if raw_id is not None else None
    if league_id is not None:
        from_prediction = league_names.get(league_id)
        if isinstance(from_prediction, str) and from_prediction.strip():
            return from_prediction.strip()
    own = event.get("league_name")
    if isinstance(own, str) and own.strip():
        return own.strip()
    league = event.get("league")
    if isinstance(league, dict):
        name = league.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    if league_id is not None:
        return f"Лига #{league_id}"
    return NA_LABEL


def _venue_label(event: dict) -> str:
    if event.get("is_neutral_ground"):
        return "Неутрален терен"
    venue_id = event.get("venue_id")
    if venue_id:
        return f"Стадион #{venue_id}"
    return NA_LABEL


def _team_key(value: object) -> str:
    """Нормализирано име на тим за сигурно совпаѓање во H2H редовите."""
    if not isinstance(value, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    text = "".join(
        ch for ch in decomposed if not unicodedata.combining(ch)
    ).lower()
    cleaned = "".join(ch if ch.isalnum() else " " for ch in text)
    return " ".join(cleaned.split())


def _same_team(left: str, right: str) -> bool:
    a, b = _team_key(left), _team_key(right)
    if not a or not b:
        return False
    if a == b:
        return True
    return a in b or b in a


def _h2h_score(row: dict) -> tuple[int, int] | None:
    """Резултат од H2H ред: од `score` низа или од одделни полиња."""
    raw = row.get("score") or row.get("score_str") or row.get("result")
    if isinstance(raw, str):
        cleaned = raw.replace(" ", "").replace(":", "-")
        parts = cleaned.split("-")
        if len(parts) == 2:
            try:
                return int(parts[0]), int(parts[1])
            except ValueError:
                pass
    home = _num(row.get("home_score"))
    away = _num(row.get("away_score"))
    if home is not None and away is not None:
        return int(round(home)), int(round(away))
    return None


def _h2h_moment(row: dict) -> datetime | None:
    raw = row.get("date") or row.get("event_date") or row.get("kickoff")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _form_from_h2h(h2h: dict, home: str, away: str) -> tuple[str, str]:
    """Компактна W/D/L форма (до 5) за двата тима од реални H2H резултати.

    Робусно е на перспективата дома/гости, на текстуални резултати и на
    редови со идни датуми што API-то понекогаш враќа со лажен резултат.
    Ако нема употребливи редови, се враќаат празни низи (недостапно).
    """
    matches = h2h.get("recent_matches") if isinstance(h2h, dict) else None
    if not isinstance(matches, list):
        return "", ""

    now = datetime.now(timezone.utc)
    usable: list[tuple[datetime | None, str, str, int, int]] = []
    for row in matches:
        if not isinstance(row, dict):
            continue
        score = _h2h_score(row)
        if score is None:
            continue
        h_name = str(row.get("home") or row.get("home_team") or "")
        a_name = str(row.get("away") or row.get("away_team") or "")
        if not h_name or not a_name:
            continue
        moment = _h2h_moment(row)
        # Идните натпревари не се одиграни, па не се форма.
        if moment is not None and moment > now:
            continue
        usable.append((moment, h_name, a_name, score[0], score[1]))

    if not usable:
        return "", ""

    usable.sort(
        key=lambda item: item[0] or datetime(1970, 1, 1, tzinfo=timezone.utc),
        reverse=True,
    )

    def build(team: str) -> str:
        letters: list[str] = []
        for _moment, h_name, a_name, hs, as_ in usable:
            if _same_team(team, h_name):
                ours, theirs = hs, as_
            elif _same_team(team, a_name):
                ours, theirs = as_, hs
            else:
                continue
            if ours > theirs:
                letters.append("W")
            elif ours == theirs:
                letters.append("D")
            else:
                letters.append("L")
            if len(letters) == 5:
                break
        return "".join(letters)

    return build(home), build(away)


def _xg_from_stats(stats: dict) -> tuple[float | None, float | None]:
    block = stats.get("stats") if isinstance(stats, dict) else None
    if not isinstance(block, dict):
        return None, None
    home = block.get("home")
    away = block.get("away")

    def read(side: object) -> float | None:
        if not isinstance(side, dict):
            return None
        for key in ("xg", "expected_goals", "xG", "xg_total"):
            value = _num(side.get(key))
            if value is not None:
                return round(value, 2)
        return None

    return read(home), read(away)


def _empty_match(
    event: dict, league: str, status: str, start: date
) -> BSDMatch:
    home = str(event.get("home_team") or NA_LABEL)
    away = str(event.get("away_team") or NA_LABEL)
    minute = event.get("current_minute")
    home_team_id = _team_id_from(event, "home")
    away_team_id = _team_id_from(event, "away")
    ht_home, ht_away, has_ht = _ht_from_event(event)
    return BSDMatch(
        id=f"event-{event.get('id')}",
        event_id=int(event.get("id") or 0),
        has_xg=bool(event.get("has_xg")),
        kickoff=_kickoff_label(event.get("event_date") or ""),
        sort_key=_sort_key(event.get("event_date") or ""),
        date_key=(_local_date(event.get("event_date") or "") or start).strftime(
            "%Y%m%d"
        ),
        day_label=_day_label(event.get("event_date") or "", start),
        source="",
        source_label="",
        derived_basis="",
        fotmob_id=0,
        stat_facts=[],
        league=league,
        home=home,
        away=away,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        home_logo_url=_team_logo_url(home_team_id),
        away_logo_url=_team_logo_url(away_team_id),
        status=status,
        status_text=_status_text(event, status),
        minute=f"{minute}'" if minute else "",
        has_ht=has_ht,
        ht_home=ht_home,
        ht_away=ht_away,
        ht_label=f"HT: {ht_home}-{ht_away}" if has_ht else "",
        score=_score_label(event, status),
        venue=_venue_label(event),
        form_home="",
        form_away="",
        has_prediction=False,
        prediction_note="Нема достапно предвидување за овој натпревар од API-то",
        model_name=NA_LABEL,
        ml_home=0.0,
        ml_draw=0.0,
        ml_away=0.0,
        ml_pick=NA_LABEL,
        ml_confidence=0.0,
        pick_side="",
        xg_home=0.0,
        xg_away=0.0,
        poi_home=0.0,
        poi_draw=0.0,
        poi_away=0.0,
        poi_btts=0.0,
        poi_over25=0.0,
        poi_under25=0.0,
        poi_over35=0.0,
        poi_under35=0.0,
        poi_over15=0.0,
        poi_under15=0.0,
        extra_label=NA_LABEL,
        extra_pick=NA_LABEL,
        extra_probability=0.0,
        top_score=NA_LABEL,
        top_score_prob=0.0,
        expected_goals=0.0,
        top_models=[],
        combos=[],
        top_combos=[],
        combo_count=0,
        combo_recommended=0,
        best_combo_label=NA_LABEL,
        best_combo_probability=0.0,
        meta_market=NA_LABEL,
        meta_pick=NA_LABEL,
        meta_confidence=0.0,
        meta_odds=0.0,
        meta_edge=0.0,
        meta_agreement=0.0,
        meta_value=NA_LABEL,
    )


def _apply_prediction(match: BSDMatch, prediction: dict) -> BSDMatch:
    markets = prediction.get("markets")
    if not isinstance(markets, dict):
        return match

    result = markets.get("match_result")
    result = result if isinstance(result, dict) else {}
    ml_home = _pick_pct(
        result,
        ("prob_home", "home", "home_win", "1", "team1", "win_home"),
    )
    ml_draw = _pick_pct(result, ("prob_draw", "draw", "x", "X", "tie"))
    ml_away = _pick_pct(
        result,
        ("prob_away", "away", "away_win", "2", "team2", "win_away"),
    )
    if ml_home is None or ml_draw is None or ml_away is None:
        return match

    total = max(1.0, ml_home + ml_draw + ml_away)
    ml_home = round(ml_home / total * 100, 1)
    ml_draw = round(ml_draw / total * 100, 1)
    ml_away = round(100.0 - ml_home - ml_draw, 1)

    btts_block = markets.get("btts")
    btts = _pick_pct(
        btts_block if isinstance(btts_block, dict) else {},
        (
            "prob_yes",
            "prob_btts",
            "yes",
            "btts_yes",
            "both_teams_to_score",
            "probability",
        ),
    )
    over_block = markets.get("over_under")
    over_block = over_block if isinstance(over_block, dict) else {}
    over25 = _over25(over_block)
    over15 = _over_line(
        over_block,
        ("prob_over_15", "prob_over_1_5", "over_1_5", "over15", "over_1.5"),
    )
    over35 = _over_line(
        over_block,
        ("prob_over_35", "prob_over_3_5", "over_3_5", "over35", "over_3.5"),
    )

    xg_block = markets.get("expected_goals")
    xg_home = None
    xg_away = None
    if isinstance(xg_block, dict):
        xg_home = _num(xg_block.get("home"))
        xg_away = _num(xg_block.get("away"))
    expected_total = (
        round((xg_home or 0.0) + (xg_away or 0.0), 2)
        if (xg_home is not None or xg_away is not None)
        else 0.0
    )

    score_block = markets.get("score")
    top_score, top_score_prob = _top_score(
        score_block if isinstance(score_block, dict) else {}
    )

    lambdas = _lambdas(xg_home, xg_away, over25, ml_home, ml_draw, ml_away)
    if (top_score == NA_LABEL or top_score_prob <= 0.0) and lambdas is not None:
        derived_score, derived_prob = _top_score_from_lambdas(*lambdas)
        if derived_prob > 0.0:
            top_score, top_score_prob = derived_score, derived_prob
    elif (
        top_score != NA_LABEL and top_score_prob <= 0.0 and lambdas is not None
    ):
        _label, derived_prob = _top_score_from_lambdas(*lambdas)
        top_score_prob = derived_prob
    over15 = _derive_over15(over15, over25, lambdas)
    if expected_total <= 0.0 and lambdas is not None:
        expected_total = round(lambdas[0] + lambdas[1], 2)

    outcomes = [
        (ml_home, f"1 · {match['home']}", "home"),
        (ml_draw, "X · Реми", "draw"),
        (ml_away, f"2 · {match['away']}", "away"),
    ]
    best = max(outcomes, key=lambda row: row[0])

    model = prediction.get("model")
    model_confidence: float | None = None
    if isinstance(model, dict):
        model_name = str(
            model.get("name")
            or model.get("version")
            or model.get("id")
            or "BSD ML"
        )
        model_confidence = _pct(model.get("confidence"))
    else:
        model_name = str(model or "BSD ML")

    top_models: list[ModelPick] = []
    for label, probability in (
        ("Match Result", best[0]),
        ("ГГ (BTTS)", btts),
        ("Над 2.5 гола", over25),
    ):
        if probability is None:
            continue
        top_models.append(
            ModelPick(
                name=f"{model_name} · {label}",
                family="API модел",
                pick=best[1] if label == "Match Result" else label,
                probability=round(probability, 1),
                accuracy=0.0,
            )
        )

    recommendations = prediction.get("recommendations")
    rec_market = ""
    rec_pick = ""
    rec_confidence = None
    rec_odds = None
    rec_flags: list[str] = []
    rows = (
        recommendations
        if isinstance(recommendations, list)
        else ([recommendations] if isinstance(recommendations, dict) else [])
    )
    labels_by_side = {
        "home": f"1 · {match['home']}",
        "draw": "X · Реми",
        "away": f"2 · {match['away']}",
    }
    for row in rows:
        if not isinstance(row, dict):
            continue
        for flag, flag_label in REC_FLAG_LABELS.items():
            if row.get(flag) is True:
                rec_flags.append(flag_label)
        favorite = row.get("favorite")
        if isinstance(favorite, str) and favorite.strip():
            side = FAVORITE_SIDES.get(favorite.strip().upper(), "")
            if side:
                rec_market = "1X2 · фаворит"
                rec_pick = labels_by_side[side]
                rec_confidence = _pct(row.get("favorite_prob"))
        if not rec_pick:
            rec_market = str(row.get("market") or row.get("type") or "")
            rec_pick = str(
                row.get("selection")
                or row.get("pick")
                or row.get("bet")
                or row.get("label")
                or ""
            )
            rec_confidence = _pct(
                row.get("confidence") or row.get("probability")
            )
        rec_odds = _num(row.get("odds") or row.get("fair_odds"))
        break

    if rec_flags:
        rec_market = f"{rec_market or '1X2'} · {', '.join(rec_flags)}"

    meta_market = rec_market or "1X2"
    meta_pick = rec_pick or best[1]
    meta_confidence = (
        rec_confidence
        if rec_confidence is not None
        else (model_confidence if model_confidence is not None else best[0])
    )
    meta_odds = (
        round(rec_odds, 2)
        if rec_odds and rec_odds > 1.0
        else _fair_odds(meta_confidence)
    )
    meta_edge = round(meta_confidence - 100.0 / meta_odds, 2)
    agreement = round(
        len([m for m in top_models if m["probability"] >= 50.0])
        / max(1, len(top_models))
        * 100,
        0,
    )

    combos: list[ComboMarket] = []
    if btts is not None and over25 is not None:
        combos = _combo_markets(
            match["home"],
            match["away"],
            ml_home,
            ml_draw,
            ml_away,
            btts,
            over25,
            over15,
            over35,
        )
    recommended = [c for c in combos if c["recommended"]]
    extra_label, extra_pick, extra_prob = _extra_recommendation(
        btts, over25, over35
    )

    match.update(
        has_prediction=True,
        prediction_note="",
        source="bzz",
        source_label="BZZ API",
        model_name=model_name,
        ml_home=ml_home,
        ml_draw=ml_draw,
        ml_away=ml_away,
        ml_pick=best[1],
        ml_confidence=round(best[0], 1),
        pick_side=best[2],
        xg_home=round(xg_home, 2) if xg_home is not None else 0.0,
        xg_away=round(xg_away, 2) if xg_away is not None else 0.0,
        poi_home=ml_home,
        poi_draw=ml_draw,
        poi_away=ml_away,
        poi_btts=round(btts, 1) if btts is not None else 0.0,
        poi_over25=round(over25, 1) if over25 is not None else 0.0,
        poi_under25=round(100.0 - over25, 1) if over25 is not None else 0.0,
        poi_over35=round(over35, 1) if over35 is not None else 0.0,
        poi_under35=round(100.0 - over35, 1) if over35 is not None else 0.0,
        poi_over15=round(over15, 1) if over15 is not None else 0.0,
        poi_under15=round(100.0 - over15, 1) if over15 is not None else 0.0,
        extra_label=extra_label,
        extra_pick=extra_pick,
        extra_probability=extra_prob,
        top_score=top_score,
        top_score_prob=top_score_prob,
        expected_goals=expected_total,
        top_models=top_models,
        combos=combos,
        top_combos=combos[:6],
        combo_count=len(combos),
        combo_recommended=len(recommended),
        best_combo_label=combos[0]["label"] if combos else NA_LABEL,
        best_combo_probability=combos[0]["probability"] if combos else 0.0,
        meta_market=meta_market,
        meta_pick=meta_pick,
        meta_confidence=round(meta_confidence, 1),
        meta_odds=meta_odds,
        meta_edge=meta_edge,
        meta_agreement=float(agreement),
        meta_value=_value_label(meta_edge),
    )
    return match


def _fetch_paginated(
    path: str,
    base_params: dict[str, str | int],
    page_limit: int,
    max_pages: int,
) -> tuple[list[dict], int]:
    """Собира до `max_pages` страници без status филтри (за да избегне 429)."""
    rows: list[dict] = []
    status = 0
    for page in range(max_pages):
        params: dict[str, str | int] = dict(base_params)
        params["limit"] = page_limit
        params["offset"] = page * page_limit
        chunk, status = api_client.get_list_soft(path, params=params)
        if not chunk:
            break
        rows.extend(chunk)
        if len(chunk) < page_limit:
            break
    return rows, status


def _is_selected_day(event: dict, start: date) -> bool:
    """Дали настанот се игра во избраниот локален ден."""
    local = _local_date(event.get("event_date") or "")
    return local is not None and local == start


def _in_window(event: dict, start: date) -> bool:
    """Дали настанот е во прозорецот „избран ден и следниот ден“."""
    local = _local_date(event.get("event_date") or "")
    if local is None:
        return False
    return start <= local <= start + timedelta(days=1)


def _fetch_status_segment(
    status_filter: str, start: date
) -> tuple[list[dict], int]:
    """Сите страници од /events/ со status филтер за избраниот прозорец."""
    date_from, date_to = _date_window(start)
    return _fetch_paginated(
        "/events/",
        {
            "date_from": date_from,
            "date_to": date_to,
            "status": status_filter,
        },
        EVENT_PAGE_LIMIT,
        MAX_EVENT_PAGES,
    )


def _fetch_live_segment() -> tuple[list[dict], int]:
    """Тековните натпревари од посветениот /events/live/ ресурс (пагинирано)."""
    return _fetch_paginated(
        "/events/live/",
        {},
        LIVE_PAGE_LIMIT,
        MAX_LIVE_PAGES,
    )


def _fetch_events(start: date) -> tuple[list[dict], int, list[str]]:
    """Ги вчитува настаните од избраниот ден и следниот ден преку три барања.

    1) /events/?status=upcoming&date_from=…&date_to=… (претстојни денес и утре)
    2) /events/?status=finished&date_from=…&date_to=… (завршени во прозорецот)
    3) /events/live/ (натпревари во тек — само за денешниот ден)

    Сите редови се спојуваат и де-дупликираат по id, а статусите се
    нормализираат од самиот ред бидејќи API-то враќа notstarted/postponed/
    finished и во филтрираните одговори. Не се вчитува ништо подалеку од
    утре. Враќа (редови, последен статус, прескокнати сегменти).
    """
    rows: list[dict] = []
    seen_ids: set[int] = set()
    skipped: list[str] = []
    last_status = 0

    segments: list[tuple[str, bool]] = [
        ("upcoming", False),
        ("finished", False),
        ("live", True),
    ]

    for key, is_live in segments:
        if is_live:
            segment_rows, status = _fetch_live_segment()
        else:
            segment_rows, status = _fetch_status_segment(key, start)
        last_status = status or last_status
        if status == api_client.RATE_LIMIT_STATUS:
            skipped.append(SEGMENT_LABELS[key])
            logging.info(f"Сегментот {key} за денес не е вчитан (HTTP 429).")
            continue
        for event in segment_rows:
            event_id = event.get("id")
            if event_id is None:
                continue
            if is_live:
                # Live ресурсот не носи датумски филтер — задржи го само
                # избраниот ден.
                if not _is_selected_day(event, start):
                    continue
                if _normalize_status(event.get("status") or "") != "finished":
                    event = dict(event)
                    event["status"] = "inprogress"
            elif not _in_window(event, start):
                continue
            numeric_id = int(event_id)
            if numeric_id in seen_ids:
                continue
            seen_ids.add(numeric_id)
            rows.append(event)

    return rows, last_status, skipped


def _fetch_event_prediction(event_id: int) -> tuple[dict, int]:
    """Документираниот ресурс за предвидување по настан (тивко барање)."""
    return api_client.get_optional_dict(f"/events/{event_id}/prediction/")


def _fetch_predictions(
    start: date,
) -> tuple[dict[int, dict], dict[int, str], int]:
    date_from, date_to = _date_window(start)
    rows, status = _fetch_paginated(
        "/predictions/",
        {"date_from": date_from, "date_to": date_to},
        PREDICTION_PAGE_LIMIT,
        MAX_PREDICTION_PAGES,
    )
    by_event: dict[int, dict] = {}
    league_names: dict[int, str] = {}
    for row in rows:
        event = row.get("event")
        event_id = None
        if isinstance(event, dict):
            event_id = event.get("id")
            league_id = event.get("league_id")
            name = event.get("league_name")
            if league_id is not None and isinstance(name, str) and name:
                league_names[int(league_id)] = name
        elif isinstance(event, int):
            event_id = event
        if event_id is None:
            event_id = row.get("event_id")
        if event_id is None:
            continue
        by_event[int(event_id)] = row
    return by_event, league_names, status


class ApiSnapshot(TypedDict):
    matches: list[BSDMatch]
    generated_at: str
    notice: str
    error: str
    rate_limited: bool


def collect_matches(start: date | None = None) -> ApiSnapshot:
    """Ги собира вистинските натпревари, предвидувања и обогатувања.

    Никогаш не крева исклучок за очекувани 429/404 одговори: натпреварите
    остануваат реални, а полињата од предвидувања остануваат недостапни.
    """
    start = start or local_today()
    if not api_client.has_api_key():
        return ApiSnapshot(
            matches=[],
            generated_at=local_clock(),
            notice=MISSING_KEY_NOTE,
            error=MISSING_KEY_ERROR,
            rate_limited=False,
        )

    events, events_status, skipped_segments = _fetch_events(start)
    predictions, league_names, predictions_status = _fetch_predictions(start)
    rate_limited = bool(skipped_segments) or (
        api_client.RATE_LIMIT_STATUS
        in (
            events_status,
            predictions_status,
        )
    )

    matches: list[BSDMatch] = []
    for event in events:
        if event.get("id") is None:
            continue
        status = _normalize_status(event.get("status") or "")
        league = _league_label(event, league_names)
        match = _empty_match(event, league, status, start)
        if predictions_status == api_client.MISSING_KEY_STATUS:
            match["prediction_note"] = MISSING_KEY_NOTE
        elif predictions_status == api_client.RATE_LIMIT_STATUS:
            match["prediction_note"] = PREDICTIONS_RATE_LIMIT_NOTE
        elif not predictions:
            match["prediction_note"] = PREDICTIONS_UNAVAILABLE_NOTE
        prediction = predictions.get(match["event_id"])
        if prediction is not None:
            match = _apply_prediction(match, prediction)
        matches.append(match)

    # Најблиско почетно време прво (денес пред следните денови).
    matches.sort(key=lambda m: m["sort_key"])

    # Резерва #1: документираниот ресурс за предвидување по настан
    # (/events/{id}/prediction/). Се користи САМО за реални BZZ настани од
    # прозорецот кои листата /predictions/ не ги вратила, и се применуваат
    # САМО вистински вратени веројатности од тој одговор.
    detail_applied = 0
    detail_skipped = 0
    if not rate_limited:
        detail_candidates = [
            m
            for m in matches
            if not m["has_prediction"]
            and m["status"] in ("upcoming", "live", "finished")
        ]
        targets = detail_candidates[:EVENT_PREDICTION_LIMIT]
        detail_skipped = len(detail_candidates) - len(targets)
        for match in detail_candidates[len(targets) :]:
            match["prediction_note"] = DETAIL_LIMIT_NOTE
        for match in targets:
            payload, status = _fetch_event_prediction(match["event_id"])
            if status == api_client.RATE_LIMIT_STATUS:
                rate_limited = True
                break
            if status == api_client.MISSING_KEY_STATUS:
                break
            if not payload:
                continue
            _apply_prediction(match, payload)
            if match["has_prediction"]:
                # Официјално, но добиено од ресурсот по настан, не од листата.
                match["source"] = "bzz_event"
                match["source_label"] = "BZZ по настан"
                detail_applied += 1

    # Резерва #2: изведено предвидување САМО од реални ресурси по настан
    # (/odds/, /h2h/, /lineups/, /stats/ и опционално /summary/, /money/).
    # Ништо не се измислува: ако нема квоти ниту H2H, натпреварот останува
    # без предвидување и добива јасна забелешка.
    derived_applied = 0
    derived_unavailable = 0
    derived_skipped = 0
    if not rate_limited:
        derived_candidates = [
            m
            for m in matches
            if not m["has_prediction"]
            and m["status"] in ("upcoming", "live", "finished")
        ]
        derived_targets = derived_candidates[:DERIVED_PREDICTION_LIMIT]
        derived_skipped = len(derived_candidates) - len(derived_targets)
        for match in derived_candidates[len(derived_targets) :]:
            match["prediction_note"] = DETAIL_LIMIT_NOTE
        for index, match in enumerate(derived_targets):
            sources = bzz_derived.fetch_sources(
                match["event_id"],
                allow_optional=index < DERIVED_OPTIONAL_LIMIT,
            )
            if sources["rate_limited"]:
                rate_limited = True
                break
            if sources["missing_key"]:
                break
            applied = False
            try:
                applied = bzz_derived.apply_derived(match, sources)
            except Exception as error:
                logging.exception(
                    f"Error: изведеното BZZ предвидување не успеа: {error}"
                )
                applied = False
            if applied:
                derived_applied += 1
            else:
                derived_unavailable += 1
                match["prediction_note"] = DERIVED_UNAVAILABLE_NOTE

    # Многу конзервативно обогатување: само неколку натпревари со
    # предвидување или со потврдени xG податоци, со прекин по прв 429.
    priority = (
        []
        if rate_limited
        else [
            m
            for m in matches
            if m["status"] in ("live", "upcoming")
            and (m["has_prediction"] or m["has_xg"])
        ][:MAX_ENRICHED]
    )

    enriched = 0
    stats_done: set[int] = set()
    for match in priority:
        event_id = match["event_id"]
        stats, status = api_client.get_optional_dict(
            f"/events/{event_id}/stats/"
        )
        stats_done.add(event_id)
        if status == api_client.RATE_LIMIT_STATUS:
            rate_limited = True
            break
        if stats:
            xg_home, xg_away = _xg_from_stats(stats)
            if xg_home is not None:
                match["xg_home"] = xg_home
            if xg_away is not None:
                match["xg_away"] = xg_away
            if xg_home is not None and xg_away is not None:
                match["expected_goals"] = round(xg_home + xg_away, 2)
                enriched += 1

    # Форма од /h2h/ за мал, безопасен број натпревари од денес — и кога
    # предвидувањата не се достапни. Не се создава предвидување од ова.
    if not rate_limited:
        form_targets = [
            m
            for m in matches
            if m["status"] in ("live", "upcoming", "finished")
            and not m["form_home"]
            and not m["form_away"]
        ][:MAX_FORM_ENRICHED]
        for match in form_targets:
            h2h, status = api_client.get_optional_dict(
                f"/events/{match['event_id']}/h2h/"
            )
            if status == api_client.RATE_LIMIT_STATUS:
                rate_limited = True
                break
            if not h2h:
                continue
            form_home, form_away = _form_from_h2h(
                h2h, match["home"], match["away"]
            )
            if form_home or form_away:
                match["form_home"] = form_home
                match["form_away"] = form_away
                enriched += 1

    has_any_prediction = any(m["has_prediction"] for m in matches)
    notice = ""
    if skipped_segments:
        notice = EVENTS_PARTIAL_SEGMENTS_NOTE.format(
            segments=", ".join(skipped_segments)
        )
    elif predictions_status == api_client.RATE_LIMIT_STATUS:
        notice = PREDICTIONS_RATE_LIMIT_NOTE
    elif matches and not has_any_prediction:
        # Натпреварите остануваат видливи и без ниту едно предвидување.
        notice = PREDICTIONS_UNAVAILABLE_NOTE
    elif rate_limited:
        notice = RATE_LIMIT_NOTE
    elif priority and enriched == 0:
        notice = ENRICH_UNAVAILABLE_NOTE

    if detail_applied:
        extra = EVENT_PREDICTION_NOTE.format(count=detail_applied)
        notice = f"{notice} {extra}".strip()

    if derived_applied:
        extra = DERIVED_APPLIED_NOTE.format(count=derived_applied)
        notice = f"{notice} {extra}".strip()
    elif derived_unavailable and not notice:
        notice = DERIVED_UNAVAILABLE_NOTE

    skipped_total = max(detail_skipped, derived_skipped)
    if skipped_total:
        extra = DETAIL_LIMIT_NOTICE.format(count=skipped_total)
        notice = f"{notice} {extra} {ENRICH_LIMIT_NOTICE}".strip()

    error = ""
    if not matches:
        error = (
            EVENTS_RATE_LIMIT_ERROR
            if skipped_segments or events_status == api_client.RATE_LIMIT_STATUS
            else "API-то не врати натпревари за избраниот датум."
        )

    return ApiSnapshot(
        matches=matches,
        generated_at=local_clock(),
        notice=notice,
        error=error,
        rate_limited=rate_limited,
    )


class BSDState(rx.State):
    """Состојба со вистински податоци од API-то и подтабови."""

    selected_date: str = ""
    sub_tab: str = "today"
    matches: list[BSDMatch] = []
    fotmob_shadows: list[ShadowPick] = []
    expanded_id: str = ""
    compare_notice: str = ""
    generated_at: str = "--:--:--"
    error: str = ""
    stats_notice: str = ""
    is_loading: bool = False
    has_loaded: bool = False
    rate_limited: bool = False

    @rx.var
    def selected_date_value(self) -> str:
        """Избраниот датум (ISO); стандардно локалниот ден во Македонија."""
        return self.selected_date or local_today().isoformat()

    @rx.var
    def is_today_selected(self) -> bool:
        return _as_date(self.selected_date_value) == local_today()

    @rx.var
    def today_label(self) -> str:
        """Избраниот датум за кој се вчитани натпреварите."""
        return _as_date(self.selected_date_value).strftime("%d.%m.%Y")

    @rx.var
    def tomorrow_label(self) -> str:
        """Датумот по избраниот (избран + 1 ден)."""
        return (
            _as_date(self.selected_date_value) + timedelta(days=1)
        ).strftime("%d.%m.%Y")

    @rx.var
    def window_label(self) -> str:
        """Кратка ознака за прозорецот „избран ден и следниот ден“."""
        start = _as_date(self.selected_date_value)
        return (
            f"{start.strftime('%d.%m')} — "
            f"{(start + timedelta(days=1)).strftime('%d.%m')}"
        )

    @rx.var
    def all_window_matches(self) -> list[BSDMatch]:
        """Сите реални настани од избраниот прозорец, по почеток."""
        return sorted(self.matches, key=lambda m: m["sort_key"])

    @rx.var
    def displayed_matches(self) -> list[BSDMatch]:
        """Сите реални настани од прозорецот — ништо не се крие.

        Настаните со предвидување добиваат целосни секции, а оние без реално
        изведено предвидување се прикажуваат со својата забелешка за
        недостапност.
        """
        return self.all_window_matches

    @rx.var
    def window_count(self) -> int:
        return len(self.matches)

    @rx.var
    def today_matches(self) -> list[BSDMatch]:
        """Претстојни (незапочнати) настани од избраниот ден.

        Настаните во тек, завршените, откажаните, одложените и оние од
        следниот ден се исклучени — тие имаат свои подтабови. Настаните без
        реално предвидување остануваат видливи со ознака за недостапност.
        """
        key = _as_date(self.selected_date_value).strftime("%Y%m%d")
        return [
            m
            for m in self.displayed_matches
            if m["status"] == "upcoming" and m["date_key"] == key
        ]

    @rx.var
    def tomorrow_matches(self) -> list[BSDMatch]:
        """Претстојни настани од денот по избраниот (сите реални настани)."""
        key = (_as_date(self.selected_date_value) + timedelta(days=1)).strftime(
            "%Y%m%d"
        )
        return [
            m
            for m in self.displayed_matches
            if m["status"] == "upcoming" and m["date_key"] == key
        ]

    @rx.var
    def today_count(self) -> int:
        return len(self.today_matches)

    @rx.var
    def upcoming_count(self) -> int:
        return len(self.today_matches)

    @rx.var
    def tomorrow_count(self) -> int:
        return len(self.tomorrow_matches)

    @rx.var
    def live_count(self) -> int:
        return len([m for m in self.displayed_matches if m["status"] == "live"])

    @rx.var
    def finished_count(self) -> int:
        return len(
            [m for m in self.displayed_matches if m["status"] == "finished"]
        )

    @rx.var
    def no_prediction_count(self) -> int:
        """Реални настани без ниту едно предвидување (сепак се прикажуваат)."""
        return len([m for m in self.matches if not m["has_prediction"]])

    @rx.var
    def excluded_count(self) -> int:
        """Откажани/одложени настани — не се прикажуваат како претстојни."""
        return len(
            [
                m
                for m in self.all_window_matches
                if m["status"] in ("cancelled", "postponed")
            ]
        )

    @rx.var
    def all_count(self) -> int:
        """Сите реално вчитани настани од прозорецот (вклучувајќи одложени)."""
        return len(self.all_window_matches)

    @rx.var
    def prediction_count(self) -> int:
        return len([m for m in self.matches if m["has_prediction"]])

    @rx.var
    def missing_prediction_count(self) -> int:
        return len([m for m in self.matches if not m["has_prediction"]])

    @rx.var
    def bzz_prediction_count(self) -> int:
        """Официјални BZZ предвидувања од листата /predictions/."""
        return len(
            [
                m
                for m in self.matches
                if m["has_prediction"] and m["source"] == "bzz"
            ]
        )

    @rx.var
    def event_prediction_count(self) -> int:
        """Официјални предвидувања од /events/{id}/prediction/."""
        return len(
            [
                m
                for m in self.matches
                if m["has_prediction"] and m["source"] == "bzz_event"
            ]
        )

    @rx.var
    def derived_odds_count(self) -> int:
        return len(
            [m for m in self.matches if "odds" in (m["derived_basis"] or "")]
        )

    @rx.var
    def derived_summary_count(self) -> int:
        return len(
            [m for m in self.matches if "summary" in (m["derived_basis"] or "")]
        )

    @rx.var
    def derived_h2h_count(self) -> int:
        return len(
            [m for m in self.matches if "h2h" in (m["derived_basis"] or "")]
        )

    @rx.var
    def derived_lineups_count(self) -> int:
        return len(
            [m for m in self.matches if "lineups" in (m["derived_basis"] or "")]
        )

    @rx.var
    def source_breakdown_label(self) -> str:
        official = self.bzz_prediction_count + self.event_prediction_count
        return (
            f"{official} официјални BZZ · "
            f"{self.derived_prediction_count} изведени BZZ · "
            f"{self.fotmob_prediction_count} Fotmob · "
            f"{self.no_prediction_count} без предвидување · "
            f"{self.excluded_count} одложени/откажани"
        )

    @rx.var
    def derived_prediction_count(self) -> int:
        """Изведени BZZ предвидувања од реални квоти/H2H/состави."""
        return len(
            [
                m
                for m in self.matches
                if m["has_prediction"]
                and m["source"] == bzz_derived.DERIVED_SOURCE
            ]
        )

    @rx.var
    def fotmob_prediction_count(self) -> int:
        return len(
            [
                m
                for m in self.matches
                if m["has_prediction"] and m["source"] == "fotmob"
            ]
        )

    @rx.var
    def visible_matches(self) -> list[BSDMatch]:
        """„Претстојни денес“ = сите незапочнати од денешниот ден.

        Live, Завршени и Утре се одделни подтабови и никогаш не се мешаат
        со денешните претстојни натпревари.
        """
        if self.sub_tab == "live":
            return [m for m in self.displayed_matches if m["status"] == "live"]
        if self.sub_tab == "finished":
            return [
                m for m in self.displayed_matches if m["status"] == "finished"
            ]
        if self.sub_tab == "tomorrow":
            return self.tomorrow_matches
        if self.sub_tab == "all":
            return self.all_window_matches
        return self.today_matches

    @rx.var
    def visible_count(self) -> int:
        return len(self.visible_matches)

    @rx.var
    def avg_visible_confidence(self) -> float:
        rows = [m for m in self.visible_matches if m["has_prediction"]]
        if not rows:
            return 0.0
        return round(sum(m["meta_confidence"] for m in rows) / len(rows), 1)

    @rx.var
    def value_visible_count(self) -> int:
        return len(
            [
                m
                for m in self.visible_matches
                if m["has_prediction"] and m["meta_edge"] >= 3.0
            ]
        )

    @rx.var
    def empty_label(self) -> str:
        return {
            "all": "API-то не врати ниту еден настан за избраниот прозорец",
            "today": "API-то не врати претстојни натпревари за избраниот датум",
            "tomorrow": "API-то не врати претстојни натпревари за следниот ден",
            "live": "Во моментот нема натпревари во тек",
            "finished": "Нема завршени натпревари за избраниот прозорец",
        }.get(self.sub_tab, "Нема податоци")

    async def _load_from_api(self):
        self.is_loading = True
        self.error = ""
        try:
            from app.states import fotmob_fallback

            snapshot = await asyncio.to_thread(
                collect_matches, _as_date(self.selected_date_value)
            )
            self.rate_limited = snapshot["rate_limited"]
            rows = snapshot["matches"]
            fotmob_note = ""
            if rows:
                _applied, fotmob_note = await fotmob_fallback.apply_fallback(
                    rows
                )
            shadows: list[ShadowPick] = []
            compare_note = ""
            if rows:
                (
                    raw_shadows,
                    compare_note,
                ) = await fotmob_fallback.compute_shadows(rows)
                shadows = [ShadowPick(**row) for row in raw_shadows]
            if rows:
                self.fotmob_shadows = shadows
                self.compare_notice = compare_note
                self.matches = rows
                self.generated_at = snapshot["generated_at"]
                self.has_loaded = True
                self.stats_notice = " ".join(
                    part for part in (snapshot["notice"], fotmob_note) if part
                )
                self.error = ""
            elif self.matches:
                # Задржи ги веќе вчитаните реални натпревари при 429.
                self.stats_notice = (
                    EVENTS_PARTIAL_RATE_LIMIT_NOTE
                    if snapshot["rate_limited"]
                    else snapshot["notice"]
                )
                self.error = ""
            else:
                self.stats_notice = snapshot["notice"]
                self.error = snapshot["error"]
        except ApiError as error:
            logging.exception("Unexpected error")
            logging.info(f"API грешка при вчитување: {error.message}")
            self.error = error.message
        except Exception as error:
            logging.exception(f"Error: неуспешно вчитување од API: {error}")
            self.error = "Неочекувана грешка при вчитување на податоците."
        finally:
            self.is_loading = False

    def _startup_sync_events(self):
        """Агрегатите што зависат од примарните BZZ податоци.

        Се враќаат и кога вчитувањето не успее, за Преглед и Маркети да се
        синхронизираат во празна состојба со порака за грешка, а апликацијата
        да остане видлива.
        """
        from app.states.markets_state import MarketsState
        from app.states.overview_state import OverviewState

        return [OverviewState.sync, MarketsState.sync]

    @rx.event(background=True)
    async def startup_load(self):
        """Не-блокирачко иницијално вчитување (background задача).

        Страницата се рендерира и хидрира веднаш: ниту едно мрежно барање не
        се чека во `on_load`. Сите промени на состојбата се прават во
        `async with self:` блокови, а мрежните барања САМО надвор од нив, за
        да не се заклучи UI-то. `is_loading` секогаш се враќа на False, дури
        и при исклучок, така што состојбата не може да остане заглавена.

        Бавните јавни извори (Mutating, SportScore, Fudbal91, ESPN) и табот
        со модели НЕ се вчитуваат тука — тие остануваат отложени до
        отворање на соодветниот таб или до бавен круг на автоматското
        освежување.
        """
        skip = False
        async with self:
            if self.has_loaded or self.is_loading:
                skip = True
            else:
                self.is_loading = True
                self.error = ""
            target = _as_date(self.selected_date_value)

        if skip:
            # Веќе е вчитано (или се вчитува) — само синхронизирај агрегати.
            for event in self._startup_sync_events():
                yield event
            return

        try:
            from app.states import fotmob_fallback

            # Тешката работа е надвор од заклучувањето на состојбата.
            snapshot = await asyncio.to_thread(collect_matches, target)
            rows = snapshot["matches"]
            fotmob_note = ""
            compare_note = ""
            shadows: list[ShadowPick] = []
            if rows:
                _applied, fotmob_note = await fotmob_fallback.apply_fallback(
                    rows
                )
                (
                    raw_shadows,
                    compare_note,
                ) = await fotmob_fallback.compute_shadows(rows)
                shadows = [ShadowPick(**row) for row in raw_shadows]

            async with self:
                self.rate_limited = snapshot["rate_limited"]
                if rows:
                    self.matches = rows
                    self.fotmob_shadows = shadows
                    self.compare_notice = compare_note
                    self.generated_at = snapshot["generated_at"]
                    self.has_loaded = True
                    self.stats_notice = " ".join(
                        part
                        for part in (snapshot["notice"], fotmob_note)
                        if part
                    )
                    self.error = ""
                else:
                    self.stats_notice = snapshot["notice"]
                    self.error = snapshot["error"]
        except ApiError as error:
            logging.exception("Unexpected error")
            logging.info(
                f"API грешка при иницијално вчитување: {error.message}"
            )
            async with self:
                self.error = error.message
        except Exception as error:
            logging.exception(f"Error: примарното вчитување не успеа: {error}")
            async with self:
                self.error = "Неочекувана грешка при вчитување на податоците."
        finally:
            async with self:
                self.is_loading = False

        # Агрегатите се синхронизираат секогаш — и при успех и при грешка.
        for event in self._startup_sync_events():
            yield event

    @rx.event
    async def refresh_data(self):
        if self.is_loading:
            return
        yield
        await self._load_from_api()
        yield

    def _sync_events(self):
        """Ги враќа настаните за синхронизација на зависните состојби."""
        from app.states.bzz_source_state import BzzSourceState
        from app.states.fudbal91_state import Fudbal91State
        from app.states.markets_state import MarketsState
        from app.states.models_state import ModelsState
        from app.states.mutating_state import MutatingState
        from app.states.overview_state import OverviewState

        return [
            BzzSourceState.clear,
            MutatingState.sync_coverage,
            Fudbal91State.sync,
            OverviewState.sync,
            MarketsState.sync,
            ModelsState.sync,
        ]

    @rx.event
    async def reload_selected(self):
        """Повторно вчитување за тековно избраниот датум."""
        if self.is_loading:
            return
        yield
        await self._load_from_api()
        yield
        for event in self._sync_events():
            yield event

    @rx.event
    async def set_selected_date(self, value: str):
        cleaned = (value or "").strip()[:10]
        try:
            date.fromisoformat(cleaned)
        except ValueError:
            return
        self.selected_date = cleaned
        self.sub_tab = "today"
        self.expanded_id = ""
        yield
        await self._load_from_api()
        yield
        for event in self._sync_events():
            yield event

    @rx.event
    async def shift_day(self, offset: int):
        target = _as_date(self.selected_date_value) + timedelta(days=offset)
        self.selected_date = target.isoformat()
        self.sub_tab = "today"
        self.expanded_id = ""
        yield
        await self._load_from_api()
        yield
        for event in self._sync_events():
            yield event

    @rx.event
    async def select_today(self):
        today = local_today().isoformat()
        if self.selected_date == today:
            return
        self.selected_date = today
        self.sub_tab = "today"
        self.expanded_id = ""
        yield
        await self._load_from_api()
        yield
        for event in self._sync_events():
            yield event

    @rx.event
    def set_sub_tab(self, tab: str):
        self.sub_tab = tab
        self.expanded_id = ""

    @rx.event
    def toggle_expanded(self, match_id: str):
        self.expanded_id = "" if self.expanded_id == match_id else match_id
