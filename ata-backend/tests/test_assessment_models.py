# /tests/test_assessment_models.py

import pytest
from pydantic import ValidationError

# Import the specific models we need to test from our application code
from app.models.assessment_model import AssessmentConfigV2, SectionConfigV2, QuestionConfigV2, ScoringMethod

# --- Test Data Fixtures ---
# Using pytest fixtures to provide clean, reusable test data.

@pytest.fixture
def valid_question_data_v2():
    """Provides a valid dictionary for a single V2 question."""
    return {
        "id": "q_test_001",
        "text": "What is the powerhouse of the cell?",
        "rubric": "Answer must mention mitochondria.",
        "maxScore": 10,
        "answer": "The mitochondria."
    }

@pytest.fixture
def valid_section_data_v2(valid_question_data_v2):
    """Provides a valid dictionary for a single V2 section containing one question."""
    return {
        "id": "sec_test_abc",
        "title": "Section A: Biology",
        "questions": [valid_question_data_v2]
    }

@pytest.fixture
def valid_assessment_config_data_v2(valid_section_data_v2):
    """Provides a complete, valid dictionary for a V2 assessment configuration."""
    return {
        "assessmentName": "Biology Midterm",
        "classId": "cls_12345",
        "scoringMethod": "per_question",
        "sections": [valid_section_data_v2],
        "includeImprovementTips": True
    }


# --- Unit Tests for AssessmentConfigV2 ---

def test_valid_assessment_config_v2_creation(valid_assessment_config_data_v2):
    """
    GIVEN: A dictionary with valid data for a V2 assessment.
    WHEN:  An AssessmentConfigV2 model is instantiated from this data.
    THEN:  The model is created successfully without raising a validation error,
           and all fields are correctly assigned.
    """
    # This is the "happy path" test.
    try:
        model = AssessmentConfigV2(**valid_assessment_config_data_v2)
        
        # Assert that all top-level fields are correct
        assert model.assessmentName == "Biology Midterm"
        assert model.scoringMethod == ScoringMethod.PER_QUESTION
        
        # Assert that the nested structures are also correct Pydantic models
        assert len(model.sections) == 1
        assert isinstance(model.sections[0], SectionConfigV2)
        assert model.sections[0].title == "Section A: Biology"
        
        assert len(model.sections[0].questions) == 1
        assert isinstance(model.sections[0].questions[0], QuestionConfigV2)
        assert model.sections[0].questions[0].text == "What is the powerhouse of the cell?"
        assert model.sections[0].questions[0].answer == "The mitochondria."

        print("\n✅ SUCCESS: test_valid_assessment_config_v2_creation passed.")

    except ValidationError as e:
        pytest.fail(f"Valid data unexpectedly failed validation: {e}")


def test_assessment_config_v2_missing_required_fields(valid_assessment_config_data_v2):
    """
    GIVEN: A dictionary for a V2 assessment that is missing a required field ('assessmentName').
    WHEN:  An attempt is made to create an AssessmentConfigV2 model.
    THEN:  A Pydantic ValidationError is raised.
    """
    # This tests our validation rules.
    invalid_data = valid_assessment_config_data_v2.copy()
    del invalid_data["assessmentName"] # Remove a required field

    with pytest.raises(ValidationError) as excinfo:
        AssessmentConfigV2(**invalid_data)

    # We can inspect the error to be more specific if needed
    assert "assessmentName" in str(excinfo.value)
    
    print("\n✅ SUCCESS: test_assessment_config_v2_missing_required_fields passed as expected.")


def test_assessment_config_v2_empty_sections_list(valid_assessment_config_data_v2):
    """
    GIVEN: A dictionary for a V2 assessment where the 'sections' list is empty.
    WHEN:  An attempt is made to create an AssessmentConfigV2 model.
    THEN:  A Pydantic ValidationError is raised because 'sections' must have at least one item.
    """
    # This tests our 'min_items=1' validator.
    invalid_data = valid_assessment_config_data_v2.copy()
    invalid_data["sections"] = [] # Make the list empty

    with pytest.raises(ValidationError) as excinfo:
        AssessmentConfigV2(**invalid_data)

    assert "List should have at least 1 item" in str(excinfo.value)
    
    print("\n✅ SUCCESS: test_assessment_config_v2_empty_sections_list passed as expected.")

def test_assessment_config_v2_invalid_scoring_method(valid_assessment_config_data_v2):
    """
    GIVEN: A dictionary for a V2 assessment with an invalid string for 'scoringMethod'.
    WHEN:  An attempt is made to create an AssessmentConfigV2 model.
    THEN:  A Pydantic ValidationError is raised because the value is not a valid member of the Enum.
    """
    # This tests our ScoringMethod Enum.
    invalid_data = valid_assessment_config_data_v2.copy()
    invalid_data["scoringMethod"] = "by_magic" # Invalid value

    with pytest.raises(ValidationError) as excinfo:
        AssessmentConfigV2(**invalid_data)

    assert "Input should be 'per_question', 'per_section' or 'total_score'" in str(excinfo.value)

    print("\n✅ SUCCESS: test_assessment_config_v2_invalid_scoring_method passed as expected.")