"""Add quiz roster tracking tables and columns

Revision ID: 20251117_060108
Revises: 018e9779debd
Create Date: 2025-11-17 06:01:08

This migration adds comprehensive class-based student roster tracking to the quiz system:
1. quiz_session_roster - Snapshot of expected students when session starts
2. quiz_outsider_students - Track students who join but aren't on roster
3. Adds class_id to quiz_sessions (denormalized from quizzes)
4. Adds is_outsider and roster_entry_id to quiz_participants
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20251117_060108'
down_revision: Union[str, Sequence[str], None] = '018e9779debd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema to add roster tracking functionality.
    """

    # ========== CREATE TABLE: quiz_session_roster ==========
    # Stores snapshot of expected students at session creation time
    op.create_table(
        'quiz_session_roster',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('student_id', sa.String(), nullable=False),
        sa.Column('student_name', sa.String(), nullable=False),
        sa.Column('student_school_id', sa.String(), nullable=False),
        sa.Column('enrollment_status', sa.String(20), nullable=False, server_default='expected'),
        sa.Column('joined', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('participant_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        # Foreign key constraints
        sa.ForeignKeyConstraint(['session_id'], ['quiz_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['participant_id'], ['quiz_participants.id'], ondelete='SET NULL'),

        # Primary key
        sa.PrimaryKeyConstraint('id'),

        # Unique constraint: one roster entry per student per session
        sa.UniqueConstraint('session_id', 'student_id', name='uq_session_student')
    )

    # Create indexes for quiz_session_roster
    op.create_index('idx_session_roster_session', 'quiz_session_roster', ['session_id'])
    op.create_index('idx_session_roster_joined', 'quiz_session_roster', ['session_id', 'joined'])
    op.create_index('idx_session_roster_student', 'quiz_session_roster', ['student_id'])

    # ========== CREATE TABLE: quiz_outsider_students ==========
    # Tracks students who joined but weren't on the expected roster
    op.create_table(
        'quiz_outsider_students',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('student_school_id', sa.String(), nullable=False),
        sa.Column('guest_name', sa.String(), nullable=False),
        sa.Column('participant_id', sa.String(), nullable=False),
        sa.Column('detection_reason', sa.String(50), nullable=False),
        sa.Column('flagged_by_teacher', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('teacher_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        # Foreign key constraints
        sa.ForeignKeyConstraint(['session_id'], ['quiz_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['participant_id'], ['quiz_participants.id'], ondelete='CASCADE'),

        # Primary key
        sa.PrimaryKeyConstraint('id'),

        # Unique constraint: one outsider record per participant per session
        sa.UniqueConstraint('session_id', 'participant_id', name='uq_session_outsider')
    )

    # Create indexes for quiz_outsider_students
    op.create_index('idx_outsider_session', 'quiz_outsider_students', ['session_id'])
    op.create_index('idx_outsider_student_id', 'quiz_outsider_students', ['student_school_id'])
    op.create_index('idx_outsider_participant', 'quiz_outsider_students', ['participant_id'])

    # ========== MODIFY TABLE: quiz_sessions ==========
    # Add class_id column (denormalized from quizzes for performance)
    op.add_column('quiz_sessions', sa.Column('class_id', sa.String(), nullable=True))

    # Create foreign key constraint for class_id
    op.create_foreign_key(
        'fk_quiz_sessions_class_id',
        'quiz_sessions',
        'classes',
        ['class_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Create index for class_id lookups
    op.create_index('idx_quiz_sessions_class', 'quiz_sessions', ['class_id'])

    # ========== MODIFY TABLE: quiz_participants ==========
    # Add is_outsider flag for quick filtering
    op.add_column('quiz_participants', sa.Column('is_outsider', sa.Boolean(), nullable=False, server_default='false'))

    # Add roster_entry_id for bidirectional link
    op.add_column('quiz_participants', sa.Column('roster_entry_id', sa.String(), nullable=True))

    # Create foreign key constraint for roster_entry_id
    op.create_foreign_key(
        'fk_quiz_participants_roster',
        'quiz_participants',
        'quiz_session_roster',
        ['roster_entry_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Create composite index for outsider filtering
    op.create_index('idx_participants_outsider', 'quiz_participants', ['session_id', 'is_outsider'])


def downgrade() -> None:
    """
    Downgrade schema to remove roster tracking functionality.
    Reverse all changes made in upgrade().
    """

    # ========== REVERT TABLE: quiz_participants ==========
    # Drop index first
    op.drop_index('idx_participants_outsider', table_name='quiz_participants')

    # Drop foreign key constraint
    op.drop_constraint('fk_quiz_participants_roster', 'quiz_participants', type_='foreignkey')

    # Drop columns
    op.drop_column('quiz_participants', 'roster_entry_id')
    op.drop_column('quiz_participants', 'is_outsider')

    # ========== REVERT TABLE: quiz_sessions ==========
    # Drop index first
    op.drop_index('idx_quiz_sessions_class', table_name='quiz_sessions')

    # Drop foreign key constraint
    op.drop_constraint('fk_quiz_sessions_class_id', 'quiz_sessions', type_='foreignkey')

    # Drop column
    op.drop_column('quiz_sessions', 'class_id')

    # ========== DROP TABLE: quiz_outsider_students ==========
    # Drop indexes first
    op.drop_index('idx_outsider_participant', table_name='quiz_outsider_students')
    op.drop_index('idx_outsider_student_id', table_name='quiz_outsider_students')
    op.drop_index('idx_outsider_session', table_name='quiz_outsider_students')

    # Drop table
    op.drop_table('quiz_outsider_students')

    # ========== DROP TABLE: quiz_session_roster ==========
    # Drop indexes first
    op.drop_index('idx_session_roster_student', table_name='quiz_session_roster')
    op.drop_index('idx_session_roster_joined', table_name='quiz_session_roster')
    op.drop_index('idx_session_roster_session', table_name='quiz_session_roster')

    # Drop table
    op.drop_table('quiz_session_roster')
