"""XGBoost + Stacking предвидувачки слој врз веќе вчитаните реални редови.

Сè што се користи тука доаѓа од вистински податоци кои апликацијата веќе ги
има (BZZ/Fotmob натпревари и излезите на 25-те постоечки модели). Ако нема
доволно решени натпревари, моделот се тренира на безбеден резервен
(синтетички) сет САМО за да може да даде калибрирани веројатности, што е
јасно означено во забелешката.
"""

import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier

from app.states import metrics

MODEL_NAME = "XGBoost_Stacking"
MODEL_VERSION = "xgb1-stack1"
MIN_TRAIN_ROWS = 24
BACKTEST_WEEKS = 12
FEATURE_COUNT = 16

FALLBACK_NOTE = (
    "Немаше доволно решени натпревари, па XGBoost + Stacking е тренирано на "
    "безбеден резервен сет; метриките се пресметани само од реалните редови."
)
NO_ROWS_NOTE = (
    "Нема реални натпревари со предвидување, па XGBoost + Stacking не може да "
    "даде излез."
)
TRAINED_NOTE = (
    "XGBoost е тренирано на {rows} решени натпревари, а stacking слојот врз "
    "излезите од {models} постоечки модели."
)


class StackRow(TypedDict):
    """Еден подготвен ред: карактеристики, база и (по потреба) исход."""

    match_id: str
    match_label: str
    home: str
    away: str
    league: str
    kickoff: str
    status: str
    source: str
    market: str
    odds: float
    features: list[float]
    base_probs: list[float]
    btts_prob: float
    over15_prob: float
    over25_prob: float
    over35_prob: float
    expected_goals: float
    label: int
    has_label: bool
    btts_outcome: bool
    over25_outcome: bool
    score: str


class BacktestWeek(TypedDict):
    week: str
    accuracy: float
    roi: float
    log_loss: float


def _model_path() -> Path:
    """Локација за зачувување на моделот (директориум за прикачувања)."""
    try:
        import reflex as rx

        base = Path(rx.get_upload_dir())
    except Exception as error:
        logging.exception(f"Error: недостапен upload dir: {error}")
        base = Path(".cache")
    base.mkdir(parents=True, exist_ok=True)
    return base / "xgb_stacking.joblib"


def _num(value: object, default: float = 0.0) -> float:
    """Дефанзивно читање на бројна вредност од редот на изворот."""
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().replace("%", ""))
        except ValueError:
            return default
    return default


def _score_parts(score: str) -> tuple[int, int] | None:
    """Голови од реален резултат („2 - 1“); None кога не е одигран."""
    parts = (score or "").replace(":", "-").split("-")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0].strip()), int(parts[1].strip())
    except ValueError:
        return None


def _label_from_score(score: str) -> int | None:
    """0 = домашен, 1 = реми, 2 = гостин; None кога нема резултат."""
    parts = _score_parts(score)
    if parts is None:
        return None
    home, away = parts
    if home > away:
        return 0
    if home == away:
        return 1
    return 2


def base_probabilities(
    match: dict, models: list[dict]
) -> tuple[list[float], int]:
    """Просечни 1X2 веројатности од излезите на постоечките 25 модели.

    Секој постоечки модел ја „изострува“ основната веројатност на натпреварот
    според своја вистинска глобална точност (повисока точност → поостар
    излез). Тоа е детерминистичка трансформација на реални вредности, без
    случајност.
    """
    probs = np.array(
        [
            max(0.5, _num(match.get("ml_home"))),
            max(0.5, _num(match.get("ml_draw"))),
            max(0.5, _num(match.get("ml_away"))),
        ],
        dtype=float,
    )
    probs = probs / probs.sum()
    usable = [
        _num(row.get("global_accuracy"))
        for row in models
        if _num(row.get("global_accuracy")) > 0.0
    ]
    if not usable:
        return [round(float(v) * 100.0, 3) for v in probs], 0
    stacked = np.zeros(3, dtype=float)
    for accuracy in usable:
        power = max(0.6, min(1.6, accuracy / 70.0))
        sharpened = probs**power
        stacked += sharpened / sharpened.sum()
    stacked /= len(usable)
    return [round(float(v) * 100.0, 3) for v in stacked], len(usable)


def build_row(match: dict, models: list[dict]) -> StackRow | None:
    """Инженеринг на карактеристики од еден вистински натпревар."""
    if not match.get("has_prediction"):
        return None
    base, _count = base_probabilities(match, models)
    ml_home = _num(match.get("ml_home"))
    ml_draw = _num(match.get("ml_draw"))
    ml_away = _num(match.get("ml_away"))
    if ml_home + ml_draw + ml_away <= 0.0:
        return None
    xg_home = _num(match.get("xg_home"))
    xg_away = _num(match.get("xg_away"))
    btts = _num(match.get("poi_btts"))
    over25 = _num(match.get("poi_over25"))
    over15 = _num(match.get("poi_over15"))
    over35 = _num(match.get("poi_over35"))
    expected = _num(match.get("expected_goals"))
    features = [
        ml_home,
        ml_draw,
        ml_away,
        ml_home - ml_away,
        max(ml_home, ml_draw, ml_away),
        base[0],
        base[1],
        base[2],
        xg_home,
        xg_away,
        xg_home - xg_away,
        expected,
        btts,
        over15,
        over25,
        over35,
    ]
    label = _label_from_score(match.get("score") or "")
    parts = _score_parts(match.get("score") or "")
    return StackRow(
        match_id=str(match.get("id") or ""),
        match_label=f"{match.get('home') or ''} — {match.get('away') or ''}",
        home=str(match.get("home") or ""),
        away=str(match.get("away") or ""),
        league=str(match.get("league") or ""),
        kickoff=str(match.get("kickoff") or ""),
        status=str(match.get("status") or ""),
        source=str(match.get("source") or ""),
        market="1X2 · XGBoost + Stacking",
        odds=_num(match.get("meta_odds")),
        features=[round(float(value), 3) for value in features],
        base_probs=base,
        btts_prob=btts,
        over15_prob=over15,
        over25_prob=over25,
        over35_prob=over35,
        expected_goals=expected,
        label=int(label) if label is not None else -1,
        has_label=label is not None,
        btts_outcome=bool(parts and parts[0] > 0 and parts[1] > 0),
        over25_outcome=bool(parts and (parts[0] + parts[1]) > 2),
        score=str(match.get("score") or ""),
    )


def build_rows(matches: list[dict], models: list[dict]) -> list[StackRow]:
    """Ги подготвува сите употребливи редови од реалните натпревари."""
    rows: list[StackRow] = []
    for match in matches:
        row = build_row(match, models)
        if row is not None:
            rows.append(row)
    return rows


def _synthetic_dataset(size: int = 240) -> tuple[np.ndarray, np.ndarray]:
    """Резервен сет за безбедно тренирање кога нема решени натпревари."""
    rng = np.random.default_rng(42)
    features = rng.normal(loc=40.0, scale=18.0, size=(size, FEATURE_COUNT))
    signal = (
        features[:, 0] - features[:, 2] + 0.4 * features[:, 10]
    ) / 25.0 + rng.normal(scale=0.6, size=size)
    labels = np.where(signal > 0.6, 0, np.where(signal < -0.6, 2, 1))
    return features, labels.astype(int)


class StackingPredictor:
    """XGBoost веројатносен модел со stacking слој врз базните модели."""

    def __init__(self) -> None:
        self.xgb: XGBClassifier | None = None
        self.meta: LogisticRegression | None = None
        self.trained_rows: int = 0
        self.used_fallback: bool = True

    def _new_xgb(self) -> XGBClassifier:
        return XGBClassifier(
            n_estimators=120,
            max_depth=3,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="multi:softprob",
            num_class=3,
            eval_metric="mlogloss",
            tree_method="hist",
            random_state=42,
            n_jobs=1,
        )

    def fit(self, rows: list[StackRow]) -> None:
        """Тренира XGBoost, а потоа stacking слој врз [xgb | базни модели]."""
        labeled = [row for row in rows if row["has_label"]]
        if len(labeled) >= MIN_TRAIN_ROWS:
            features = np.asarray(
                [row["features"] for row in labeled], dtype=float
            )
            labels = np.asarray([row["label"] for row in labeled], dtype=int)
            self.used_fallback = False
        else:
            features, labels = _synthetic_dataset()
            if labeled:
                features = np.vstack(
                    [
                        features,
                        np.asarray(
                            [row["features"] for row in labeled], dtype=float
                        ),
                    ]
                )
                labels = np.concatenate(
                    [
                        labels,
                        np.asarray(
                            [row["label"] for row in labeled], dtype=int
                        ),
                    ]
                )
            self.used_fallback = True
        if len(set(labels.tolist())) < 3:
            # Без сите три класи XGBoost не може да даде 1X2 излез.
            extra_features, extra_labels = _synthetic_dataset(120)
            features = np.vstack([features, extra_features])
            labels = np.concatenate([labels, extra_labels])
        self.trained_rows = len(labeled)
        model = self._new_xgb()
        model.fit(features, labels)
        self.xgb = model

        xgb_probs = model.predict_proba(features)
        if not self.used_fallback:
            base = (
                np.asarray([row["base_probs"] for row in labeled], dtype=float)
                / 100.0
            )
        else:
            base = xgb_probs.copy()
            if len(base) != len(features):
                base = xgb_probs.copy()
        if len(base) != len(features):
            base = xgb_probs.copy()
        stacked_input = np.hstack([xgb_probs, base])
        meta = LogisticRegression(max_iter=500)
        try:
            meta.fit(stacked_input, labels)
            self.meta = meta
        except Exception as error:
            logging.exception(f"Error: stacking слојот не е трениран: {error}")
            self.meta = None

    def predict_proba(self, rows: list[StackRow]) -> list[list[float]]:
        """Враќа 1X2 веројатности (во проценти) за секој ред."""
        if self.xgb is None or not rows:
            return []
        features = np.asarray([row["features"] for row in rows], dtype=float)
        base = (
            np.asarray([row["base_probs"] for row in rows], dtype=float) / 100.0
        )
        xgb_probs = self.xgb.predict_proba(features)
        probs = xgb_probs
        if self.meta is not None:
            try:
                probs = self.meta.predict_proba(np.hstack([xgb_probs, base]))
            except Exception as error:
                logging.exception(f"Error: stacking предвидување: {error}")
                probs = xgb_probs
        # Дополнително мешање со базните модели за стабилен ансамбл.
        blended = 0.65 * probs + 0.35 * base
        blended = np.clip(blended, 1e-6, 1.0)
        blended = blended / blended.sum(axis=1, keepdims=True)
        return [
            [round(float(value) * 100.0, 1) for value in row] for row in blended
        ]

    def save(self, path: Path | None = None) -> bool:
        """Го запишува моделот со joblib; враќа дали успело."""
        target = path or _model_path()
        try:
            joblib.dump(
                {
                    "xgb": self.xgb,
                    "meta": self.meta,
                    "trained_rows": self.trained_rows,
                    "used_fallback": self.used_fallback,
                    "version": MODEL_VERSION,
                },
                target,
            )
            return True
        except Exception as error:
            logging.exception(f"Error: моделот не е зачуван: {error}")
            return False

    @classmethod
    def load(cls, path: Path | None = None) -> "StackingPredictor | None":
        """Го чита зачуваниот модел; None кога не постои или е невалиден."""
        target = path or _model_path()
        if not target.exists():
            return None
        try:
            payload = joblib.load(target)
        except Exception as error:
            logging.exception(f"Error: моделот не е прочитан: {error}")
            return None
        if not isinstance(payload, dict) or payload.get("xgb") is None:
            return None
        model = cls()
        model.xgb = payload.get("xgb")
        model.meta = payload.get("meta")
        model.trained_rows = int(payload.get("trained_rows") or 0)
        model.used_fallback = bool(payload.get("used_fallback", True))
        return model


def _label_split(labeled: list[StackRow]) -> list[list[StackRow]]:
    """Ги дели решените редови на до 12 псевдо-недели за бектест."""
    if not labeled:
        return []
    weeks = min(BACKTEST_WEEKS, max(1, len(labeled)))
    size = max(1, len(labeled) // weeks)
    buckets: list[list[StackRow]] = []
    for index in range(0, len(labeled), size):
        buckets.append(labeled[index : index + size])
    return buckets[:BACKTEST_WEEKS]


def backtest(rows: list[StackRow]) -> list[BacktestWeek]:
    """Ротирачка симулација низ до 12 „недели“ од достапните решени редови."""
    labeled = [row for row in rows if row["has_label"]]
    buckets = _label_split(labeled)
    out: list[BacktestWeek] = []
    history: list[StackRow] = []
    for index, bucket in enumerate(buckets):
        model = StackingPredictor()
        model.fit(history if history else bucket)
        probs = model.predict_proba(bucket)
        y_true = [row["label"] for row in bucket]
        odds = [row["odds"] for row in bucket]
        summary = metrics.summarize(
            y_true,
            probs,
            odds,
            [row["btts_prob"] for row in bucket],
            [row["btts_outcome"] for row in bucket],
            [row["over25_prob"] for row in bucket],
            [row["over25_outcome"] for row in bucket],
        )
        out.append(
            BacktestWeek(
                week=f"Н{index + 1}",
                accuracy=summary["accuracy"],
                roi=summary["roi"],
                log_loss=summary["log_loss"],
            )
        )
        history.extend(bucket)
    return out


class StackingMarket(TypedDict):
    """Дополнителен маркет изведен САМО од веќе реални вредности."""

    match_id: str
    match_label: str
    group: str
    market: str
    pick: str
    confidence: float
    odds: float
    edge: float
    has_odds: bool
    available: bool
    basis: str


SECOND_LAYER_LABEL = "XGBoost + Stacking · втор слој"
UNAVAILABLE_PICK = "недостапно"
NO_XG_NOTE = "нема очекувани голови од изворот"
NO_LINE_NOTE = "изворот не дава веројатност за оваа линија"


def _poisson_over_pct(lam_total: float, line: int) -> float | None:
    """Poisson изведба за „над линија“ САМО од реални очекувани голови."""
    if lam_total <= 0.0:
        return None
    cumulative = 0.0
    for k in range(line + 1):
        cumulative += math.exp(-lam_total) * lam_total**k / math.factorial(k)
    value = max(0.0, 1.0 - cumulative) * 100.0
    return round(min(97.0, max(2.0, value)), 1)


def _market_row(
    row: StackRow,
    group: str,
    market: str,
    pick: str,
    confidence: float,
    basis: str,
) -> StackingMarket:
    return StackingMarket(
        match_id=row["match_id"],
        match_label=row["match_label"],
        group=group,
        market=market,
        pick=pick,
        confidence=round(max(0.0, min(99.0, confidence)), 1),
        odds=0.0,
        edge=0.0,
        has_odds=False,
        available=True,
        basis=basis,
    )


def _unavailable_row(
    row: StackRow, group: str, market: str, note: str
) -> StackingMarket:
    return StackingMarket(
        match_id=row["match_id"],
        match_label=row["match_label"],
        group=group,
        market=market,
        pick=UNAVAILABLE_PICK,
        confidence=0.0,
        odds=0.0,
        edge=0.0,
        has_odds=False,
        available=False,
        basis=note,
    )


def _binary_row(
    row: StackRow,
    group: str,
    market: str,
    yes_label: str,
    no_label: str,
    probability: float,
    basis: str,
) -> StackingMarket:
    if probability >= 50.0:
        return _market_row(row, group, market, yes_label, probability, basis)
    return _market_row(row, group, market, no_label, 100.0 - probability, basis)


def derive_markets(row: StackRow, probs: list[float]) -> list[StackingMarket]:
    """Дополнителни маркети од stacking 1X2 излезот и реалните веројатности."""
    out: list[StackingMarket] = []
    if len(probs) < 3:
        return out
    btts = float(row["btts_prob"])
    over15 = float(row["over15_prob"])
    over25 = float(row["over25_prob"])
    over35 = float(row["over35_prob"])
    expected = float(row["expected_goals"])

    if btts > 0.0:
        out.append(
            _binary_row(
                row,
                "goals",
                "ГГ / НГ",
                "ГГ · двата тима",
                "НГ · без ГГ",
                btts,
                "од реална ГГ веројатност",
            )
        )
    else:
        out.append(_unavailable_row(row, "goals", "ГГ / НГ", NO_LINE_NOTE))

    for line, value in (("2.5", over25), ("3.5", over35)):
        if value > 0.0:
            out.append(
                _binary_row(
                    row,
                    "goals",
                    f"Над / Под {line}",
                    f"Над {line} гола",
                    f"Под {line} гола",
                    value,
                    "од реална линија на изворот",
                )
            )
        else:
            out.append(
                _unavailable_row(
                    row, "goals", f"Над / Под {line}", NO_LINE_NOTE
                )
            )

    over45 = _poisson_over_pct(expected, 4) if expected > 0.0 else None
    if over45 is not None:
        out.append(
            _binary_row(
                row,
                "goals",
                "Над / Под 4.5",
                "Над 4.5 гола",
                "Под 4.5 гола",
                over45,
                f"Poisson од {expected:.2f} очекувани голови",
            )
        )
    else:
        out.append(_unavailable_row(row, "goals", "Над / Под 4.5", NO_XG_NOTE))

    outcomes = (
        (f"1 · {row['home']}", probs[0]),
        ("X · Реми", probs[1]),
        (f"2 · {row['away']}", probs[2]),
    )
    for line, value in (("1.5", over15), ("2.5", over25)):
        for label, outcome in outcomes:
            market = f"Исход + {line}"
            if value <= 0.0:
                out.append(_unavailable_row(row, "combo", market, NO_LINE_NOTE))
                continue
            out.append(
                _market_row(
                    row,
                    "combo",
                    market,
                    f"{label} и Над {line}",
                    outcome * value / 100.0,
                    "stacking 1X2 × реална гол линија",
                )
            )
            out.append(
                _market_row(
                    row,
                    "combo",
                    market,
                    f"{label} и Под {line}",
                    outcome * max(0.0, 100.0 - value) / 100.0,
                    "stacking 1X2 × реална гол линија",
                )
            )
    return out


class StackingResult(TypedDict):
    metrics: dict[str, float]
    today_correct: int
    today_total: int
    today_accuracy: float
    rows: int
    predictions: int
    note: str
    used_fallback: bool
    backtest: list[BacktestWeek]
    picks: list[dict[str, str | float | int | bool]]
    markets: list[StackingMarket]


def _pick_label(row: StackRow, probs: list[float]) -> tuple[str, str, int]:
    """Ознака и страна на избраниот 1X2 исход."""
    index = int(np.argmax(np.asarray(probs, dtype=float)))
    if index == 0:
        return f"1 · {row['home']}", "home", index
    if index == 1:
        return "X · Реми", "draw", index
    return f"2 · {row['away']}", "away", index


def run_pipeline(matches: list[dict], models: list[dict]) -> StackingResult:
    """Целосен тек: подготовка, тренирање/вчитување, предвидување, метрики."""
    rows = build_rows(matches, models)
    empty = StackingResult(
        metrics={
            "accuracy": 0.0,
            "acc_1x2": 0.0,
            "acc_btts": 0.0,
            "acc_over25": 0.0,
            "log_loss": 0.0,
            "brier": 0.0,
            "roi": 0.0,
            "sample": 0.0,
        },
        today_correct=0,
        today_total=0,
        today_accuracy=0.0,
        rows=0,
        predictions=0,
        note=NO_ROWS_NOTE,
        used_fallback=True,
        backtest=[],
        picks=[],
        markets=[],
    )
    if not rows:
        return empty

    labeled = [row for row in rows if row["has_label"]]
    model = StackingPredictor()
    model.fit(rows)
    model.save()
    if model.xgb is None:
        cached = StackingPredictor.load()
        if cached is None:
            return empty
        model = cached

    probs = model.predict_proba(rows)
    if not probs:
        return empty

    by_id = {row["match_id"]: probs[index] for index, row in enumerate(rows)}
    labeled_probs = [by_id[row["match_id"]] for row in labeled]
    summary = metrics.summarize(
        [row["label"] for row in labeled],
        labeled_probs,
        [row["odds"] for row in labeled],
        [row["btts_prob"] for row in labeled],
        [row["btts_outcome"] for row in labeled],
        [row["over25_prob"] for row in labeled],
        [row["over25_outcome"] for row in labeled],
    )

    today_total = len(labeled)
    today_correct = 0
    for row in labeled:
        _label, _side, index = _pick_label(row, by_id[row["match_id"]])
        if index == row["label"]:
            today_correct += 1
    today_accuracy = (
        round(today_correct / today_total * 100.0, 1) if today_total else 0.0
    )

    picks: list[dict[str, str | float | int | bool]] = []
    markets: list[StackingMarket] = []
    for index, row in enumerate(rows):
        row_probs = probs[index]
        label, side, best = _pick_label(row, row_probs)
        try:
            markets.extend(derive_markets(row, row_probs))
        except Exception as error:
            logging.exception(
                f"Error: дополнителните stacking маркети не се изведени: {error}"
            )
        picks.append(
            {
                "match_id": row["match_id"],
                "match_label": row["match_label"],
                "home": row["home"],
                "away": row["away"],
                "league": row["league"],
                "kickoff": row["kickoff"],
                "status": row["status"],
                "source": row["source"],
                "market": row["market"],
                "pick": label,
                "pick_side": side,
                "prob_home": row_probs[0],
                "prob_draw": row_probs[1],
                "prob_away": row_probs[2],
                "confidence": row_probs[best],
                "odds": row["odds"],
                "edge": round(
                    row_probs[best]
                    - (100.0 / row["odds"] if row["odds"] > 1.0 else 0.0),
                    2,
                ),
                "actual_score": row["score"],
                "has_label": row["has_label"],
                "is_correct": bool(row["has_label"] and best == row["label"]),
            }
        )

    note = (
        FALLBACK_NOTE
        if model.used_fallback
        else TRAINED_NOTE.format(rows=len(labeled), models=len(models))
    )
    return StackingResult(
        metrics=summary,
        today_correct=today_correct,
        today_total=today_total,
        today_accuracy=today_accuracy,
        rows=len(rows),
        predictions=len(picks),
        note=note,
        used_fallback=model.used_fallback,
        backtest=backtest(rows),
        picks=picks,
        markets=markets,
    )


def persist_predictions(
    result: StackingResult, summary: dict[str, float]
) -> int:
    """Ги запишува XGBoost_Stacking предвидувањата во управуваната база."""
    import reflex as rx

    from app.models import Prediction

    written = 0
    try:
        with rx.session() as session:
            for pick in result["picks"]:
                session.add(
                    Prediction(
                        match_id=str(pick["match_id"]),
                        match_label=str(pick["match_label"]),
                        home_team=str(pick["home"]),
                        away_team=str(pick["away"]),
                        league=str(pick["league"]),
                        kickoff=str(pick["kickoff"]),
                        status=str(pick["status"]),
                        source=str(pick["source"]),
                        model_name=MODEL_NAME,
                        model_version=MODEL_VERSION,
                        is_meta=True,
                        market=str(pick["market"]),
                        pick=str(pick["pick"]),
                        pick_side=str(pick["pick_side"]),
                        prob_home=float(pick["prob_home"]),
                        prob_draw=float(pick["prob_draw"]),
                        prob_away=float(pick["prob_away"]),
                        confidence=float(pick["confidence"]),
                        odds=float(pick["odds"]),
                        edge=float(pick["edge"]),
                        accuracy=float(summary.get("accuracy", 0.0)),
                        accuracy_1x2=float(summary.get("acc_1x2", 0.0)),
                        log_loss=float(summary.get("log_loss", 0.0)),
                        brier=float(summary.get("brier", 0.0)),
                        roi=float(summary.get("roi", 0.0)),
                        sample_size=int(summary.get("sample", 0.0)),
                        actual_score=str(pick["actual_score"]),
                        actual_side="",
                        is_correct=(
                            bool(pick["is_correct"])
                            if bool(pick["has_label"])
                            else None
                        ),
                        settled_at=(
                            datetime.now(timezone.utc)
                            if bool(pick["has_label"])
                            else None
                        ),
                    )
                )
                written += 1
            for market in result["markets"]:
                if not market["available"]:
                    continue
                session.add(
                    Prediction(
                        match_id=str(market["match_id"]),
                        match_label=str(market["match_label"]),
                        model_name=MODEL_NAME,
                        model_version=MODEL_VERSION,
                        is_meta=True,
                        market=f"{market['market']} · втор слој",
                        pick=str(market["pick"]),
                        confidence=float(market["confidence"]),
                        odds=float(market["odds"]),
                        edge=float(market["edge"]),
                        accuracy=float(summary.get("accuracy", 0.0)),
                        accuracy_1x2=float(summary.get("acc_1x2", 0.0)),
                        log_loss=float(summary.get("log_loss", 0.0)),
                        brier=float(summary.get("brier", 0.0)),
                        roi=float(summary.get("roi", 0.0)),
                        sample_size=int(summary.get("sample", 0.0)),
                    )
                )
                written += 1
            session.commit()
    except Exception as error:
        logging.exception(f"Error: предвидувањата не се зачувани: {error}")
        return 0
    return written
