# /app/services/ocr_service.py (FINAL & ROBUST - MULTIPROCESSING BRIDGE)

# --- Core Imports ---
import io
import asyncio
from multiprocessing import Process, Manager # Import multiprocessing tools

# --- Third-Party Library Imports ---
import docx

# --- Local Service Imports ---
# NOTE: We cannot pass the gemini_service module to the new process.
# The new process must initialize it itself.

# This function will be run in a completely separate process.
def _run_ocr_in_process(file_bytes, mime_type, return_dict):
    """
    This function initializes its own Gemini client and runs the OCR task
    in total isolation to prevent any state/loop conflicts.
    """
    # We must import and configure services INSIDE the new process.
    from . import gemini_service
    
    async def ocr_task():
        return await gemini_service.ocr_file_with_gemini(file_bytes, mime_type)

    try:
        result = asyncio.run(ocr_task())
        return_dict['result'] = result
    except Exception as e:
        return_dict['error'] = str(e) # Pass error message as a string


# --- The Core Function (Synchronous Wrapper using a Process) ---
def extract_text_from_file(file_bytes: bytes, content_type: str) -> str:
    """
    Extracts raw text by calling the Gemini service in a separate, isolated
    process. This is the most robust way to call async code from a sync
    context within a running async application, preventing all state conflicts.
    """
    # --- Logic for Gemini-supported files (PDFs and Images) ---
    if content_type == 'application/pdf' or content_type.startswith('image/'):
        # A Manager dictionary is a special type that can be shared between processes.
        with Manager() as manager:
            return_dict = manager.dict()

            # Create and start a new process.
            p = Process(
                target=_run_ocr_in_process,
                args=(file_bytes, content_type, return_dict)
            )
            p.start()
            p.join() # The main application waits here for the process to finish.

            if 'error' in return_dict:
                print(f"ERROR: OCR task in separate process failed. Upstream error: {return_dict['error']}")
                return ""
            
            return return_dict.get('result', "")

    # --- Logic for DOCX Files (Unchanged) ---
    elif content_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        try:
            doc = docx.Document(io.BytesIO(file_bytes))
            full_text = [para.text for para in doc.paragraphs]
            text = '\n'.join(full_text)
            return text.strip()
        except Exception as e:
            print(f"ERROR processing .docx file locally: {e}")
            return ""

    # --- Logic for Unsupported Files ---
    else:
        error_message = f"Unsupported file type for processing: '{content_type}'"
        raise ValueError(error_message)