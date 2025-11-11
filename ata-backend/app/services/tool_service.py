# /ata-backend/app/services/tool_service.py (MODIFIED AND APPROVED - FLAWLESS VERSION)

"""
This service module acts as the central orchestrator for all AI content
generation tools.

It is responsible for:
1. Receiving a generation request from the `tools_router`.
2. Processing any source material (direct text, uploaded file, or library content).
3. Dispatching the request to the appropriate specialist AI handler.
4. Calling the `history_service` to persist the final, user-owned generation record.

This module has been made "user-aware" to ensure that all generated content
is correctly saved to the history of the authenticated user who initiated the request.
"""

from typing import Dict, Any, Optional
from pydantic import ValidationError
from fastapi import UploadFile
import asyncio
import os

from ..models.tool_model import ToolId, QuestionGeneratorSettings, SlideGeneratorSettings, RubricGeneratorSettings
from ..services import gemini_service, history_service, prompt_library, ocr_service
from .database_service import DatabaseService

# --- Tool-Specific Logic Functions (These are pure utilities and require no changes) ---

async def _handle_question_generator(settings: Dict[str, Any]) -> str:
    """
    Specialist handler for the Question Generator tool.
    Validates settings and calls the AI with the appropriate prompt.
    """
    try:
        validated_settings = QuestionGeneratorSettings(**settings)
    except ValidationError as e:
        raise ValueError(f"Invalid question settings provided. Details: {e}")
    if not validated_settings.source_text or len(validated_settings.source_text) < 20:
        raise ValueError("A valid source must be provided (Text, File, or Library Chapters) with sufficient content.")
    plan_lines = [f"- Generate {config.count} {config.difficulty.value} '{config.label}'." for config in validated_settings.question_configs]
    generation_plan_string = "\n".join(plan_lines)
    prompt = prompt_library.QUESTION_GENERATOR_PROMPT_V2.format(
        grade_level=validated_settings.grade_level,
        source_text=validated_settings.source_text,
        generation_plan_string=generation_plan_string
    )
    return await gemini_service.generate_text(prompt, temperature=0.7)


async def _handle_slide_generator(settings: Dict[str, Any]) -> str:
    """
    Specialist handler for the Slide Generator tool.
    Validates settings and calls the AI with the appropriate prompt.
    """
    try:
        validated_settings = SlideGeneratorSettings(**settings)
    except ValidationError as e:
        raise ValueError(f"Invalid slide settings provided. Details: {e}")
    if not validated_settings.source_text or len(validated_settings.source_text) < 10:
        raise ValueError("A valid source must be provided (Text, File, or Library Chapters) with sufficient content.")
    prompt = prompt_library.SLIDE_GENERATOR_PROMPT_V2.format(
        grade_level=validated_settings.grade_level,
        num_slides=validated_settings.num_slides,
        slide_style=validated_settings.slide_style.value,
        include_speaker_notes=validated_settings.include_speaker_notes,
        source_text=validated_settings.source_text
    )
    return await gemini_service.generate_text(prompt, temperature=0.6)


async def _handle_rubric_generator(settings: Dict[str, Any]) -> str:
    """
    Specialist handler for the Rubric Generator tool.
    Validates settings and calls the AI with the appropriate prompt.
    """
    try:
        validated_settings = RubricGeneratorSettings(**settings)
    except ValidationError as e:
        raise ValueError(f"Invalid rubric settings provided. Details: {e}")
    assignment_context_text = validated_settings.assignment_text or ""
    rubric_guidance_text = validated_settings.guidance_text or "None provided."
    if not assignment_context_text:
         raise ValueError("An 'Assignment Context' must be provided from Text, a File, or the Library.")
    criteria_string = ", ".join(validated_settings.criteria)
    levels_string = ", ".join(validated_settings.levels)
    prompt = prompt_library.RUBRIC_GENERATOR_PROMPT_V2.format(
        grade_level=validated_settings.grade_level,
        criteria_string=criteria_string,
        levels_string=levels_string,
        assignment_context_text=assignment_context_text,
        rubric_guidance_text=rubric_guidance_text
    )
    return await gemini_service.generate_text(prompt, temperature=0.5)


# --- Tool Handler Dispatcher (This is a static mapping and requires no changes) ---
TOOL_HANDLERS = {
    ToolId.QUESTION_GENERATOR: _handle_question_generator,
    ToolId.SLIDE_GENERATOR: _handle_slide_generator,
    ToolId.RUBRIC_GENERATOR: _handle_rubric_generator,
}


# --- Main Orchestration Function (MODIFIED AND SECURE) ---
async def generate_content_for_tool(
    settings_payload: Dict[str, Any],
    source_file: Optional[UploadFile],
    db: DatabaseService,
    user_id: str  # <-- CRITICAL MODIFICATION 1/2: Added user_id
) -> Dict[str, Any]:
    """
    Orchestrates the entire AI tool generation process.

    This function is now secure. It receives the authenticated user's ID and
    ensures that the final call to the `history_service` includes this ID,
    thereby guaranteeing that the generated content is saved to the correct
    user's history.

    Args:
        settings_payload: The raw payload from the router, containing tool_id and settings.
        source_file: An optional uploaded file for context.
        db: The DatabaseService instance.
        user_id: The ID of the authenticated user making the request.

    Returns:
        A dictionary containing the details of the saved generation record.
    """
    
    # This initial logic for processing the source material remains unchanged.
    tool_id_str = settings_payload.get("tool_id")
    settings_dict = settings_payload.get("settings")
    if not tool_id_str or settings_dict is None:
        raise ValueError("Payload must include 'tool_id' and 'settings'.")

    if source_file:
        if ("source_text" in settings_dict and settings_dict["source_text"]) or \
           ("selected_chapter_paths" in settings_dict and settings_dict["selected_chapter_paths"]):
             raise ValueError("Cannot provide a source file simultaneously with source text or library chapters.")
        file_bytes = await source_file.read()
        extracted_text = await asyncio.to_thread(
            ocr_service.extract_text_from_file, file_bytes, source_file.content_type
        )
        if not extracted_text:
            raise ValueError("Could not extract any readable text from the uploaded file.")
        settings_dict["source_text"] = extracted_text
    elif "selected_chapter_paths" in settings_dict and settings_dict["selected_chapter_paths"]:
        if "source_text" in settings_dict and settings_dict["source_text"]:
            raise ValueError("Cannot provide source text simultaneously with library chapters.")
        combined_text = []
        for path_str in settings_dict["selected_chapter_paths"]:
            abs_path = os.path.abspath(path_str)
            if not abs_path.startswith(os.path.abspath("Books")):
                raise ValueError(f"Invalid chapter path provided: {path_str}")
            try:
                with open(abs_path, 'r', encoding='utf-8') as f:
                    combined_text.append(f.read())
            except FileNotFoundError:
                raise ValueError(f"Could not find chapter file at path: {path_str}")
        settings_dict["source_text"] = "\n\n--- END OF CHAPTER ---\n\n".join(combined_text)

    tool_id = ToolId(tool_id_str)
    handler = TOOL_HANDLERS.get(tool_id)
    if not handler:
        raise ValueError(f"Invalid or not-yet-implemented toolId: {tool_id}")
    
    generated_content = await handler(settings_dict)
    
    # --- [CRITICAL MODIFICATION 2/2: SECURE PERSISTENCE] ---
    # The authenticated user's ID is now passed to the history_service.
    # This ensures the generated content is saved to the correct user's account.
    history_record = history_service.save_generation(
        db=db,
        user_id=user_id,  # <-- The user_id is now correctly passed.
        tool_id=tool_id.value,
        settings=settings_dict,
        generated_content=generated_content,
        source_filename=source_file.filename if source_file else None
    )
    
    # The response construction remains the same.
    return {
        "generation_id": history_record.id,
        "tool_id": history_record.tool_id.value,
        "content": history_record.generated_content
    }

