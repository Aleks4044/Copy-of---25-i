"""Читање на реалните BZZ подресурси по настан (панел со детали за извор).

Се користат САМО автентицираните, документирани патеки:

  /api/v2/events/{id}/summary/
  /api/v2/events/{id}/lineups/
  /api/v2/events/{id}/prediction/
  /api/v2/events/{id}/odds/
  /api/v2/events/{id}/money/
  /api/v2/events/{id}/stats/
  /api/v2/events/{id}/h2h/

Секој одговор се чита тивко: 404 / 429 / timeout стануваат ознака за статус
и забелешка, никогаш исклучок. Ниту една вредност не се измислува — фактите
се исклучиво она што ресурсот навистина го вратил. Ниту еден клуч не се
логира.
"""

import logging
from typing import TypedDict

from app.states import api_client, bzz_derived


class EndpointRow(TypedDict):
    key: str
    label: str
    path: str
    status_code: int
    status_label: str
    status_kind: str
    available: bool
    capability: str
    facts: list[str]


class SourcePanel(TypedDict):
    match_id: str
    event_id: int
    match_label: str
    fetched_at: str
    endpoints: list[EndpointRow]
    available_count: int
    total_count: int
    has_any: bool
    note: str


CAPABILITIES: dict[str, str] = {
    "summary": (
        "Ако врати реални полиња: текст/резиме, просечни голови или "
        "веројатности што можат да се употребат за изведено предвидување."
    ),
    "lineups": (
        "Дава состави и број отсутни играчи по страна — се користи само како "
        "мала корекција на веројатностите, не како самостојно предвидување."
    ),
    "prediction": (
        "Официјално BZZ предвидување: 1/X/2 веројатности, ГГ, Над/Под и "
        "препораки — кога постои, тоа се прикажува како официјално."
    ),
    "odds": (
        "Реални квоти 1/X/2, линии за голови и ГГ → имплицирани веројатности "
        "1/X/2, Над/Под 1.5/2.5/3.5 и ГГ (без маржа)."
    ),
    "money": (
        "Распоред на пари 1/X/2 ако е објавен — се меша со имплицираните "
        "веројатности од квотите."
    ),
    "stats": (
        "Статистики на настанот: xG по тим, shotmap и моментум → очекувани "
        "голови и матрица на резултати."
    ),
    "h2h": (
        "Меѓусебни средби: стапки на победи, просечни голови и стапки за ГГ "
        "и Над 2.5 од реални резултати."
    ),
}

ENDPOINT_ORDER: tuple[tuple[str, str], ...] = (
    ("summary", "Summary"),
    ("lineups", "Lineups"),
    ("prediction", "Prediction"),
    ("odds", "Odds"),
    ("money", "Money"),
    ("stats", "Stats"),
    ("h2h", "H2H"),
)

MISSING_KEY_NOTE = (
    "Не е поставен BZZ API клуч, па подресурсите по настан не можат да се "
    "прочитаат."
)
RATE_LIMIT_NOTE = (
    "API-то ограничи дел од барањата (429) при читањето на подресурсите. "
    "Прикажано е само она што стигна да се прочита."
)
EMPTY_NOTE = (
    "Ниту еден подресурс на овој настан не врати податоци (сите одговорија "
    "404 или се недостапни), па нема што да се пресмета и ништо не се "
    "измислува."
)
OK_NOTE = (
    "Прикажани се точно оние полиња што ресурсите навистина ги вратија. "
    "Недостапните ресурси стојат како ознака, без измислен текст."
)


def _status_label(code: int) -> tuple[str, str]:
    """Читлива ознака и вид на статус за приказ (без чувствителни податоци)."""
    if code == 200:
        return "200 · достапно", "ok"
    if code == api_client.MISSING_KEY_STATUS:
        return "нема API клуч", "error"
    if code == api_client.RATE_LIMIT_STATUS:
        return "429 · ограничено", "limited"
    if code == 404:
        return "404 · недостапно", "missing"
    if code == 400:
        return "400 · недостапно", "missing"
    if code == 0:
        return "мрежна грешка / timeout", "error"
    return f"HTTP {code}", "error"


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


def _odds_facts(payload: dict) -> list[str]:
    market = bzz_derived._market_probs(bzz_derived._odds_block(payload))
    facts: list[str] = []
    if "home" in market:
        facts.append(
            "Реални квоти 1/X/2: "
            f"{market.get('odd_home', 0.0):.2f} · "
            f"{market.get('odd_draw', 0.0):.2f} · "
            f"{market.get('odd_away', 0.0):.2f}"
        )
        facts.append(
            "Имплицирани 1/X/2: "
            f"{market['home']:.1f}% · {market['draw']:.1f}% · "
            f"{market['away']:.1f}%"
        )
    for line in ("15", "25", "35"):
        value = market.get(f"over{line}")
        if value is None:
            continue
        label = line[0] + "." + line[1]
        facts.append(
            f"Линија {label}: Над {value:.1f}% · "
            f"Под {max(0.0, 100.0 - value):.1f}%"
        )
    if "btts" in market:
        facts.append(
            f"ГГ / НГ имплицирано: {market['btts']:.1f}% · "
            f"{max(0.0, 100.0 - market['btts']):.1f}%"
        )
    if not facts:
        facts.append(
            "Ресурсот врати одговор, но без употребливи квоти 1/X/2 или линии."
        )
    return facts[:6]


def _h2h_facts(payload: dict) -> list[str]:
    summary = bzz_derived._h2h_summary(payload)
    facts: list[str] = []
    if summary:
        total = int(summary["total"])
        facts.append(
            f"Меѓусебни средби: {total} · "
            f"{int(summary['home_wins'])}-{int(summary['draws'])}-"
            f"{int(summary['away_wins'])}"
        )
        facts.append(
            "Стапки на победи: "
            f"{summary['home_rate']:.1f}% · {summary['draw_rate']:.1f}% · "
            f"{summary['away_rate']:.1f}%"
        )
        if "avg_goals" in summary:
            facts.append(f"Просечни голови: {summary['avg_goals']:.2f}")
        if "btts_rate" in summary:
            facts.append(
                f"ГГ стапка од реални резултати: {summary['btts_rate']:.1f}%"
            )
        if "over25_rate" in summary:
            facts.append(
                f"Над 2.5 стапка од реални резултати: {summary['over25_rate']:.1f}%"
            )
    rows = payload.get("recent_matches")
    if isinstance(rows, list) and rows:
        facts.append(f"Последни меѓусебни редови: {len(rows)}")
    if not facts:
        facts.append("Ресурсот врати одговор без употребливи H2H агрегати.")
    return facts[:6]


def _lineup_facts(payload: dict) -> list[str]:
    gaps = bzz_derived._lineup_gaps(payload)
    facts: list[str] = []
    status = str(gaps.get("status") or "")
    if status:
        facts.append(f"Состојба на составите: {status}")
    if gaps.get("available"):
        facts.append(
            f"Отсутни играчи: {int(gaps['home_missing'])} дома · "
            f"{int(gaps['away_missing'])} во гости"
        )
    beta = payload.get("beta")
    if isinstance(beta, bool):
        facts.append(
            "Ресурсот е означен како beta" if beta else "Стабилен ресурс"
        )
    if not facts:
        facts.append(
            "Ресурсот врати одговор без употребливи податоци за состави."
        )
    return facts[:5]


def _prediction_facts(payload: dict) -> list[str]:
    from app.states.bsd_state import _pick_pct

    facts: list[str] = []
    model = payload.get("model")
    if isinstance(model, dict):
        name = model.get("name") or model.get("version") or model.get("id")
        if name:
            facts.append(f"Модел: {name}")
    elif isinstance(model, str) and model:
        facts.append(f"Модел: {model}")
    markets = payload.get("markets")
    if isinstance(markets, dict) and markets:
        facts.append("Маркети: " + ", ".join(sorted(markets.keys())[:6]))
        result = markets.get("match_result")
        if isinstance(result, dict):
            home = _pick_pct(result, ("prob_home", "home", "home_win", "1"))
            draw = _pick_pct(result, ("prob_draw", "draw", "x", "X"))
            away = _pick_pct(result, ("prob_away", "away", "away_win", "2"))
            if home is not None and draw is not None and away is not None:
                facts.append(
                    f"Официјални 1/X/2: {home:.1f}% · {draw:.1f}% · {away:.1f}%"
                )
    recommendations = payload.get("recommendations")
    if isinstance(recommendations, list) and recommendations:
        facts.append(f"Препораки од API-то: {len(recommendations)}")
    elif isinstance(recommendations, dict) and recommendations:
        facts.append("Препорака од API-то: 1")
    if not facts:
        facts.append("Ресурсот врати одговор без употребливи маркети.")
    return facts[:6]


def _money_facts(payload: dict) -> list[str]:
    share = bzz_derived._money_share(payload)
    if share is not None:
        return [
            "Распоред на пари 1/X/2: "
            f"{share[0]:.1f}% · {share[1]:.1f}% · {share[2]:.1f}%"
        ]
    return [
        "Ресурсот врати одговор, но без употреблив распоред на пари 1/X/2, "
        "па ништо не се пресметува од него."
    ]


def _stats_facts(payload: dict) -> list[str]:
    from app.states.bsd_state import _xg_from_stats

    facts: list[str] = []
    xg_home, xg_away = _xg_from_stats(payload)
    if xg_home is not None and xg_away is not None:
        facts.append(
            f"xG по тим: {xg_home:.2f} — {xg_away:.2f} · "
            f"вкупно {xg_home + xg_away:.2f}"
        )
    block = payload.get("stats")
    if isinstance(block, dict):
        home = block.get("home")
        if isinstance(home, dict) and home:
            facts.append(
                "Статистички полиња: " + ", ".join(sorted(home.keys())[:6])
            )
    shotmap = payload.get("shotmap")
    if isinstance(shotmap, list) and shotmap:
        facts.append(f"Shotmap записи: {len(shotmap)}")
    momentum = payload.get("momentum")
    if isinstance(momentum, list) and momentum:
        facts.append(f"Моментум точки: {len(momentum)}")
    if not facts:
        facts.append("Ресурсот врати одговор без употребливи статистики.")
    return facts[:6]


def _summary_facts(payload: dict) -> list[str]:
    facts: list[str] = []
    for key, value in payload.items():
        if len(facts) >= 6:
            break
        if isinstance(value, bool):
            continue
        if isinstance(value, str) and value.strip():
            text = " ".join(value.split())
            facts.append(f"{key}: {text[:120]}")
            continue
        number = _num(value)
        if number is not None:
            facts.append(f"{key}: {number:.2f}")
    if not facts:
        facts.append(
            "Ресурсот врати одговор без текстуални или бројни полиња што "
            "можат да се употребат."
        )
    return facts


FACT_BUILDERS = {
    "summary": _summary_facts,
    "lineups": _lineup_facts,
    "prediction": _prediction_facts,
    "odds": _odds_facts,
    "money": _money_facts,
    "stats": _stats_facts,
    "h2h": _h2h_facts,
}


def _empty_endpoint(key: str, label: str, path: str) -> EndpointRow:
    return EndpointRow(
        key=key,
        label=label,
        path=path,
        status_code=0,
        status_label="не е побарано",
        status_kind="missing",
        available=False,
        capability=CAPABILITIES[key],
        facts=[],
    )


def fetch_panel(event_id: int, match_id: str, match_label: str) -> SourcePanel:
    """Ги чита сите подресурси на настанот. Никогаш не крева исклучок."""
    from app.states.bsd_state import local_clock

    rows: list[EndpointRow] = []
    limited = False
    missing_key = False
    for key, label in ENDPOINT_ORDER:
        path = f"/events/{event_id}/{key}/"
        row = _empty_endpoint(key, label, path)
        if event_id <= 0:
            row["status_label"] = "нема ID на настан"
            row["status_kind"] = "error"
            rows.append(row)
            continue
        payload, status = api_client.get_optional_dict(path)
        row["status_code"] = status
        row["status_label"], row["status_kind"] = _status_label(status)
        if status == api_client.RATE_LIMIT_STATUS:
            limited = True
        if status == api_client.MISSING_KEY_STATUS:
            missing_key = True
        if status == 200 and payload:
            row["available"] = True
            try:
                row["facts"] = FACT_BUILDERS[key](payload)
            except Exception as error:
                logging.exception("Unexpected error")
                logging.info(
                    f"Фактите за {key} не се изведени: {type(error).__name__}"
                )
                row["facts"] = [
                    "Одговорот е примен, но не можеше да се прочита безбедно."
                ]
        elif status == 200:
            row["status_label"] = "200 · празен одговор"
            row["status_kind"] = "missing"
        rows.append(row)

    available = len([row for row in rows if row["available"]])
    if missing_key:
        note = MISSING_KEY_NOTE
    elif limited:
        note = RATE_LIMIT_NOTE
    elif available == 0:
        note = EMPTY_NOTE
    else:
        note = OK_NOTE

    return SourcePanel(
        match_id=match_id,
        event_id=event_id,
        match_label=match_label,
        fetched_at=local_clock(),
        endpoints=rows,
        available_count=available,
        total_count=len(rows),
        has_any=available > 0,
        note=note,
    )
