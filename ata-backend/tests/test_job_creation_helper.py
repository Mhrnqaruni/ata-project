# /tests/test_job_creation_helper.py

import pytest
from unittest.mock import MagicMock, call

# Import the specialist functions we want to test
from app.services.assessment_helpers import job_creation

# Import the Pydantic models needed to create test data
from app.models.assessment_model import AssessmentConfig, AssessmentConfigV2, QuestionConfig, SectionConfigV2, QuestionConfigV2, ScoringMethod

# --- Test Data Fixtures ---

@pytest.fixture
def mock_db_service():
    """Mocks the DatabaseService to isolate our test from the real CSV files."""
    db = MagicMock()
    # When get_students_by_class_id is called, return a predefined list
    db.get_students_by_class_id.return_value = [
        {'id': 'stu_001', 'name': 'Student One'},
        {'id': 'stu_002', 'name': 'Student Two'},
        {'id': 'stu_003', 'name': 'Student Three'},
    ]
    return db

@pytest.fixture
def mock_db_service_v2():
    """A separate mock for the V2 test with a different number of students."""
    db = MagicMock()
    db.get_students_by_class_id.return_value = [
        {'id': 'stu_101', 'name': 'Student A'},
        {'id': 'stu_102', 'name': 'Student B'},
        {'id': 'stu_103', 'name': 'Student C'},
        {'id': 'stu_104', 'name': 'Student D'},
    ]
    return db

@pytest.fixture
def v1_config():
    """Creates a valid V1 AssessmentConfig object for testing."""
    return AssessmentConfig(
        assessmentName="V1 Test",
        classId="cls_v1",
        questions=[
            QuestionConfig(text="Q1", rubric="R1"),
            QuestionConfig(text="Q2", rubric="R2"),
        ]
    )

@pytest.fixture
def v2_config():
    """Creates a valid V2 AssessmentConfigV2 object for testing."""
    return AssessmentConfigV2(
        assessmentName="V2 Test",
        classId="cls_v2",
        scoringMethod=ScoringMethod.PER_QUESTION,
        sections=[
            SectionConfigV2(title="Section 1", questions=[
                QuestionConfigV2(text="Q1", rubric="R1", maxScore=10)
            ]),
            SectionConfigV2(title="Section 2", questions=[
                QuestionConfigV2(text="Q2", rubric="R2", maxScore=15),
                QuestionConfigV2(text="Q3", rubric="R3", maxScore=5),
            ])
        ]
    )

# --- Unit Tests ---

def test_create_initial_job_records_v1(mock_db_service, v1_config):
    """
    GIVEN: A V1 assessment config with 2 questions and a mock DB with 3 students.
    WHEN:  The _create_initial_job_records (V1) specialist is called.
    THEN:  It should create exactly 1 job record and 6 result records (3 students * 2 questions).
    """
    job_id = "job_v1_test"
    user_id = "user_v1_test"
    answer_sheet_data = [{"path": "/fake/path.pdf", "contentType": "application/pdf"}]

    # Call the function we are testing
    job_creation._create_initial_job_records(mock_db_service, job_id, v1_config, answer_sheet_data, user_id)

    # Assert that the main job was created exactly once
    mock_db_service.add_assessment_job.assert_called_once()
    
    # Assert that the result record creation was called the correct number of times
    # 3 students * 2 questions = 6 calls
    assert mock_db_service.save_student_grade_result.call_count == 6
    
    # Optional: A more specific check on one of the calls
    first_call_args = mock_db_service.save_student_grade_result.call_args_list[0]
    assert first_call_args[0][0]['student_id'] == 'stu_001'
    assert first_call_args[0][0]['status'] == 'pending_match'
    
    print("\n✅ SUCCESS: test_create_initial_job_records_v1 passed.")

def test_create_initial_job_records_v2(mock_db_service_v2, v2_config):
    """
    GIVEN: A V2 assessment config with 3 total questions and a mock DB with 4 students.
    WHEN:  The _create_initial_job_records_v2 (V2) specialist is called.
    THEN:  It should create exactly 1 job record and 12 result records (4 students * 3 questions).
    """
    job_id = "job_v2_test"
    user_id = "user_v2_test"
    answer_sheet_data = [{"path": "/fake/path.docx", "contentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}]

    # Call the function we are testing
    job_creation._create_initial_job_records_v2(mock_db_service_v2, job_id, v2_config, answer_sheet_data, user_id)

    # Assert that the main job was created exactly once
    mock_db_service_v2.add_assessment_job.assert_called_once()
    
    # Assert that the result record creation was called the correct number of times
    # 4 students * 3 questions = 12 calls
    assert mock_db_service_v2.save_student_grade_result.call_count == 12
    
    # Optional: A more specific check on one of the calls to ensure the nested loop is working
    last_call_args = mock_db_service_v2.save_student_grade_result.call_args_list[-1]
    assert last_call_args[0][0]['student_id'] == 'stu_104'
    assert last_call_args[0][0]['question_id'] == v2_config.sections[1].questions[1].id
    
    print("\n✅ SUCCESS: test_create_initial_job_records_v2 passed.")