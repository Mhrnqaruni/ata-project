# /tests/test_assessment_helpers/test_data_assembly.py

import pytest
import json
from datetime import datetime
from unittest.mock import MagicMock

# Import the specialist functions we want to test
from app.services.assessment_helpers.data_assembly import _assemble_job_summaries, _build_results_dictionary
from app.models.assessment_model import QuestionConfig

# --- Test Data Fixtures ---

@pytest.fixture
def mock_all_jobs():
    """Provides a list of mock job objects, as if from the database."""
    def create_mock_job(id, config_dict, status, created_at_iso):
        mock = MagicMock()
        mock.id = id
        mock.config = json.dumps(config_dict)
        mock.status = status
        # FIX: Convert ISO string to a real datetime object
        mock.created_at = datetime.fromisoformat(created_at_iso.replace('Z', '+00:00'))
        # This is needed for the `r.__dict__` call in the code under test
        mock.__dict__ = {'id': mock.id, 'config': mock.config, 'status': mock.status, 'created_at': mock.created_at}
        return mock

    v1_config = {
        "assessmentName": "History Quiz",
        "classId": "cls_101",
        "questions": [{"id": "q_1", "text": "Q1", "rubric": "R1", "maxScore": 10}],
        "includeImprovementTips": False
    }
    return [
        create_mock_job("job_1", v1_config, "Completed", "2025-01-01T12:00:00Z"),
    ]

@pytest.fixture
def mock_all_results():
    """Provides a list of mock result objects, as if from the database."""
    def create_mock_result(job_id, student_id, question_id, grade, status):
        mock = MagicMock()
        mock.job_id = job_id
        mock.student_id = student_id
        mock.question_id = question_id
        mock.grade = grade
        mock.status = status
        # This is needed for the `r.__dict__` call in the code under test
        mock.__dict__ = {'job_id': mock.job_id, 'student_id': mock.student_id, 'question_id': mock.question_id, 'grade': mock.grade, 'status': mock.status}
        return mock

    return [
        create_mock_result("job_1", "stu_A", "q_1", 9.5, "ai_graded"),
        create_mock_result("job_1", "stu_B", "q_1", None, "pending"),
        create_mock_result("job_1", "stu_C", "q_1", 7.0, "edited_by_teacher"),
        create_mock_result("job_2", "stu_D", "q_x", 10.0, "ai_graded"),
    ]

@pytest.fixture
def mock_all_classes():
    """Provides a mock dictionary of class IDs to names."""
    return {
        "cls_101": "10th Grade History",
        "cls_102": "11th Grade Physics"
    }

@pytest.fixture
def mock_class_students():
    """Provides a mock list of student objects for a specific class."""
    def create_mock_student(id, name):
        mock = MagicMock()
        mock.id = id
        mock.name = name
        return mock

    return [
        create_mock_student("stu_A", "Alice"),
        create_mock_student("stu_B", "Bob"),
        create_mock_student("stu_C", "Charlie"),
    ]

@pytest.fixture
def mock_questions_config():
    """Provides a mock list of QuestionConfig objects."""
    return [
        QuestionConfig(id="q_1", text="Q1", rubric="R1", maxScore=10),
        QuestionConfig(id="q_2", text="Q2", rubric="R2", maxScore=15), # A question with no results yet
    ]


# --- Unit Tests for Data Assembly Specialists ---

def test_assemble_job_summaries(mock_all_jobs, mock_all_results, mock_all_classes):
    """
    GIVEN: Raw lists of jobs, results, and classes.
    WHEN:  _assemble_job_summaries is called.
    THEN:  It should return a correctly formatted list of summaries with accurate progress.
    """
    # Call the function under test
    summaries = _assemble_job_summaries(mock_all_jobs, mock_all_results, mock_all_classes)

    # Assertions
    assert isinstance(summaries, list)
    assert len(summaries) == 1  # It should only process the one job in our fixture

    summary = summaries[0]
    assert summary['id'] == "job_1"
    assert summary['assessmentName'] == "History Quiz"
    assert summary['className'] == "10th Grade History"
    assert summary['status'] == "Completed"
    
    # CRITICAL: Test the progress calculation
    # 3 unique students (A, B, C) are associated with job_1
    assert summary['progress']['total'] == 3
    # 2 students (A, C) have a non-pending status ('ai_graded', 'edited_by_teacher')
    assert summary['progress']['processed'] == 2
    
    print("\n✅ SUCCESS: test_assemble_job_summaries passed.")


def test_build_results_dictionary(mock_class_students, mock_questions_config, mock_all_results):
    """
    GIVEN: Raw lists of students, questions, and results for a single job.
    WHEN:  _build_results_dictionary is called.
    THEN:  It should return a correctly nested dictionary with all students and questions.
    """
    # Filter results for just job_1 for this test
    # FIX: Use attribute access (r.job_id) instead of dictionary access (r['job_id'])
    job_1_results = [r for r in mock_all_results if r.job_id == 'job_1']

    # Call the function under test
    results_dict = _build_results_dictionary(mock_class_students, mock_questions_config, job_1_results)

    # Assertions
    assert isinstance(results_dict, dict)
    
    # Check that all students are present as keys
    assert "stu_A" in results_dict
    assert "stu_B" in results_dict
    assert "stu_C" in results_dict
    
    # Check a student with a result (Alice)
    alice_results = results_dict['stu_A']
    assert "q_1" in alice_results
    assert "q_2" in alice_results # Even questions with no result should be present
    assert alice_results['q_1']['grade'] == 9.5 # Check safe_float_convert
    assert alice_results['q_1']['status'] == 'ai_graded'
    assert alice_results['q_2']['grade'] is None # Check handling of missing results
    
    # Check a student with a pending result (Bob)
    bob_results = results_dict['stu_B']
    assert bob_results['q_1']['grade'] is None # Correctly handles None grade
    assert bob_results['q_1']['status'] == 'pending'
    
    print("\n✅ SUCCESS: test_build_results_dictionary passed.")