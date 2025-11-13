"""
Quiz WebSocket Router

This module provides the WebSocket endpoint for real-time quiz sessions.
It handles authentication, message routing, and real-time broadcasts.

Endpoints:
- WS /api/ws/quiz-sessions/{session_id} - WebSocket connection for hosts and participants

Authentication:
- Hosts: JWT token in query parameter (token=...)
- Participants: Guest token in query parameter (guest_token=...)

Message Flow:
- Client connects → Server accepts and registers
- Client sends messages → Server processes and broadcasts
- Server broadcasts events → All clients in room receive
- Client disconnects → Server cleans up and notifies others

Security:
- All connections are authenticated
- Room-based isolation (sessions don't interfere)
- Automatic cleanup on disconnect
- Rate limiting and message validation

Performance:
- Supports 500+ concurrent connections per session
- Efficient async/await for non-blocking I/O
- Automatic reconnection support with heartbeat
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, HTTPException, status
from typing import Optional, Dict, Any
import json
import logging
from datetime import datetime

# Application imports
from ..core.quiz_websocket import (
    connection_manager,
    MessageType,
    ParticipantRole,
    build_session_started_message,
    build_question_started_message,
    build_participant_joined_message,
    build_participant_left_message,
    build_leaderboard_update_message,
    build_error_message
)
from ..core.deps import get_current_user_from_token
from ..services.database_service import DatabaseService, get_db_service
from ..services import quiz_service
from ..db.models.user_model import User as UserModel
from ..core.quiz_config import quiz_settings

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== WEBSOCKET ENDPOINT ====================

@router.websocket("/quiz-sessions/{session_id}")
async def quiz_session_websocket(
    websocket: WebSocket,
    session_id: str,
    token: Optional[str] = Query(None),
    guest_token: Optional[str] = Query(None),
    db: DatabaseService = Depends(get_db_service)
):
    """
    WebSocket endpoint for real-time quiz sessions.

    Authentication:
    - Hosts: Provide JWT token in query param (token=...)
    - Participants: Provide guest_token in query param (guest_token=...)

    Path Parameters:
    - session_id: Quiz session ID

    Query Parameters:
    - token: JWT token (for hosts)
    - guest_token: Guest authentication token (for participants)

    WebSocket Protocol:
    - Client connects with auth credentials
    - Server sends connection_established message
    - Server broadcasts events to all clients in room
    - Client sends messages (submit_answer, heartbeat_pong)
    - Client/Server sends ping/pong for connection health

    Message Types (Server → Client):
    - connection_established: Confirmation of connection
    - session_started: Session has started
    - question_started: New question is active
    - participant_joined: New participant joined
    - participant_left: Participant left
    - leaderboard_update: Updated leaderboard
    - stats_update: Real-time statistics
    - ping: Heartbeat check
    - error: Error occurred

    Message Types (Client → Server):
    - submit_answer: Submit answer to current question
    - pong: Heartbeat response
    - request_leaderboard: Request current leaderboard

    Connection Lifecycle:
    1. Client connects with credentials
    2. Server authenticates and accepts
    3. Server broadcasts participant_joined to all in room
    4. Client/Server exchange messages
    5. Server monitors connection health (heartbeat)
    6. Client disconnects (or timeout)
    7. Server broadcasts participant_left to all in room
    8. Server cleans up connection
    """

    # ===== AUTHENTICATION =====

    # Determine role and authenticate
    user_id = None
    role = None
    participant = None
    display_name = None

    # Try host authentication (JWT token)
    if token:
        try:
            # Verify JWT token
            current_user = get_current_user_from_token(token, db)

            # Verify user owns the session
            session = db.get_quiz_session_by_id(session_id, current_user.id)
            if not session:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Session not found or access denied")
                return

            user_id = current_user.id
            role = ParticipantRole.HOST
            display_name = f"Host: {current_user.email}"

            logger.info(f"Host authenticated for session {session_id}: {current_user.email}")

        except Exception as e:
            logger.error(f"Host authentication failed: {e}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
            return

    # Try participant authentication (guest token)
    elif guest_token:
        try:
            # Verify guest token and get participant
            participant = db.get_participant_by_guest_token(guest_token)
            if not participant or participant.session_id != session_id:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid guest token")
                return

            # Verify session exists
            # Note: We don't check user_id for participants, they access via guest token
            session = db.get_quiz_session_by_id(session_id, user_id=None)
            if not session:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Session not found")
                return

            user_id = guest_token  # Use guest token as identifier
            role = ParticipantRole.PARTICIPANT
            display_name = participant.guest_name or "Participant"

            logger.info(f"Participant authenticated for session {session_id}: {display_name}")

        except Exception as e:
            logger.error(f"Participant authentication failed: {e}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid guest token")
            return

    else:
        # No authentication provided
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required")
        return

    # ===== CONNECTION ESTABLISHMENT =====

    try:
        # Connect to WebSocket manager
        await connection_manager.connect(
            websocket=websocket,
            session_id=session_id,
            user_id=user_id,
            role=role,
            participant_id=participant.id if participant else None,
            display_name=display_name
        )

        # Broadcast participant joined (if participant)
        if role == ParticipantRole.PARTICIPANT and participant:
            # Get current participant count
            participants = db.get_participants_by_session(session_id, active_only=True)
            total_participants = len(participants)

            # Broadcast to all in room
            # FIX: Convert UUID to string for JSON serialization
            message = build_participant_joined_message(
                participant_id=str(participant.id),
                display_name=display_name,
                total_participants=total_participants
            )
            await connection_manager.broadcast_to_room(session_id, message)

        # Send current session state to new connection
        await _send_current_state(websocket, session_id, role, db)

    except Exception as e:
        logger.error(f"Error during connection establishment: {e}")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Connection error")
        return

    # ===== MESSAGE LOOP =====

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                message_type = message.get("type")

                # Handle different message types
                if message_type == MessageType.PONG:
                    # Update heartbeat timestamp
                    connection_manager.update_heartbeat(websocket)

                elif message_type == MessageType.SUBMIT_ANSWER:
                    # Participant submitting answer
                    if role == ParticipantRole.PARTICIPANT and participant:
                        await _handle_submit_answer(
                            websocket=websocket,
                            session_id=session_id,
                            participant_id=participant.id,
                            message=message,
                            db=db
                        )
                    else:
                        await connection_manager.send_personal_message(
                            websocket,
                            build_error_message("unauthorized", "Only participants can submit answers")
                        )

                elif message_type == MessageType.REQUEST_LEADERBOARD:
                    # Request current leaderboard
                    await _send_leaderboard(websocket, session_id, db)

                else:
                    logger.warning(f"Unknown message type: {message_type}")
                    await connection_manager.send_personal_message(
                        websocket,
                        build_error_message("unknown_message_type", f"Unknown message type: {message_type}")
                    )

            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received: {data}")
                await connection_manager.send_personal_message(
                    websocket,
                    build_error_message("invalid_json", "Message must be valid JSON")
                )
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await connection_manager.send_personal_message(
                    websocket,
                    build_error_message("processing_error", str(e))
                )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: session {session_id}, role {role}")

    except Exception as e:
        logger.error(f"Unexpected error in WebSocket loop: {e}")

    finally:
        # ===== CLEANUP =====

        # Disconnect from manager
        connection_manager.disconnect(websocket, session_id)

        # Broadcast participant left (if participant)
        if role == ParticipantRole.PARTICIPANT and participant:
            # Get updated participant count
            participants = db.get_participants_by_session(session_id, active_only=True)
            total_participants = len(participants)

            # Broadcast to all in room
            # FIX: Convert UUID to string for JSON serialization
            message = build_participant_left_message(
                participant_id=str(participant.id),
                display_name=display_name,
                total_participants=total_participants
            )
            await connection_manager.broadcast_to_room(session_id, message)

        logger.info(f"WebSocket cleanup complete: session {session_id}, role {role}")


# ==================== HELPER FUNCTIONS ====================

async def _send_current_state(
    websocket: WebSocket,
    session_id: str,
    role: str,
    db: DatabaseService
) -> None:
    """
    Send current session state to newly connected client.

    Args:
        websocket: WebSocket connection
        session_id: Session ID
        role: User role (host or participant)
        db: Database service
    """
    try:
        # Get session (without user_id check for both hosts and participants at this point)
        session = db.get_quiz_session_by_id(session_id, user_id=None)

        if not session:
            return

        # Send current session status
        # FIX: Convert UUID to string for JSON serialization
        await connection_manager.send_personal_message(websocket, {
            "type": "current_state",
            "session": {
                "id": str(session.id),
                "status": session.status,
                "current_question_index": session.current_question_index,
                "started_at": session.started_at.isoformat() if session.started_at else None
            }
        })

        # Send current leaderboard
        await _send_leaderboard(websocket, session_id, db)

    except Exception as e:
        logger.error(f"Error sending current state: {e}")


async def _send_leaderboard(
    websocket: WebSocket,
    session_id: str,
    db: DatabaseService
) -> None:
    """
    Send current leaderboard to a WebSocket connection.

    Args:
        websocket: WebSocket connection
        session_id: Session ID
        db: Database service
    """
    try:
        # Get top participants
        top_participants = db.get_leaderboard(
            session_id,
            limit=quiz_settings.LEADERBOARD_TOP_COUNT
        )

        # Format leaderboard
        # FIX: Convert UUID to string for JSON serialization
        leaderboard = []
        for rank, participant in enumerate(top_participants, start=1):
            leaderboard.append({
                "rank": rank,
                "participant_id": str(participant.id),
                "display_name": participant.guest_name or "Student",
                "score": participant.score,
                "correct_answers": participant.correct_answers,
                "total_time_ms": participant.total_time_ms
            })

        # Send leaderboard update
        message = build_leaderboard_update_message(leaderboard)
        await connection_manager.send_personal_message(websocket, message)

    except Exception as e:
        logger.error(f"Error sending leaderboard: {e}")


async def _handle_submit_answer(
    websocket: WebSocket,
    session_id: str,
    participant_id: str,
    message: Dict[str, Any],
    db: DatabaseService
) -> None:
    """
    Handle answer submission from participant via WebSocket.

    FIX #9 & #10: Complete implementation with duplicate prevention and grading.

    Args:
        websocket: WebSocket connection
        session_id: Session ID
        participant_id: Participant ID
        message: Message with answer data
        db: Database service
    """
    try:
        # Extract answer data
        question_id = message.get("question_id")
        answer = message.get("answer")
        time_taken_ms = message.get("time_taken_ms", 0)

        logger.info(f"[WebSocket] Answer submission: participant={participant_id}, "
                   f"question={question_id}, time={time_taken_ms}ms")

        if not question_id or answer is None:
            logger.warning(f"[WebSocket] Invalid answer data from participant {participant_id}")
            await connection_manager.send_personal_message(
                websocket,
                build_error_message("invalid_answer", "Missing question_id or answer")
            )
            return

        # FIX #9 & #10: Submit answer with grading (includes duplicate check)
        try:
            result = quiz_service.submit_answer_with_grading(
                participant_id, question_id, answer, time_taken_ms, db
            )

            logger.info(f"[WebSocket] Answer graded: participant={participant_id}, "
                       f"correct={result['is_correct']}, points={result['points_earned']}")

            # Send result to participant
            await connection_manager.send_personal_message(websocket, {
                "type": "answer_submitted",
                "question_id": question_id,
                "is_correct": result['is_correct'],
                "points_earned": result['points_earned'],
                "correct_answer": result.get('correct_answer'),
                "timestamp": datetime.utcnow().isoformat()
            })

            # Broadcast to hosts that answer was received
            await connection_manager.broadcast_to_hosts(session_id, {
                "type": MessageType.PARTICIPANT_ANSWERED,
                "participant_id": participant_id,
                "question_id": question_id,
                "is_correct": result['is_correct'],
                "timestamp": datetime.utcnow().isoformat()
            })

            # FIX #10: Get updated leaderboard and broadcast to everyone
            # FIX: Convert UUID to string for JSON serialization
            top_participants = db.get_leaderboard(session_id, limit=10)
            leaderboard_data = [
                {
                    "rank": rank,
                    "participant_id": str(p.id),
                    "display_name": p.guest_name or "Student",
                    "score": p.score,
                    "correct_answers": p.correct_answers,
                    "total_time_ms": p.total_time_ms
                }
                for rank, p in enumerate(top_participants, start=1)
            ]

            logger.info(f"[WebSocket] Broadcasting updated leaderboard to session {session_id}")
            await connection_manager.broadcast_to_room(
                session_id,
                build_leaderboard_update_message(leaderboard_data)
            )

        except ValueError as ve:
            # FIX #9: Business logic errors (duplicate answer, invalid question, etc.)
            logger.warning(f"[WebSocket] Validation error: {ve}")
            await connection_manager.send_personal_message(
                websocket,
                build_error_message("validation_error", str(ve))
            )
        except Exception as db_error:
            # Database or unexpected errors
            logger.error(f"[WebSocket] Database error during answer submission: {db_error}",
                        exc_info=True)
            await connection_manager.send_personal_message(
                websocket,
                build_error_message("submission_error",
                                   "Failed to submit answer. Please try again.")
            )

    except Exception as e:
        logger.error(f"[WebSocket] Unexpected error in answer submission: {e}", exc_info=True)
        await connection_manager.send_personal_message(
            websocket,
            build_error_message("submission_error", "An unexpected error occurred.")
        )
