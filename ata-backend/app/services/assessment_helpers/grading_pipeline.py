# /app/services/assessment_helpers/grading_pipeline.py (VISION-OPTIMIZED)

import io
import json
from typing import List, Dict, Optional
import fitz  # PyMuPDF
from PIL import Image

from ..database_service import DatabaseService
from .. import gemini_service

def _safe_float_convert(value) -> Optional[float]:
    """A helper to safely convert grade values to float, returning None if invalid."""
    if value is None or str(value).strip() == '':
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

def _prepare_images_from_answersheet(answer_sheet_path: str, content_type: str) -> List[Image.Image]:
    """
    Specialist for file ingestion.
    Reads a file from disk and converts it into a list of PIL Images, handling PDF conversion.
    KEPT FOR COMPATIBILITY: This is still used for name extraction in analytics_and_matching.py
    """
    with open(answer_sheet_path, "rb") as f:
        file_bytes = f.read()

    image_list = []
    if content_type and 'pdf' in content_type:
        pdf_document = fitz.open(stream=file_bytes, filetype="pdf")
        for page in pdf_document:
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_bytes))
            image_list.append(image)
    else:
        image = Image.open(io.BytesIO(file_bytes))
        image_list.append(image)

    if not image_list:
        raise ValueError(f"Could not extract any images from the file: {answer_sheet_path}")

    return image_list

async def _invoke_grading_ai_vision(
    file_bytes: bytes,
    mime_type: str,
    prompt: str
) -> Dict:
    """
    Vision-optimized AI grading function.
    Uses Gemini File API with vision capabilities to grade a single question.
    Returns structured JSON with extracted_answer, grade, and feedback.
    """
    return await gemini_service.process_file_with_vision_json(
        file_bytes=file_bytes,
        mime_type=mime_type,
        prompt=prompt,
        temperature=0.1
    )

def _save_single_grading_result_to_db(
    db: DatabaseService,
    job_id: str,
    student_id: str,
    question_id: str,
    grading_result: Dict
):
    """
    Specialist for persistence - saves a single question's grading result.
    """
    clean_grade = _safe_float_convert(grading_result.get('grade'))
    clean_feedback = grading_result.get('feedback', 'No feedback provided.')
    extracted_answer = grading_result.get('extracted_answer', '')

    db.update_student_result_with_grade(
        job_id=job_id,
        student_id=student_id,
        question_id=question_id,
        grade=clean_grade,
        feedback=clean_feedback,
        extracted_answer=extracted_answer,
        status="ai_graded"
    )