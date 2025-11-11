# /app/services/assessment_helpers/data_assembly.py (FINAL, HARDENED VERSION)

import json
from typing import List, Dict, Union
import pandas as pd

from ...models import assessment_model

def _get_validated_config_from_job(job_record: 'Assessment') -> Union[assessment_model.AssessmentConfig, assessment_model.AssessmentConfigV2]:
    """A specialist helper that robustly parses a job's config JSON."""
    config_str = json.dumps(job_record.config)
    try:
        return assessment_model.AssessmentConfigV2.model_validate_json(config_str)
    except Exception:
        return assessment_model.AssessmentConfig.model_validate_json(config_str)

def _safe_float_convert(value):
    if value is None or str(value).strip() == '': return None
    try: return float(value)
    except (ValueError, TypeError): return None

# --- [THIS IS THE NEW, CORRECTED FUNCTION] ---
def _assemble_job_summaries(all_jobs: List['Assessment'], all_results: List['Result'], all_classes: Dict) -> List[Dict]:
    """
    Specialist for assembling the dashboard summary list.
    This version is hardened to gracefully handle failed or malformed jobs.
    """
    summaries = []
    # Create a DataFrame from the results for efficient, vectorized operations.
    # This is much faster than looping in Python for large datasets.
    results_df = pd.DataFrame([r.__dict__ for r in all_results]) if all_results else pd.DataFrame(columns=['job_id', 'student_id', 'status'])

    for job in all_jobs:
        # Start with a basic, default summary. This will be shown even if parsing fails.
        total_pages_value = job.total_pages if hasattr(job, 'total_pages') and job.total_pages else 0
        print(f"[DATA ASSEMBLY] Job {job.id}: total_pages = {total_pages_value}, status = {job.status}")

        summary = {
            "id": job.id,
            "assessmentName": "Assessment (Processing Error)", # A clear default name
            "className": "Unknown Class",
            "createdAt": job.created_at.isoformat() if job.created_at else "",
            "status": job.status,
            "progress": {"total": 0, "processed": 0},
            "totalPages": total_pages_value
        }
        
        try:
            # Attempt to parse the full, rich details.
            config = _get_validated_config_from_job(job)
            summary["assessmentName"] = config.assessmentName
            summary["className"] = all_classes.get(config.classId, "Unknown Class")
            
            # Only calculate progress if the job is not in a failed state and results exist.
            if job.status != "Failed" and not results_df.empty:
                job_results_df = results_df[results_df['job_id'] == job.id]
                if not job_results_df.empty:
                    total_students = len(job_results_df['student_id'].unique())
                    # Correctly filter for statuses that mean "processed"
                    processed_students = len(job_results_df[~job_results_df['status'].isin(['pending_match', 'matched', 'pending'])]['student_id'].unique())
                    summary["progress"] = {"total": total_students, "processed": processed_students}
            
        except Exception as e:
            # If parsing the config or progress fails, we log it, but we still have the basic summary
            # with the correct ID and "Failed" status, so it will appear in the UI.
            print(f"Could not fully parse summary for job {job.id}, showing basic info. Error: {e}")

        print(f"[DATA ASSEMBLY] Final summary for {job.id}: {summary}")
        summaries.append(summary)

    print(f"[DATA ASSEMBLY] Returning {len(summaries)} summaries")
    return summaries
# --- [END OF THE NEW FUNCTION] ---


def _build_results_dictionary(class_students: List['Student'], config: assessment_model.AssessmentConfigV2, all_results_for_job: List['Result']) -> Dict:
    """Specialist for assembling the complex, nested results dictionary."""
    # This function is already correct and does not need to be changed.
    results_map = {}
    for res in all_results_for_job:
        s_id = res.student_id; q_id = res.question_id
        if s_id not in results_map: results_map[s_id] = {}
        results_map[s_id][q_id] = res

    final_results_dict = {}
    all_questions = [q for section in config.sections for q in section.questions]

    for s in class_students:
        s_id = s.id
        final_results_dict[s_id] = {}
        for q in all_questions:
            q_id = q.id
            result_obj = results_map.get(s_id, {}).get(q_id)
            final_grade = _safe_float_convert(getattr(result_obj, 'grade', None))
            final_results_dict[s_id][q_id] = {
                "grade": final_grade,
                "feedback": getattr(result_obj, 'feedback', None),
                "extractedAnswer": getattr(result_obj, 'extractedAnswer', None),
                "status": getattr(result_obj, 'status', 'pending')
            }
    return final_results_dict