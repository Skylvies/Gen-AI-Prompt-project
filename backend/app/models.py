"""Database tables (SQLAlchemy ORM). One Experiment has many VariantResults."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    """Naive UTC timestamp (SQLite has no timezone type); serialised with a trailing 'Z'."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    task: Mapped[str] = mapped_column(Text)
    reference_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    mode: Mapped[str] = mapped_column(String(10))  # "demo" | "real"
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(80))
    target_words: Mapped[int] = mapped_column(Integer)
    weights_json: Mapped[str] = mapped_column(Text)  # normalised weights used for the overall score
    price_input_per_mtok: Mapped[float] = mapped_column(Float, default=0.0)
    price_output_per_mtok: Mapped[float] = mapped_column(Float, default=0.0)
    recommendation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    results: Mapped[list["VariantResult"]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan", order_by="VariantResult.id"
    )


class VariantResult(Base):
    __tablename__ = "variant_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"), index=True)
    experiment: Mapped[Experiment] = relationship(back_populates="results")

    technique: Mapped[str] = mapped_column(String(30))
    label: Mapped[str] = mapped_column(String(40))
    prompt: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    tokens_estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    # raw 0-100 text metrics
    relevance: Mapped[float] = mapped_column(Float, default=0.0)
    validity: Mapped[float] = mapped_column(Float, default=0.0)
    reliability: Mapped[float] = mapped_column(Float, default=0.0)
    conciseness: Mapped[float] = mapped_column(Float, default=0.0)
    # normalised 0-100 efficiency scores (relative to the other variants)
    tokens_score: Mapped[float] = mapped_column(Float, default=0.0)
    cost_score: Mapped[float] = mapped_column(Float, default=0.0)
    latency_score: Mapped[float] = mapped_column(Float, default=0.0)

    overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    details_json: Mapped[str] = mapped_column(Text, default="{}")  # validity checks, reliability flags, ...
