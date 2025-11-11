# /tests/test_assessment_service.py (CORRECTED, WARNING-FREE)

import pytest
from unittest.mock import MagicMock, AsyncMock
import json

# We are no longer using the global pytestmark
# pytestmark = pytest.mark.asyncio 

from app.services.assessment_service import AssessmentService
from app.models.assessment_model import AssessmentConfigV2, SectionConfigV2, QuestionConfigV2, ScoringMethod
from app.services import prompt_library

# --- Test Data Fixtures (Unchanged) ---

@pytest.fixture
def mock_db_service():
    return MagicMock()

@pytest.fixture
def mock_gemini_service(mocker):
    mock = MagicMock()
    mock_json_response = json.dumps({"results": [{"question_id": "q_test_001", "grade": 9, "feedback": "Excellent work."}]})
    mock.generate_multimodal_response = AsyncMock(return_value=mock_json_response)
    return mocker.patch('app.services.assessment_service.gemini_service', mock)

@pytest.fixture
def mock_library_service(mocker):
    mock = MagicMock()
    mock.get_chapter_content = MagicMock(return_value="This is the text from Biology Chapter 1 about cells.")
    return mocker.patch('app.services.assessment_service.library_service', mock)

@pytest.fixture
def v2_config_for_library_test():
    return AssessmentConfigV2(
        assessmentName="Biology Midterm", classId="cls_123",
        scoringMethod=ScoringMethod.PER_QUESTION, gradingMode="library",
        librarySource="biology/chapter1.txt",
        sections=[
            SectionConfigV2(
                questions=[
                    QuestionConfigV2(
                        id="q_test_001", text="What is the powerhouse of the cell?",
                        rubric="Answer must mention mitochondria.", maxScore=10
                    )
                ]
            )
        ]
    )

# --- The Integration Test ---

# --- [THE FIX IS HERE] ---
# Apply the asyncio mark directly to the test function that needs it.
@pytest.mark.asyncio
async def test_grade_submission_with_library_source(
    mock_db_service, 
    mock_gemini_service,
    mock_library_service,
    v2_config_for_library_test,
    mocker
):
# --- [END OF FIX] ---
    """
    GIVEN a V2 assessment configured to grade using a library source
    WHEN the _grade_entire_submission_for_student method is called
    THEN it should call the library service and inject the result into the AI prompt.
    """
    # 1. SETUP
    grading_pipeline_mock = MagicMock()
    grading_pipeline_mock._prepare_images_from_answersheet.return_value = [MagicMock()]
    grading_pipeline_mock._invoke_grading_ai = mock_gemini_service.generate_multimodal_response
    parsed_response_data = {"results": [{"question_id": "q_test_001", "grade": 9, "feedback": "Excellent work."}]}
    grading_pipeline_mock._parse_ai_grading_response.return_value = parsed_response_data
    grading_pipeline_mock._save_grading_results_to_db = MagicMock()
    mocker.patch('app.services.assessment_service.grading_pipeline', grading_pipeline_mock)
    assessment_svc = AssessmentService(db=mock_db_service)

    # 2. EXECUTION
    await assessment_svc._grade_entire_submission_for_entity(
        job_id="job_test_123", entity_id="stu_test_456", is_outsider=False,
        answer_sheet_path="/fake/path.pdf", content_type="application/pdf",
        config=v2_config_for_library_test, user_id="user_test_123"
    )

    # 3. ASSERTION
    mock_library_service.get_chapter_content.assert_called_once_with("biology/chapter1.txt")
    print("\n✅ SUCCESS: Library service was correctly called.")
    mock_gemini_service.generate_multimodal_response.assert_called_once()
    print("✅ SUCCESS: Gemini service was called.")
    call_args, _ = mock_gemini_service.generate_multimodal_response.call_args
    final_prompt = call_args[0]
    assert "This is the text from Biology Chapter 1 about cells." in final_prompt
    print("✅ SUCCESS: Prompt correctly contained the library text.")
    grading_pipeline_mock._save_grading_results_to_db.assert_called_once()
    print("✅ SUCCESS: Database save function was correctly called.")

# --- [NEW TEST FOR PROMPT VALIDATION] ---
# --- [THE FIX IS HERE] ---
# This function is synchronous, so it no longer has the unnecessary asyncio mark.
def test_student_centric_grading_prompt_formats_correctly(v2_config_for_library_test):
# --- [END OF FIX] ---
    """
    GIVEN a valid V2 assessment configuration
    WHEN the STUDENT_CENTRIC_GRADING_PROMPT is formatted with its data
    THEN the resulting prompt string should be correctly structured.
    """

    # 1. SETUP
    config = v2_config_for_library_test
    answer_key_context = "This is the provided answer key context from the library."
    all_questions = [q for section in config.sections for q in section.questions]
    questions_json_str = json.dumps([q.model_dump() for q in all_questions], indent=2)

    # 2. EXECUTION
    final_prompt = prompt_library.STUDENT_CENTRIC_GRADING_PROMPT.format(
        answer_key_context=answer_key_context,
        questions_json=questions_json_str
    )

    # 3. ASSERTION
    assert "You are a highly experienced and objective Teaching Assistant." in final_prompt
    print("\n✅ SUCCESS: Prompt contains the correct persona instruction.")
    assert "This is the provided answer key context from the library." in final_prompt
    print("✅ SUCCESS: Prompt correctly injected the answer key context.")
    assert '"id": "q_test_001"' in final_prompt
    assert '"text": "What is the powerhouse of the cell?"' in final_prompt
    print("✅ SUCCESS: Prompt correctly injected the formatted questions JSON.")
    assert "Generate the JSON output now." in final_prompt
    print("✅ SUCCESS: Prompt contains the correct final instruction.")