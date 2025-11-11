# /ata-backend/app/routers/chatbot_router.py (SUPERVISOR-APPROVED FLAWLESS VERSION)

"""
This module defines all API endpoints for the Chatbot feature, including both
RESTful endpoints for session management and the real-time WebSocket endpoint
for conversations.

Every endpoint in this router is now a protected resource. REST endpoints are
secured using the standard `Depends(get_current_active_user)` dependency. The
WebSocket endpoint is secured by requiring a JWT passed as a query parameter,
which is the standard practice for authenticating real-time connections.
"""

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Response, status, HTTPException, Query
from app.core.logger import get_logger

logger = get_logger(__name__)
from typing import List
import json

# --- Application-specific Imports ---
from ..services import chatbot_service
from ..services.database_service import DatabaseService, get_db_service
from ..models import chatbot_model

# --- [CRITICAL SECURITY IMPORTS] ---
# Import the dependency for protecting REST endpoints.
from app.core.deps import get_current_active_user
# Import the utility for decoding WebSocket tokens.
from app.core.security import decode_token
# Import the SQLAlchemy User model for type hinting the authenticated user.
from app.db.models.user_model import User as UserModel

router = APIRouter()

# --- REST ENDPOINTS FOR SESSION MANAGEMENT (NOW SECURE) ---

@router.get(
    "/sessions",
    response_model=List[chatbot_model.ChatSessionSummary],
    summary="Get Current User's Chat History",
    description="Retrieves a list of all past chat session summaries for the authenticated user."
)
def get_chat_sessions(
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)  # Protect the endpoint.
):
    """
    Securely retrieves the chat session history for the currently logged-in user.
    """
    # The user's ID is passed to the database service to ensure the query is filtered.
    return db.get_chat_sessions_by_user_id(user_id=current_user.id)


@router.get(
    "/sessions/{session_id}",
    response_model=chatbot_model.ChatSessionDetail,
    summary="Get a Single Chat Session with History",
    description="Retrieves the full details and message history for a specific chat session, if owned by the user."
)
def get_chat_session_details(
    session_id: str,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)  # Protect the endpoint.
):
    """
    Securely retrieves the details of a single chat session, enforcing ownership.
    """
    # The user's ID is passed to the service layer for an ownership check.
    details = chatbot_service.get_chat_session_details_logic(session_id, current_user.id, db)
    if not details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with ID {session_id} not found or access denied.",
        )
    return details


@router.post(
    "/sessions",
    response_model=chatbot_model.CreateChatSessionResponse,
    summary="Create a New Chat Session",
    description="Initiates a new chat session for the authenticated user."
)
def create_new_chat_session(
    request: chatbot_model.NewChatSessionRequest,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)  # Protect the endpoint.
):
    """
    Creates a new chat session, automatically assigning ownership to the authenticated user.
    """
    # The user's ID is passed to the service layer to stamp ownership on the new record.
    session_info = chatbot_service.start_new_chat_session(current_user.id, request, db)
    return session_info


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Chat Session",
    description="Permanently deletes a chat session, if owned by the user."
)
def delete_chat_session(
    session_id: str,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)  # Protect the endpoint.
):
    """
    Securely deletes a chat session, enforcing ownership.
    """
    # The user's ID is passed to the service layer for an ownership check before deletion.
    was_deleted = chatbot_service.delete_chat_session_logic(session_id, current_user.id, db)
    if not was_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with ID {session_id} not found or access denied.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- REAL-TIME WEBSOCKET ENDPOINT (NOW SECURE) ---

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),  # Expect the JWT as a query parameter named 'token'.
    db: DatabaseService = Depends(get_db_service)
):
    """
    Handles the real-time WebSocket connection for a chat session.

    Authentication is performed using a JWT passed as a query parameter.
    The connection is only accepted if the token is valid and the user owns
    the requested chat session.
    """
    # 1. Authenticate the user via the token from the query parameter.
    user_id = decode_token(token)
    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or missing token")
        return

    # 2. Authorize access to the specific chat session.
    # This secure database call checks for both existence and ownership.
    session = db.get_chat_session_by_id(session_id=session_id, user_id=user_id)
    if not session:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Session not found or access denied")
        return

    # 3. If authentication and authorization succeed, accept the connection.
    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)

            if message_data.get("type") == "user_message":
                message_text = message_data.get("payload", {}).get("text")
                file_id = message_data.get("payload", {}).get("file_id")

                if message_text:
                    # 4. Pass the validated user_id to the service layer for processing.
                    await chatbot_service.add_new_message_to_session(
                        session_id=session_id,
                        user_id=user_id,  # Use the validated user_id.
                        message_text=message_text,
                        file_id=file_id,
                        db=db,
                        websocket=websocket
                    )
            
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from chat session: {session_id}")
    except Exception as e:
        logger.info(f"An unexpected error occurred in WebSocket for session {session_id}: {e}")
        try:
            await websocket.send_json({
                "type": "error", 
                "payload": {"message": "A server error occurred. Please try reconnecting."}
            })
        except Exception:
            # The client may have already disconnected, so we ignore errors here.
            pass