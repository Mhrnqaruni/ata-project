# /ata-backend/app/models/tool_model.py (CORRECTED AND MODERNIZED)

# --- Core Imports ---
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, List, Optional
from enum import Enum

# --- Enumerations for Tool Settings (Unchanged) ---
class QuestionDifficulty(str, Enum):
    VERY_EASY = "very easy"
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    VERY_HARD = "very hard"

class SlideStyle(str, Enum):
    INFORMATIVE = "informative"
    ENGAGING = "engaging"
    PROFESSIONAL = "professional"

class ToolId(str, Enum):
    QUESTION_GENERATOR = "question-generator"
    SLIDE_GENERATOR = "slide-generator"
    RUBRIC_GENERATOR = "rubric-generator"
    LESSON_PLAN_GENERATOR = "lesson-plan-generator"

# --- Models for the Question Generator ---
class QuestionTypeConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    type: str
    label: str
    count: int
    difficulty: QuestionDifficulty

class QuestionGeneratorSettings(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    grade_level: str
    source_text: Optional[str] = None
    selected_chapter_paths: Optional[List[str]] = None
    question_configs: List[QuestionTypeConfig]

# --- Models for the Slide Generator ---
class SlideGeneratorSettings(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    grade_level: str
    source_text: Optional[str] = None
    selected_chapter_paths: Optional[List[str]] = None
    num_slides: int
    slide_style: SlideStyle
    include_speaker_notes: bool

# --- Models for the Rubric Generator (UPGRADED) ---
class RubricGeneratorSettings(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    grade_level: str
    
    # --- [MODERNIZED ALIAS] ---
    # The validation_alias now uses a simple list of strings.
    assignment_text: Optional[str] = Field(
        default=None,
        validation_alias='source_text' # Pydantic V2 prefers a single alias here for clarity
    )
    # --- [END OF MODERNIZED ALIAS] ---
    
    assignment_chapter_paths: Optional[List[str]] = None
    guidance_text: Optional[str] = None
    guidance_chapter_paths: Optional[List[str]] = None
    criteria: List[str] = Field(..., min_length=2)
    levels: List[str] = Field(..., min_length=2)

# --- Universal Tool Models ---
class ToolGenerationRequest(BaseModel):
    # This is an incoming request model, so it does not need from_attributes.
    tool_id: ToolId
    settings: Dict[str, Any]

class ToolGenerationResponse(BaseModel):
    # This is a response model, so it needs from_attributes.
    model_config = ConfigDict(from_attributes=True)
    generation_id: str
    tool_id: ToolId
    content: str