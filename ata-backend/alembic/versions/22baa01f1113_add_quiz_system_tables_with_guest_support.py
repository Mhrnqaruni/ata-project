"""Add quiz system tables with guest support

Revision ID: 22baa01f1113
Revises: 004a6ff4b05e
Create Date: 2025-11-12 00:00:00.000000

This migration adds 5 tables for the complete quiz system:
1. quizzes - Quiz definitions created by teachers
2. quiz_questions - Individual questions within quizzes
3. quiz_sessions - Live quiz session instances
4. quiz_participants - Participants in sessions (students OR guests)
5. quiz_responses - Individual answer submissions

Key features:
- JSONB columns for flexible question types
- Soft delete for quizzes (preserve analytics)
- Check constraints for data integrity
- Composite indexes for performance
- GDPR compliance with anonymization support
- Guest user support via dual-identity pattern
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '22baa01f1113'
down_revision: Union[str, Sequence[str], None] = '004a6ff4b05e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create all quiz system tables with proper constraints and indexes.
    """

    # ========== CREATE TABLE: quizzes ==========
    op.create_table(
        'quizzes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('class_id', sa.String(), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_room_code', sa.String(length=10), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        # Primary key
        sa.PrimaryKeyConstraint('id'),

        # Foreign keys
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='SET NULL'),
    )

    # Indexes for quizzes table
    op.create_index('idx_quizzes_user_id', 'quizzes', ['user_id'])
    op.create_index('idx_quizzes_class_id', 'quizzes', ['class_id'])
    op.create_index('idx_quizzes_title', 'quizzes', ['title'])
    op.create_index('idx_quizzes_status', 'quizzes', ['status'])
    op.create_index('idx_quizzes_last_room_code', 'quizzes', ['last_room_code'])

    # Composite partial index: user's non-deleted quizzes by status
    op.create_index(
        'idx_quizzes_user_status_not_deleted',
        'quizzes',
        ['user_id', 'status'],
        postgresql_where=sa.text('deleted_at IS NULL')
    )

    # Composite partial index: class quizzes (non-deleted)
    op.create_index(
        'idx_quizzes_class_not_deleted',
        'quizzes',
        ['class_id'],
        postgresql_where=sa.text('deleted_at IS NULL')
    )


    # ========== CREATE TABLE: quiz_questions ==========
    op.create_table(
        'quiz_questions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('quiz_id', sa.String(), nullable=False),
        sa.Column('question_type', sa.String(length=20), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('options', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('correct_answer', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('points', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('time_limit_seconds', sa.Integer(), nullable=True),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('media_url', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        # Primary key
        sa.PrimaryKeyConstraint('id'),

        # Foreign keys
        sa.ForeignKeyConstraint(['quiz_id'], ['quizzes.id'], ondelete='CASCADE'),
    )

    # Indexes for quiz_questions table
    op.create_index('idx_quiz_questions_quiz_id', 'quiz_questions', ['quiz_id'])
    op.create_index('idx_quiz_questions_type', 'quiz_questions', ['question_type'])

    # Composite index: retrieve questions in order
    op.create_index(
        'idx_quiz_questions_quiz_order',
        'quiz_questions',
        ['quiz_id', 'order_index']
    )


    # ========== CREATE TABLE: quiz_sessions ==========
    op.create_table(
        'quiz_sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('quiz_id', sa.String(), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('room_code', sa.String(length=10), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='waiting'),
        sa.Column('current_question_index', sa.Integer(), nullable=True),
        sa.Column('config_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('timeout_hours', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('auto_ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        # Primary key
        sa.PrimaryKeyConstraint('id'),

        # Foreign keys
        sa.ForeignKeyConstraint(['quiz_id'], ['quizzes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),

        # Unique constraint on room code
        sa.UniqueConstraint('room_code')
    )

    # Indexes for quiz_sessions table
    op.create_index('idx_quiz_sessions_quiz_id', 'quiz_sessions', ['quiz_id'])
    op.create_index('idx_quiz_sessions_user_id', 'quiz_sessions', ['user_id'])
    op.create_index('idx_quiz_sessions_room_code', 'quiz_sessions', ['room_code'], unique=True)
    op.create_index('idx_quiz_sessions_status', 'quiz_sessions', ['status'])

    # Composite indexes for common queries
    op.create_index(
        'idx_quiz_sessions_status_created',
        'quiz_sessions',
        ['status', 'created_at']
    )

    op.create_index(
        'idx_quiz_sessions_user_status',
        'quiz_sessions',
        ['user_id', 'status']
    )


    # ========== CREATE TABLE: quiz_participants ==========
    op.create_table(
        'quiz_participants',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('student_id', sa.String(), nullable=True),
        sa.Column('guest_name', sa.String(length=50), nullable=True),
        sa.Column('guest_token', sa.String(length=64), nullable=True),
        sa.Column('score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('correct_answers', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_time_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('anonymized_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        # Primary key
        sa.PrimaryKeyConstraint('id'),

        # Foreign keys
        sa.ForeignKeyConstraint(['session_id'], ['quiz_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='SET NULL'),

        # CHECK constraint: EITHER student_id OR (guest_name AND guest_token)
        sa.CheckConstraint(
            "(student_id IS NOT NULL AND guest_name IS NULL AND guest_token IS NULL) OR "
            "(student_id IS NULL AND guest_name IS NOT NULL AND guest_token IS NOT NULL)",
            name='chk_participant_identity'
        ),

        # Unique constraint on guest_token
        sa.UniqueConstraint('guest_token')
    )

    # Indexes for quiz_participants table
    op.create_index('idx_quiz_participants_session_id', 'quiz_participants', ['session_id'])
    op.create_index('idx_quiz_participants_student_id', 'quiz_participants', ['student_id'])
    op.create_index('idx_quiz_participants_guest_token', 'quiz_participants', ['guest_token'], unique=True)

    # Composite index: leaderboard queries (session + score descending)
    op.create_index(
        'idx_participants_session_score',
        'quiz_participants',
        ['session_id', sa.text('score DESC')]
    )

    # Composite index: active participants
    op.create_index(
        'idx_participants_session_active',
        'quiz_participants',
        ['session_id', 'is_active']
    )

    # Composite partial index: GDPR cleanup (find old guests)
    op.create_index(
        'idx_participants_gdpr_cleanup',
        'quiz_participants',
        ['joined_at', 'anonymized_at'],
        postgresql_where=sa.text('guest_token IS NOT NULL')
    )


    # ========== CREATE TABLE: quiz_responses ==========
    op.create_table(
        'quiz_responses',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('participant_id', sa.String(), nullable=False),
        sa.Column('question_id', sa.String(), nullable=False),
        sa.Column('answer', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_correct', sa.Boolean(), nullable=True),
        sa.Column('points_earned', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('time_taken_ms', sa.Integer(), nullable=False),
        sa.Column('answered_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        # Primary key
        sa.PrimaryKeyConstraint('id'),

        # Foreign keys
        sa.ForeignKeyConstraint(['session_id'], ['quiz_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['participant_id'], ['quiz_participants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_id'], ['quiz_questions.id'], ondelete='CASCADE'),

        # UNIQUE constraint: one answer per participant per question
        sa.UniqueConstraint('session_id', 'participant_id', 'question_id', name='uq_one_answer_per_participant_question')
    )

    # Indexes for quiz_responses table
    op.create_index('idx_quiz_responses_session_id', 'quiz_responses', ['session_id'])
    op.create_index('idx_quiz_responses_participant_id', 'quiz_responses', ['participant_id'])
    op.create_index('idx_quiz_responses_question_id', 'quiz_responses', ['question_id'])

    # Composite index: leaderboard calculation
    op.create_index(
        'idx_responses_leaderboard',
        'quiz_responses',
        ['session_id', 'is_correct', 'points_earned']
    )

    # Composite index: question analytics
    op.create_index(
        'idx_responses_question_analytics',
        'quiz_responses',
        ['question_id', 'is_correct', 'time_taken_ms']
    )


def downgrade() -> None:
    """
    Drop all quiz system tables in reverse order.
    """
    # Drop tables in reverse order of creation (respecting foreign key constraints)
    op.drop_table('quiz_responses')
    op.drop_table('quiz_participants')
    op.drop_table('quiz_sessions')
    op.drop_table('quiz_questions')
    op.drop_table('quizzes')
