"""modify_participant_identity_constraint_to_support_identified_guests

Revision ID: dfcbca98dcdf
Revises: 22baa01f1113
Create Date: 2025-11-13 06:38:47.711777

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dfcbca98dcdf'
down_revision: Union[str, Sequence[str], None] = '22baa01f1113'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Modify participant identity constraint to support identified guests.

    Changes:
    1. Drop FK constraint on student_id (allow arbitrary student IDs from school)
    2. Modify check constraint to allow three identity types

    OLD constraint allowed:
    1. Registered student: student_id NOT NULL (FK), guest_name NULL, guest_token NULL
    2. Pure guest: student_id NULL, guest_name NOT NULL, guest_token NOT NULL

    NEW constraint allows:
    1. Registered student: student_id NOT NULL, guest_name NULL, guest_token NULL
    2. Pure guest: student_id NULL, guest_name NOT NULL, guest_token NOT NULL
    3. Identified guest (NEW): student_id NOT NULL, guest_name NOT NULL, guest_token NOT NULL
       - Students with school ID but no account
       - student_id is just an identifier string (not a FK)
    """
    # Drop foreign key constraint on student_id
    # This allows student_id to be any string, not just IDs from students table
    op.drop_constraint('quiz_participants_student_id_fkey', 'quiz_participants', type_='foreignkey')

    # Drop old check constraint
    op.drop_constraint('chk_participant_identity', 'quiz_participants', type_='check')

    # Create new check constraint with three scenarios
    op.create_check_constraint(
        'chk_participant_identity',
        'quiz_participants',
        "(student_id IS NOT NULL AND guest_name IS NULL AND guest_token IS NULL) OR "  # Registered student
        "(student_id IS NULL AND guest_name IS NOT NULL AND guest_token IS NOT NULL) OR "  # Pure guest
        "(student_id IS NOT NULL AND guest_name IS NOT NULL AND guest_token IS NOT NULL)"  # Identified guest (NEW)
    )


def downgrade() -> None:
    """Revert to old constraints."""
    # Drop new check constraint
    op.drop_constraint('chk_participant_identity', 'quiz_participants', type_='check')

    # Restore old check constraint (two scenarios only)
    op.create_check_constraint(
        'chk_participant_identity',
        'quiz_participants',
        "(student_id IS NOT NULL AND guest_name IS NULL AND guest_token IS NULL) OR "
        "(student_id IS NULL AND guest_name IS NOT NULL AND guest_token IS NOT NULL)"
    )

    # Restore foreign key constraint on student_id
    op.create_foreign_key(
        'quiz_participants_student_id_fkey',
        'quiz_participants',
        'students',
        ['student_id'],
        ['id'],
        ondelete='SET NULL'
    )
