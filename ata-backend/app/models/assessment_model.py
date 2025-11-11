# /ata-backend/app/models/assessment_model.py (DEFINITIVELY CORRECTED)

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Dict, Union, Any, Literal
from enum import Enum
import uuid

def to_camel(s: str) -> str:
    parts = s.split('_')
    return parts[0] + ''.join(p.capitalize() for p in parts[1:])

# --- Core Enumerations ---
class JobStatus(str, Enum):
    QUEUED = "Queued"; PROCESSING = "Processing"; SUMMARIZING = "Summarizing"
    PENDING_REVIEW = "Pending Review"; COMPLETED = "Completed"; FAILED = "Failed"
    
class ScoringMethod(str, Enum):
    PER_QUESTION = "per_question"; PER_SECTION = "per_section"; TOTAL_SCORE = "total_score"

class GradingMode(str, Enum):
    ANSWER_KEY_PROVIDED = "answer_key_provided"
    AI_AUTO_GRADE = "ai_auto_grade"
    LIBRARY = "library"

# --- API Contract Models ---

class QuestionConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str = Field(default_factory=lambda: f"q_{uuid.uuid4().hex[:8]}")
    text: str = Field(..., min_length=1)
    rubric: Optional[str] = Field(default="", description="The specific grading rubric for this question. Can be None or empty string.")
    maxScore: int = Field(default=10, gt=0)
    answer: Optional[str] = Field(default="", description="The correct answer from the answer key document. Can be None or empty string.")

class AssessmentConfig(BaseModel):
    # This model is for incoming data, so it doesn't strictly need from_attributes,
    # but adding it is harmless and good for consistency.
    model_config = ConfigDict(from_attributes=True)
    assessmentName: str
    classId: str
    questions: List[QuestionConfig] = Field(..., min_length=1)
    includeImprovementTips: bool = Field(default=False)

    @field_validator('questions')
    @classmethod
    def questions_must_not_be_empty(cls, v):
        if not v: raise ValueError('Assessment must have at least one question.')
        return v

class QuestionConfigV2(QuestionConfig):
    model_config = ConfigDict(from_attributes=True)
    maxScore: Optional[int] = Field(None, gt=0)
    answer: Optional[Union[str, Dict[str, Any]]] = Field(None, description="The correct answer, which can be a string or a structured object.")

class SectionConfigV2(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str = Field(default_factory=lambda: f"sec_{uuid.uuid4().hex[:8]}")
    title: str = Field(default="Main Section")
    total_score: Optional[int] = Field(None, gt=0)
    questions: List[QuestionConfigV2] = Field(..., min_length=1)

class AssessmentConfigV2(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    assessmentName: str
    classId: str
    scoringMethod: ScoringMethod
    totalScore: Optional[int] = Field(None, gt=0)
    sections: List[SectionConfigV2] = Field(..., min_length=1)
    includeImprovementTips: bool = Field(default=False)
    gradingMode: GradingMode = Field(default=GradingMode.ANSWER_KEY_PROVIDED)
    librarySource: Optional[str] = Field(None)

class AssessmentJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    jobId: str; status: JobStatus; message: str

class StudentForGrading(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; name: str; answerSheetPath: str

class GradingResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    grade: Optional[float] = None; feedback: Optional[str] = None
    extractedAnswer: Optional[str] = None; status: str

class Analytics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    classAverage: float; medianGrade: float
    gradeDistribution: Dict[str, int]; performanceByQuestion: Dict[str, float]

class AssessmentResultsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    jobId: str; assessmentName: str; status: JobStatus
    config: AssessmentConfigV2
    students: List[StudentForGrading]
    results: Dict[str, Dict[str, GradingResult]]
    analytics: Optional[Analytics] = None
    aiSummary: Optional[str] = None

class AssessmentJobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str; assessmentName: str; className: str
    createdAt: str; status: JobStatus
    progress: Optional[Dict[str, int]] = None
    totalPages: Optional[float] = None

class AssessmentJobListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    assessments: List[AssessmentJobSummary]

class AssessmentConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    assessmentName: str
    questions: List[QuestionConfig]
    includeImprovementTips: bool

# --- Models for Review Workflow ---

class ReviewStatus(str, Enum):
    AI_GRADED = "AI_GRADED"
    PENDING_REVIEW = "PENDING_REVIEW"
    TEACHER_GRADED = "TEACHER_GRADED"

class FinalizedBy(str, Enum):
    AI = "AI"
    TEACHER = "TEACHER"

class StudentAIGradedSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)
    student_id: str
    name: str
    total_score: float

class StudentPendingSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)
    student_id: str
    name: str
    num_pending: int

class AssessmentResultsOverviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)
    job_id: str
    assessment_name: str
    status: JobStatus
    students_ai_graded: List[StudentAIGradedSummary]
    students_pending: List[StudentPendingSummary]
    students: List['StudentResultRow'] = []

class QuestionForReview(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)
    question_id: str
    question_text: str
    max_score: int
    student_answer: Optional[str] = None
    status: str
    grade: Optional[float] = None
    feedback: Optional[str] = None

class StudentReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)
    job_id: str
    student_id: str
    student_name: str
    assessment_name: str
    config: AssessmentConfigV2
    per_question: List[QuestionForReview]

class QuestionSaveRequest(BaseModel):
    grade: float
    feedback: str

class StudentSaveConfirmation(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)
    student_id: str
    total_score: float
    message: str = "Changes saved successfully."

class CamelModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

class StudentResultRow(CamelModel):
    entity_id: str  # The stable, unique DB ID for API calls
    student_id: str # The display ID, which could be 'Outsider'
    student_name: str
    status: Literal["AI_GRADED", "PENDING_REVIEW", "TEACHER_GRADED", "ABSENT", "OUTSIDER"]
    total_score: Optional[float] = None
    max_total_score: Optional[float] = None
    report_token: Optional[str] = None
    is_outsider: bool = False
    is_absent: bool = False

class ScoreDistributionRequest(BaseModel):
    config: AssessmentConfigV2
    totalMarks: int