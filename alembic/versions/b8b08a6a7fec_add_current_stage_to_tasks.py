"""add_current_stage_to_tasks

Revision ID: b8b08a6a7fec
Revises: f01f052e7dfd
Create Date: 2026-01-20 20:05:13.739762

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8b08a6a7fec"
down_revision: Union[str, Sequence[str], None] = "f01f052e7dfd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add current_stage column to tasks table
    op.add_column(
        "tasks", sa.Column("current_stage", sa.String(length=128), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove current_stage column from tasks table
    op.drop_column("tasks", "current_stage")
