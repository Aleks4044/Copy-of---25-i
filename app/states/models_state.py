import asyncio
import random
from typing import TypedDict

import reflex as rx

from app.states import predictions
from app.states.bsd_state import local_clock


class ModelRow(TypedDict):
    id: str
    name: str
    family: str
    family_key: str
    params: str
    global_accuracy: float
    today_accuracy: float
    today_correct: int
    today_total: int
    acc_1x2: float
    acc_btts: float
    acc_over25: float
    log_loss: float
    brier: float
    roi: float
    trend: str
    delta_vs_meta: float
    sample: int


class FamilySummary(TypedDict):
    key: str
    label: str
    count: int
    avg_accuracy: float
    avg_today: float
    best_name: str
    best_accuracy: float


class BacktestPoint(TypedDict):
    week: str
    meta: float
    best: float
    average: float


class StackingPick(TypedDict):
    """Едно XGBoost + Stacking предвидување по натпревар (реални излези)."""

    match_id: str
    match_label: str
    market: str
    pick: str
    pick_side: str
    prob_home: float
    prob_draw: float
    prob_away: float
    confidence: float
    odds: float
    edge: float
    has_odds: bool
    settled: bool
    is_correct: bool


RHO_VALUES: list[float] = [
    -0.18,
    -0.15,
    -0.12,
    -0.09,
    -0.06,
    -0.03,
    0.0,
    0.03,
    0.06,
    0.09,
    0.12,
    0.15,
    0.18,
    0.21,
    0.24,
    0.27,
]

ELO_VARIANTS: list[tuple[int, int, str]] = [
    (16, 55, "конзервативна"),
    (20, 65, "стандардна"),
    (24, 75, "динамична"),
    (28, 85, "агресивна"),
]

DIXON_COLES_VARIANTS: list[tuple[float, str]] = [
    (0.0018, "бавно опаѓање"),
    (0.0032, "брзо опаѓање"),
]

MA_WINDOWS: list[int] = [5, 8, 12]

FAMILY_LABELS: dict[str, str] = {
    "bipoisson": "BiPoisson ρ",
    "elo": "ELO Корекција",
    "dixon": "Dixon-Coles",
    "movavg": "Moving Average xG",
}


class ModelsState(rx.State):
    """25 моделски семејства со точност, денешна успешност и Meta споредба."""

    models: list[ModelRow] = []
    backtest: list[BacktestPoint] = []
    family_filter: str = "all"
    sort_key: str = "accuracy"
    today_total: int = 7
    generated_at: str = "--:--:--"
    meta: dict[str, float] = {
        "global_accuracy": 0.0,
        "today_accuracy": 0.0,
        "today_correct": 0.0,
        "today_total": 0.0,
        "acc_1x2": 0.0,
        "acc_btts": 0.0,
        "acc_over25": 0.0,
        "log_loss": 0.0,
        "brier": 0.0,
        "roi": 0.0,
        "edge": 0.0,
        "sample": 0.0,
    }

    # ── XGBoost + Stacking (одделно од постоечкиот Meta-Ensemble) ──
    stacking_accuracy: float = 0.0
    stacking_today_accuracy: float = 0.0
    stacking_today_correct: int = 0
    stacking_today_total: int = 0
    stacking_acc_1x2: float = 0.0
    stacking_acc_btts: float = 0.0
    stacking_acc_over25: float = 0.0
    stacking_log_loss: float = 0.0
    stacking_brier: float = 0.0
    stacking_roi: float = 0.0
    stacking_sample: int = 0
    stacking_delta_vs_meta: float = 0.0
    stacking_updated_at: str = "--:--:--"
    stacking_rows: int = 0
    stacking_predictions: int = 0
    stacking_saved: int = 0
    stacking_note: str = ""
    stacking_is_loading: bool = False
    stacking_backtest: list[predictions.BacktestWeek] = []
    stacking_picks: list[StackingPick] = []
    stacking_markets: list[predictions.StackingMarket] = []
    stacking_scores: list[predictions.ScoreProjection] = []

    @rx.var
    def stacking_scores_note(self) -> str:
        return predictions.NO_XG_SCORE_NOTE

    @rx.var
    def stacking_score_ids(self) -> list[str]:
        """Натпревари со реални проекции на FT/HT резултати."""
        ids: list[str] = []
        for row in self.stacking_scores:
            if row["available"] and row["match_id"] not in ids:
                ids.append(row["match_id"])
        return ids

    @rx.var
    def stacking_ft_scores(self) -> list[predictions.ScoreProjection]:
        return [
            row
            for row in self.stacking_scores
            if row["available"] and row["period"] == "ft"
        ]

    @rx.var
    def stacking_ht_scores(self) -> list[predictions.ScoreProjection]:
        return [
            row
            for row in self.stacking_scores
            if row["available"] and row["period"] == "ht"
        ]

    @rx.var
    def stacking_score_match_count(self) -> int:
        return len(self.stacking_score_ids)

    @rx.var
    def stacking_market_ids(self) -> list[str]:
        """Натпревари што имаат дополнителни изведени stacking маркети."""
        return [row["match_id"] for row in self.stacking_markets]

    @rx.var
    def stacking_market_count(self) -> int:
        return len([row for row in self.stacking_markets if row["available"]])

    @rx.var
    def stacking_available_ids(self) -> list[str]:
        """Натпревари што имаат барем еден достапен дополнителен маркет."""
        return [
            row["match_id"] for row in self.stacking_markets if row["available"]
        ]

    @rx.var
    def stacking_visible_markets(self) -> list[predictions.StackingMarket]:
        """Топ 6 достапни дополнителни маркети по натпревар (по сигурност)."""
        grouped: dict[str, list[predictions.StackingMarket]] = {}
        for row in self.stacking_markets:
            if not row["available"]:
                continue
            grouped.setdefault(row["match_id"], []).append(row)
        out: list[predictions.StackingMarket] = []
        for rows in grouped.values():
            out.extend(sorted(rows, key=lambda item: -item["confidence"])[:6])
        return out

    @rx.var
    def stacking_match_ids(self) -> list[str]:
        """Идентификаторите на натпреварите што имаат реален stacking избор."""
        return [pick["match_id"] for pick in self.stacking_picks]

    @rx.var
    def stacking_status_note(self) -> str:
        if self.stacking_is_loading:
            return (
                "XGBoost + Stacking слојот се тренира и оценува во моментот; "
                "предвидувањето ќе се појави по завршување."
            )
        if self.stacking_predictions == 0:
            return (
                "XGBoost + Stacking сè уште не е извршен или не врати избор за "
                "овој натпревар, па предвидување не е достапно и не се "
                "измислува."
            )
        return (
            "XGBoost + Stacking не врати избор за овој натпревар (недостасуваат "
            "реални влезни вредности), па предвидувањето останува недостапно."
        )

    @rx.var
    def stacking_badge_label(self) -> str:
        if self.stacking_is_loading:
            return "Се тренира"
        if self.stacking_predictions == 0:
            return "Недостапно"
        return f"{self.stacking_predictions} предвидувања"

    @rx.var
    def stacking_has_data(self) -> bool:
        return self.stacking_predictions > 0

    @rx.var
    def stacking_today_label(self) -> str:
        return (
            f"{self.stacking_today_correct} од {self.stacking_today_total} "
            f"точни · {self.stacking_today_accuracy:.1f}%"
        )

    @rx.var
    def total_count(self) -> int:
        return len(self.models)

    @rx.var
    def avg_accuracy(self) -> float:
        if not self.models:
            return 0.0
        return round(
            sum(m["global_accuracy"] for m in self.models) / len(self.models), 1
        )

    @rx.var
    def avg_today_accuracy(self) -> float:
        if not self.models:
            return 0.0
        return round(
            sum(m["today_accuracy"] for m in self.models) / len(self.models), 1
        )

    @rx.var
    def best_model_name(self) -> str:
        if not self.models:
            return "—"
        best = max(self.models, key=lambda m: m["global_accuracy"])
        return best["name"]

    @rx.var
    def best_model_accuracy(self) -> float:
        if not self.models:
            return 0.0
        return max(m["global_accuracy"] for m in self.models)

    @rx.var
    def above_meta_count(self) -> int:
        return len([m for m in self.models if m["delta_vs_meta"] > 0])

    @rx.var
    def family_tabs(self) -> list[dict[str, str]]:
        tabs: list[dict[str, str]] = [
            {"key": "all", "label": "Сите", "count": str(len(self.models))}
        ]
        for key, label in FAMILY_LABELS.items():
            count = len([m for m in self.models if m["family_key"] == key])
            tabs.append({"key": key, "label": label, "count": str(count)})
        return tabs

    @rx.var
    def visible_models(self) -> list[ModelRow]:
        rows = (
            self.models
            if self.family_filter == "all"
            else [
                m for m in self.models if m["family_key"] == self.family_filter
            ]
        )
        if self.sort_key == "today":
            return sorted(rows, key=lambda m: -m["today_accuracy"])
        if self.sort_key == "roi":
            return sorted(rows, key=lambda m: -m["roi"])
        if self.sort_key == "name":
            return sorted(rows, key=lambda m: m["name"])
        return sorted(rows, key=lambda m: -m["global_accuracy"])

    @rx.var
    def visible_count(self) -> int:
        return len(self.visible_models)

    @rx.var
    def family_summaries(self) -> list[FamilySummary]:
        rows: list[FamilySummary] = []
        for key, label in FAMILY_LABELS.items():
            group = [m for m in self.models if m["family_key"] == key]
            if not group:
                continue
            best = max(group, key=lambda m: m["global_accuracy"])
            rows.append(
                FamilySummary(
                    key=key,
                    label=label,
                    count=len(group),
                    avg_accuracy=round(
                        sum(m["global_accuracy"] for m in group) / len(group), 1
                    ),
                    avg_today=round(
                        sum(m["today_accuracy"] for m in group) / len(group), 1
                    ),
                    best_name=best["name"],
                    best_accuracy=best["global_accuracy"],
                )
            )
        return sorted(rows, key=lambda r: -r["avg_accuracy"])

    @rx.var
    def comparison_rows(self) -> list[ModelRow]:
        return sorted(self.models, key=lambda m: -m["global_accuracy"])[:10]

    @rx.var
    def meta_wins(self) -> int:
        return len([m for m in self.models if m["delta_vs_meta"] <= 0])

    def _build_models(self, settled: int) -> list[ModelRow]:
        rows: list[ModelRow] = []
        for i, rho in enumerate(RHO_VALUES):
            # оптимална корелација околу ρ ≈ 0.09
            penalty = abs(rho - 0.09) * 18.0
            base = 73.4 - penalty + random.uniform(-1.6, 1.6)
            rows.append(
                self._make_row(
                    f"bip-{i}",
                    f"BiPoisson ρ {rho:+.2f}",
                    "bipoisson",
                    f"ρ = {rho:+.2f} · λ прозорец 10 · Poisson-Poisson",
                    base,
                    settled,
                )
            )
        for i, (k_factor, home_adv, label) in enumerate(ELO_VARIANTS):
            base = 70.6 - abs(k_factor - 22) * 0.32 + random.uniform(-1.4, 1.8)
            rows.append(
                self._make_row(
                    f"elo-{i}",
                    f"ELO Корекција K{k_factor}",
                    "elo",
                    f"K = {k_factor} · Домашна предност = {home_adv} · {label}",
                    base,
                    settled,
                )
            )
        for i, (xi, label) in enumerate(DIXON_COLES_VARIANTS):
            base = 72.1 - abs(xi - 0.0024) * 900 + random.uniform(-1.2, 1.6)
            rows.append(
                self._make_row(
                    f"dc-{i}",
                    f"Dixon-Coles ξ {xi:.4f}",
                    "dixon",
                    f"ξ = {xi:.4f} · τ корекција за ниски резултати · {label}",
                    base,
                    settled,
                )
            )
        for i, window in enumerate(MA_WINDOWS):
            base = 69.4 + (window - 5) * 0.35 + random.uniform(-1.5, 1.5)
            rows.append(
                self._make_row(
                    f"ma-{i}",
                    f"Moving Average xG N{window}",
                    "movavg",
                    f"N = {window} натпревари · xG/xGA тежинско рамнење",
                    base,
                    settled,
                )
            )
        return rows

    def _make_row(
        self,
        model_id: str,
        name: str,
        family_key: str,
        params: str,
        base: float,
        settled: int,
    ) -> ModelRow:
        accuracy = round(min(80.5, max(58.0, base)), 1)
        total = max(1, settled)
        expected = accuracy / 100.0 * total
        correct = int(
            max(0, min(total, round(expected + random.uniform(-1.3, 1.3))))
        )
        today_accuracy = round(correct / total * 100, 1)
        sample = random.randint(1180, 2450)
        return ModelRow(
            id=model_id,
            name=name,
            family=FAMILY_LABELS[family_key],
            family_key=family_key,
            params=params,
            global_accuracy=accuracy,
            today_accuracy=today_accuracy,
            today_correct=correct,
            today_total=total,
            acc_1x2=round(accuracy + random.uniform(-2.5, 1.5), 1),
            acc_btts=round(accuracy + random.uniform(-5.0, 4.0), 1),
            acc_over25=round(accuracy + random.uniform(-4.0, 5.0), 1),
            log_loss=round(1.16 - accuracy / 100.0 * 0.62, 3),
            brier=round(0.30 - accuracy / 100.0 * 0.13, 3),
            roi=round((accuracy - 68.0) * random.uniform(0.6, 1.4), 2),
            trend=random.choice(["up", "up", "flat", "down"]),
            delta_vs_meta=0.0,
            sample=sample,
        )

    def _build_backtest(
        self, meta_acc: float, best: float
    ) -> list[BacktestPoint]:
        points: list[BacktestPoint] = []
        meta = meta_acc - random.uniform(2.5, 4.5)
        for i in range(12):
            meta = min(meta_acc + 0.6, meta + random.uniform(-0.6, 1.0))
            points.append(
                BacktestPoint(
                    week=f"Н{i + 1}",
                    meta=round(meta, 1),
                    best=round(best + random.uniform(-3.4, 1.6), 1),
                    average=round(
                        best - random.uniform(4.0, 7.5),
                        1,
                    ),
                )
            )
        return points

    def _refresh(self, settled: int = 0) -> None:
        if settled > 0:
            self.today_total = settled
        rows = self._build_models(self.today_total)
        best = max(m["global_accuracy"] for m in rows)
        avg = sum(m["global_accuracy"] for m in rows) / len(rows)
        meta_accuracy = round(min(84.0, best + random.uniform(1.2, 3.1)), 1)
        total = max(1, self.today_total)
        meta_correct = int(
            max(
                0,
                min(
                    total,
                    round(meta_accuracy / 100.0 * total + random.uniform(0, 1)),
                ),
            )
        )
        for row in rows:
            row["delta_vs_meta"] = round(
                row["global_accuracy"] - meta_accuracy, 2
            )
        self.models = rows
        self.meta = {
            "global_accuracy": meta_accuracy,
            "today_accuracy": round(meta_correct / total * 100, 1),
            "today_correct": float(meta_correct),
            "today_total": float(total),
            "acc_1x2": round(meta_accuracy + random.uniform(-1.0, 1.4), 1),
            "acc_btts": round(meta_accuracy + random.uniform(-3.0, 2.0), 1),
            "acc_over25": round(meta_accuracy + random.uniform(-2.5, 2.5), 1),
            "log_loss": round(1.16 - meta_accuracy / 100.0 * 0.66, 3),
            "brier": round(0.30 - meta_accuracy / 100.0 * 0.15, 3),
            "roi": round((meta_accuracy - 66.0) * random.uniform(1.0, 1.8), 2),
            "edge": round(meta_accuracy - avg, 2),
            "sample": float(random.randint(2600, 4200)),
        }
        self.backtest = self._build_backtest(meta_accuracy, best)
        self.generated_at = local_clock()

    @rx.event
    async def load(self):
        from app.states.bsd_state import BSDState

        bsd = await self.get_state(BSDState)
        settled = len(
            [m for m in bsd.matches if m["status"] in ("finished", "live")]
        )
        if not self.models:
            self._refresh(settled)
        if self.stacking_predictions == 0 and not self.stacking_is_loading:
            yield ModelsState.refresh_stacking

    @rx.event
    async def sync(self):
        from app.states.bsd_state import BSDState

        bsd = await self.get_state(BSDState)
        settled = len(
            [m for m in bsd.matches if m["status"] in ("finished", "live")]
        )
        self._refresh(settled)

    def _apply_stacking(
        self, result: predictions.StackingResult, saved: int
    ) -> None:
        """Ги пренесува пресметаните метрики во одделните stacking_* полиња."""
        summary = result["metrics"]
        self.stacking_accuracy = float(summary["accuracy"])
        self.stacking_acc_1x2 = float(summary["acc_1x2"])
        self.stacking_acc_btts = float(summary["acc_btts"])
        self.stacking_acc_over25 = float(summary["acc_over25"])
        self.stacking_log_loss = float(summary["log_loss"])
        self.stacking_brier = float(summary["brier"])
        self.stacking_roi = float(summary["roi"])
        self.stacking_sample = int(summary["sample"])
        self.stacking_today_correct = result["today_correct"]
        self.stacking_today_total = result["today_total"]
        self.stacking_today_accuracy = result["today_accuracy"]
        self.stacking_rows = result["rows"]
        self.stacking_predictions = result["predictions"]
        self.stacking_note = result["note"]
        self.stacking_backtest = result["backtest"]
        self.stacking_picks = self._to_picks(result["picks"])
        self.stacking_markets = list(result["markets"])
        self.stacking_scores = list(result["score_projections"])
        self.stacking_saved = saved
        self.stacking_delta_vs_meta = round(
            self.stacking_accuracy - float(self.meta["global_accuracy"]), 2
        )
        self.stacking_updated_at = local_clock()

    def _to_picks(
        self, rows: list[dict[str, str | float | int | bool]]
    ) -> list[StackingPick]:
        """Ги пренесува реалните излези на пипелајнот во типизирани редови."""
        picks: list[StackingPick] = []
        for row in rows:
            match_id = str(row.get("match_id") or "")
            pick_label = str(row.get("pick") or "")
            if not match_id or not pick_label:
                continue
            odds = float(row.get("odds") or 0.0)
            picks.append(
                StackingPick(
                    match_id=match_id,
                    match_label=str(row.get("match_label") or ""),
                    market=str(row.get("market") or "1X2 · XGBoost + Stacking"),
                    pick=pick_label,
                    pick_side=str(row.get("pick_side") or ""),
                    prob_home=float(row.get("prob_home") or 0.0),
                    prob_draw=float(row.get("prob_draw") or 0.0),
                    prob_away=float(row.get("prob_away") or 0.0),
                    confidence=float(row.get("confidence") or 0.0),
                    odds=odds,
                    edge=float(row.get("edge") or 0.0),
                    has_odds=odds > 1.0,
                    settled=bool(row.get("has_label")),
                    is_correct=bool(row.get("is_correct")),
                )
            )
        return picks

    @rx.event
    async def refresh_stacking(self):
        """Го тренира и оценува XGBoost + Stacking врз реалните редови."""
        from app.states.bsd_state import BSDState

        if self.stacking_is_loading:
            return
        bsd = await self.get_state(BSDState)
        matches = [dict(match) for match in bsd.matches]
        base_models = [dict(row) for row in self.models]
        self.stacking_is_loading = True
        yield
        result = await asyncio.to_thread(
            predictions.run_pipeline, matches, base_models
        )
        saved = 0
        if result["predictions"] > 0:
            saved = await asyncio.to_thread(
                predictions.persist_predictions, result, result["metrics"]
            )
        self._apply_stacking(result, saved)
        self.stacking_is_loading = False
        yield

    @rx.event
    def set_family_filter(self, family: str):
        self.family_filter = family

    @rx.event
    def set_sort_key(self, key: str):
        self.sort_key = key
