# /app/services/assessment_helpers/document_parser.py

import json
import uuid
import io
from typing import Dict, Optional
from fastapi import UploadFile

from ...models.assessment_model import AssessmentConfigV2
from .. import gemini_service, prompt_library

def _convert_docx_to_pdf(docx_bytes: bytes) -> bytes:
    """
    Convert DOCX file to PDF format for vision processing.
    This preserves images, tables, and formatting using LibreOffice.

    Tries multiple methods in order:
    1. LibreOffice command-line (best quality, preserves everything)
    2. docx2pdf library (Windows with MS Word)
    3. PyMuPDF fallback (basic conversion)
    """
    import tempfile
    import subprocess
    import os
    import platform

    try:
        # Create temporary directory for conversion
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save DOCX to temp file
            docx_path = os.path.join(temp_dir, "input.docx")
            pdf_path = os.path.join(temp_dir, "input.pdf")

            with open(docx_path, 'wb') as f:
                f.write(docx_bytes)

            print(f"[DOCX-CONVERSION] Saved DOCX to temp file ({len(docx_bytes)} bytes)")

            # Method 1: Try LibreOffice/OpenOffice conversion (best quality)
            try:
                if platform.system() == 'Windows':
                    # Common LibreOffice paths on Windows
                    soffice_paths = [
                        r'C:\Program Files\LibreOffice\program\soffice.exe',
                        r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
                        r'C:\Program Files\OpenOffice 4\program\soffice.exe',
                        'soffice'  # If in PATH
                    ]
                else:
                    soffice_paths = ['soffice', 'libreoffice']

                soffice_cmd = None
                for path in soffice_paths:
                    try:
                        # Test if command exists (suppress window on Windows)
                        startupinfo = None
                        if platform.system() == 'Windows':
                            startupinfo = subprocess.STARTUPINFO()
                            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                            startupinfo.wShowWindow = subprocess.SW_HIDE

                        result = subprocess.run(
                            [path, '--version'],
                            capture_output=True,
                            timeout=5,
                            startupinfo=startupinfo,
                            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0
                        )
                        if result.returncode == 0:
                            soffice_cmd = path
                            print(f"[DOCX-CONVERSION] Found LibreOffice at: {path}")
                            break
                    except (FileNotFoundError, subprocess.TimeoutExpired):
                        continue

                if soffice_cmd:
                    # Run LibreOffice conversion (suppress window on Windows)
                    print(f"[DOCX-CONVERSION] Converting with LibreOffice...")
                    startupinfo = None
                    creationflags = 0
                    if platform.system() == 'Windows':
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        startupinfo.wShowWindow = subprocess.SW_HIDE
                        creationflags = subprocess.CREATE_NO_WINDOW

                    result = subprocess.run(
                        [soffice_cmd, '--headless', '--convert-to', 'pdf', '--outdir', temp_dir, docx_path],
                        capture_output=True,
                        timeout=30,
                        text=True,
                        startupinfo=startupinfo,
                        creationflags=creationflags
                    )

                    if result.returncode == 0 and os.path.exists(pdf_path):
                        with open(pdf_path, 'rb') as f:
                            pdf_bytes = f.read()
                        print(f"[DOCX-CONVERSION] Successfully converted DOCX to PDF using LibreOffice ({len(pdf_bytes)} bytes)")
                        return pdf_bytes
                    else:
                        print(f"[DOCX-CONVERSION] LibreOffice conversion failed: {result.stderr}")

            except Exception as e:
                print(f"[DOCX-CONVERSION] LibreOffice method failed: {e}")

            # Method 2: docx2pdf is DISABLED because it opens Word windows and triggers UAC prompts
            # This causes issues on Windows. LibreOffice is the preferred method.
            # If LibreOffice is not available, we fall back to PyMuPDF below.

            # Method 3: Fallback - use PyMuPDF to create a basic PDF
            print(f"[DOCX-CONVERSION] Using PyMuPDF fallback method...")
            try:
                import fitz  # PyMuPDF
                from docx import Document

                # Read DOCX
                doc = Document(io.BytesIO(docx_bytes))

                # Create a new PDF with PyMuPDF
                pdf_doc = fitz.open()
                page = pdf_doc.new_page(width=595, height=842)  # A4 size

                # Add text content
                y_position = 50
                for paragraph in doc.paragraphs:
                    if paragraph.text.strip():
                        try:
                            # Truncate very long lines
                            text = paragraph.text[:500]
                            page.insert_text((50, y_position), text, fontsize=11)
                            y_position += 20

                            # Create new page if needed
                            if y_position > 800:
                                page = pdf_doc.new_page(width=595, height=842)
                                y_position = 50
                        except Exception:
                            continue

                # Save PDF to bytes
                pdf_bytes = pdf_doc.tobytes()
                pdf_doc.close()

                print(f"[DOCX-CONVERSION] Successfully converted DOCX to PDF using PyMuPDF fallback ({len(pdf_bytes)} bytes)")
                return pdf_bytes

            except Exception as e:
                print(f"[DOCX-CONVERSION] PyMuPDF fallback failed: {e}")
                raise ValueError(f"All DOCX to PDF conversion methods failed. LibreOffice is recommended for best quality.")

    except Exception as e:
        print(f"[DOCX-CONVERSION] Error converting DOCX to PDF: {e}")
        raise ValueError(f"Failed to convert DOCX file to PDF for processing: {e}")

async def parse_document_to_config(
    question_file: UploadFile,
    answer_key_file: Optional[UploadFile],
    class_id: str,
    assessment_name: str
) -> Dict:
    """
    Hybrid document parser:
    - For PDF/Images: Uses AI vision directly for better accuracy
    - For DOCX: Uses OCR text extraction + AI (vision API doesn't support DOCX)
    """
    # Read question file
    question_bytes = await question_file.read()
    question_content_type = question_file.content_type

    # DIAGNOSTIC LOGGING - Track file properties
    print(f"[DOC-PARSE] Starting document parse for assessment: {assessment_name}")
    print(f"[DOC-PARSE] Question file: {question_file.filename}")
    print(f"[DOC-PARSE] Question size: {len(question_bytes)} bytes ({len(question_bytes) / 1024:.2f} KB)")
    print(f"[DOC-PARSE] Question type: {question_content_type}")

    if not question_bytes:
        raise ValueError("The Question Document is empty.")

    # Read answer key file if provided
    answer_key_bytes = None
    answer_key_content_type = None
    if answer_key_file and answer_key_file.filename:
        answer_key_bytes = await answer_key_file.read()
        answer_key_content_type = answer_key_file.content_type
        print(f"[DOC-PARSE] Answer key file: {answer_key_file.filename}")
        print(f"[DOC-PARSE] Answer key size: {len(answer_key_bytes)} bytes ({len(answer_key_bytes) / 1024:.2f} KB)")
        print(f"[DOC-PARSE] Answer key type: {answer_key_content_type}")

    # Check if files are DOCX - convert to PDF using LibreOffice
    is_question_docx = 'wordprocessing' in (question_content_type or '') or question_file.filename.endswith('.docx')
    is_answer_key_docx = answer_key_bytes and ('wordprocessing' in (answer_key_content_type or '') or (answer_key_file and answer_key_file.filename.endswith('.docx')))

    # Convert DOCX to PDF using LibreOffice (preserves images, tables, formatting)
    if is_question_docx:
        print(f"[DOCX-CONVERSION] Converting question DOCX to PDF using LibreOffice...")
        question_bytes = _convert_docx_to_pdf(question_bytes)
        question_content_type = 'application/pdf'
        print(f"[DOCX-CONVERSION] Conversion complete. New size: {len(question_bytes)} bytes")

    if is_answer_key_docx and answer_key_bytes:
        print(f"[DOCX-CONVERSION] Converting answer key DOCX to PDF using LibreOffice...")
        answer_key_bytes = _convert_docx_to_pdf(answer_key_bytes)
        answer_key_content_type = 'application/pdf'
        print(f"[DOCX-CONVERSION] Conversion complete. New size: {len(answer_key_bytes)} bytes")

    # Always use vision-optimized prompt now (DOCX converted to PDF)
    prompt = prompt_library.VISION_DOCUMENT_PARSING_PROMPT

    try:
        total_tokens_used = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}

        # Handle dual files with Vision API
        if answer_key_bytes:
            # Use the new dual-file vision processing function with retry logic
            # Increased retries for large documents (5 instead of 3)
            result = await gemini_service.process_dual_files_with_vision_json(
                file1_bytes=question_bytes,
                file1_mime_type=question_content_type,
                file2_bytes=answer_key_bytes,
                file2_mime_type=answer_key_content_type,
                prompt=prompt,
                temperature=0.1,
                log_context="PARSE-DOCUMENT (Question + Answer Key)",
                max_retries=5
            )
            parsed_json = result['data']
            total_tokens_used = result['tokens']

        else:
            # Only question file - use single file vision processing
            # Increased retries for large documents (5 instead of 3)
            result = await gemini_service.process_file_with_vision_json(
                file_bytes=question_bytes,
                mime_type=question_content_type,
                prompt=prompt,
                temperature=0.1,
                log_context="PARSE-DOCUMENT (Question Only)",
                max_retries=5
            )
            parsed_json = result['data']
            total_tokens_used = result['tokens']

    except json.JSONDecodeError as e:
        print(f"Failed to parse AI vision response: {e}")
        raise ValueError("The AI was unable to structure the provided document. Please try a different file or format.")
    except Exception as e:
        print(f"Error in vision-based document parsing: {e}")
        raise ValueError(f"Error processing document with AI vision: {e}")

    try:
        # Generate unique IDs for sections and questions
        if 'sections' in parsed_json and isinstance(parsed_json['sections'], list):
            for section in parsed_json['sections']:
                # Defensive: Ensure section title is never null
                if section.get('title') is None or section.get('title') == '':
                    section['title'] = 'Main Section'
                    print(f"[WARNING] AI returned null/empty section title, using 'Main Section' as fallback")

                # Assign a unique ID to the section
                section['id'] = f"sec_{uuid.uuid4().hex[:8]}"
                if 'questions' in section and isinstance(section['questions'], list):
                    for question in section['questions']:
                        # Assign a unique ID to each question
                        question['id'] = f"q_{uuid.uuid4().hex[:8]}"

        # Add assessment metadata
        parsed_json['assessmentName'] = assessment_name
        parsed_json['classId'] = class_id

        # Validate with Pydantic
        validated_config = AssessmentConfigV2(**parsed_json)

        return validated_config.model_dump()

    except Exception as e:
        print(f"Pydantic validation failed for AI-parsed config: {e}")
        raise ValueError(f"The AI structured the document in an unexpected way. Please check the document's formatting. Details: {e}")
