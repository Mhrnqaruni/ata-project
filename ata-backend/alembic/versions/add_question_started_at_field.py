"""add_question_started_at_to_quiz_sessions

Revision ID: 1a2b3c4d5e6f
Revises: dfcbca98dcdf
Create Date: 2025-11-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1a2b3c4d5e6f'
down_revision: Union[str, Sequence[str], None] = 'dfcbca98dcdf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add question_started_at field to quiz_sessions table.

    This field tracks when the current question was started, enabling:
    1. Server-side time limit enforcement
    2. Preventing late answer submissions
    3. Auto-advance functionality with accurate timing
    """
    op.add_column('quiz_sessions',
        sa.Column('question_started_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Remove question_started_at field."""
    op.drop_column('quiz_sessions', 'question_started_at')
