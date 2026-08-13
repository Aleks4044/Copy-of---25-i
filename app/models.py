"""Managed-database schema for prediction history.

Schema-only: no UI or query code depends on this module yet. Every column has
a default or is nullable so the table can be migrated onto existing rows.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Text, func
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedAsDataclass,
    mapped_column,
)


class Base(MappedAsDataclass, DeclarativeBase, kw_only=True):
    """Single declarative base for the whole app."""


class Prediction(Base):
    """One stored prediction row (e.g. XGBoost_Stacking or a meta ensemble).

    Probabilities and confidence are stored as percentages (0-100) to match
    how the app already works with real source values. Metric snapshot fields
    capture the model quality at the moment the prediction was written, so
    later accuracy reviews do not depend on live recomputation.
    """

    __tablename__ = "prediction"
    __table_args__ = (
        Index("ix_prediction_match_model", "match_id", "model_name"),
        Index("ix_prediction_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)

    # Match identity and context.
    match_id: Mapped[str] = mapped_column(default="", index=True)
    match_label: Mapped[str] = mapped_column(default="")
    home_team: Mapped[str] = mapped_column(default="")
    away_team: Mapped[str] = mapped_column(default="")
    league: Mapped[str] = mapped_column(default="")
    kickoff: Mapped[str] = mapped_column(default="")
    kickoff_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, nullable=True
    )
    status: Mapped[str] = mapped_column(default="")
    source: Mapped[str] = mapped_column(default="")

    # Model identity.
    model_name: Mapped[str] = mapped_column(default="XGBoost_Stacking")
    model_version: Mapped[str] = mapped_column(default="")
    is_meta: Mapped[bool] = mapped_column(default=False)

    # Selection.
    market: Mapped[str] = mapped_column(default="")
    pick: Mapped[str] = mapped_column(default="")
    pick_side: Mapped[str] = mapped_column(default="")

    # 1X2 probabilities (percent) and confidence of the stored pick.
    prob_home: Mapped[float] = mapped_column(default=0.0)
    prob_draw: Mapped[float] = mapped_column(default=0.0)
    prob_away: Mapped[float] = mapped_column(default=0.0)
    confidence: Mapped[float] = mapped_column(default=0.0)
    odds: Mapped[float] = mapped_column(default=0.0)
    edge: Mapped[float] = mapped_column(default=0.0)

    # Metrics snapshot at write time.
    accuracy: Mapped[float] = mapped_column(default=0.0)
    accuracy_1x2: Mapped[float] = mapped_column(default=0.0)
    log_loss: Mapped[float] = mapped_column(default=0.0)
    brier: Mapped[float] = mapped_column(default=0.0)
    roi: Mapped[float] = mapped_column(default=0.0)
    sample_size: Mapped[int] = mapped_column(default=0)

    # Outcome bookkeeping (filled in once the match is settled).
    actual_side: Mapped[str] = mapped_column(default="")
    actual_score: Mapped[str] = mapped_column(default="")
    is_correct: Mapped[bool | None] = mapped_column(default=None, nullable=True)
    settled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, nullable=True
    )

    # Optional raw payload from the source/model, stored verbatim as JSON text.
    raw_payload: Mapped[str | None] = mapped_column(
        Text, default=None, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
