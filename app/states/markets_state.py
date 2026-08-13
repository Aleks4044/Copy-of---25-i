from typing import TypedDict

import reflex as rx

from app.states.bsd_state import (
    COMBO_GROUP_LABELS,
    BSDMatch,
    _recommendation_label,
    local_clock,
)

MAX_VISIBLE_ROWS = 60

# Групи за редови од дополнителните извори (Mutating и SportScore). Тие
# доаѓаат од реални проценти/статистики, но НЕ носат квота, па квотата и
# предноста остануваат недостапни.
EXTRA_GROUP_LABELS: dict[str, str] = {
    "source_goals": "Извори · Голови и ГГ",
    "source_outcome": "Извори · Исход",
    "source_double": "Извори · Двоен шанс",
}
ALL_GROUP_LABELS: dict[str, str] = {
    **COMBO_GROUP_LABELS,
    **EXTRA_GROUP_LABELS,
}


def _parse_pct(value: object) -> float | None:
    """Реален процент од ознака на извор; None кога не е објавен."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        cleaned = value.replace("%", "").strip()
        if not cleaned:
            return None
        try:
            number = float(cleaned)
        except ValueError:
            return None
    else:
        return None
    if number <= 0.0 or number > 100.0:
        return None
    return round(number, 1)


# Филтер по конкретен избор во комбинацијата (1, X, 2, Над/Под 1.5 и 2.5).
MARKET_FILTER_LABELS: dict[str, str] = {
    "home": "1 · Домашен",
    "draw": "X · Реми",
    "away": "2 · Гостин",
    "over15": "Над 1.5 гола",
    "under15": "Под 1.5 гола",
    "over25": "Над 2.5 гола",
    "under25": "Под 2.5 гола",
}

# Чиповите за конкретен избор смеат да прикажат САМО чисти директни редови:
# единечен 1X2 исход или гол-линија. Комбинации како „1 и ГГ“, „1X и Над 2.5“
# или двоен шанс НЕ добиваат ознака и затоа не се појавуваат во тие филтри.
DIRECT_MARKET_TAGS: dict[str, str] = {
    "1": "home",
    "x": "draw",
    "2": "away",
    "o15": "over15",
    "u15": "under15",
    "o25": "over25",
    "u25": "under25",
}


def _market_tags(key: str) -> list[str]:
    """Ознака само за чист директен маркет; комбинациите остануваат без."""
    tag = DIRECT_MARKET_TAGS.get(key)
    return [tag] if tag is not None else []


class MarketRow(TypedDict):
    id: str
    match_id: str
    match_label: str
    league: str
    kickoff: str
    status: str
    label: str
    group: str
    group_label: str
    probability: float
    odds: float
    edge: float
    recommended: bool
    recommendation: str
    market_tags: list[str]
    source: str
    source_label: str
    has_odds: bool


class MarketsState(rx.State):
    """Комбинирани маркети од сите натпревари со филтри и статистики."""

    rows_cache: list[MarketRow] = []
    combos_per_match: int = 0
    generated_at: str = "--:--:--"
    group_filter: str = "all"
    status_filter: str = "all"
    match_filter: str = "all"
    market_filter: str = "all"
    sort_key: str = "probability"
    min_probability: float = 40.0
    only_recommended: bool = False
    missing_predictions: int = 0
    error: str = ""

    def _mutating_rows(
        self, rows: list[dict], covered: set[str]
    ) -> list[MarketRow]:
        """Маркети од Mutating страницата за детали (реални проценти).

        Само непокриени настани со реални имена, предвидување и објавени
        проценти. Квота и предност НЕ се измислуваат.
        """
        out: list[MarketRow] = []
        for row in rows:
            if not (
                row.get("has_names")
                and row.get("has_pick")
                and row.get("has_markets")
            ):
                continue
            fixture_id = str(row.get("fixture_id") or "")
            if not fixture_id or fixture_id in covered:
                continue
            kickoff = str(row.get("kickoff") or "")
            if not kickoff or kickoff == "—":
                kickoff = str(row.get("status") or "—")
            match_id = f"mutating-{fixture_id}"
            label = f"{row.get('home') or ''} — {row.get('away') or ''}"
            status = str(row.get("status_kind") or "upcoming")
            for key, market_label, tag in (
                ("btts_label", "ГГ · двата тима", ""),
                ("ng_label", "НГ · без ГГ", ""),
                ("over15_label", "Над 1.5 гола", "over15"),
                ("under15_label", "Под 1.5 гола", "under15"),
                ("over25_label", "Над 2.5 гола", "over25"),
                ("under25_label", "Под 2.5 гола", "under25"),
            ):
                probability = _parse_pct(row.get(key))
                if probability is None:
                    continue
                out.append(
                    MarketRow(
                        id=f"{match_id}-{key}",
                        match_id=match_id,
                        match_label=label,
                        league=str(row.get("league_label") or "—"),
                        kickoff=kickoff,
                        status=status,
                        label=market_label,
                        group="source_goals",
                        group_label=ALL_GROUP_LABELS["source_goals"],
                        probability=probability,
                        odds=0.0,
                        edge=0.0,
                        recommended=probability > 40.0,
                        recommendation=_recommendation_label(probability),
                        market_tags=[tag] if tag else [],
                        source="mutating",
                        source_label="Mutating",
                        has_odds=False,
                    )
                )
        return out

    def _fudbal91_group(self, label: str) -> str:
        """Групата за изведен Fudbal91 ред според самата ознака на опцијата."""
        if label.startswith("Над") or label.startswith("Под"):
            return "source_goals"
        head = label.split(" ")[0].upper()
        if head in ("1X", "12", "X2"):
            return "source_double"
        return "source_outcome"

    def _fudbal91_tag(self, label: str) -> str:
        """Ознака за чист директен избор; комбинациите остануваат без."""
        head = label.split(" ")[0].upper()
        if head == "1":
            return "home"
        if head == "X":
            return "draw"
        if head == "2":
            return "away"
        if label.startswith("Над 2.5"):
            return "over25"
        if label.startswith("Под 2.5"):
            return "under25"
        if label.startswith("Над 1.5"):
            return "over15"
        if label.startswith("Под 1.5"):
            return "under15"
        return ""

    def _fudbal91_rows(self, rows: list[dict]) -> list[MarketRow]:
        """Изведени маркети од јавните просечни квоти на Fudbal91.

        Прикажани се САМО непокриени претстојни настани. Веројатностите се
        имплицирани од просечните квоти (без маржа), а квотата и предноста
        остануваат недостапни — ништо не се измислува.
        """
        out: list[MarketRow] = []
        for row in rows:
            if row.get("covered") or not row.get("is_upcoming"):
                continue
            match_id = str(row.get("id") or "")
            if not match_id:
                continue
            home = str(row.get("home") or "")
            away = str(row.get("away") or "")
            match_label = f"{home} — {away}"
            league = str(row.get("competition") or "—")
            kickoff = str(row.get("kickoff") or "--:--")
            p_home = _parse_pct(row.get("prob_home"))
            p_draw = _parse_pct(row.get("prob_draw"))
            p_away = _parse_pct(row.get("prob_away"))
            p_over = _parse_pct(row.get("prob_over25"))
            p_under = _parse_pct(row.get("prob_under25"))
            entries: list[tuple[str, str, float]] = []
            if p_home is not None:
                entries.append(("1", f"1 · {home}", p_home))
            if p_draw is not None:
                entries.append(("x", "X · Реми", p_draw))
            if p_away is not None:
                entries.append(("2", f"2 · {away}", p_away))
            if p_home is not None and p_draw is not None:
                entries.append(
                    (
                        "dc-1x",
                        "1X · домашен или реми",
                        round(min(99.0, p_home + p_draw), 1),
                    )
                )
            if p_home is not None and p_away is not None:
                entries.append(
                    (
                        "dc-12",
                        "12 · без реми",
                        round(min(99.0, p_home + p_away), 1),
                    )
                )
            if p_draw is not None and p_away is not None:
                entries.append(
                    (
                        "dc-x2",
                        "X2 · реми или гостин",
                        round(min(99.0, p_draw + p_away), 1),
                    )
                )
            if p_over is not None:
                entries.append(("o25", "Над 2.5 гола", p_over))
            if p_under is not None:
                entries.append(("u25", "Под 2.5 гола", p_under))
            seen = {label for _key, label, _prob in entries}
            options = row.get("options")
            if isinstance(options, list):
                for index, option in enumerate(options):
                    if not isinstance(option, dict):
                        continue
                    label = str(option.get("label") or "")
                    probability = _parse_pct(option.get("probability"))
                    if not label or label in seen or probability is None:
                        continue
                    seen.add(label)
                    entries.append((f"top-{index}", label, probability))
            for key, label, probability in entries:
                if probability <= 0.0:
                    continue
                tag = self._fudbal91_tag(label)
                group = self._fudbal91_group(label)
                out.append(
                    MarketRow(
                        id=f"{match_id}-{key}",
                        match_id=match_id,
                        match_label=match_label,
                        league=league,
                        kickoff=kickoff,
                        status="upcoming",
                        label=label,
                        group=group,
                        group_label=ALL_GROUP_LABELS[group],
                        probability=probability,
                        odds=0.0,
                        edge=0.0,
                        recommended=probability > 40.0,
                        recommendation=_recommendation_label(probability),
                        market_tags=[tag] if tag else [],
                        source="fudbal91",
                        source_label="Fudbal91",
                        has_odds=False,
                    )
                )
        return out

    def _sportscore_rows(self, rows: list[dict]) -> list[MarketRow]:
        """Маркети изведени САМО од реални SportScore статистики."""
        out: list[MarketRow] = []
        for row in rows:
            if row.get("covered") or not row.get("has_prediction"):
                continue
            match_id = str(row.get("id") or "")
            if not match_id:
                continue
            label = f"{row.get('home') or ''} — {row.get('away') or ''}"
            league = str(row.get("competition") or "—")
            kickoff = str(row.get("kickoff") or "--:--")
            status = str(row.get("status") or "upcoming")
            confidence = _parse_pct(row.get("meta_confidence"))
            pick = str(row.get("meta_pick") or "")
            if confidence is not None and pick:
                tag = ""
                if pick.startswith("1 ·"):
                    tag = "home"
                elif pick.startswith("2 ·"):
                    tag = "away"
                out.append(
                    MarketRow(
                        id=f"{match_id}-meta",
                        match_id=match_id,
                        match_label=label,
                        league=league,
                        kickoff=kickoff,
                        status=status,
                        label=pick,
                        group="source_outcome",
                        group_label=ALL_GROUP_LABELS["source_outcome"],
                        probability=confidence,
                        odds=0.0,
                        edge=0.0,
                        recommended=confidence > 40.0,
                        recommendation=_recommendation_label(confidence),
                        market_tags=[tag] if tag else [],
                        source="sportscore",
                        source_label="SportScore",
                        has_odds=False,
                    )
                )
            goals_pick = str(row.get("goals_pick") or "")
            goals_confidence = _parse_pct(row.get("goals_confidence"))
            if goals_pick and goals_confidence is not None:
                tag = ""
                if goals_pick.startswith("Над 2.5"):
                    tag = "over25"
                elif goals_pick.startswith("Под 2.5"):
                    tag = "under25"
                out.append(
                    MarketRow(
                        id=f"{match_id}-goals",
                        match_id=match_id,
                        match_label=label,
                        league=league,
                        kickoff=kickoff,
                        status=status,
                        label=goals_pick,
                        group="source_goals",
                        group_label=ALL_GROUP_LABELS["source_goals"],
                        probability=goals_confidence,
                        odds=0.0,
                        edge=0.0,
                        recommended=goals_confidence > 40.0,
                        recommendation=_recommendation_label(goals_confidence),
                        market_tags=[tag] if tag else [],
                        source="sportscore",
                        source_label="SportScore",
                        has_odds=False,
                    )
                )
        return out

    def _build_rows(
        self,
        matches: list[BSDMatch],
        generated_at: str = "",
        mutating_rows: list[dict] | None = None,
        covered: set[str] | None = None,
        sportscore_rows: list[dict] | None = None,
        fudbal91_rows: list[dict] | None = None,
    ) -> None:
        """Ги собира комбинираните маркети од сите реални извори."""
        rows: list[MarketRow] = []
        predicted = [m for m in matches if m["has_prediction"] and m["combos"]]
        self.missing_predictions = len(matches) - len(predicted)
        for match in predicted:
            label = f"{match['home']} — {match['away']}"
            is_fotmob = match["source"] == "fotmob"
            source = "fotmob" if is_fotmob else "bzz"
            source_label = match["source_label"] or (
                "Fotmob" if is_fotmob else "BZZ API"
            )
            for combo in match["combos"]:
                rows.append(
                    MarketRow(
                        id=f"{match['id']}-{combo['key']}",
                        match_id=match["id"],
                        match_label=label,
                        league=match["league"],
                        kickoff=match["kickoff"],
                        status=match["status"],
                        label=combo["label"],
                        group=combo["group"],
                        group_label=combo["group_label"],
                        probability=combo["probability"],
                        odds=combo["odds"],
                        edge=combo["edge"],
                        recommended=combo["recommended"],
                        recommendation=combo["recommendation"],
                        market_tags=_market_tags(combo["key"]),
                        source=source,
                        source_label=source_label,
                        has_odds=combo["odds"] > 1.0,
                    )
                )
        rows.extend(self._mutating_rows(mutating_rows or [], covered or set()))
        rows.extend(self._sportscore_rows(sportscore_rows or []))
        rows.extend(self._fudbal91_rows(fudbal91_rows or []))
        self.rows_cache = rows
        self.combos_per_match = predicted[0]["combo_count"] if predicted else 0
        self.generated_at = generated_at or local_clock()
        if self.match_filter != "all" and all(
            (r["match_id"] != self.match_filter for r in rows)
        ):
            self.match_filter = "all"

    @rx.var
    def rows(self) -> list[MarketRow]:
        return self.rows_cache

    @rx.var
    def filtered_rows(self) -> list[MarketRow]:
        rows = list(self.rows_cache)
        if self.group_filter != "all":
            rows = [r for r in rows if r["group"] == self.group_filter]
        if self.status_filter != "all":
            rows = [r for r in rows if r["status"] == self.status_filter]
        if self.match_filter != "all":
            rows = [r for r in rows if r["match_id"] == self.match_filter]
        if self.market_filter != "all":
            rows = [r for r in rows if self.market_filter in r["market_tags"]]
        if self.only_recommended:
            rows = [r for r in rows if r["recommended"]]
        rows = [r for r in rows if r["probability"] >= self.min_probability]
        if self.sort_key == "edge":
            return sorted(rows, key=lambda r: -r["edge"])
        if self.sort_key == "odds":
            return sorted(rows, key=lambda r: -r["odds"])
        if self.sort_key == "match":
            return sorted(
                rows, key=lambda r: (r["match_label"], -r["probability"])
            )
        if self.sort_key == "market":
            return sorted(rows, key=lambda r: (r["label"], -r["probability"]))
        return sorted(rows, key=lambda r: -r["probability"])

    @rx.var
    def visible_rows(self) -> list[MarketRow]:
        return self.filtered_rows[:MAX_VISIBLE_ROWS]

    @rx.var
    def total_count(self) -> int:
        return len(self.rows_cache)

    @rx.var
    def filtered_count(self) -> int:
        return len(self.filtered_rows)

    @rx.var
    def visible_count(self) -> int:
        return len(self.visible_rows)

    @rx.var
    def recommended_count(self) -> int:
        return len([r for r in self.filtered_rows if r["recommended"]])

    @rx.var
    def strong_count(self) -> int:
        return len([r for r in self.filtered_rows if r["probability"] >= 70.0])

    @rx.var
    def value_count(self) -> int:
        return len([r for r in self.filtered_rows if r["edge"] >= 3.0])

    @rx.var
    def avg_probability(self) -> float:
        rows = self.filtered_rows
        if not rows:
            return 0.0
        return round(sum(r["probability"] for r in rows) / len(rows), 1)

    @rx.var
    def best_row_label(self) -> str:
        rows = self.filtered_rows
        if not rows:
            return "—"
        best = max(rows, key=lambda r: r["probability"])
        return f"{best['label']} · {best['match_label']}"

    @rx.var
    def best_row_probability(self) -> float:
        rows = self.filtered_rows
        if not rows:
            return 0.0
        return max(r["probability"] for r in rows)

    @rx.var
    def source_counts(self) -> list[dict[str, str]]:
        """Колку редови дава секој реален извор (за ознаките во заглавјето)."""
        labels: dict[str, str] = {
            "bzz": "BZZ API",
            "fotmob": "Fotmob",
            "mutating": "Mutating",
            "sportscore": "SportScore",
            "fudbal91": "Fudbal91",
        }
        out: list[dict[str, str]] = []
        for key, label in labels.items():
            count = len([r for r in self.rows_cache if r["source"] == key])
            if count:
                out.append({"key": key, "label": label, "count": str(count)})
        return out

    @rx.var
    def without_odds_count(self) -> int:
        return len([r for r in self.filtered_rows if not r["has_odds"]])

    @rx.var
    def group_tabs(self) -> list[dict[str, str]]:
        rows = self.rows_cache
        tabs: list[dict[str, str]] = [
            {"key": "all", "label": "Сите групи", "count": str(len(rows))}
        ]
        for key, label in ALL_GROUP_LABELS.items():
            tabs.append(
                {
                    "key": key,
                    "label": label,
                    "count": str(len([r for r in rows if r["group"] == key])),
                }
            )
        return tabs

    @rx.var
    def match_options(self) -> list[dict[str, str]]:
        options: list[dict[str, str]] = [
            {"key": "all", "label": "Сите натпревари"}
        ]
        seen: set[str] = set()
        for row in self.rows_cache:
            if row["match_id"] in seen:
                continue
            seen.add(row["match_id"])
            options.append(
                {"key": row["match_id"], "label": row["match_label"]}
            )
        return options

    @rx.var
    def market_tabs(self) -> list[dict[str, str]]:
        """Чипови за конкретните избори (1/X/2 и Над/Под) со број комбинации."""
        rows = self.rows_cache
        tabs: list[dict[str, str]] = []
        for key, label in MARKET_FILTER_LABELS.items():
            count = len([r for r in rows if key in r["market_tags"]])
            tabs.append({"key": key, "label": label, "count": str(count)})
        return tabs

    @rx.var
    def inline_filter_tabs(self) -> list[dict[str, str]]:
        """Еден ред чипови: групите, а веднаш по нив конкретните избори.

        Групните чипови (`kind = "group"`) го менуваат `group_filter`, а
        чиповите за конкретен избор (`kind = "market"`) го менуваат
        `market_filter`. Не се создава посебен таб ниту dropdown.
        """
        tabs: list[dict[str, str]] = []
        for tab in self.group_tabs:
            tabs.append(
                {
                    "key": tab["key"],
                    "label": tab["label"],
                    "count": tab["count"],
                    "kind": "group",
                }
            )
        for tab in self.market_tabs:
            tabs.append(
                {
                    "key": tab["key"],
                    "label": tab["label"],
                    "count": tab["count"],
                    "kind": "market",
                }
            )
        return tabs

    @rx.var
    def market_filter_label(self) -> str:
        if self.market_filter == "all":
            return "Сите избори"
        return MARKET_FILTER_LABELS.get(self.market_filter, "Сите избори")

    @rx.var
    def group_summaries(self) -> list[dict[str, str]]:
        rows = self.filtered_rows
        summaries: list[dict[str, str]] = []
        for key, label in ALL_GROUP_LABELS.items():
            group = [r for r in rows if r["group"] == key]
            if not group:
                continue
            avg = sum(r["probability"] for r in group) / len(group)
            best = max(group, key=lambda r: r["probability"])
            summaries.append(
                {
                    "key": key,
                    "label": label,
                    "count": str(len(group)),
                    "avg": f"{avg:.1f}%",
                    "avg_width": f"{round(avg, 1)}%",
                    "recommended": str(
                        len([r for r in group if r["recommended"]])
                    ),
                    "best_label": best["label"],
                    "best_probability": f"{best['probability']:.1f}%",
                }
            )
        return summaries

    @rx.var
    def min_probability_label(self) -> str:
        return f"{self.min_probability:.0f}%"

    @rx.var
    def is_truncated(self) -> bool:
        return self.filtered_count > MAX_VISIBLE_ROWS

    @rx.var
    def has_data(self) -> bool:
        return len(self.rows_cache) > 0

    @rx.var
    def sources_label(self) -> str:
        rows = self.source_counts
        if not rows:
            return "Нема достапни извори"
        return " · ".join(f"{row['count']} {row['label']}" for row in rows)

    @rx.event
    async def load(self):
        yield MarketsState.sync

    @rx.event
    async def sync(self):
        from app.states.bsd_state import BSDState
        from app.states.fudbal91_state import Fudbal91State
        from app.states.mutating_state import MutatingState
        from app.states.sportscore_state import SportScoreState

        bsd = await self.get_state(BSDState)
        mutating = await self.get_state(MutatingState)
        sportscore = await self.get_state(SportScoreState)
        fudbal91 = await self.get_state(Fudbal91State)
        self.error = bsd.error
        self._build_rows(
            bsd.matches,
            bsd.generated_at,
            [dict(row) for row in mutating.rows],
            set(mutating.covered_keys),
            [dict(row) for row in sportscore.rows],
            [dict(row) for row in fudbal91.rows],
        )

    @rx.event
    def set_group_filter(self, group: str):
        self.group_filter = group

    @rx.event
    def set_status_filter(self, status: str):
        self.status_filter = status

    @rx.event
    def set_match_filter(self, match_id: str):
        self.match_filter = match_id

    @rx.event
    def set_market_filter(self, market: str):
        self.market_filter = market

    @rx.event
    def toggle_market_filter(self, market: str):
        """Чиповите за конкретен избор се вклучуваат/исклучуваат со клик.

        Кога се активира конкретен избор, групниот филтер се враќа на „Сите
        групи“ за да не остане празна табела од две стеснувања одеднаш.
        """
        if self.market_filter == market:
            self.market_filter = "all"
            return
        self.market_filter = market
        self.group_filter = "all"

    @rx.event
    def apply_inline_filter(self, key: str):
        """Еден клик од редот со чипови: група или конкретен избор.

        - група (или „Сите групи“) → го поставува `group_filter`
        - конкретен избор (1, X, 2, Над/Под 1.5 и 2.5) → го поставува
          `market_filter` и ја враќа групата на „Сите групи“ за да не
          останат две стеснувања одеднаш; повторен клик го исклучува.
        """
        if key == "all":
            self.group_filter = "all"
            self.market_filter = "all"
            return
        if key in ALL_GROUP_LABELS:
            self.group_filter = key
            return
        if key in MARKET_FILTER_LABELS:
            if self.market_filter == key:
                self.market_filter = "all"
                return
            self.market_filter = key
            self.group_filter = "all"

    @rx.event
    def set_sort_key(self, key: str):
        self.sort_key = key

    @rx.event
    def set_min_probability(self, value: float):
        """Го поставува минималниот процент од range влезот.

        Reflex го праќа `on_change` како број, но HTML range може да даде и
        текст, па вредноста се претвора дефанзивно и се ограничува на
        дозволениот опсег (0–90) за да остане филтерот валиден.
        """
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 0.0
        self.min_probability = round(max(0.0, min(90.0, number)), 1)

    @rx.event
    def toggle_only_recommended(self):
        self.only_recommended = not self.only_recommended

    @rx.event
    def reset_filters(self):
        self.group_filter = "all"
        self.status_filter = "all"
        self.match_filter = "all"
        self.market_filter = "all"
        self.sort_key = "probability"
        self.min_probability = 40.0
        self.only_recommended = False
        return rx.toast("Филтрите се вратени на почетни", duration=2000)
