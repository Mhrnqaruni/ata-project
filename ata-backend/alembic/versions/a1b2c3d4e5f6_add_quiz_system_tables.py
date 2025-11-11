"""Add quiz system tables with JSONB, indexes, and constraints

Revision ID: a1b2c3d4e5f6
Revises: 004a6ff4b05e
Create Date: 2025-11-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '004a6ff4b05e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema - Create all quiz system tables.

    Tables created:
    1. quizzes - Quiz definitions created by teachers
    2. quiz_questions - Questions belonging to quizzes
    3. quiz_sessions - Active quiz sessions with room codes
    4. quiz_participants - Participants in sessions (students + guests)
    5. quiz_responses - Individual answers to questions
    """

    # --- Table 1: quizzes ---
    op.create_table(
        'quizzes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('class_id', sa.String(), nullable=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='draft'),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('last_room_code', sa.String(length=6), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quizzes_id'), 'quizzes', ['id'], unique=False)
    op.create_index(op.f('ix_quizzes_user_id'), 'quizzes', ['user_id'], unique=False)
    op.create_index(op.f('ix_quizzes_class_id'), 'quizzes', ['class_id'], unique=False)
    op.create_index(op.f('ix_quizzes_title'), 'quizzes', ['title'], unique=False)
    op.create_index(op.f('ix_quizzes_status'), 'quizzes', ['status'], unique=False)
    op.create_index(op.f('ix_quizzes_last_room_code'), 'quizzes', ['last_room_code'], unique=False)
    # Composite index for common query: user's non-deleted quizzes by status
    op.create_index(
        'idx_quizzes_user_status_not_deleted',
        'quizzes',
        ['user_id', 'status'],
        postgresql_where=sa.text('deleted_at IS NULL')
    )
    # Index for class association
    op.create_index(
        'idx_quizzes_class_not_deleted',
        'quizzes',
        ['class_id'],
        postgresql_where=sa.text('deleted_at IS NULL')
    )

    # --- Table 2: quiz_questions ---
    op.create_table(
        'quiz_questions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('quiz_id', sa.String(), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('question_type', sa.String(), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('points', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('time_limit', sa.Integer(), nullable=True),
        sa.Column('options', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('correct_answer', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('media_url', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['quiz_id'], ['quizzes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quiz_questions_id'), 'quiz_questions', ['id'], unique=False)
    op.create_index(op.f('ix_quiz_questions_quiz_id'), 'quiz_questions', ['quiz_id'], unique=False)
    op.create_index(op.f('ix_quiz_questions_question_type'), 'quiz_questions', ['question_type'], unique=False)
    # Composite index for ordered question retrieval
    op.create_index('idx_quiz_questions_quiz_order', 'quiz_questions', ['quiz_id', 'order_index'])
    # Index for question type filtering
    op.create_index('idx_quiz_questions_type', 'quiz_questions', ['question_type'])

    # --- Table 3: quiz_sessions ---
    op.create_table(
        'quiz_sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('quiz_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='waiting'),
        sa.Column('room_code', sa.String(length=6), nullable=False),
        sa.Column('current_question_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('session_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('timeout_hours', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('auto_ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['quiz_id'], ['quizzes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quiz_sessions_id'), 'quiz_sessions', ['id'], unique=False)
    op.create_index(op.f('ix_quiz_sessions_quiz_id'), 'quiz_sessions', ['quiz_id'], unique=False)
    op.create_index(op.f('ix_quiz_sessions_user_id'), 'quiz_sessions', ['user_id'], unique=False)
    op.create_index(op.f('ix_quiz_sessions_room_code'), 'quiz_sessions', ['room_code'], unique=True)
    op.create_index(op.f('ix_quiz_sessions_status'), 'quiz_sessions', ['status'], unique=False)
    # Composite index for finding user's sessions by status
    op.create_index('idx_quiz_sessions_user_status', 'quiz_sessions', ['user_id', 'status'])

    # --- Table 4: quiz_participants ---
    op.create_table(
        'quiz_participants',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('student_id', sa.String(), nullable=True),
        sa.Column('guest_name', sa.String(), nullable=True),
        sa.Column('guest_token', sa.String(), nullable=True),
        sa.Column('score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('correct_answers', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_time_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('anonymized_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('left_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['quiz_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='SET NULL'),
        # CheckConstraint to ensure EITHER student_id OR guest_name (not both, not neither)
        sa.CheckConstraint(
            '(student_id IS NOT NULL AND guest_name IS NULL) OR '
            '(student_id IS NULL AND guest_name IS NOT NULL)',
            name='chk_participant_identity'
        ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quiz_participants_id'), 'quiz_participants', ['id'], unique=False)
    op.create_index(op.f('ix_quiz_participants_session_id'), 'quiz_participants', ['session_id'], unique=False)
    op.create_index(op.f('ix_quiz_participants_student_id'), 'quiz_participants', ['student_id'], unique=False)
    op.create_index(op.f('ix_quiz_participants_guest_token'), 'quiz_participants', ['guest_token'], unique=True)
    # Composite index for session participant lists
    op.create_index('idx_participants_session_active', 'quiz_participants', ['session_id', 'is_active'])
    # Index for GDPR cleanup job
    op.create_index(
        'idx_participants_anonymization',
        'quiz_participants',
        ['guest_name', 'joined_at'],
        postgresql_where=sa.text('guest_name IS NOT NULL AND anonymized_at IS NULL')
    )
    # Index for leaderboard queries
    op.create_index('idx_participants_session_score', 'quiz_participants', ['session_id', 'score', 'total_time_ms'])

    # --- Table 5: quiz_responses ---
    op.create_table(
        'quiz_responses',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('participant_id', sa.String(), nullable=False),
        sa.Column('question_id', sa.String(), nullable=False),
        sa.Column('answer', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_correct', sa.Boolean(), nullable=True),  # NULL for poll questions
        sa.Column('points_earned', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('time_taken_ms', sa.Integer(), nullable=False),
        sa.Column('answered_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['quiz_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['participant_id'], ['quiz_participants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_id'], ['quiz_questions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quiz_responses_id'), 'quiz_responses', ['id'], unique=False)
    op.create_index(op.f('ix_quiz_responses_session_id'), 'quiz_responses', ['session_id'], unique=False)
    op.create_index(op.f('ix_quiz_responses_participant_id'), 'quiz_responses', ['participant_id'], unique=False)
    op.create_index(op.f('ix_quiz_responses_question_id'), 'quiz_responses', ['question_id'], unique=False)
    # Composite index for leaderboard calculation
    op.create_index('idx_responses_leaderboard', 'quiz_responses', ['session_id', 'participant_id', 'is_correct'])
    # Index for question analytics
    op.create_index('idx_responses_question_correct', 'quiz_responses', ['question_id', 'is_correct'])
    # Unique constraint: one answer per participant per question
    op.create_index(
        'idx_responses_unique_answer',
        'quiz_responses',
        ['session_id', 'participant_id', 'question_id'],
        unique=True
    )


def downgrade() -> None:
    """
    Downgrade schema - Drop all quiz system tables in reverse order.

    Order is important due to foreign key constraints.
    """
    # Drop tables in reverse order of creation to respect foreign keys

    # Drop quiz_responses
    op.drop_index('idx_responses_unique_answer', table_name='quiz_responses')
    op.drop_index('idx_responses_question_correct', table_name='quiz_responses')
    op.drop_index('idx_responses_leaderboard', table_name='quiz_responses')
    op.drop_index(op.f('ix_quiz_responses_question_id'), table_name='quiz_responses')
    op.drop_index(op.f('ix_quiz_responses_participant_id'), table_name='quiz_responses')
    op.drop_index(op.f('ix_quiz_responses_session_id'), table_name='quiz_responses')
    op.drop_index(op.f('ix_quiz_responses_id'), table_name='quiz_responses')
    op.drop_table('quiz_responses')

    # Drop quiz_participants
    op.drop_index('idx_participants_session_score', table_name='quiz_participants')
    op.drop_index('idx_participants_anonymization', table_name='quiz_participants')
    op.drop_index('idx_participants_session_active', table_name='quiz_participants')
    op.drop_index(op.f('ix_quiz_participants_guest_token'), table_name='quiz_participants')
    op.drop_index(op.f('ix_quiz_participants_student_id'), table_name='quiz_participants')
    op.drop_index(op.f('ix_quiz_participants_session_id'), table_name='quiz_participants')
    op.drop_index(op.f('ix_quiz_participants_id'), table_name='quiz_participants')
    op.drop_table('quiz_participants')

    # Drop quiz_sessions
    op.drop_index('idx_quiz_sessions_user_status', table_name='quiz_sessions')
    op.drop_index(op.f('ix_quiz_sessions_status'), table_name='quiz_sessions')
    op.drop_index(op.f('ix_quiz_sessions_room_code'), table_name='quiz_sessions')
    op.drop_index(op.f('ix_quiz_sessions_user_id'), table_name='quiz_sessions')
    op.drop_index(op.f('ix_quiz_sessions_quiz_id'), table_name='quiz_sessions')
    op.drop_index(op.f('ix_quiz_sessions_id'), table_name='quiz_sessions')
    op.drop_table('quiz_sessions')

    # Drop quiz_questions
    op.drop_index('idx_quiz_questions_type', table_name='quiz_questions')
    op.drop_index('idx_quiz_questions_quiz_order', table_name='quiz_questions')
    op.drop_index(op.f('ix_quiz_questions_question_type'), table_name='quiz_questions')
    op.drop_index(op.f('ix_quiz_questions_quiz_id'), table_name='quiz_questions')
    op.drop_index(op.f('ix_quiz_questions_id'), table_name='quiz_questions')
    op.drop_table('quiz_questions')

    # Drop quizzes
    op.drop_index('idx_quizzes_class_not_deleted', table_name='quizzes')
    op.drop_index('idx_quizzes_user_status_not_deleted', table_name='quizzes')
    op.drop_index(op.f('ix_quizzes_last_room_code'), table_name='quizzes')
    op.drop_index(op.f('ix_quizzes_status'), table_name='quizzes')
    op.drop_index(op.f('ix_quizzes_title'), table_name='quizzes')
    op.drop_index(op.f('ix_quizzes_class_id'), table_name='quizzes')
    op.drop_index(op.f('ix_quizzes_user_id'), table_name='quizzes')
    op.drop_index(op.f('ix_quizzes_id'), table_name='quizzes')
    op.drop_table('quizzes')
