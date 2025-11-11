# /tests/test_document_parser.py (WITH DIAGNOSTIC PRINT)

import pytest
import json
from unittest.mock import MagicMock, AsyncMock
from fastapi import UploadFile

pytestmark = pytest.mark.asyncio

from app.services.assessment_helpers.document_parser import parse_document_to_config
from app.models.assessment_model import AssessmentConfigV2
# Import the entire prompt_library module so we can inspect it
from app.services import prompt_library


@pytest.fixture
def mock_upload_file():
    mock = MagicMock(spec=UploadFile)
    mock.read = AsyncMock(return_value=b"fake pdf content")
    mock.content_type = "application/pdf"
    mock.filename = "test_document.pdf"
    return mock

@pytest.fixture
def mock_ai_response():
    return json.dumps({
      "scoringMethod": "per_question",
      "totalScore": None,
      "sections": [
        {
          "title": "Section A: Biology",
          "total_score": None,
          "questions": [
            {
              "id": "q_test_001",
              "text": "What is the powerhouse of the cell?",
              "rubric": "Answer must mention mitochondria.",
              "maxScore": 10,
              "answer": "The mitochondria."
            }
          ]
        }
      ],
      "includeImprovementTips": False
    })


async def test_parse_document_to_config_success(mocker, mock_upload_file, mock_ai_response):
    """
    GIVEN: A mock uploaded file.
    WHEN:  The parse_document_to_config function is called.
    AND:   The OCR and Gemini services are mocked.
    THEN:  The function should return a correctly structured dictionary.
    """
    # --- [DIAGNOSTIC STEP] ---
    # We will print the contents of the imported prompt string to see what the
    # test runner is actually loading at runtime.
    print("\n--- DIAGNOSTIC: Inspecting DOCUMENT_PARSING_PROMPT at runtime ---")
    print(prompt_library.DOCUMENT_PARSING_PROMPT)
    print("--- END DIAGNOSTIC ---")
    # --- [END DIAGNOSTIC STEP] ---
    
    mocker.patch('app.services.ocr_service.extract_text_from_file', return_value="Mock OCR text about mitochondria.")
    mocker.patch('app.services.gemini_service.generate_multimodal_response', new_callable=AsyncMock, return_value=mock_ai_response)
    
    mock_pdf_page = MagicMock()
    mock_pdf_page.get_pixmap.return_value.tobytes.return_value = b"fake_png_bytes"
    mock_pdf_doc = MagicMock()
    mock_pdf_doc.__iter__.return_value = [mock_pdf_page]
    mocker.patch('fitz.open', return_value=mock_pdf_doc)
    mocker.patch('PIL.Image.open', return_value=MagicMock())

    class_id = "cls_test_123"
    assessment_name = "Test Biology Midterm"
    
    result_dict = await parse_document_to_config(mock_upload_file, None, class_id, assessment_name)

    assert isinstance(result_dict, dict)
    assert result_dict['assessmentName'] == assessment_name
    assert result_dict['classId'] == class_id
    assert result_dict['scoringMethod'] == 'per_question'

    print("\n✅ SUCCESS: test_parse_document_to_config_success passed.")