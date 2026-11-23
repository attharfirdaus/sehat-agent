"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-17 21:46:55.157860
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op
from app.settings import settings

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if settings.EMBED_DIM is None:
        raise RuntimeError("EMBED_DIM belum di-set di .env (PRD bagian 12): dibutuhkan kb_chunks")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("channel", sa.Text(), nullable=True),
        sa.Column("intent", sa.Text(), nullable=True),
        sa.Column("node_timings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("llm_calls", sa.Integer(), nullable=True),
        sa.Column("total_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_runs")),
    )
    op.create_table(
        "kb_documents",
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("publisher", sa.Text(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("lang", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("source_id", name=op.f("pk_kb_documents")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), server_default="user", nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("reminder_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("role IN ('user','clinician','admin')", name=op.f("ck_users_role")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("telegram_chat_id", name=op.f("uq_users_telegram_chat_id")),
    )
    op.create_table(
        "assessments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("flags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("framingham", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("diabetes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("trends", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_assessments_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessments")),
    )
    op.create_table(
        "daily_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("steps", sa.Integer(), nullable=True),
        sa.Column("sleep_hours", sa.Numeric(precision=3, scale=1), nullable=True),
        sa.Column("water_l", sa.Numeric(precision=3, scale=1), nullable=True),
        sa.Column("calories_kcal", sa.Integer(), nullable=True),
        sa.Column("smoked", sa.Boolean(), nullable=True),
        sa.Column("alcohol", sa.Boolean(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source IN ('web','telegram','form')", name=op.f("ck_daily_logs_source")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_daily_logs_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_daily_logs")),
        sa.UniqueConstraint("user_id", "log_date", name=op.f("uq_daily_logs_user_id")),
    )
    op.create_table(
        "food_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("kcal_estimate", sa.Integer(), nullable=False),
        sa.Column("confirmed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("image_path", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_food_entries_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_food_entries")),
    )
    op.create_table(
        "kb_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("ord", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(settings.EMBED_DIM), nullable=False),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('simple', text)", persisted=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["kb_documents.source_id"],
            name=op.f("fk_kb_chunks_source_id_kb_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_kb_chunks")),
    )
    op.create_index(
        "kb_chunks_embedding_idx",
        "kb_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index("kb_chunks_tsv_idx", "kb_chunks", ["tsv"], unique=False, postgresql_using="gin")
    op.create_table(
        "measurements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("measured_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("value", sa.Numeric(precision=6, scale=1), nullable=False),
        sa.CheckConstraint(
            "kind IN ('weight_kg','systolic','diastolic','resting_hr','cholesterol_total')",
            name=op.f("ck_measurements_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_measurements_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_measurements")),
    )
    op.create_table(
        "profiles",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("sex", sa.Text(), nullable=False),
        sa.Column("height_cm", sa.Numeric(precision=5, scale=1), nullable=False),
        sa.Column("family_history_cvd", sa.Boolean(), nullable=True),
        sa.Column("family_history_diabetes", sa.Boolean(), nullable=True),
        sa.Column("dx_hypertension", sa.Boolean(), nullable=True),
        sa.Column("dx_high_chol", sa.Boolean(), nullable=True),
        sa.Column("dx_diabetes", sa.Boolean(), nullable=True),
        sa.Column("bp_treated", sa.Boolean(), nullable=True),
        sa.Column("smoker_lifetime_100", sa.Boolean(), nullable=True),
        sa.Column("phys_activity_30d", sa.Boolean(), nullable=True),
        sa.Column("fruits_daily", sa.Boolean(), nullable=True),
        sa.Column("veggies_daily", sa.Boolean(), nullable=True),
        sa.Column("heavy_alcohol", sa.Boolean(), nullable=True),
        sa.Column("gen_health", sa.SmallInteger(), nullable=True),
        sa.Column("diff_walk", sa.Boolean(), nullable=True),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("sex IN ('male','female')", name=op.f("ck_profiles_sex")),
        sa.CheckConstraint("gen_health BETWEEN 1 AND 5", name=op.f("ck_profiles_gen_health")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_profiles_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_profiles")),
    )
    op.create_table(
        "red_flag_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_red_flag_events_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_red_flag_events")),
    )
    op.create_table(
        "telegram_link_tokens",
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_telegram_link_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("token", name=op.f("pk_telegram_link_tokens")),
    )
    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("assessment_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending_review','active','superseded','rejected')",
            name=op.f("ck_plans_status"),
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"], ["assessments.id"], name=op.f("fk_plans_assessment_id_assessments")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_plans_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plans")),
    )
    op.create_table(
        "clinician_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=True),
        sa.Column("decision", sa.Text(), nullable=True),
        sa.Column("edited_content", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "decision IN ('approve','edit','reject')", name=op.f("ck_clinician_reviews_decision")
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["plans.id"], name=op.f("fk_clinician_reviews_plan_id_plans")
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"], ["users.id"], name=op.f("fk_clinician_reviews_reviewer_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clinician_reviews")),
    )


def downgrade() -> None:
    op.drop_table("clinician_reviews")
    op.drop_table("plans")
    op.drop_table("telegram_link_tokens")
    op.drop_table("red_flag_events")
    op.drop_table("profiles")
    op.drop_table("measurements")
    op.drop_index("kb_chunks_tsv_idx", table_name="kb_chunks", postgresql_using="gin")
    op.drop_index(
        "kb_chunks_embedding_idx",
        table_name="kb_chunks",
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.drop_table("kb_chunks")
    op.drop_table("food_entries")
    op.drop_table("daily_logs")
    op.drop_table("assessments")
    op.drop_table("users")
    op.drop_table("kb_documents")
    op.drop_table("agent_runs")
