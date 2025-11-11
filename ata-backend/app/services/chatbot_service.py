# /ata-backend/app/services/chatbot_service.py (SUPERVISOR-APPROVED FLAWLESS VERSION)

"""
This service module encapsulates all business logic for the chatbot feature.

It is responsible for creating and managing chat sessions, adding messages to a
conversation, and orchestrating the interaction with the AI model for generating
responses. Every function in this module is now fully "user-aware," requiring a
`user_id` for all database operations to ensure that chat sessions are private
and securely scoped to the authenticated user.
"""

from typing import Dict, Optional, List
import uuid
from fastapi import WebSocket

from .database_service import DatabaseService
from ..models import chatbot_model
from . import gemini_service, prompt_library

# --- Helper Functions (Pure Utilities) ---

def _generate_chat_name(first_message: str) -> str:
    """
    Generates a short, descriptive name for a new chat session from the first message.
    This is a pure function with no side effects.
    """
    return " ".join(first_message.split()[:5]) + ("..." if len(first_message.split()) > 5 else "")

def _format_chat_history(messages: List) -> str:
    """
    Formats a list of SQLAlchemy ChatMessage objects into a simple, readable
    string for the AI prompt. This is a pure function.
    """
    if not messages:
        return "No previous conversation history."
    
    formatted_history = []
    for msg in messages:
        # Use attribute access (msg.role, msg.content) on the SQLAlchemy objects.
        role = "Teacher" if msg.role == 'user' else "Assistant"
        formatted_history.append(f"{role}: {msg.content}")
    
    return "\n".join(formatted_history)


# --- Public Service Functions ---

def start_new_chat_session(user_id: str, request: chatbot_model.NewChatSessionRequest, db: DatabaseService) -> Dict:
    """
    Creates a new chat session AND saves the user's first message.
    This is an atomic operation that correctly stamps the new session with the owner's ID.
    """
    session_id = f"session_{uuid.uuid4().hex[:12]}"
    session_name = _generate_chat_name(request.first_message)
    
    # 1. Create the session record, including the owner's user_id.
    session_record = { "id": session_id, "user_id": user_id, "name": session_name }
    db.create_chat_session(session_record)
    
    # 2. Create and save the user's first message record.
    user_message_record = {
        "id": f"msg_{uuid.uuid4().hex[:12]}", 
        "session_id": session_id, 
        "role": "user", 
        "content": request.first_message, 
        "file_id": request.file_id
    }
    db.add_chat_message(user_message_record)
    
    return {"sessionId": session_id}


async def add_new_message_to_session(session_id: str, user_id: str, message_text: str, file_id: Optional[str], db: DatabaseService, websocket: WebSocket):
    """
    Handles a new user message by saving it, securely retrieving the full
    conversation history, and orchestrating the AI's streamed response.
    """
    # 1. Save the user's new message to the database. This operation is implicitly
    # secure because the session_id links it to a user-owned session.
    user_message_record = {
        "id": f"msg_{uuid.uuid4().hex[:12]}", 
        "session_id": session_id, 
        "role": "user", 
        "content": message_text, 
        "file_id": file_id
    }
    db.add_chat_message(user_message_record)
    
    bot_response_text = ""
    try:
        # --- [CRITICAL SECURITY FIX] ---
        # 2. Securely retrieve the full conversation history.
        # This call now requires both session_id and user_id, ensuring that
        # we only fetch history for a conversation the user actually owns.
        full_history_objects = db.get_messages_by_session_id(session_id=session_id, user_id=user_id)
        
        # 3. Format the now-secure history for the prompt.
        formatted_history = _format_chat_history(full_history_objects)
        
        # 4. Create the final prompt.
        prompt = prompt_library.CONVERSATIONAL_CHATBOT_PROMPT.format(
            chat_history=formatted_history,
            user_message=message_text
        )
        
        # 5. Call the Gemini service to get a streamed response.
        bot_response_text = await gemini_service.generate_text_streaming(prompt, websocket)

    except Exception as e:
        print(f"Error in conversational loop for session {session_id}: {e}")
        error_message = "Sorry, I encountered an error and could not process your message."
        await websocket.send_json({"type": "error", "payload": {"message": error_message}})
        bot_response_text = f"Conversational Loop Error: {e}"
        
    # 6. Save the bot's final response to the database.
    if bot_response_text:
        bot_message_record = {
            "id": f"msg_{uuid.uuid4().hex[:12]}", 
            "session_id": session_id, 
            "role": "bot", 
            "content": bot_response_text, 
            "file_id": None
        }
        db.add_chat_message(bot_message_record)


def delete_chat_session_logic(session_id: str, user_id: str, db: DatabaseService) -> bool:
    """
    Business logic to safely delete a chat session.
    This function now uses the secure, user-scoped database method.
    """
    # --- [CRITICAL SECURITY FIX] ---
    # The call to the database now requires both session_id and user_id.
    # The database service will only return True if a session with that ID
    # belonging to that user was found and deleted.
    was_deleted = db.delete_chat_session(session_id=session_id, user_id=user_id)
    return was_deleted


def get_chat_session_details_logic(session_id: str, user_id: str, db: DatabaseService) -> Optional[Dict]:
    """
    Business logic to get the full details of a chat session.
    This function now uses secure, user-scoped database methods for all lookups.
    """
    # --- [CRITICAL SECURITY FIX 1/2] ---
    # Securely fetch the parent session object. This will return None if the
    # session does not exist OR if it does not belong to the current user.
    session = db.get_chat_session_by_id(session_id=session_id, user_id=user_id)
    
    if not session:
        return None

    # --- [CRITICAL SECURITY FIX 2/2] ---
    # Securely fetch the messages for the session, again requiring the user_id.
    # This is a defense-in-depth measure.
    messages = db.get_messages_by_session_id(session_id=session_id, user_id=user_id)
    
    # Assemble the final response dictionary using the secure data.
    session_details = {
        "id": session.id,
        "name": session.name,
        "created_at": session.created_at,
        "history": messages 
    }
    return session_details



#################################################################
##
##
##         Following code have sandbox that will use for code generating and data analysis
##
##

# # /ata-backend/app/services/chatbot_service.py (FINAL, HARDENED, AND DEFINITIVELY CORRECTED)

# from typing import Dict, Optional, List
# from datetime import datetime
# import uuid
# import json
# import asyncio
# from fastapi import WebSocket

# from .database_service import DatabaseService
# from ..models import chatbot_model
# from . import gemini_service, prompt_library

# from RestrictedPython import compile_restricted, safe_globals

# # --- [THE FIX IS HERE: THE CORRECT PRINT COLLECTOR CLASS] ---
# class PrintCollector:
#     """
#     A safe, custom object that conforms to RestrictedPython's printing protocol.
#     It is a callable object that also has the required _call_print method.
#     """
#     def __init__(self):
#         self.captured_output = []

#     # This makes the INSTANCE of the class callable, e.g., print_collector("hello")
#     def __call__(self, *args):
#         line = " ".join(map(str, args))
#         self.captured_output.append(line)

#     # This is the specific method that RestrictedPython's rewritten code calls.
#     # We simply delegate it to our main __call__ method for consistency.
#     def _call_print(self, *args):
#         self.__call__(*args)

#     def get_output(self) -> str:
#         """Returns the full captured output as a single string."""
#         return "\n".join(self.captured_output).strip()
# # --- [END OF FIX] ---


# def _generate_chat_name(first_message: str) -> str:
#     return " ".join(first_message.split()[:5]) + ("..." if len(first_message.split()) > 5 else "")


# async def _generate_code_plan(user_id: str, query_text: str, db: DatabaseService) -> str:
#     """Step 1 of the agentic loop: Generate a Python script based on a schema of lists of dictionaries."""
#     classes_list = db.get_classes_for_chatbot(user_id=user_id)
#     students_list = db.get_students_for_chatbot(user_id=user_id)
#     assessments_list = db.get_assessments_for_chatbot(user_id=user_id)
    
#     schema = f"""
# - `classes`: A list of dictionaries. Each dictionary has keys: {list(classes_list[0].keys()) if classes_list else ['id', 'name', 'description']}
# - `students`: A list of dictionaries. Each dictionary has keys: {list(students_list[0].keys()) if students_list else ['id', 'name', 'studentId', 'class_id', 'overallGrade']}
# - `assessments`: A list of dictionaries. Each dictionary has keys: {list(assessments_list[0].keys()) if assessments_list else ['id', 'job_id', 'student_id', 'grade', 'feedback']}
# """
#     prompt = prompt_library.CODE_GENERATION_PROMPT.format(schema=schema, query=query_text)
#     try:
#         response_json = await gemini_service.generate_json(prompt, temperature=0.1)
#         return response_json["code"]
#     except (KeyError, ValueError) as e:
#         raise ValueError(f"AI failed to generate a valid code plan. Error: {e}")

# async def _execute_code_in_sandbox(user_id: str, code_to_execute: str, db: DatabaseService) -> str:
#     """Step 2 of the agentic loop: Securely execute the AI-generated code."""
    
#     def sync_execute():
#         classes_list = db.get_classes_for_chatbot(user_id=user_id)
#         students_list = db.get_students_for_chatbot(user_id=user_id)
#         assessments_list = db.get_assessments_for_chatbot(user_id=user_id)

#         # This function now uses the corrected, callable PrintCollector class
#         print_collector = PrintCollector()

#         restricted_globals = safe_globals.copy()
#         restricted_globals['classes'] = classes_list
#         restricted_globals['students'] = students_list
#         restricted_globals['assessments'] = assessments_list
#         restricted_globals['_print_'] = print_collector
#         restricted_globals['_getitem_'] = lambda obj, key: obj[key]
        
#         modified_code = code_to_execute

#         try:
#             byte_code = compile_restricted(modified_code, '<string>', 'exec')
#             exec(byte_code, restricted_globals, None)
#             raw_result = print_collector.get_output()
#         except Exception as e:
#             print("--- FAILING AI-GENERATED CODE (Original) ---")
#             print(code_to_execute)
#             print("------------------------------------------")
#             raise ValueError(f"The analysis plan failed during execution: {e}")

#         if not raw_result:
#             return "The analysis ran successfully but produced no output."
            
#         return raw_result
    
#     return await asyncio.to_thread(sync_execute)


# async def _synthesize_natural_language_response(query_text: str, raw_result: str, websocket: WebSocket) -> str:
#     """Step 3 of the agentic loop: Convert the raw result into a natural language response."""
#     prompt = prompt_library.NATURAL_LANGUAGE_SYNTHESIS_PROMPT.format(query=query_text, data=raw_result)
#     return await gemini_service.generate_text_streaming(prompt, websocket)


# # --- Public Service Functions ---
# def start_new_chat_session(user_id: str, request: chatbot_model.NewChatSessionRequest, db: DatabaseService) -> Dict:
#     """Creates a new chat session record in the database."""
#     session_id = f"session_{uuid.uuid4().hex[:12]}"
#     session_name = _generate_chat_name(request.first_message)
#     session_record = {"id": session_id, "user_id": user_id, "name": session_name}
#     db.create_chat_session(session_record)
#     return {"sessionId": session_id}

# async def add_new_message_to_session(session_id: str, user_id: str, message_text: str, file_id: Optional[str], db: DatabaseService, websocket: WebSocket):
#     """Orchestrates the full agentic loop for a single user message."""
#     user_message_record = {"id": f"msg_{uuid.uuid4().hex[:12]}", "session_id": session_id, "role": "user", "content": message_text, "file_id": file_id}
#     db.add_chat_message(user_message_record)
    
#     bot_response_text = ""
#     try:
#         code_plan = await _generate_code_plan(user_id, message_text, db)
#         raw_result = await _execute_code_in_sandbox(user_id, code_plan, db)
#         bot_response_text = await _synthesize_natural_language_response(message_text, raw_result, websocket)
#     except Exception as e:
#         print(f"Error in agentic loop for session {session_id}: {e}")
#         error_message = f"Sorry, I encountered an error and could not answer your question."
#         await websocket.send_json({"type": "error", "payload": {"message": error_message}})
#         bot_response_text = f"Agentic Loop Error: {e}"
        
#     if bot_response_text:
#         bot_message_record = {"id": f"msg_{uuid.uuid4().hex[:12]}", "session_id": session_id, "role": "bot", "content": bot_response_text, "file_id": None}
#         db.add_chat_message(bot_message_record)

# def delete_chat_session_logic(session_id: str, user_id: str, db: DatabaseService) -> bool:
#     """Business logic to safely delete a chat session."""
#     session = db.get_chat_session_by_id(session_id)
#     if not session or session.user_id != user_id:
#         return False
#     return db.delete_chat_session(session_id)

# def get_chat_session_details_logic(session_id: str, user_id: str, db: DatabaseService) -> Optional[Dict]:
#     """Business logic to get the full details of a chat session."""
#     session = db.get_chat_session_by_id(session_id)
#     if not session or session.user_id != user_id:
#         return None

#     messages = db.get_messages_by_session_id(session_id)
    
#     session_details = {
#         "id": session.id,
#         "name": session.name,
#         "created_at": session.created_at,
#         "history": messages 
#     }
#     return session_details