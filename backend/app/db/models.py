"""SQLAlchemy models, mirror PRD bagian 9."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    Date,
    ForeignKey,
    Index,
    MetaData,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP

from app.settings import settings


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )
    type_annotation_map = {datetime: TIMESTAMP(timezone=True), dict[str, Any]: JSONB}


def _now() -> Mapped[datetime]:
    return mapped_column(server_default=func.now())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('user','clinician','admin')", name="role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, server_default="user")
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    reminder_enabled: Mapped[bool] = mapped_column(server_default="true")
    created_at: Mapped[datetime] = _now()


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint("sex IN ('male','female')", name="sex"),
        CheckConstraint("gen_health BETWEEN 1 AND 5", name="gen_health"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    birth_date: Mapped[date] = mapped_column(Date)
    sex: Mapped[str] = mapped_column(Text)
    height_cm: Mapped[Decimal] = mapped_column(Numeric(5, 1))
    family_history_cvd: Mapped[bool | None]
    family_history_diabetes: Mapped[bool | None]
    dx_hypertension: Mapped[bool | None]
    dx_high_chol: Mapped[bool | None]
    dx_diabetes: Mapped[bool | None]
    bp_treated: Mapped[bool | None]
    smoker_lifetime_100: Mapped[bool | None]
    phys_activity_30d: Mapped[bool | None]
    fruits_daily: Mapped[bool | None]
    veggies_daily: Mapped[bool | None]
    heavy_alcohol: Mapped[bool | None]
    gen_health: Mapped[int | None] = mapped_column(SmallInteger)
    diff_walk: Mapped[bool | None]
    updated_at: Mapped[datetime] = _now()


class DailyLog(Base):
    __tablename__ = "daily_logs"
    __table_args__ = (
        UniqueConstraint("user_id", "log_date"),
        CheckConstraint("source IN ('web','telegram','form')", name="source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    log_date: Mapped[date] = mapped_column(Date)
    steps: Mapped[int | None]
    sleep_hours: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    water_l: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    calories_kcal: Mapped[int | None]
    smoked: Mapped[bool | None]
    alcohol: Mapped[bool | None]
    source: Mapped[str] = mapped_column(Text)
    raw_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _now()


class Measurement(Base):
    __tablename__ = "measurements"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('weight_kg','systolic','diastolic','resting_hr','cholesterol_total')",
            name="kind",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    measured_at: Mapped[datetime]
    kind: Mapped[str] = mapped_column(Text)
    value: Mapped[Decimal] = mapped_column(Numeric(6, 1))


class FoodEntry(Base):
    __tablename__ = "food_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    log_date: Mapped[date] = mapped_column(Date)
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    kcal_estimate: Mapped[int]
    confirmed: Mapped[bool] = mapped_column(server_default="false")
    image_path: Mapped[str | None] = mapped_column(Text)


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    thread_id: Mapped[str] = mapped_column(Text)
    flags: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    framingham: Mapped[dict[str, Any]]
    diabetes: Mapped[dict[str, Any]]
    trends: Mapped[dict[str, Any]]
    created_at: Mapped[datetime] = _now()


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_review','active','superseded','rejected')", name="status"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    assessment_id: Mapped[int | None] = mapped_column(ForeignKey("assessments.id"))
    status: Mapped[str] = mapped_column(Text)
    content: Mapped[dict[str, Any]]
    starts_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = _now()


class RedFlagEvent(Base):
    __tablename__ = "red_flag_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(Text)
    detail: Mapped[dict[str, Any]]
    created_at: Mapped[datetime] = _now()


class ClinicianReview(Base):
    __tablename__ = "clinician_reviews"
    __table_args__ = (CheckConstraint("decision IN ('approve','edit','reject')", name="decision"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    thread_id: Mapped[str] = mapped_column(Text)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str | None] = mapped_column(Text)
    edited_content: Mapped[dict[str, Any] | None]
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _now()
    decided_at: Mapped[datetime | None]


class TelegramLinkToken(Base):
    __tablename__ = "telegram_link_tokens"

    token: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]


class KbDocument(Base):
    __tablename__ = "kb_documents"

    source_id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    publisher: Mapped[str] = mapped_column(Text)
    year: Mapped[int | None]
    lang: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(Text)


class KbChunk(Base):
    __tablename__ = "kb_chunks"
    __table_args__ = (
        Index(
            "kb_chunks_embedding_idx",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("kb_chunks_tsv_idx", "tsv", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("kb_documents.source_id", ondelete="CASCADE"))
    ord: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[Any] = mapped_column(Vector(settings.EMBED_DIM))
    tsv: Mapped[Any] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple', text)", persisted=True)
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[str] = mapped_column(Text)
    user_id: Mapped[int | None]
    channel: Mapped[str | None] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(Text)
    node_timings: Mapped[dict[str, Any] | None]
    llm_calls: Mapped[int | None]
    total_ms: Mapped[int | None]
    created_at: Mapped[datetime] = _now()
