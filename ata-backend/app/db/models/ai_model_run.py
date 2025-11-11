import uuid
from sqlalchemy import Column, String, Text, SmallInteger, DateTime, ForeignKey, UniqueConstraint, Numeric, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from ..base_class import Base

class AIModelRun(Base):
    __tablename__ = 'ai_model_runs'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(String, ForeignKey('assessments.id', ondelete='CASCADE'), nullable=False, index=True)

    # An AI run can be linked to a rostered student OR an outsider student
    student_id = Column(String, ForeignKey('students.id', ondelete='CASCADE'), nullable=True, index=True)
    outsider_student_id = Column(String, ForeignKey('outsider_students.id', ondelete='CASCADE'), nullable=True, index=True)

    question_id = Column(String, nullable=False, index=True)
    run_index = Column(SmallInteger, nullable=False)

    raw_json = Column(JSONB, nullable=False)
    grade = Column(Numeric(10, 2), nullable=True)
    comment = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint('job_id', 'student_id', 'question_id', 'run_index', name='_job_student_question_run_uc'),
        UniqueConstraint('job_id', 'outsider_student_id', 'question_id', 'run_index', name='_job_outsider_question_run_uc'),
        CheckConstraint(
            '(student_id IS NOT NULL AND outsider_student_id IS NULL) OR '
            '(student_id IS NULL AND outsider_student_id IS NOT NULL)',
            name='chk_aimodelrun_student_or_outsider'
        ),
    )