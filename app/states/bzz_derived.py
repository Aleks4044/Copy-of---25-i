"""Изведени предвидувања САМО од реални BZZ ресурси по настан.

Кога листата /predictions/ и ресурсот /events/{id}/prediction/ не даваат
официјално предвидување, овде се читаат вистинските јавни (автентицирани)
ресурси на самиот настан:

  * /events/{id}/odds/     — реални квоти 1/X/2, линии за голови и ГГ
  * /events/{id}/h2h/      — реални меѓусебни средби и стапки на победи
  * /events/{id}/lineups/  — состави и отсутни играчи
  * /events/{id}/stats/    — статистики (xG кога постои)
  * /events/{id}/summary/  и /events/{id}/money/ — само ако вратат 200

Сите веројатности се изведени детерминистички од тие реални вредности. Ако
нема ниту квоти, ниту H2H, ниту состави — предвидувањето останува
недостапно и НИШТО не се измислува. Ниту еден клуч не се логира.
"""

import logging
import math
from typing import TypedDict

from app.states import api_client

DERIVED_SOURCE = "bzz_derived"
DERIVED_SOURCE_LABEL = "BZZ изведено"
DERIVED_MODEL_PREFIX = "BZZ изведено"

# Минимален број меѓусебни средби за H2H да носи самостојно предвидување.
MIN_H2H_FOR_BASE = 3
MAX_H2H_WEIGHT = 0.18
MONEY_WEIGHT = 0.10
MAX_LINEUP_SHIFT = 4.0

ODDS_HOME_KEYS = ("home_win", "home", "win_home", "home_odds", "1")
ODDS_DRAW_KEYS = ("draw", "x", "draw_odds", "tie")
ODDS_AWAY_KEYS = ("away_win", "away", "win_away", "away_odds", "2")

OVER_KEYS: dict[str, tuple[str, ...]] = {
    "15": ("over_15_goals", "over_1_5", "over_15", "over_1_5_goals"),
    "25": ("over_25_goals", "over_2_5", "over_25", "over_2_5_goals"),
    "35": ("over_35_goals", "over_3_5", "over_35", "over_3_5_goals"),
}
UNDER_KEYS: dict[str, tuple[str, ...]] = {
    "15": ("under_15_goals", "under_1_5", "under_15", "under_1_5_goals"),
    "25": ("under_25_goals", "under_2_5", "under_25", "under_2_5_goals"),
    "35": ("under_35_goals", "under_3_5", "under_35", "under_3_5_goals"),
}
BTTS_YES_KEYS = (
    "btts_yes",
    "btts",
    "both_teams_to_score",
    "both_teams_to_score_yes",
    "gg",
)
BTTS_NO_KEYS = (
    "btts_no",
    "both_teams_to_score_no",
    "no_btts",
    "ng",
)


class DerivedSources(TypedDict):
    """Реални одговори по настан (празен речник кога ресурсот не е достапен)."""

    odds: dict
    h2h: dict
    lineups: dict
    stats: dict
    summary: dict
    money: dict
    rate_limited: bool
    missing_key: bool
    available: list[str]


def _empty_sources() -> DerivedSources:
    return DerivedSources(
        odds={},
        h2h={},
        lineups={},
        stats={},
        summary={},
        money={},
        rate_limited=False,
        missing_key=False,
        available=[],
    )


def _num(value: object) -> float | None:
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


def _share(value: object) -> float | None:
    """Процент (0-100) од вредност што може да е и дел (0-1)."""
    number = _num(value)
    if number is None:
        return None
    if 0.0 <= number <= 1.0:
        number *= 100.0
    if number < 0.0 or number > 100.0:
        return None
    return round(number, 1)


def _odd(block: dict, keys: tuple[str, ...]) -> float | None:
    if not isinstance(block, dict):
        return None
    for key in keys:
        value = _num(block.get(key))
        if value is not None and value > 1.0:
            return round(value, 2)
        nested = block.get(key)
        if isinstance(nested, dict):
            for inner in ("odds", "value", "price", "average", "avg"):
                candidate = _num(nested.get(inner))
                if candidate is not None and candidate > 1.0:
                    return round(candidate, 2)
    return None


def _odds_block(payload: dict) -> dict:
    """Го наоѓа речникот со квоти во одговорот на ресурсот."""
    if not isinstance(payload, dict):
        return {}
    block = payload.get("odds")
    if isinstance(block, dict):
        return block
    if isinstance(block, list):
        for row in block:
            if isinstance(row, dict):
                return row
    return payload


def _normalize3(
    values: tuple[float, float, float],
) -> tuple[float, float, float]:
    total = sum(max(0.5, value) for value in values)
    if total <= 0.0:
        return 0.0, 0.0, 0.0
    home = round(max(0.5, values[0]) / total * 100.0, 1)
    draw = round(max(0.5, values[1]) / total * 100.0, 1)
    away = round(100.0 - home - draw, 1)
    return home, draw, max(0.5, away)


def _blend3(
    base: tuple[float, float, float],
    other: tuple[float, float, float],
    weight: float,
) -> tuple[float, float, float]:
    factor = max(0.0, min(0.5, weight))
    mixed = tuple(
        base[index] * (1.0 - factor) + other[index] * factor
        for index in range(3)
    )
    return _normalize3((mixed[0], mixed[1], mixed[2]))


def _implied_triple(
    home: float | None, draw: float | None, away: float | None
) -> tuple[float, float, float] | None:
    if home is None or draw is None or away is None:
        return None
    inverse = (1.0 / home, 1.0 / draw, 1.0 / away)
    return _normalize3(inverse)


def _implied_line(over: float | None, under: float | None) -> float | None:
    """Имплицирана веројатност за „над“ линијата (проценти)."""
    if over is not None and under is not None:
        total = 1.0 / over + 1.0 / under
        if total <= 0.0:
            return None
        return round(1.0 / over / total * 100.0, 1)
    if over is not None:
        value = 1.0 / over / 1.06 * 100.0
        return round(min(97.0, max(3.0, value)), 1)
    if under is not None:
        value = 100.0 - 1.0 / under / 1.06 * 100.0
        return round(min(97.0, max(3.0, value)), 1)
    return None


def _market_probs(block: dict) -> dict[str, float]:
    """Реални квоти и имплицирани веројатности од ресурсот за квоти."""
    out: dict[str, float] = {}
    if not isinstance(block, dict):
        return out
    odd_home = _odd(block, ODDS_HOME_KEYS)
    odd_draw = _odd(block, ODDS_DRAW_KEYS)
    odd_away = _odd(block, ODDS_AWAY_KEYS)
    triple = _implied_triple(odd_home, odd_draw, odd_away)
    if triple is not None:
        out["home"], out["draw"], out["away"] = triple
        out["odd_home"] = float(odd_home or 0.0)
        out["odd_draw"] = float(odd_draw or 0.0)
        out["odd_away"] = float(odd_away or 0.0)
    for line, keys in OVER_KEYS.items():
        over = _odd(block, keys)
        under = _odd(block, UNDER_KEYS[line])
        value = _implied_line(over, under)
        if value is not None:
            out[f"over{line}"] = value
        if over is not None:
            out[f"odd_over{line}"] = float(over)
        if under is not None:
            out[f"odd_under{line}"] = float(under)
    btts_yes = _odd(block, BTTS_YES_KEYS)
    btts_no = _odd(block, BTTS_NO_KEYS)
    btts = _implied_line(btts_yes, btts_no)
    if btts is not None:
        out["btts"] = btts
    if btts_yes is not None:
        out["odd_btts_yes"] = float(btts_yes)
    if btts_no is not None:
        out["odd_btts_no"] = float(btts_no)
    return out


def _recent_rates(payload: dict) -> tuple[float | None, float | None]:
    """ГГ и Над 2.5 стапки од реални меѓусебни резултати."""
    from app.states.bsd_state import _h2h_score

    rows = payload.get("recent_matches") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return None, None
    btts = 0
    over25 = 0
    count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        score = _h2h_score(row)
        if score is None:
            continue
        count += 1
        if score[0] > 0 and score[1] > 0:
            btts += 1
        if score[0] + score[1] > 2:
            over25 += 1
    if count == 0:
        return None, None
    return (
        round(btts / count * 100.0, 1),
        round(over25 / count * 100.0, 1),
    )


def _h2h_summary(payload: dict) -> dict[str, float]:
    """Реални H2H агрегати (празно кога изворот не ги дава)."""
    out: dict[str, float] = {}
    if not isinstance(payload, dict):
        return out
    total = _num(payload.get("total_matches"))
    if total is None or total < 1.0:
        return out
    home_wins = _num(payload.get("home_wins")) or 0.0
    away_wins = _num(payload.get("away_wins")) or 0.0
    draws = _num(payload.get("draws"))
    if draws is None:
        draws = max(0.0, total - home_wins - away_wins)
    home_rate = _share(payload.get("home_win_rate"))
    away_rate = _share(payload.get("away_win_rate"))
    if home_rate is None:
        home_rate = round(home_wins / total * 100.0, 1)
    if away_rate is None:
        away_rate = round(away_wins / total * 100.0, 1)
    draw_rate = round(max(0.0, 100.0 - home_rate - away_rate), 1)
    out["total"] = float(total)
    out["home_wins"] = home_wins
    out["draws"] = draws
    out["away_wins"] = away_wins
    out["home_rate"] = home_rate
    out["draw_rate"] = draw_rate
    out["away_rate"] = away_rate
    avg_goals = _num(payload.get("avg_total_goals"))
    if avg_goals is not None and avg_goals > 0.0:
        out["avg_goals"] = round(min(6.0, avg_goals), 2)
    btts_rate, over25_rate = _recent_rates(payload)
    if btts_rate is not None:
        out["btts_rate"] = btts_rate
    if over25_rate is not None:
        out["over25_rate"] = over25_rate
    return out


def _count_side(value: object) -> int:
    if isinstance(value, list):
        return len([row for row in value if row])
    if isinstance(value, dict):
        total = 0
        for inner in value.values():
            if isinstance(inner, list):
                total += len([row for row in inner if row])
        return total
    number = _num(value)
    return int(number) if number is not None and number >= 0 else 0


def _lineup_gaps(payload: dict) -> dict[str, float | str]:
    """Отсутни играчи по страна од реалниот ресурс за состави."""
    out: dict[str, float | str] = {
        "available": 0.0,
        "home_missing": 0.0,
        "away_missing": 0.0,
        "status": "",
    }
    if not isinstance(payload, dict):
        return out
    status = payload.get("lineup_status")
    if isinstance(status, str) and status.strip():
        out["status"] = status.strip()
    block = payload.get("unavailable_players")
    home_missing = 0
    away_missing = 0
    found = False
    if isinstance(block, dict):
        home_missing = _count_side(block.get("home"))
        away_missing = _count_side(block.get("away"))
        found = True
    lineups = payload.get("lineups")
    if isinstance(lineups, dict):
        for side, key in (("home", "home"), ("away", "away")):
            inner = lineups.get(key)
            if not isinstance(inner, dict):
                continue
            extra = _count_side(inner.get("unavailable_players"))
            if extra:
                found = True
                if side == "home":
                    home_missing += extra
                else:
                    away_missing += extra
    if not found and not out["status"]:
        return out
    out["available"] = 1.0
    out["home_missing"] = float(home_missing)
    out["away_missing"] = float(away_missing)
    return out


def _money_share(payload: dict) -> tuple[float, float, float] | None:
    """Реален распоред на пари 1/X/2 (само ако изворот го дава)."""
    if not isinstance(payload, dict):
        return None
    block = (
        payload.get("money")
        if isinstance(payload.get("money"), dict)
        else payload
    )
    home = _share(block.get("home") or block.get("home_win"))
    draw = _share(block.get("draw") or block.get("x"))
    away = _share(block.get("away") or block.get("away_win"))
    if home is None or draw is None or away is None:
        return None
    if home + draw + away <= 0.0:
        return None
    return _normalize3((home, draw, away))


def _summary_goals(payload: dict) -> float | None:
    """Очекувани голови ако ресурсот за резиме навистина ги објавува."""
    if not isinstance(payload, dict):
        return None
    for key in ("avg_total_goals", "expected_goals", "expected_total_goals"):
        value = _num(payload.get(key))
        if value is not None and 0.4 <= value <= 7.0:
            return round(value, 2)
    return None


SUMMARY_HOME_KEYS: tuple[str, ...] = (
    "home_win_probability",
    "home_probability",
    "prob_home",
    "home_win_chance",
    "home_chance",
)
SUMMARY_DRAW_KEYS: tuple[str, ...] = (
    "draw_probability",
    "prob_draw",
    "draw_chance",
)
SUMMARY_AWAY_KEYS: tuple[str, ...] = (
    "away_win_probability",
    "away_probability",
    "prob_away",
    "away_win_chance",
    "away_chance",
)


def _first_share(block: dict, keys: tuple[str, ...]) -> float | None:
    for key in keys:
        if key in block:
            value = _share(block.get(key))
            if value is not None:
                return value
    return None


def _summary_triple(payload: dict) -> tuple[float, float, float] | None:
    """1/X/2 од ресурсот за резиме, САМО ако полињата навистина постојат."""
    if not isinstance(payload, dict):
        return None
    blocks: list[dict] = [payload]
    for key in ("summary", "prediction", "probabilities", "markets"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            blocks.append(nested)
            inner = nested.get("match_result")
            if isinstance(inner, dict):
                blocks.append(inner)
    for block in blocks:
        home = _first_share(block, SUMMARY_HOME_KEYS)
        draw = _first_share(block, SUMMARY_DRAW_KEYS)
        away = _first_share(block, SUMMARY_AWAY_KEYS)
        if home is None or draw is None or away is None:
            continue
        if home + draw + away <= 0.0:
            continue
        return _normalize3((home, draw, away))
    return None


def _poisson_pmf(lam: float, k: int) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


def _poisson_over(lam_total: float, line: int) -> float | None:
    if lam_total <= 0.0:
        return None
    cumulative = sum(_poisson_pmf(lam_total, k) for k in range(line + 1))
    value = max(0.0, 1.0 - cumulative) * 100.0
    return round(min(97.0, max(2.0, value)), 1)


def _poisson_btts(lam_home: float, lam_away: float) -> float | None:
    if lam_home <= 0.0 or lam_away <= 0.0:
        return None
    value = (1.0 - math.exp(-lam_home)) * (1.0 - math.exp(-lam_away)) * 100.0
    return round(min(96.0, max(3.0, value)), 1)


def _split_lambdas(
    total: float, probs: tuple[float, float, float]
) -> tuple[float, float]:
    weight_home = probs[0] + probs[1] / 2.0
    weight_away = probs[2] + probs[1] / 2.0
    denominator = weight_home + weight_away
    share = weight_home / denominator if denominator > 0.0 else 0.5
    share = min(0.72, max(0.28, share))
    capped = min(5.0, max(0.9, total))
    return round(capped * share, 2), round(capped * (1.0 - share), 2)


def fetch_sources(
    event_id: int, allow_optional: bool = False
) -> DerivedSources:
    """Ги чита реалните ресурси по настан. Никогаш не крева исклучок."""
    out = _empty_sources()
    if event_id <= 0:
        return out

    # Прво квоти, потоа резиме, потоа H2H — точно по редот на изведување.
    primary = (
        ("odds", f"/events/{event_id}/odds/"),
        ("summary", f"/events/{event_id}/summary/"),
        ("h2h", f"/events/{event_id}/h2h/"),
    )
    for key, path in primary:
        payload, status = api_client.get_optional_dict(path)
        if status == api_client.RATE_LIMIT_STATUS:
            out["rate_limited"] = True
            return out
        if status == api_client.MISSING_KEY_STATUS:
            out["missing_key"] = True
            return out
        if payload:
            out[key] = payload
            out["available"].append(key)

    if not out["odds"] and not out["h2h"] and not out["summary"]:
        # Без квоти, без резиме и без H2H не се прави дополнително барање.
        return out

    secondary = [
        ("lineups", f"/events/{event_id}/lineups/"),
        ("stats", f"/events/{event_id}/stats/"),
    ]
    if allow_optional:
        secondary.append(("money", f"/events/{event_id}/money/"))
    for key, path in secondary:
        payload, status = api_client.get_optional_dict(path)
        if status == api_client.RATE_LIMIT_STATUS:
            out["rate_limited"] = True
            return out
        if status == api_client.MISSING_KEY_STATUS:
            out["missing_key"] = True
            return out
        if payload:
            out[key] = payload
            out["available"].append(key)
    return out


def apply_derived(match: dict, sources: DerivedSources) -> bool:
    """Пополнува изведено предвидување. Враќа дали има доволно реални податоци."""
    from app.states.bsd_state import (
        _combo_markets,
        _derive_over15,
        _extra_recommendation,
        _fair_odds,
        _form_from_h2h,
        _lambdas,
        _top_score_from_lambdas,
        _value_label,
        _xg_from_stats,
    )

    market = _market_probs(_odds_block(sources["odds"]))
    h2h = _h2h_summary(sources["h2h"])
    gaps = _lineup_gaps(sources["lineups"])
    money = _money_share(sources["money"])

    facts: list[str] = []
    segments: list[str] = []
    basis: list[str] = []
    probs: tuple[float, float, float] | None = None

    if "home" in market and "draw" in market and "away" in market:
        probs = (market["home"], market["draw"], market["away"])
        segments.append("квоти 1/X/2")
        basis.append("odds")
        facts.append(
            "Реални BZZ квоти 1/X/2: "
            f"{market.get('odd_home', 0.0):.2f} · "
            f"{market.get('odd_draw', 0.0):.2f} · "
            f"{market.get('odd_away', 0.0):.2f}"
        )

    summary_triple = _summary_triple(sources["summary"])
    if summary_triple is not None:
        if probs is None:
            probs = summary_triple
            segments.append("резиме на настанот")
        else:
            probs = _blend3(probs, summary_triple, 0.20)
            segments.append("резиме")
        basis.append("summary")
        facts.append(
            "Реални полиња од резимето 1/X/2: "
            f"{summary_triple[0]:.1f}% · {summary_triple[1]:.1f}% · "
            f"{summary_triple[2]:.1f}%"
        )

    if h2h:
        h2h_triple = (
            h2h["home_rate"],
            h2h["draw_rate"],
            h2h["away_rate"],
        )
        total = int(h2h["total"])
        if probs is None:
            if total >= MIN_H2H_FOR_BASE:
                probs = _normalize3(h2h_triple)
                segments.append(f"H2H ({total} средби)")
                basis.append("h2h")
        else:
            weight = min(MAX_H2H_WEIGHT, total * 0.03)
            if weight > 0.0:
                probs = _blend3(probs, h2h_triple, weight)
                segments.append(f"H2H ({total})")
                basis.append("h2h")
        facts.append(
            f"H2H: {total} средби · "
            f"{int(h2h['home_wins'])}-{int(h2h['draws'])}-"
            f"{int(h2h['away_wins'])}"
            + (
                f" · {h2h['avg_goals']:.2f} гола во просек"
                if "avg_goals" in h2h
                else ""
            )
        )

    if probs is not None and money is not None:
        probs = _blend3(probs, money, MONEY_WEIGHT)
        segments.append("распоред на пари")
        basis.append("money")
        facts.append(
            "Реален распоред на пари 1/X/2: "
            f"{money[0]:.1f}% · {money[1]:.1f}% · {money[2]:.1f}%"
        )

    if probs is None:
        return False

    if gaps["available"]:
        home_missing = int(gaps["home_missing"])
        away_missing = int(gaps["away_missing"])
        if home_missing or away_missing:
            diff = away_missing - home_missing
            shift = max(-MAX_LINEUP_SHIFT, min(MAX_LINEUP_SHIFT, diff * 0.8))
            probs = _normalize3((probs[0] + shift, probs[1], probs[2] - shift))
            segments.append("состави")
            basis.append("lineups")
        status_label = str(gaps["status"]) or "објавени"
        facts.append(
            f"Состави ({status_label}): {home_missing} отсутни дома · "
            f"{away_missing} во гости"
        )

    over25 = market.get("over25")
    over15 = market.get("over15")
    over35 = market.get("over35")
    btts = market.get("btts")

    if over25 is not None:
        facts.append(
            f"Линија 2.5 од реални квоти: Над {over25:.1f}% · "
            f"Под {max(0.0, 100.0 - over25):.1f}%"
        )
    if btts is not None:
        facts.append(f"ГГ од реални квоти: {btts:.1f}%")

    expected = _summary_goals(sources["summary"]) or h2h.get("avg_goals")

    lambdas = _lambdas(None, None, over25, probs[0], probs[1], probs[2])
    if lambdas is None and expected:
        lambdas = _split_lambdas(float(expected), probs)
        segments.append("просек голови")

    if lambdas is not None:
        lam_total = lambdas[0] + lambdas[1]
        if over25 is None:
            over25 = _poisson_over(lam_total, 2)
        if over35 is None:
            over35 = _poisson_over(lam_total, 3)
        if btts is None:
            btts = _poisson_btts(lambdas[0], lambdas[1])

    if btts is None and h2h.get("btts_rate") is not None:
        btts = h2h["btts_rate"]
    elif btts is not None and h2h.get("btts_rate") is not None:
        btts = round(btts * 0.85 + float(h2h["btts_rate"]) * 0.15, 1)
    if over25 is None and h2h.get("over25_rate") is not None:
        over25 = h2h["over25_rate"]
    elif over25 is not None and h2h.get("over25_rate") is not None:
        over25 = round(over25 * 0.85 + float(h2h["over25_rate"]) * 0.15, 1)

    over15 = _derive_over15(over15, over25, lambdas)

    xg_home, xg_away = _xg_from_stats(sources["stats"])
    if xg_home is None and lambdas is not None:
        xg_home = lambdas[0]
    if xg_away is None and lambdas is not None:
        xg_away = lambdas[1]
    if xg_home is not None and xg_away is not None:
        expected_total = round(xg_home + xg_away, 2)
    elif expected:
        expected_total = round(float(expected), 2)
    else:
        expected_total = 0.0

    top_score = "Недостапно"
    top_score_prob = 0.0
    if lambdas is not None:
        top_score, top_score_prob = _top_score_from_lambdas(*lambdas)

    outcomes = [
        (probs[0], f"1 · {match['home']}", "home", market.get("odd_home")),
        (probs[1], "X · Реми", "draw", market.get("odd_draw")),
        (probs[2], f"2 · {match['away']}", "away", market.get("odd_away")),
    ]
    best = max(outcomes, key=lambda row: row[0])

    options: list[tuple[str, str, float, float | None]] = [
        ("1X2 · изведено од BZZ квоти", best[1], best[0], best[3])
    ]
    if over25 is not None and over25 > 0.0:
        if over25 >= 50.0:
            options.append(
                (
                    "Голови · изведено од BZZ",
                    "Над 2.5 гола",
                    over25,
                    market.get("odd_over25"),
                )
            )
        else:
            options.append(
                (
                    "Голови · изведено од BZZ",
                    "Под 2.5 гола",
                    round(100.0 - over25, 1),
                    market.get("odd_under25"),
                )
            )
    if btts is not None and btts > 0.0:
        if btts >= 50.0:
            options.append(
                (
                    "ГГ · изведено од BZZ",
                    "ГГ · двата тима",
                    btts,
                    market.get("odd_btts_yes"),
                )
            )
        else:
            options.append(
                (
                    "ГГ · изведено од BZZ",
                    "НГ · без ГГ",
                    round(100.0 - btts, 1),
                    market.get("odd_btts_no"),
                )
            )
    meta_market, meta_pick, meta_confidence, meta_real_odds = max(
        options, key=lambda row: row[2]
    )
    meta_odds = (
        round(float(meta_real_odds), 2)
        if meta_real_odds and float(meta_real_odds) > 1.0
        else _fair_odds(meta_confidence)
    )
    meta_edge = round(meta_confidence - 100.0 / meta_odds, 2)

    top_models: list[dict[str, str | float]] = [
        {
            "name": f"{DERIVED_MODEL_PREFIX} · имплицирани квоти 1X2",
            "family": DERIVED_SOURCE_LABEL,
            "pick": best[1],
            "probability": round(best[0], 1),
            "accuracy": 0.0,
        }
    ]
    if btts is not None:
        top_models.append(
            {
                "name": f"{DERIVED_MODEL_PREFIX} · ГГ поддршка",
                "family": DERIVED_SOURCE_LABEL,
                "pick": "ГГ (BTTS)",
                "probability": round(btts, 1),
                "accuracy": 0.0,
            }
        )
    if over25 is not None:
        top_models.append(
            {
                "name": f"{DERIVED_MODEL_PREFIX} · линија 2.5",
                "family": DERIVED_SOURCE_LABEL,
                "pick": "Над 2.5 гола",
                "probability": round(over25, 1),
                "accuracy": 0.0,
            }
        )

    combos: list[dict] = []
    if btts is not None and over25 is not None:
        combos = _combo_markets(
            match["home"],
            match["away"],
            probs[0],
            probs[1],
            probs[2],
            btts,
            over25,
            over15,
            over35,
        )
    recommended = [row for row in combos if row["recommended"]]
    extra_label, extra_pick, extra_prob = _extra_recommendation(
        btts, over25, over35
    )
    agreement = round(
        len([m for m in top_models if float(m["probability"]) >= 50.0])
        / max(1, len(top_models))
        * 100,
        0,
    )

    model_name = f"{DERIVED_MODEL_PREFIX} · " + " + ".join(
        segments or ["квоти"]
    )
    match.update(
        has_prediction=True,
        prediction_note="",
        source=DERIVED_SOURCE,
        source_label=DERIVED_SOURCE_LABEL,
        derived_basis="+".join(basis) or "odds",
        stat_facts=facts[:4],
        model_name=model_name,
        ml_home=probs[0],
        ml_draw=probs[1],
        ml_away=probs[2],
        ml_pick=best[1],
        ml_confidence=round(best[0], 1),
        pick_side=best[2],
        xg_home=round(xg_home, 2) if xg_home is not None else 0.0,
        xg_away=round(xg_away, 2) if xg_away is not None else 0.0,
        poi_home=probs[0],
        poi_draw=probs[1],
        poi_away=probs[2],
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
        best_combo_label=combos[0]["label"] if combos else top_score,
        best_combo_probability=combos[0]["probability"] if combos else 0.0,
        meta_market=meta_market,
        meta_pick=meta_pick,
        meta_confidence=round(meta_confidence, 1),
        meta_odds=meta_odds,
        meta_edge=meta_edge,
        meta_agreement=float(agreement),
        meta_value=_value_label(meta_edge),
    )

    if not match["form_home"] and not match["form_away"] and sources["h2h"]:
        try:
            form_home, form_away = _form_from_h2h(
                sources["h2h"], match["home"], match["away"]
            )
        except Exception as error:
            logging.exception("Unexpected error")
            logging.info(
                f"Формата од H2H не е изведена: {type(error).__name__}"
            )
            form_home, form_away = "", ""
        if form_home or form_away:
            match["form_home"] = form_home
            match["form_away"] = form_away
    return True
