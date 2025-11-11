import uuid
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class OutsiderStudent(Base):
    __tablename__ = 'outsider_students'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, index=True)
    assessment_id = Column(String, ForeignKey('assessments.id'), nullable=False, index=True)

    assessment = relationship("Assessment", back_populates="outsider_students")
    results = relationship("Result", back_populates="outsider_student")