"""Реален Fotmob fallback за настани без предвидување од BZZ API-то.

Не се симулираат тимови, натпревари ниту статистики: сите вредности се
изведени од вистински Fotmob податоци (teamForm, h2h, poll stat facts,
infoBox). Ако Fotmob нема совпаднат натпревар или нема употребливи
статистики, состојбата останува „недостапно“.
"""

import asyncio
import logging
import math
import time
import unicodedata

from app.states.log_filters import install_fotmob_log_filter

install_fotmob_log_filter()

FOTMOB_SOURCE = "fotmob"
FOTMOB_SOURCE_LABEL = "Fotmob статистика"

# Конзервативни лимити за да не се оптовари Fotmob (без официјален API).
MAX_DAYS = 3
MAX_FALLBACK_MATCHES = 6
MAX_SHADOW_MATCHES = 6
SHADOW_UNAVAILABLE_NOTE = (
    "Fotmob не врати совпаднати статистики за BZZ натпреварите, па споредбата "
    "не е достапна."
)
DETAIL_DELAY = 0.35
DAY_CACHE_TTL = 300.0
DETAIL_CACHE_TTL = 900.0
MIN_NAME_SCORE = 0.6
MIN_FORM_MATCHES = 3
LEAGUE_BASELINE = 1.35
MAX_GOALS = 8

FOTMOB_IMPORT_NOTE = (
    "Fotmob библиотеката не е достапна, па резервните предвидувања не се "
    "пресметани. Натпреварите од BZZ API-то остануваат непроменети."
)
FOTMOB_FAILURE_NOTE = (
    "Fotmob не одговори или ограничи дел од барањата, па некои резервни "
    "предвидувања не се пресметани."
)
FOTMOB_APPLIED_NOTE = (
    "{count} натпревари без BZZ предвидување добија резервно предвидување "
    "пресметано од реални Fotmob статистики."
)

_DAY_CACHE: dict[str, tuple[float, list[dict]]] = {}
_DETAIL_CACHE: dict[int, tuple[float, dict]] = {}

_STOPWORDS = {
    "fc",
    "cf",
    "sc",
    "ac",
    "afc",
    "cd",
    "ud",
    "fk",
    "sk",
    "bk",
    "if",
    "club",
    "calcio",
    "cs",
    "as",
    "ss",
    "us",
    "sv",
    "vfl",
    "vfb",
    "tsv",
    "nk",
    "hnk",
    "kf",
    "cska",
    "team",
    "the",
    "de",
    "ii",
    "b",
}


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _norm(value: object) -> str:
    if not isinstance(value, str):
        return ""
    text = _strip_accents(value).lower()
    cleaned = "".join(ch if ch.isalnum() else " " for ch in text)
    return " ".join(cleaned.split())


def _tokens(value: str) -> set[str]:
    return {t for t in _norm(value).split() if t and t not in _STOPWORDS}


def _name_score(left: str, right: str) -> float:
    a, b = _norm(left), _norm(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ta, tb = _tokens(left), _tokens(right)
    if not ta or not tb:
        return 0.0
    if ta == tb:
        return 0.98
    if ta <= tb or tb <= ta:
        return 0.9
    shared = ta & tb
    if not shared:
        joined_a = "".join(sorted(ta))
        joined_b = "".join(sorted(tb))
        if joined_a in joined_b or joined_b in joined_a:
            return 0.75
        return 0.0
    return round(len(shared) / len(ta | tb), 3)


def _flatten_day(payload: object) -> list[dict]:
    rows: list[dict] = []
    if not isinstance(payload, dict):
        return rows
    leagues = payload.get("leagues")
    if not isinstance(leagues, list):
        return rows
    for league in leagues:
        if not isinstance(league, dict):
            continue
        league_name = league.get("name")
        for row in league.get("matches") or []:
            if not isinstance(row, dict):
                continue
            item = dict(row)
            if isinstance(league_name, str):
                item["_league_name"] = league_name
            rows.append(item)
    return rows


async def _fetch_day(client: object, day: str) -> list[dict]:
    cached = _DAY_CACHE.get(day)
    now = time.monotonic()
    if cached and now - cached[0] < DAY_CACHE_TTL:
        return cached[1]
    try:
        payload = await client.get_matches_by_date(day)
    except Exception as error:
        logging.exception("Unexpected error")
        logging.info(
            f"Fotmob не врати податоци за {day}: {type(error).__name__}"
        )
        return []
    rows = _flatten_day(payload)
    _DAY_CACHE[day] = (now, rows)
    return rows


async def _fetch_details(client: object, match_id: int) -> dict:
    cached = _DETAIL_CACHE.get(match_id)
    now = time.monotonic()
    if cached and now - cached[0] < DETAIL_CACHE_TTL:
        return cached[1]
    try:
        payload = await client.get_match_details(match_id)
    except Exception as error:
        logging.exception("Unexpected error")
        logging.info(f"Fotmob детали не се достапни: {type(error).__name__}")
        return {}
    data = payload if isinstance(payload, dict) else {}
    if data:
        _DETAIL_CACHE[match_id] = (now, data)
    return data


def _candidate_names(row: dict) -> tuple[str, str]:
    home = row.get("home") if isinstance(row.get("home"), dict) else {}
    away = row.get("away") if isinstance(row.get("away"), dict) else {}
    home_name = str(home.get("longName") or home.get("name") or "")
    away_name = str(away.get("longName") or away.get("name") or "")
    return home_name, away_name


def _best_candidate(
    home: str, away: str, rows: list[dict]
) -> tuple[dict, float]:
    best: dict = {}
    best_score = 0.0
    for row in rows:
        cand_home, cand_away = _candidate_names(row)
        score_home = max(
            _name_score(home, cand_home),
            _name_score(home, (row.get("home") or {}).get("name") or ""),
        )
        score_away = max(
            _name_score(away, cand_away),
            _name_score(away, (row.get("away") or {}).get("name") or ""),
        )
        if score_home < MIN_NAME_SCORE or score_away < MIN_NAME_SCORE:
            continue
        total = score_home + score_away
        if total > best_score:
            best, best_score = row, total
    return best, best_score


def _parse_score(value: object) -> tuple[int, int] | None:
    if not isinstance(value, str):
        return None
    parts = value.replace(" ", "").split("-")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


class FormStats:
    """Агрегати од вистинската Fotmob форма на еден тим."""

    def __init__(self) -> None:
        self.played = 0
        self.points = 0
        self.scored = 0
        self.conceded = 0
        self.btts = 0
        self.over25 = 0
        self.results: list[str] = []

    @property
    def ok(self) -> bool:
        return self.played >= MIN_FORM_MATCHES

    @property
    def scored_avg(self) -> float:
        return self.scored / self.played if self.played else 0.0

    @property
    def conceded_avg(self) -> float:
        return self.conceded / self.played if self.played else 0.0

    @property
    def ppg(self) -> float:
        return self.points / self.played if self.played else 0.0

    @property
    def form_label(self) -> str:
        return "".join(self.results[-5:])


def _form_stats(rows: object) -> FormStats:
    stats = FormStats()
    if not isinstance(rows, list):
        return stats
    for row in rows[-6:]:
        if not isinstance(row, dict):
            continue
        score = _parse_score(row.get("score"))
        if score is None:
            tooltip = row.get("tooltipText")
            if isinstance(tooltip, dict):
                score = _parse_score(
                    f"{tooltip.get('homeScore')}-{tooltip.get('awayScore')}"
                )
        if score is None:
            continue
        home_side = row.get("home") if isinstance(row.get("home"), dict) else {}
        ours_home = bool(home_side.get("isOurTeam"))
        ours = score[0] if ours_home else score[1]
        theirs = score[1] if ours_home else score[0]
        stats.played += 1
        stats.scored += ours
        stats.conceded += theirs
        if ours > 0 and theirs > 0:
            stats.btts += 1
        if ours + theirs > 2:
            stats.over25 += 1
        if ours > theirs:
            stats.points += 3
            stats.results.append("W")
        elif ours == theirs:
            stats.points += 1
            stats.results.append("D")
        else:
            stats.results.append("L")
    return stats


def _h2h_goal_avg(h2h: object) -> tuple[float, int, float]:
    """Средно вкупно голови, број на решени H2H и дел со ГГ."""
    if not isinstance(h2h, dict):
        return 0.0, 0, 0.0
    rows = h2h.get("matches")
    if not isinstance(rows, list):
        return 0.0, 0, 0.0
    total = 0
    count = 0
    btts = 0
    for row in rows[:8]:
        if not isinstance(row, dict):
            continue
        status = (
            row.get("status") if isinstance(row.get("status"), dict) else {}
        )
        score = _parse_score(status.get("scoreStr") or row.get("score"))
        if score is None:
            home = row.get("home") if isinstance(row.get("home"), dict) else {}
            away = row.get("away") if isinstance(row.get("away"), dict) else {}
            score = _parse_score(f"{home.get('score')}-{away.get('score')}")
        if score is None:
            continue
        count += 1
        total += score[0] + score[1]
        if score[0] > 0 and score[1] > 0:
            btts += 1
    if count == 0:
        return 0.0, 0, 0.0
    return round(total / count, 2), count, round(btts / count, 3)


def _stat_facts(match_facts: object) -> list[str]:
    facts: list[str] = []
    if not isinstance(match_facts, dict):
        return facts
    poll = match_facts.get("poll")
    blocks = []
    if isinstance(poll, dict):
        for value in poll.values():
            if isinstance(value, dict):
                blocks.append(value)
    for block in blocks:
        rows = block.get("Facts")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            text = row.get("defaultText")
            if isinstance(text, str) and text.strip() and text not in facts:
                facts.append(text.strip())
    insights = match_facts.get("insights")
    if isinstance(insights, list):
        for row in insights:
            if isinstance(row, dict):
                text = row.get("text") or row.get("defaultText")
                if isinstance(text, str) and text.strip():
                    if text.strip() not in facts:
                        facts.append(text.strip())
    return facts[:4]


def _poisson(lam: float, k: int) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


def _poisson_markets(
    lam_home: float, lam_away: float
) -> dict[str, float | str]:
    home_probs = [_poisson(lam_home, k) for k in range(MAX_GOALS + 1)]
    away_probs = [_poisson(lam_away, k) for k in range(MAX_GOALS + 1)]
    p_home = p_draw = p_away = 0.0
    btts = 0.0
    totals = [0.0] * (2 * MAX_GOALS + 1)
    best_prob = 0.0
    best_score = "0-0"
    for h, ph in enumerate(home_probs):
        for a, pa in enumerate(away_probs):
            joint = ph * pa
            if h > a:
                p_home += joint
            elif h == a:
                p_draw += joint
            else:
                p_away += joint
            if h > 0 and a > 0:
                btts += joint
            totals[h + a] += joint
            if joint > best_prob:
                best_prob, best_score = joint, f"{h}-{a}"
    norm = p_home + p_draw + p_away or 1.0
    over15 = max(0.0, 1.0 - totals[0] - totals[1])
    over25 = max(0.0, over15 - totals[2])
    over35 = max(0.0, over25 - totals[3])
    return {
        "home": round(p_home / norm * 100, 1),
        "draw": round(p_draw / norm * 100, 1),
        "away": round(p_away / norm * 100, 1),
        "btts": round(min(97.0, btts * 100), 1),
        "over15": round(min(98.5, over15 * 100), 1),
        "over25": round(min(96.0, over25 * 100), 1),
        "over35": round(min(92.0, over35 * 100), 1),
        "top_score": best_score,
        "top_score_prob": round(best_prob * 100, 1),
    }


def _blend(base: float, target: float, weight: float) -> float:
    return base * (1.0 - weight) + target * weight


def _build_stat_rows(
    home: str,
    away: str,
    form_home: FormStats,
    form_away: FormStats,
    markets: dict[str, float | str],
    h2h_avg: float,
    h2h_count: int,
    pick_label: str,
) -> list[dict[str, str | float]]:
    rows: list[dict[str, str | float]] = [
        {
            "name": f"Fotmob форма · {home} {form_home.form_label}",
            "family": FOTMOB_SOURCE_LABEL,
            "pick": pick_label,
            "probability": float(markets["home"])
            if pick_label.startswith("1")
            else max(
                float(markets["home"]),
                float(markets["away"]),
                float(markets["draw"]),
            ),
            "accuracy": 0.0,
        },
        {
            "name": (
                f"Fotmob голови · {form_home.scored_avg:.2f} / "
                f"{form_away.scored_avg:.2f} по натпревар"
            ),
            "family": FOTMOB_SOURCE_LABEL,
            "pick": "Над 2.5 гола",
            "probability": float(markets["over25"]),
            "accuracy": 0.0,
        },
        {
            "name": (
                f"Fotmob H2H · {h2h_count} претходни ({h2h_avg:.2f} гола)"
                if h2h_count
                else f"Fotmob форма · {away} {form_away.form_label}"
            ),
            "family": FOTMOB_SOURCE_LABEL,
            "pick": "ГГ (BTTS)",
            "probability": float(markets["btts"]),
            "accuracy": 0.0,
        },
    ]
    return rows


def _venue_label(match_facts: object) -> str:
    if not isinstance(match_facts, dict):
        return ""
    info = match_facts.get("infoBox")
    if not isinstance(info, dict):
        return ""
    stadium = info.get("Stadium")
    if isinstance(stadium, dict):
        name = stadium.get("name")
        city = stadium.get("city")
        if isinstance(name, str) and name:
            return f"{name}, {city}" if isinstance(city, str) and city else name
    return ""


def _apply_fallback(match: dict, candidate: dict, details: dict) -> bool:
    from app.states.bsd_state import (
        _combo_markets,
        _extra_recommendation,
        _fair_odds,
        _value_label,
    )

    content = details.get("content")
    content = content if isinstance(content, dict) else {}
    match_facts = content.get("matchFacts")
    match_facts = match_facts if isinstance(match_facts, dict) else {}
    team_form = match_facts.get("teamForm")
    if not isinstance(team_form, list) or len(team_form) < 2:
        return False

    form_home = _form_stats(team_form[0])
    form_away = _form_stats(team_form[1])
    if not form_home.ok or not form_away.ok:
        return False

    h2h_avg, h2h_count, h2h_btts = _h2h_goal_avg(content.get("h2h"))

    lam_home = max(
        0.25,
        (form_home.scored_avg + form_away.conceded_avg) / 2.0 * 1.10,
    )
    lam_away = max(
        0.20,
        (form_away.scored_avg + form_home.conceded_avg) / 2.0 * 0.92,
    )
    if h2h_count >= 2:
        expected_total = lam_home + lam_away
        target = _blend(expected_total, h2h_avg, 0.25)
        if expected_total > 0:
            scale = target / expected_total
            lam_home *= scale
            lam_away *= scale
    # Мала корекција според освоени поени во формата (реални резултати).
    ppg_gap = form_home.ppg - form_away.ppg
    lam_home *= 1.0 + max(-0.12, min(0.12, ppg_gap * 0.05))
    lam_away *= 1.0 - max(-0.12, min(0.12, ppg_gap * 0.05))
    lam_home = round(min(3.4, max(0.25, lam_home)), 2)
    lam_away = round(min(3.2, max(0.20, lam_away)), 2)

    markets = _poisson_markets(lam_home, lam_away)

    form_btts = (form_home.btts + form_away.btts) / max(
        1, form_home.played + form_away.played
    )
    btts = round(
        _blend(
            float(markets["btts"]),
            _blend(form_btts, h2h_btts, 0.35 if h2h_count >= 2 else 0.0) * 100,
            0.3,
        ),
        1,
    )
    form_over = (form_home.over25 + form_away.over25) / max(
        1, form_home.played + form_away.played
    )
    over25 = round(
        _blend(float(markets["over25"]), form_over * 100, 0.25),
        1,
    )
    markets["btts"] = btts
    markets["over25"] = over25

    ml_home = float(markets["home"])
    ml_draw = float(markets["draw"])
    ml_away = float(markets["away"])
    outcomes = [
        (ml_home, f"1 · {match['home']}", "home"),
        (ml_draw, "X · Реми", "draw"),
        (ml_away, f"2 · {match['away']}", "away"),
    ]
    best = max(outcomes, key=lambda row: row[0])

    goals_pick = (
        ("Над 2.5 гола", over25)
        if over25 >= 50.0
        else ("Под 2.5 гола", round(100.0 - over25, 1))
    )
    btts_pick = (
        ("ГГ · двата тима", btts)
        if btts >= 50.0
        else ("НГ · без ГГ", round(100.0 - btts, 1))
    )
    options = [
        ("1X2 · Fotmob форма", best[1], best[0]),
        ("Голови · Fotmob форма", goals_pick[0], goals_pick[1]),
        ("ГГ · Fotmob форма", btts_pick[0], btts_pick[1]),
    ]
    meta_market, meta_pick, meta_confidence = max(
        options, key=lambda row: row[2]
    )
    meta_odds = _fair_odds(meta_confidence)
    meta_edge = round(meta_confidence - 100.0 / meta_odds, 2)

    stat_rows = _build_stat_rows(
        match["home"],
        match["away"],
        form_home,
        form_away,
        markets,
        h2h_avg,
        h2h_count,
        best[1],
    )
    agreement = round(
        len([r for r in stat_rows if float(r["probability"]) >= 50.0])
        / max(1, len(stat_rows))
        * 100,
        0,
    )

    combos = _combo_markets(
        match["home"],
        match["away"],
        ml_home,
        ml_draw,
        ml_away,
        btts,
        over25,
        float(markets["over15"]),
        float(markets["over35"]),
    )
    recommended = [c for c in combos if c["recommended"]]

    general = details.get("general")
    general = general if isinstance(general, dict) else {}
    league_name = general.get("leagueName") or candidate.get("_league_name")
    venue = _venue_label(match_facts)

    match.update(
        has_prediction=True,
        prediction_note="",
        source=FOTMOB_SOURCE,
        source_label=FOTMOB_SOURCE_LABEL,
        fotmob_id=int(candidate.get("id") or 0),
        stat_facts=_stat_facts(match_facts),
        model_name=f"Fotmob форма + Poisson · {form_home.form_label} / {form_away.form_label}",
        ml_home=ml_home,
        ml_draw=ml_draw,
        ml_away=ml_away,
        ml_pick=best[1],
        ml_confidence=round(best[0], 1),
        pick_side=best[2],
        xg_home=lam_home,
        xg_away=lam_away,
        poi_home=ml_home,
        poi_draw=ml_draw,
        poi_away=ml_away,
        poi_btts=btts,
        poi_over25=over25,
        poi_under25=round(100.0 - over25, 1),
        poi_over35=float(markets["over35"]),
        poi_under35=round(100.0 - float(markets["over35"]), 1),
        poi_over15=float(markets["over15"]),
        poi_under15=round(100.0 - float(markets["over15"]), 1),
        extra_label=_extra_recommendation(
            btts, over25, float(markets["over35"])
        )[0],
        extra_pick=_extra_recommendation(
            btts, over25, float(markets["over35"])
        )[1],
        extra_probability=_extra_recommendation(
            btts, over25, float(markets["over35"])
        )[2],
        top_score=str(markets["top_score"]),
        top_score_prob=max(0.1, float(markets["top_score_prob"])),
        expected_goals=round(lam_home + lam_away, 2),
        top_models=stat_rows,
        combos=combos,
        top_combos=combos[:6],
        combo_count=len(combos),
        combo_recommended=len(recommended),
        best_combo_label=combos[0]["label"] if combos else match["top_score"],
        best_combo_probability=combos[0]["probability"] if combos else 0.0,
        meta_market=meta_market,
        meta_pick=meta_pick,
        meta_confidence=round(meta_confidence, 1),
        meta_odds=meta_odds,
        meta_edge=meta_edge,
        meta_agreement=float(agreement),
        meta_value=_value_label(meta_edge),
    )
    if isinstance(league_name, str) and league_name:
        if match["league"].startswith("Лига #") or match["league"] in (
            "",
            "Недостапно",
        ):
            match["league"] = league_name
    if venue and match["venue"] in ("", "Недостапно"):
        match["venue"] = venue
    if not match["form_home"]:
        match["form_home"] = form_home.form_label
    if not match["form_away"]:
        match["form_away"] = form_away.form_label
    return True


async def compute_shadows(matches: list[dict]) -> tuple[list[dict], str]:
    """Пресметува Fotmob предвидувања САМО за споредба со BZZ.

    Не ги менува BZZ натпреварите: работи врз копија на секој натпревар и
    враќа само избори за споредба. Ако Fotmob не најде совпаѓање, ништо не
    се измислува.
    """
    targets = [
        m
        for m in matches
        if m.get("has_prediction")
        and m.get("source") != FOTMOB_SOURCE
        and m.get("date_key")
    ]
    if not targets:
        return [], ""

    try:
        from fotmob import FotMob
    except Exception as error:
        logging.exception(f"Error: Fotmob увоз неуспешен: {error}")
        return [], FOTMOB_IMPORT_NOTE

    try:
        client = FotMob()
    except Exception as error:
        logging.exception(f"Error: Fotmob клиент неуспешен: {error}")
        return [], FOTMOB_FAILURE_NOTE

    shadows: list[dict] = []
    failures = 0
    try:
        days: list[str] = []
        for match in targets:
            day = str(match["date_key"])
            if day and day not in days:
                days.append(day)
        index: dict[str, list[dict]] = {}
        for day in days[:MAX_DAYS]:
            index[day] = await _fetch_day(client, day)
            if not index[day]:
                failures += 1

        for match in targets:
            if len(shadows) >= MAX_SHADOW_MATCHES:
                break
            rows = index.get(match["date_key"])
            if not rows:
                continue
            candidate, _score = _best_candidate(
                match["home"], match["away"], rows
            )
            if not candidate:
                continue
            details = await _fetch_details(
                client, int(candidate.get("id") or 0)
            )
            await asyncio.sleep(DETAIL_DELAY)
            if not details:
                failures += 1
                continue
            probe = dict(match)
            try:
                if not _apply_fallback(probe, candidate, details):
                    continue
            except Exception as error:
                logging.exception(f"Error: Fotmob споредба: {error}")
                failures += 1
                continue
            shadows.append(
                {
                    "match_id": str(match["id"]),
                    "ml_pick": str(probe["ml_pick"]),
                    "ml_side": str(probe["pick_side"]),
                    "ml_confidence": float(probe["ml_confidence"]),
                    "meta_market": str(probe["meta_market"]),
                    "meta_pick": str(probe["meta_pick"]),
                    "meta_confidence": float(probe["meta_confidence"]),
                    "meta_edge": float(probe["meta_edge"]),
                }
            )
    except Exception as error:
        logging.exception(f"Error: Fotmob споредба: {error}")
        failures += 1
    finally:
        try:
            close = getattr(client, "close", None)
            if close is not None:
                result = close()
                if asyncio.iscoroutine(result):
                    await result
        except Exception as error:
            logging.exception(f"Error: Fotmob затворање: {error}")

    if shadows:
        return shadows, ""
    if failures:
        return [], FOTMOB_FAILURE_NOTE
    return [], SHADOW_UNAVAILABLE_NOTE


async def apply_fallback(matches: list[dict]) -> tuple[int, str]:
    """Пополнува резервни предвидувања од Fotmob. Враќа (број, забелешка)."""
    targets = [
        m for m in matches if not m.get("has_prediction") and m.get("date_key")
    ]
    if not targets:
        return 0, ""

    try:
        from fotmob import FotMob
    except Exception as error:
        logging.exception(f"Error: Fotmob увоз неуспешен: {error}")
        return 0, FOTMOB_IMPORT_NOTE

    try:
        client = FotMob()
    except Exception as error:
        logging.exception(f"Error: Fotmob клиент неуспешен: {error}")
        return 0, FOTMOB_FAILURE_NOTE

    applied = 0
    failures = 0
    try:
        days: list[str] = []
        for match in targets:
            day = str(match["date_key"])
            if day and day not in days:
                days.append(day)
        index: dict[str, list[dict]] = {}
        for day in days[:MAX_DAYS]:
            index[day] = await _fetch_day(client, day)
            if not index[day]:
                failures += 1

        for match in targets:
            if applied >= MAX_FALLBACK_MATCHES:
                break
            rows = index.get(match["date_key"])
            if not rows:
                continue
            candidate, _score = _best_candidate(
                match["home"], match["away"], rows
            )
            if not candidate:
                continue
            details = await _fetch_details(
                client, int(candidate.get("id") or 0)
            )
            await asyncio.sleep(DETAIL_DELAY)
            if not details:
                failures += 1
                continue
            try:
                if _apply_fallback(match, candidate, details):
                    applied += 1
            except Exception as error:
                logging.exception(f"Error: Fotmob пресметка: {error}")
                failures += 1
    except Exception as error:
        logging.exception(f"Error: Fotmob fallback: {error}")
        failures += 1
    finally:
        try:
            close = getattr(client, "close", None)
            if close is not None:
                result = close()
                if asyncio.iscoroutine(result):
                    await result
        except Exception as error:
            logging.exception(f"Error: Fotmob затворање: {error}")

    if applied:
        return applied, FOTMOB_APPLIED_NOTE.format(count=applied)
    if failures:
        return 0, FOTMOB_FAILURE_NOTE
    return 0, ""
