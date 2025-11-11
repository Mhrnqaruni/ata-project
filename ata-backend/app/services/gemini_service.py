# /app/services/gemini_service.py (CLEANED AND FINAL VERSION)

import os
import io
from dotenv import load_dotenv
from typing import List, Dict
import json
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from PIL import Image
from fastapi import WebSocket

# --- Local Imports ---
from .prompt_library import GEMINI_OCR_PROMPT

# --- CONFIGURATION (STABLE) ---
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise ValueError("FATAL ERROR: GOOGLE_API_KEY environment variable is not set.")

GEMINI_PRO_MODEL = 'gemini-2.5-flash' # Correct model for multi-modal
GEMINI_FLASH_MODEL = 'gemini-2.5-flash'
genai.configure(api_key=API_KEY)


# --- CORE GENERATIVE FUNCTIONS ---

async def generate_text(prompt: str, temperature: float = 0.5) -> str:
    """The workhorse for text-only, non-streaming tasks."""
    try:
        model = genai.GenerativeModel(GEMINI_FLASH_MODEL)
        config = GenerationConfig(temperature=temperature)
        response = await model.generate_content_async(prompt, generation_config=config)
        if not response.parts:
            raise ValueError("AI model returned an empty response.")
        return response.text
    except Exception as e:
        print(f"ERROR in generate_text with Gemini API: {e}")
        raise

async def generate_multimodal_response(prompt: str, images: List[Image.Image]) -> str:
    """
    The specialist for multi-modal requests. It accepts a LIST of Pillow Image objects.
    """
    try:
        model = genai.GenerativeModel(GEMINI_PRO_MODEL)
        content = [prompt, *images]
        response = await model.generate_content_async(content)
        if not response.parts:
            raise ValueError("AI model returned an empty response for the multi-modal request.")
        return response.text
    except Exception as e:
        print(f"ERROR in generate_multimodal_response with Gemini API ({len(images)} images): {e}")
        raise

async def generate_text_streaming(prompt: str, websocket: WebSocket) -> str:
    """
    Generates text, streams the response token-by-token over a WebSocket,
    AND returns the final, complete string for persistence.
    """
    full_response = []
    try:
        model = genai.GenerativeModel(GEMINI_FLASH_MODEL)
        stream = await model.generate_content_async(prompt, stream=True)
        
        is_stream_started = False
        async for chunk in stream:
            if chunk.text:
                full_response.append(chunk.text)
                if not is_stream_started:
                    await websocket.send_json({"type": "stream_start", "payload": {}})
                    is_stream_started = True
                await websocket.send_json({"type": "stream_token", "payload": {"token": chunk.text}})

        if is_stream_started:
            await websocket.send_json({"type": "stream_end", "payload": {}})

    except Exception as e:
        print(f"ERROR during streaming generation: {e}")
        try:
            await websocket.send_json({
                "type": "error", 
                "payload": {"message": "Sorry, an error occurred while generating the response."}
            })
        except Exception as ws_error:
            print(f"Failed to send streaming error over WebSocket: {ws_error}")
    
    return "".join(full_response)

async def generate_json(prompt: str, temperature: float = 0.1) -> Dict:
    """
    Generates a response and GUARANTEES the output is a parsable JSON object
    by using the Gemini API's JSON Mode.
    """
    try:
        model = genai.GenerativeModel(GEMINI_FLASH_MODEL)
        config = GenerationConfig(
            temperature=temperature,
            response_mime_type="application/json"
        )
        response = await model.generate_content_async(prompt, generation_config=config)
        if not response.text:
            raise ValueError("AI model returned an empty response.")
        return json.loads(response.text)
    except Exception as e:
        print(f"ERROR in generate_json with Gemini API: {e}")
        raise ValueError(f"Failed to get a valid JSON response from the AI. Error: {e}")

async def generate_multimodal_json(prompt: str, images: List[Image.Image]) -> Dict:
    """
    Generates a JSON response from a multimodal request (text + images),
    guaranteeing a parsable JSON object by using the Gemini API's JSON Mode.
    """
    try:
        model = genai.GenerativeModel(GEMINI_PRO_MODEL)
        config = GenerationConfig(
            temperature=0.1,
            response_mime_type="application/json"
        )
        content = [prompt, *images]
        response = await model.generate_content_async(content, generation_config=config)
        if not response.text:
            raise ValueError("AI model returned an empty response.")
        return json.loads(response.text)
    except Exception as e:
        print(f"ERROR in generate_multimodal_json with Gemini API: {e}")
        raise ValueError(f"Failed to get a valid JSON response from the multimodal AI. Error: {e}")

async def process_file_with_vision(file_bytes: bytes, mime_type: str, prompt: str, temperature: float = 0.1) -> str:
    """
    Processes a file (PDF or image) using Gemini's vision capabilities.
    The AI will OCR, analyze, and respond according to the prompt.
    This replaces traditional OCR with AI vision for better handwriting recognition.

    Uses inline data (base64) instead of File API to avoid ragStoreName errors.
    """
    import base64
    try:
        # Convert file bytes to base64 for inline data
        base64_data = base64.b64encode(file_bytes).decode('utf-8')

        # Create inline data part for the image/PDF
        inline_data = {
            'mime_type': mime_type,
            'data': base64_data
        }

        model = genai.GenerativeModel(GEMINI_FLASH_MODEL)
        config = GenerationConfig(temperature=temperature)

        # Send both the prompt and the inline data to the AI
        response = await model.generate_content_async(
            [prompt, inline_data],
            generation_config=config
        )

        if not response.text:
            raise ValueError("AI model returned an empty response.")

        return response.text
    except Exception as e:
        print(f"ERROR in process_file_with_vision: {e}")
        raise

async def process_file_with_vision_json(file_bytes: bytes, mime_type: str, prompt: str, temperature: float = 0.1, log_context: str = "", max_retries: int = 3) -> Dict:
    """
    Processes a file (PDF or image) using Gemini's vision capabilities and returns JSON.
    The AI will OCR, analyze, and structure the response as JSON according to the prompt.

    Uses inline data (base64) instead of File API to avoid ragStoreName errors.
    Includes retry logic with better JSON extraction for complex documents.

    Args:
        file_bytes: The file content as bytes
        mime_type: The MIME type of the file
        prompt: The prompt to send to the AI
        temperature: Temperature setting for the AI
        log_context: Optional context string for token logging (e.g., "PARSE-QUESTION", "GRADE-STUDENT")
        max_retries: Maximum number of retry attempts (default: 3)

    Returns:
        Dict with two keys: 'data' (the parsed JSON) and 'tokens' (usage metadata)
    """
    import base64
    import re

    # Convert file bytes to base64 for inline data (do this once)
    base64_data = base64.b64encode(file_bytes).decode('utf-8')

    # Create inline data part for the image/PDF
    inline_data = {
        'mime_type': mime_type,
        'data': base64_data
    }

    last_error = None
    total_tokens_used = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}

    for attempt in range(max_retries):
        try:
            model = genai.GenerativeModel(GEMINI_FLASH_MODEL)
            config = GenerationConfig(
                temperature=temperature,
                response_mime_type="application/json"
            )

            # Send both the prompt and the inline data to the AI with JSON mode
            response = await model.generate_content_async(
                [prompt, inline_data],
                generation_config=config
            )

            if not response.text:
                raise ValueError("AI model returned an empty response.")

            # Extract and accumulate token usage data
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                total_tokens_used['prompt_tokens'] += getattr(response.usage_metadata, 'prompt_token_count', 0)
                total_tokens_used['completion_tokens'] += getattr(response.usage_metadata, 'candidates_token_count', 0)
                total_tokens_used['total_tokens'] += getattr(response.usage_metadata, 'total_token_count', 0)

            # Try to extract JSON from response (handle markdown code blocks)
            response_text = response.text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                # Extract content between ```json and ``` or between ``` and ```
                json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1).strip()

            # Try to parse JSON
            parsed_data = json.loads(response_text)

            # Success! Log and return
            if log_context:
                print(f"[TOKEN-USAGE] {log_context} - Prompt: {total_tokens_used['prompt_tokens']}, Completion: {total_tokens_used['completion_tokens']}, Total: {total_tokens_used['total_tokens']}")

            return {
                'data': parsed_data,
                'tokens': total_tokens_used
            }

        except json.JSONDecodeError as e:
            last_error = e

            # Safe printing - handle Unicode encoding errors on Windows
            try:
                print(f"[RETRY {attempt + 1}/{max_retries}] JSON parsing failed in {log_context}: {e}")
                print(f"[RETRY {attempt + 1}/{max_retries}] Response length: {len(response.text) if response and response.text else 0} characters")
            except (UnicodeEncodeError, UnicodeDecodeError):
                print(f"[RETRY {attempt + 1}/{max_retries}] JSON parsing failed (contains special characters)")

            # Try to print preview safely
            if response and response.text:
                try:
                    # Try to print with ASCII-safe encoding
                    safe_preview = response.text[:1000].encode('ascii', errors='replace').decode('ascii')
                    print(f"[RETRY {attempt + 1}/{max_retries}] Response preview: {safe_preview}...")
                except Exception:
                    print(f"[RETRY {attempt + 1}/{max_retries}] Response contains non-printable characters")

                # Show context around error position
                error_pos = getattr(e, 'pos', None)
                if error_pos:
                    try:
                        start = max(0, error_pos - 200)
                        end = min(len(response.text), error_pos + 200)
                        safe_context = response.text[start:end].encode('ascii', errors='replace').decode('ascii')
                        print(f"[RETRY {attempt + 1}/{max_retries}] Context around error position {error_pos}: ...{safe_context}...")
                    except Exception:
                        print(f"[RETRY {attempt + 1}/{max_retries}] Error position: {error_pos}")

            if attempt < max_retries - 1:
                # Try again with slightly higher temperature for variety
                temperature = min(temperature + 0.05, 0.3)
            else:
                # Final attempt failed - save to file for debugging instead of printing
                try:
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.json', prefix='gemini_response_') as f:
                        f.write(response.text if response and response.text else 'No response')
                        temp_path = f.name
                    print(f"[FINAL RETRY FAILED] Full AI response saved to: {temp_path}")
                except Exception as save_err:
                    print(f"[FINAL RETRY FAILED] Could not save response to file: {save_err}")

                raise ValueError(f"Failed to get valid JSON after {max_retries} attempts. Last error: {e}")

        except Exception as e:
            last_error = e
            print(f"[RETRY {attempt + 1}/{max_retries}] Error in {log_context}: {e}")

            if attempt < max_retries - 1:
                # Try again
                continue
            else:
                raise ValueError(f"Failed to get a valid JSON response from the vision AI after {max_retries} attempts. Error: {e}")

    # Should never reach here, but just in case
    raise ValueError(f"Failed to get a valid JSON response from the vision AI. Last error: {last_error}")


async def process_dual_files_with_vision_json(
    file1_bytes: bytes,
    file1_mime_type: str,
    file2_bytes: bytes,
    file2_mime_type: str,
    prompt: str,
    temperature: float = 0.1,
    log_context: str = "",
    max_retries: int = 3
) -> Dict:
    """
    Processes TWO files (PDFs or images) using Gemini's vision capabilities and returns JSON.
    This is specifically for document parsing where both question and answer key are provided.

    Uses inline data (base64) instead of File API to avoid ragStoreName errors.
    Includes retry logic with better JSON extraction for complex documents.

    Args:
        file1_bytes: The first file content as bytes
        file1_mime_type: The MIME type of the first file
        file2_bytes: The second file content as bytes
        file2_mime_type: The MIME type of the second file
        prompt: The prompt to send to the AI
        temperature: Temperature setting for the AI
        log_context: Optional context string for token logging
        max_retries: Maximum number of retry attempts (default: 3)

    Returns:
        Dict with two keys: 'data' (the parsed JSON) and 'tokens' (usage metadata)
    """
    import base64
    import re

    # Convert both files to base64 for inline data (do this once)
    file1_base64 = base64.b64encode(file1_bytes).decode('utf-8')
    file2_base64 = base64.b64encode(file2_bytes).decode('utf-8')

    # Create inline data parts for both files
    inline_data1 = {
        'mime_type': file1_mime_type,
        'data': file1_base64
    }

    inline_data2 = {
        'mime_type': file2_mime_type,
        'data': file2_base64
    }

    last_error = None
    total_tokens_used = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}

    for attempt in range(max_retries):
        try:
            model = genai.GenerativeModel(GEMINI_FLASH_MODEL)
            config = GenerationConfig(
                temperature=temperature,
                response_mime_type="application/json"
            )

            # Send prompt and both files to the AI with JSON mode
            response = await model.generate_content_async(
                [prompt, inline_data1, inline_data2],
                generation_config=config
            )

            if not response.text:
                raise ValueError("AI model returned an empty response.")

            # Extract and accumulate token usage data
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                total_tokens_used['prompt_tokens'] += getattr(response.usage_metadata, 'prompt_token_count', 0)
                total_tokens_used['completion_tokens'] += getattr(response.usage_metadata, 'candidates_token_count', 0)
                total_tokens_used['total_tokens'] += getattr(response.usage_metadata, 'total_token_count', 0)

            # Try to extract JSON from response (handle markdown code blocks)
            response_text = response.text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1).strip()

            # Try to parse JSON
            parsed_data = json.loads(response_text)

            # VALIDATION: Check for empty questions array (Issue #2)
            if 'sections' in parsed_data:
                total_questions = sum(len(section.get('questions', [])) for section in parsed_data.get('sections', []))
                print(f"[VALIDATION] {log_context} - Extracted {total_questions} questions from response")

                # DIAGNOSTIC: Check if answers are populated
                questions_with_answers = 0
                for section in parsed_data.get('sections', []):
                    for question in section.get('questions', []):
                        if question.get('answer') and str(question.get('answer')).strip():
                            questions_with_answers += 1
                print(f"[VALIDATION] {log_context} - Questions with answers: {questions_with_answers}/{total_questions}")

                if total_questions == 0:
                    raise ValueError(f"AI returned valid JSON but with ZERO questions. This is invalid.")

            # Success! Log and return
            if log_context:
                print(f"[TOKEN-USAGE] {log_context} - Prompt: {total_tokens_used['prompt_tokens']}, Completion: {total_tokens_used['completion_tokens']}, Total: {total_tokens_used['total_tokens']}")

            return {
                'data': parsed_data,
                'tokens': total_tokens_used
            }

        except (json.JSONDecodeError, ValueError) as e:
            last_error = e

            # Safe printing - handle Unicode encoding errors on Windows
            try:
                error_type = "JSON parsing" if isinstance(e, json.JSONDecodeError) else "Validation"
                print(f"[RETRY {attempt + 1}/{max_retries}] {error_type} failed in {log_context}: {e}")
                print(f"[RETRY {attempt + 1}/{max_retries}] Response length: {len(response.text) if response and response.text else 0} characters")
            except (UnicodeEncodeError, UnicodeDecodeError):
                print(f"[RETRY {attempt + 1}/{max_retries}] Error occurred (contains special characters)")

            # Try to print preview safely
            if response and response.text:
                try:
                    # Try to print with ASCII-safe encoding
                    safe_preview = response.text[:1000].encode('ascii', errors='replace').decode('ascii')
                    print(f"[RETRY {attempt + 1}/{max_retries}] Response preview: {safe_preview}...")
                except Exception:
                    print(f"[RETRY {attempt + 1}/{max_retries}] Response contains non-printable characters")

                # Show context around error position
                error_pos = getattr(e, 'pos', None)
                if error_pos:
                    try:
                        start = max(0, error_pos - 200)
                        end = min(len(response.text), error_pos + 200)
                        safe_context = response.text[start:end].encode('ascii', errors='replace').decode('ascii')
                        print(f"[RETRY {attempt + 1}/{max_retries}] Context around error position {error_pos}: ...{safe_context}...")
                    except Exception:
                        print(f"[RETRY {attempt + 1}/{max_retries}] Error position: {error_pos}")

            if attempt < max_retries - 1:
                # Try again with slightly higher temperature for variety
                temperature = min(temperature + 0.05, 0.3)
            else:
                # Final attempt failed - save to file for debugging instead of printing
                try:
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.json', prefix='gemini_response_') as f:
                        f.write(response.text if response and response.text else 'No response')
                        temp_path = f.name
                    print(f"[FINAL RETRY FAILED] Full AI response saved to: {temp_path}")
                except Exception as save_err:
                    print(f"[FINAL RETRY FAILED] Could not save response to file: {save_err}")

                raise ValueError(f"Failed to get valid JSON after {max_retries} attempts. Last error: {e}")

        except Exception as e:
            last_error = e
            print(f"[RETRY {attempt + 1}/{max_retries}] Error in {log_context}: {e}")

            if attempt < max_retries - 1:
                # Try again
                continue
            else:
                raise ValueError(f"Failed to get a valid JSON response from the vision AI after {max_retries} attempts. Error: {e}")

    # Should never reach here, but just in case
    raise ValueError(f"Failed to get a valid JSON response from the vision AI. Last error: {last_error}")



async def generate_text_streaming(prompt: str, websocket: WebSocket) -> str:
    """
    Generates text, streams the response token-by-token over a WebSocket,
    AND returns the final, complete string for persistence.
    """
    full_response = []
    try:
        model = genai.GenerativeModel(GEMINI_FLASH_MODEL)
        stream = await model.generate_content_async(prompt, stream=True)
        
        is_stream_started = False
        async for chunk in stream:
            if chunk.text:
                full_response.append(chunk.text)
                if not is_stream_started:
                    # Send a start message the moment the first token arrives
                    await websocket.send_json({"type": "stream_start", "payload": {}})
                    is_stream_started = True
                await websocket.send_json({"type": "stream_token", "payload": {"token": chunk.text}})

        if is_stream_started:
            # Always send an end message if the stream was started
            await websocket.send_json({"type": "stream_end", "payload": {}})

    except Exception as e:
        print(f"ERROR during streaming generation: {e}")
        try:
            await websocket.send_json({
                "type": "error", 
                "payload": {"message": "Sorry, an error occurred while generating the response."}
            })
        except Exception as ws_error:
            print(f"Failed to send streaming error over WebSocket: {ws_error}")
    
    return "".join(full_response)