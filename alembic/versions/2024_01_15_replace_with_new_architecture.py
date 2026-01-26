"""Replace Task model with new Video-centric architecture

Revision ID: 2024_01_15_new_arch
Revises: 7398d95d647d
Create Date: 2024-01-15 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2024_01_15_new_arch"
down_revision: Union[str, None] = "7398d95d647d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade to new architecture."""

    # ============================================================================
    # 1. CREATE NEW TABLES
    # ============================================================================

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)

    # Create refresh_tokens table
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=500), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_refresh_tokens_id"), "refresh_tokens", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_refresh_tokens_token"), "refresh_tokens", ["token"], unique=True
    )

    # Create videos table
    op.create_table(
        "videos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("language", sa.String(length=5), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("file_path", sa.String(length=1024), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING", "PROCESSING", "COMPLETED", "FAILED", name="processingstatus"
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("progress", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("current_stage", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url", "language", name="uq_video_url_language"),
    )
    op.create_index(
        op.f("ix_videos_created_at"), "videos", ["created_at"], unique=False
    )
    op.create_index(op.f("ix_videos_id"), "videos", ["id"], unique=False)
    op.create_index(op.f("ix_videos_language"), "videos", ["language"], unique=False)
    op.create_index(op.f("ix_videos_status"), "videos", ["status"], unique=False)
    op.create_index(op.f("ix_videos_task_id"), "videos", ["task_id"], unique=True)
    op.create_index(op.f("ix_videos_url"), "videos", ["url"], unique=False)

    # Create segments table
    op.create_table(
        "segments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("video_id", sa.Integer(), nullable=False),
        sa.Column("segment_id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Integer(), nullable=False),
        sa.Column("end_time", sa.Integer(), nullable=False),
        sa.Column("topic_title", sa.String(length=500), nullable=True),
        sa.Column("short_summary", sa.Text(), nullable=True),
        sa.Column("keywords", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("video_id", "segment_id", name="uq_segment_video_segment"),
    )
    op.create_index(op.f("ix_segments_id"), "segments", ["id"], unique=False)
    op.create_index(
        op.f("ix_segments_video_id"), "segments", ["video_id"], unique=False
    )

    # Create quizzes table
    op.create_table(
        "quizzes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("segment_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("correct_index", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=5), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(["segment_id"], ["segments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_quizzes_id"), "quizzes", ["id"], unique=False)
    op.create_index(
        op.f("ix_quizzes_segment_id"), "quizzes", ["segment_id"], unique=False
    )

    # Create user_answers table
    op.create_table(
        "user_answers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("quiz_id", sa.Integer(), nullable=False),
        sa.Column("segment_id", sa.Integer(), nullable=False),
        sa.Column("selected_index", sa.Integer(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column(
            "answered_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["quiz_id"], ["quizzes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["segment_id"], ["segments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "quiz_id", name="uq_user_answer_user_quiz"),
    )
    op.create_index(
        op.f("ix_user_answers_answered_at"),
        "user_answers",
        ["answered_at"],
        unique=False,
    )
    op.create_index(op.f("ix_user_answers_id"), "user_answers", ["id"], unique=False)
    op.create_index(
        op.f("ix_user_answers_quiz_id"), "user_answers", ["quiz_id"], unique=False
    )
    op.create_index(
        op.f("ix_user_answers_user_id"), "user_answers", ["user_id"], unique=False
    )

    # ============================================================================
    # 2. DROP OLD TABLES
    # ============================================================================

    # Drop old tasks table (no data migration - fresh start)
    op.drop_table("tasks")


def downgrade() -> None:
    """Downgrade to old architecture."""

    # Recreate tasks table (old schema)
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("video_title", sa.String(length=512), nullable=True),
        sa.Column("language", sa.String(length=10), nullable=True, server_default="ru"),
        sa.Column("video_path", sa.String(length=1024), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("file_hash", sa.String(length=64), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("fps", sa.Float(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PENDING", "PROCESSING", "COMPLETED", "FAILED", name="taskstatus"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("progress", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("current_stage", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "segments_json", postgresql.JSON(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("total_segments", sa.Integer(), nullable=True),
        sa.Column("total_quizzes", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("is_public", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("share_token", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tasks_created_at"), "tasks", ["created_at"], unique=False)
    op.create_index(op.f("ix_tasks_file_hash"), "tasks", ["file_hash"], unique=False)
    op.create_index(op.f("ix_tasks_id"), "tasks", ["id"], unique=False)
    op.create_index(op.f("ix_tasks_share_token"), "tasks", ["share_token"], unique=True)
    op.create_index(op.f("ix_tasks_status"), "tasks", ["status"], unique=False)
    op.create_index(op.f("ix_tasks_user_id"), "tasks", ["user_id"], unique=False)

    # Drop new tables
    op.drop_table("user_answers")
    op.drop_table("quizzes")
    op.drop_table("segments")
    op.drop_table("videos")
    op.drop_table("refresh_tokens")
    op.drop_table("users")

    # Drop ProcessingStatus enum (if it exists)
    op.execute("DROP TYPE IF EXISTS processingstatus")
