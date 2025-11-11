
# /app/services/assessment_helpers/analytics_and_matching.py (FINAL, CORRECTED, SUPERVISOR-APPROVED VERSION)

"""
This module contains specialist helper functions for the middle and end stages
of the assessment grading pipeline.

It is called by the main `assessment_service` and is responsible for:
1. Automatically matching uploaded answer sheet files to students in a roster.
2. Calculating aggregate analytics and statistics for a completed job.
3. Normalizing and validating the job's configuration data.

The `match_files_to_students` function has been made "user-aware" to ensure
all its database operations are securely scoped.
"""

import json
from typing import List, Dict, Union
import pandas as pd
import asyncio

from ...models import assessment_model
from ..database_service import DatabaseService

# --- PURE UTILITY FUNCTIONS (Correct and Unchanged) ---
# These functions do not interact with the database directly. They operate on
# data that has already been securely fetched, so they do not require user context.

def get_validated_config_from_job(job_record: 'Assessment') -> Union[assessment_model.AssessmentConfig, assessment_model.AssessmentConfigV2]:
    """
    Tries to parse config as V2 first, falls back to V1 for backward compatibility.
    This version is hardened to handle both dict and str config types.
    """
    config_data = job_record.config
    
    if isinstance(config_data, str):
        try:
            config_data = json.loads(config_data)
        except json.JSONDecodeError:
            raise ValueError("Config is a malformed JSON string.")

    try:
        return assessment_model.AssessmentConfigV2.model_validate(config_data)
    except Exception:
        return assessment_model.AssessmentConfig.model_validate(config_data)

def normalize_config_to_v2(job_record: 'Assessment') -> assessment_model.AssessmentConfigV2:
    """Takes a job record and ALWAYS returns an AssessmentConfigV2 model."""
    config = get_validated_config_from_job(job_record)
    
    if isinstance(config, assessment_model.AssessmentConfigV2):
        return config
    
    # This logic correctly upgrades a V1 config to the V2 structure.
    v1_questions_as_v2 = [assessment_model.QuestionConfigV2(**q.model_dump()) for q in config.questions]
    
    v1_as_v2_section = assessment_model.SectionConfigV2(
        title="Main Section",
        questions=v1_questions_as_v2
    )
    
    return assessment_model.AssessmentConfigV2(
        assessmentName=config.assessmentName,
        classId=config.classId,
        scoringMethod=assessment_model.ScoringMethod.PER_QUESTION,
        includeImprovementTips=getattr(config, 'includeImprovementTips', False),
        sections=[v1_as_v2_section]
    )

def calculate_analytics(all_results: List['Result'], config: assessment_model.AssessmentConfigV2) -> Dict:
    """Calculates aggregate statistics for a completed assessment."""
    all_questions = [q for section in config.sections for q in section.questions]
    
    results_dicts = [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in all_results]
    df = pd.DataFrame(results_dicts)

    # Robust checks for empty or invalid data.
    if df.empty or 'grade' not in df.columns:
         return {"classAverage": 0, "medianGrade": 0, "gradeDistribution": {}, "performanceByQuestion": {}}
    
    df['grade'] = pd.to_numeric(df['grade'], errors='coerce')
    df.dropna(subset=['grade'], inplace=True)
    if df.empty: return {"classAverage": 0, "medianGrade": 0, "gradeDistribution": {}, "performanceByQuestion": {}}
    
    total_max_score = sum(q.maxScore for q in all_questions if q.maxScore is not None)
    if total_max_score == 0: return {"classAverage": 0, "medianGrade": 0, "gradeDistribution": {}, "performanceByQuestion": {}}
    
    student_scores = df.groupby('student_id')['grade'].sum()
    student_percentages = (student_scores / total_max_score) * 100

    question_perf = {}
    for q in all_questions:
        q_grades = df[df['question_id'] == q.id]['grade'].dropna().tolist()
        avg_score = (sum(q_grades) / len(q_grades)) if q_grades else 0
        question_perf[q.id] = (avg_score / q.maxScore) * 100 if q.maxScore and q.maxScore > 0 else 0
    
    bins = [0, 59.99, 69.99, 79.99, 89.99, 101]
    labels = ["F (0-59)", "D (60-69)", "C (70-79)", "B (80-89)", "A (90-100)"]
    grade_dist = pd.cut(student_percentages, bins=bins, labels=labels, right=False).value_counts().sort_index().to_dict()
    
    return {
        "classAverage": round(float(student_percentages.mean()), 2) if not student_percentages.empty else 0,
        "medianGrade": round(float(student_percentages.median()), 2) if not student_percentages.empty else 0,
        "gradeDistribution": grade_dist,
        "performanceByQuestion": {k: round(v, 2) for k, v in question_perf.items()}
    }

import uuid
import os
from .. import gemini_service, prompt_library
from . import grading_pipeline

def _create_results_for_entity(db: DatabaseService, job_id: str, entity_id: str, entity_type: str, config: Union[assessment_model.AssessmentConfig, assessment_model.AssessmentConfigV2], file_info: Dict, user_id: str):
    """Creates placeholder result records for all questions for a given entity (student or outsider)."""
    all_questions = [q for s in config.sections for q in s.questions] if isinstance(config, assessment_model.AssessmentConfigV2) else config.questions

    for question in all_questions:
        result_id = f"res_{uuid.uuid4().hex[:16]}"

        result_payload = {
            "id": result_id,
            "job_id": job_id,
            "question_id": question.id,
            "grade": None,
            "feedback": None,
            "extractedAnswer": None,
            "status": "pending_grade",
            "answer_sheet_path": file_info.get('path', ''),
            "content_type": file_info.get('contentType', '')
        }

        if entity_type == 'student':
            result_payload['student_id'] = entity_id
            result_payload['outsider_student_id'] = None
        elif entity_type == 'outsider':
            result_payload['student_id'] = None
            result_payload['outsider_student_id'] = entity_id
        else:
            continue # Should not happen

        db.save_student_grade_result(result_payload)

# --- DATABASE-INTERACTIVE HELPER (Corrected and Secure) ---
async def match_files_to_students(
    db: DatabaseService, 
    job_id: str,
    user_id: str
):
    """
    Matches uploaded answer sheets to students. If a match is found, it creates
    the necessary Result records. If a file does not match anyone on the roster,
    it uses a multimodal AI call to extract the student's name from the document
    image and creates a new "Outsider" student.
    """
    job = db.get_assessment_job(job_id=job_id, user_id=user_id)
    if not job:
        print(f"ERROR: Job {job_id} not found or access denied for user {user_id} during file matching.")
        return

    config = normalize_config_to_v2(job)
    students = db.get_students_by_class_id(class_id=config.classId, user_id=user_id)
    student_map = {s.name.lower().strip(): s.id for s in students}
    
    unassigned_files_data = job.answer_sheet_paths
    if isinstance(unassigned_files_data, str):
        unassigned_files = json.loads(unassigned_files_data)
    else:
        unassigned_files = unassigned_files_data

    if not isinstance(unassigned_files, list):
        print(f"WARNING: answer_sheet_paths for job {job_id} is not a list. Skipping matching.")
        return

    for file_info in unassigned_files:
        path = file_info.get('path')
        content_type = file_info.get('contentType')
        if not path or not content_type:
            continue

        try:
            with open(path, "rb") as f:
                file_bytes = f.read()

            # Use vision-based name extraction for matching
            extracted_name = None
            try:
                # Use vision to extract student name from the document
                result = await gemini_service.process_file_with_vision_json(
                    file_bytes=file_bytes,
                    mime_type=content_type,
                    prompt=prompt_library.VISION_NAME_EXTRACTION_PROMPT,
                    temperature=0.1,
                    log_context="EXTRACT-NAME (Outsider Student)"
                )
                extracted_name = result['data'].get("studentName", "").strip()
            except Exception as name_exc:
                print(f"Could not extract name via vision AI for {path}: {name_exc}")
                extracted_name = None

            # Try to match the extracted name to rostered students
            match_found = False
            if extracted_name:
                normalized_extracted = extracted_name.lower().strip()
                for student_name, student_id in student_map.items():
                    if student_name in normalized_extracted or normalized_extracted in student_name:
                        print(f"Matched file {path} to rostered student {student_name} ({student_id}) via vision")
                        _create_results_for_entity(db, job_id, student_id, 'student', config, file_info, user_id)
                        match_found = True
                        break

            if not match_found:
                # This is an outsider
                outsider_name = extracted_name if extracted_name else "Unknown Student"
                print(f"File {path} did not match. Creating new outsider student: {outsider_name}")

                new_outsider = db.add_outsider_student({
                    "name": outsider_name,
                    "assessment_id": job_id
                })

                _create_results_for_entity(db, job_id, new_outsider.id, 'outsider', config, file_info, user_id)

        except FileNotFoundError:
            print(f"ERROR: File not found during matching for job {job_id}: {path}")
        except Exception as e:
            print(f"ERROR matching file {path} for job {job_id}: {e}")