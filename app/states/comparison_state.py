"""Споредба: BZZ API предвидувања наспроти Fotmob предвидувања.

Се користат само реални податоци: BZZ предвидувањето од API-то и Fotmob
предвидувањето пресметано од вистински Fotmob статистики. Ако Fotmob не може
да се совпадне, редот воопшто не се создава.
"""

from typing import TypedDict

import reflex as rx

from app.states.bsd_state import (
    BSDMatch,
    BSDState,
    ShadowPick,
    local_clock,
)


class ComparisonRow(TypedDict):
    id: str
    match_label: str
    league: str
    kickoff: str
    status: str
    score: str
    settled: bool
    bzz_pick: str
    bzz_side: str
    bzz_confidence: float
    bzz_edge: float
    bzz_market: str
    fm_pick: str
    fm_side: str
    fm_confidence: float
    fm_edge: float
    fm_market: str
    agree: bool
    winner: str
    winner_label: str
    verdict_label: str


def _actual_side(score: str) -> str:
    parts = score.split("-")
    if len(parts) != 2:
        return ""
    try:
        home = int(parts[0].strip())
        away = int(parts[1].strip())
    except ValueError:
        return ""
    if home > away:
        return "home"
    if away > home:
        return "away"
    return "draw"


class ComparisonState(rx.State):
    """Редови за споредба, филтри и агрегати."""

    rows_cache: list[ComparisonRow] = []
    generated_at: str = "--:--:--"
    notice: str = ""
    error: str = ""
    filter_mode: str = "all"
    sort_key: str = "confidence"

    def _build(
        self,
        matches: list[BSDMatch],
        shadows: list[ShadowPick],
        generated_at: str,
    ) -> None:
        by_id: dict[str, ShadowPick] = {s["match_id"]: s for s in shadows}
        rows: list[ComparisonRow] = []
        for match in matches:
            shadow = by_id.get(match["id"])
            if shadow is None or not match["has_prediction"]:
                continue
            bzz_side = match["pick_side"]
            fm_side = shadow["ml_side"]
            agree = bool(bzz_side) and bzz_side == fm_side
            settled = match["status"] == "finished"
            actual = _actual_side(match["score"]) if settled else ""
            winner = "tie"
            winner_label = "Изедначено"
            verdict = "Лидер по сигурност"
            if settled and actual:
                verdict = "Решено по резултат"
                bzz_ok = bzz_side == actual
                fm_ok = fm_side == actual
                if bzz_ok and not fm_ok:
                    winner, winner_label = "bzz", "BZZ API точно"
                elif fm_ok and not bzz_ok:
                    winner, winner_label = "fotmob", "Fotmob точно"
                elif bzz_ok and fm_ok:
                    winner, winner_label = "tie", "Двата точни"
                else:
                    winner, winner_label = "none", "Двата погрешни"
            else:
                if match["meta_confidence"] > shadow["meta_confidence"]:
                    winner, winner_label = "bzz", "BZZ повисока сигурност"
                elif shadow["meta_confidence"] > match["meta_confidence"]:
                    winner, winner_label = "fotmob", "Fotmob повисока сигурност"
                else:
                    winner, winner_label = "tie", "Иста сигурност"
            rows.append(
                ComparisonRow(
                    id=match["id"],
                    match_label=f"{match['home']} — {match['away']}",
                    league=match["league"],
                    kickoff=match["kickoff"],
                    status=match["status"],
                    score=match["score"],
                    settled=settled and bool(actual),
                    bzz_pick=match["meta_pick"],
                    bzz_side=bzz_side,
                    bzz_confidence=match["meta_confidence"],
                    bzz_edge=match["meta_edge"],
                    bzz_market=match["meta_market"],
                    fm_pick=shadow["meta_pick"],
                    fm_side=fm_side,
                    fm_confidence=shadow["meta_confidence"],
                    fm_edge=shadow["meta_edge"],
                    fm_market=shadow["meta_market"],
                    agree=agree,
                    winner=winner,
                    winner_label=winner_label,
                    verdict_label=verdict,
                )
            )
        self.rows_cache = rows
        self.generated_at = generated_at or local_clock()

    @rx.var
    def filtered_rows(self) -> list[ComparisonRow]:
        rows = list(self.rows_cache)
        if self.filter_mode == "agree":
            rows = [r for r in rows if r["agree"]]
        elif self.filter_mode == "disagree":
            rows = [r for r in rows if not r["agree"]]
        elif self.filter_mode == "settled":
            rows = [r for r in rows if r["settled"]]
        if self.sort_key == "edge":
            return sorted(rows, key=lambda r: -max(r["bzz_edge"], r["fm_edge"]))
        if self.sort_key == "match":
            return sorted(rows, key=lambda r: r["match_label"])
        return sorted(
            rows,
            key=lambda r: -max(r["bzz_confidence"], r["fm_confidence"]),
        )

    @rx.var
    def total_count(self) -> int:
        return len(self.rows_cache)

    @rx.var
    def visible_count(self) -> int:
        return len(self.filtered_rows)

    @rx.var
    def agree_count(self) -> int:
        return len([r for r in self.rows_cache if r["agree"]])

    @rx.var
    def disagree_count(self) -> int:
        return len([r for r in self.rows_cache if not r["agree"]])

    @rx.var
    def settled_count(self) -> int:
        return len([r for r in self.rows_cache if r["settled"]])

    @rx.var
    def bzz_wins(self) -> int:
        return len(
            [
                r
                for r in self.rows_cache
                if r["settled"] and r["winner"] == "bzz"
            ]
        )

    @rx.var
    def fotmob_wins(self) -> int:
        return len(
            [
                r
                for r in self.rows_cache
                if r["settled"] and r["winner"] == "fotmob"
            ]
        )

    @rx.var
    def agreement_rate(self) -> float:
        if not self.rows_cache:
            return 0.0
        return round(self.agree_count / len(self.rows_cache) * 100, 1)

    @rx.var
    def avg_bzz_confidence(self) -> float:
        if not self.rows_cache:
            return 0.0
        return round(
            sum(r["bzz_confidence"] for r in self.rows_cache)
            / len(self.rows_cache),
            1,
        )

    @rx.var
    def avg_fotmob_confidence(self) -> float:
        if not self.rows_cache:
            return 0.0
        return round(
            sum(r["fm_confidence"] for r in self.rows_cache)
            / len(self.rows_cache),
            1,
        )

    @rx.var
    def filter_tabs(self) -> list[dict[str, str]]:
        return [
            {
                "key": "all",
                "label": "Сите",
                "count": str(self.total_count),
            },
            {
                "key": "agree",
                "label": "Согласни",
                "count": str(self.agree_count),
            },
            {
                "key": "disagree",
                "label": "Различни",
                "count": str(self.disagree_count),
            },
            {
                "key": "settled",
                "label": "Решени",
                "count": str(self.settled_count),
            },
        ]

    @rx.var
    def has_data(self) -> bool:
        return len(self.rows_cache) > 0

    @rx.event
    async def sync(self):
        bsd = await self.get_state(BSDState)
        self.error = bsd.error
        self.notice = bsd.compare_notice
        self._build(bsd.matches, bsd.fotmob_shadows, bsd.generated_at)

    @rx.event
    async def load(self):
        yield ComparisonState.sync

    @rx.event
    def set_filter_mode(self, mode: str):
        self.filter_mode = mode

    @rx.event
    def set_sort_key(self, key: str):
        self.sort_key = key
