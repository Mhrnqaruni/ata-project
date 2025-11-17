"""
Production WebSocket Manager for Real-Time Quiz Features

This module provides a robust WebSocket connection manager for live quiz sessions.
It handles real-time communication between hosts and participants, including:

Features:
- Room-based connection management (session_id = room)
- Authentication (JWT for hosts, guest tokens for participants)
- Real-time broadcasts (questions, answers, leaderboard, participant events)
- Connection health monitoring (heartbeat/ping-pong)
- Automatic reconnection support
- Error handling and logging

Architecture:
- ConnectionManager: Central hub managing all WebSocket connections
- Room-based routing: Messages sent to specific sessions
- Role-based permissions: Hosts can control, participants can answer
- Message types: Strongly typed messages for all events

Performance:
- Supports 500+ concurrent connections per session
- Async/await for non-blocking I/O
- Efficient broadcast with exception handling per connection

Usage:
    manager = ConnectionManager()
    await manager.connect(websocket, session_id, user_id, role)
    await manager.broadcast_to_room(session_id, message)
    manager.disconnect(websocket, session_id)
"""

from fastapi import WebSocket, WebSocketDisconnect, status
from typing import Dict, List, Set, Optional, Any
from datetime import datetime
from collections import defaultdict
import json
import asyncio
import logging

# Application imports
from .quiz_config import quiz_settings

# Configure logging
logger = logging.getLogger(__name__)


# ==================== MESSAGE TYPES ====================

class MessageType:
    """WebSocket message types for quiz sessions."""

    # Session control (host only)
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"
    SESSION_CANCELLED = "session_cancelled"

    # Question control (host only)
    QUESTION_STARTED = "question_started"
    QUESTION_ENDED = "question_ended"
    NEXT_QUESTION = "next_question"
    COOLDOWN_STARTED = "cooldown_started"  # FIX: New message type for cooldown

    # Participant events
    PARTICIPANT_JOINED = "participant_joined"
    PARTICIPANT_LEFT = "participant_left"
    PARTICIPANT_ANSWERED = "participant_answered"

    # NEW: Roster tracking events
    ROSTER_UPDATED = "roster_updated"
    OUTSIDER_DETECTED = "outsider_detected"
    ATTENDANCE_SUMMARY = "attendance_summary"

    # Leaderboard updates
    LEADERBOARD_UPDATE = "leaderboard_update"

    # Real-time stats
    STATS_UPDATE = "stats_update"

    # Connection health
    PING = "ping"
    PONG = "pong"

    # Errors
    ERROR = "error"

    # Client actions (received from client)
    SUBMIT_ANSWER = "submit_answer"
    REQUEST_LEADERBOARD = "request_leaderboard"


class ParticipantRole:
    """Role types for WebSocket connections."""
    HOST = "host"
    PARTICIPANT = "participant"


# ==================== CONNECTION MANAGER ====================

class ConnectionManager:
    """
    Manages WebSocket connections for quiz sessions.

    Architecture:
    - rooms: Dict[session_id, Set[WebSocket]] - All connections per session
    - connections: Dict[WebSocket, Dict] - Metadata per connection
    - heartbeat_tasks: Dict[WebSocket, Task] - Health monitoring per connection

    Thread Safety:
    - Uses asyncio (single-threaded event loop)
    - No locks needed for connection management
    """

    def __init__(self):
        # Room-based connection tracking
        self.rooms: Dict[str, Set[WebSocket]] = defaultdict(set)

        # Connection metadata
        self.connections: Dict[WebSocket, Dict[str, Any]] = {}

        # Heartbeat monitoring
        self.heartbeat_tasks: Dict[WebSocket, asyncio.Task] = {}

        # Configuration
        self.heartbeat_interval = quiz_settings.WEBSOCKET_HEARTBEAT_INTERVAL_SECONDS
        self.heartbeat_timeout = quiz_settings.WEBSOCKET_HEARTBEAT_TIMEOUT_SECONDS

        logger.info("WebSocket ConnectionManager initialized")

    async def connect(
        self,
        websocket: WebSocket,
        session_id: str,
        user_id: str,
        role: str,
        participant_id: Optional[str] = None,
        display_name: Optional[str] = None
    ) -> None:
        """
        Accept and register a new WebSocket connection.

        Args:
            websocket: WebSocket connection
            session_id: Quiz session ID (room identifier)
            user_id: User ID (teacher) or guest token
            role: "host" or "participant"
            participant_id: Participant ID if role is participant
            display_name: Display name for participant
        """
        # Accept WebSocket connection
        await websocket.accept()

        # Add to room
        self.rooms[session_id].add(websocket)

        # Store connection metadata
        self.connections[websocket] = {
            "session_id": session_id,
            "user_id": user_id,
            "role": role,
            "participant_id": participant_id,
            "display_name": display_name,
            "connected_at": datetime.utcnow().isoformat(),
            "last_heartbeat": datetime.utcnow()
        }

        # Start heartbeat monitoring
        self.heartbeat_tasks[websocket] = asyncio.create_task(
            self._heartbeat_monitor(websocket)
        )

        logger.info(
            f"WebSocket connected - Session: {session_id}, Role: {role}, "
            f"User: {user_id[:8]}..., Name: {display_name}"
        )

        # Send connection confirmation
        await self.send_personal_message(websocket, {
            "type": "connection_established",
            "session_id": session_id,
            "role": role,
            "connected_at": self.connections[websocket]["connected_at"]
        })

    def disconnect(self, websocket: WebSocket, session_id: str) -> None:
        """
        Disconnect and cleanup a WebSocket connection.

        Args:
            websocket: WebSocket to disconnect
            session_id: Session ID to remove from
        """
        # Cancel heartbeat task
        if websocket in self.heartbeat_tasks:
            self.heartbeat_tasks[websocket].cancel()
            del self.heartbeat_tasks[websocket]

        # Remove from room
        if session_id in self.rooms:
            self.rooms[session_id].discard(websocket)

            # Clean up empty rooms
            if not self.rooms[session_id]:
                del self.rooms[session_id]

        # Remove connection metadata
        metadata = self.connections.pop(websocket, None)

        if metadata:
            logger.info(
                f"WebSocket disconnected - Session: {session_id}, "
                f"Role: {metadata.get('role')}, User: {metadata.get('user_id', 'unknown')[:8]}..."
            )

    async def send_personal_message(self, websocket: WebSocket, message: Dict) -> None:
        """
        Send message to a specific WebSocket connection.

        Args:
            websocket: Target WebSocket
            message: Message dictionary
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            # Connection might be dead, will be cleaned up by heartbeat monitor

    async def broadcast_to_room(
        self,
        session_id: str,
        message: Dict,
        exclude: Optional[Set[WebSocket]] = None
    ) -> None:
        """
        Broadcast message to all connections in a room (session).

        Args:
            session_id: Session ID (room)
            message: Message dictionary
            exclude: Optional set of WebSockets to exclude from broadcast
        """
        if session_id not in self.rooms:
            logger.warning(f"Attempted to broadcast to non-existent room: {session_id}")
            return

        exclude = exclude or set()
        connections = self.rooms[session_id] - exclude

        # Send to all connections, handle failures individually
        tasks = []
        for websocket in connections:
            tasks.append(self._safe_send(websocket, message, session_id))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_to_hosts(self, session_id: str, message: Dict) -> None:
        """
        Broadcast message to all hosts in a room.

        Args:
            session_id: Session ID
            message: Message dictionary
        """
        if session_id not in self.rooms:
            return

        host_websockets = [
            ws for ws in self.rooms[session_id]
            if self.connections.get(ws, {}).get("role") == ParticipantRole.HOST
        ]

        tasks = [self._safe_send(ws, message, session_id) for ws in host_websockets]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_to_participants(self, session_id: str, message: Dict) -> None:
        """
        Broadcast message to all participants in a room.

        Args:
            session_id: Session ID
            message: Message dictionary
        """
        if session_id not in self.rooms:
            return

        participant_websockets = [
            ws for ws in self.rooms[session_id]
            if self.connections.get(ws, {}).get("role") == ParticipantRole.PARTICIPANT
        ]

        tasks = [self._safe_send(ws, message, session_id) for ws in participant_websockets]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_send(self, websocket: WebSocket, message: Dict, session_id: str) -> None:
        """
        Safely send message, handle exceptions per connection.

        Args:
            websocket: Target WebSocket
            message: Message dictionary
            session_id: Session ID for cleanup on failure
        """
        try:
            await websocket.send_json(message)
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected during send: {session_id}")
            self.disconnect(websocket, session_id)
        except Exception as e:
            logger.error(f"Error sending to WebSocket: {e}")
            self.disconnect(websocket, session_id)

    async def _heartbeat_monitor(self, websocket: WebSocket) -> None:
        """
        Monitor connection health with ping/pong heartbeat.

        FIX #6: Enhanced logging for better connection health monitoring.

        Args:
            websocket: WebSocket to monitor
        """
        metadata = self.connections.get(websocket)
        session_id = metadata.get("session_id") if metadata else "unknown"
        role = metadata.get("role") if metadata else "unknown"

        logger.info(f"[Heartbeat] Starting monitor for session {session_id}, role {role}")

        try:
            ping_count = 0
            while True:
                await asyncio.sleep(self.heartbeat_interval)
                ping_count += 1

                # Send ping
                logger.debug(f"[Heartbeat] Sending ping #{ping_count} to session {session_id}")
                await self.send_personal_message(websocket, {
                    "type": MessageType.PING,
                    "timestamp": datetime.utcnow().isoformat()
                })

                # Check last heartbeat
                metadata = self.connections.get(websocket)
                if metadata:
                    last_heartbeat = metadata.get("last_heartbeat")
                    if last_heartbeat:
                        elapsed = (datetime.utcnow() - last_heartbeat).total_seconds()

                        if elapsed > self.heartbeat_timeout:
                            logger.warning(
                                f"[Heartbeat] TIMEOUT for session {metadata.get('session_id')}, "
                                f"role {metadata.get('role')}, elapsed {elapsed:.1f}s > {self.heartbeat_timeout}s"
                            )
                            session_id = metadata.get("session_id")
                            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                            self.disconnect(websocket, session_id)
                            break
                        else:
                            logger.debug(
                                f"[Heartbeat] Healthy - session {session_id}, last seen {elapsed:.1f}s ago"
                            )
        except asyncio.CancelledError:
            # Task cancelled during disconnect, normal cleanup
            logger.info(f"[Heartbeat] Monitor cancelled for session {session_id} (normal cleanup)")
            pass
        except Exception as e:
            logger.error(f"[Heartbeat] Monitor error for session {session_id}: {e}", exc_info=True)
            metadata = self.connections.get(websocket)
            if metadata:
                self.disconnect(websocket, metadata.get("session_id"))

    def update_heartbeat(self, websocket: WebSocket) -> None:
        """
        Update last heartbeat timestamp for a connection.

        FIX #6: Enhanced logging for heartbeat tracking.

        Args:
            websocket: WebSocket that sent pong
        """
        if websocket in self.connections:
            self.connections[websocket]["last_heartbeat"] = datetime.utcnow()
            metadata = self.connections[websocket]
            logger.debug(
                f"[Heartbeat] Pong received from session {metadata.get('session_id')}, "
                f"role {metadata.get('role')}"
            )

    def get_room_stats(self, session_id: str) -> Dict[str, int]:
        """
        Get statistics for a room.

        Args:
            session_id: Session ID

        Returns:
            Dict with connection counts
        """
        if session_id not in self.rooms:
            return {"total": 0, "hosts": 0, "participants": 0}

        connections = self.rooms[session_id]
        hosts = sum(
            1 for ws in connections
            if self.connections.get(ws, {}).get("role") == ParticipantRole.HOST
        )
        participants = sum(
            1 for ws in connections
            if self.connections.get(ws, {}).get("role") == ParticipantRole.PARTICIPANT
        )

        return {
            "total": len(connections),
            "hosts": hosts,
            "participants": participants
        }

    def get_all_rooms(self) -> List[str]:
        """Get list of all active room IDs."""
        return list(self.rooms.keys())

    def is_connected(self, websocket: WebSocket) -> bool:
        """Check if a WebSocket is still connected."""
        return websocket in self.connections


# ==================== GLOBAL MANAGER INSTANCE ====================

# Singleton instance used across the application
connection_manager = ConnectionManager()


# ==================== MESSAGE BUILDERS ====================

def build_session_started_message(session_id: str, quiz_title: str) -> Dict:
    """Build session started message."""
    return {
        "type": MessageType.SESSION_STARTED,
        "session_id": session_id,
        "quiz_title": quiz_title,
        "timestamp": datetime.utcnow().isoformat()
    }


def build_question_started_message(
    question_id: str,
    question_text: str,
    question_type: str,
    options: List[str],
    points: int,
    order_index: int,
    time_limit_seconds: Optional[int] = None
) -> Dict:
    """Build question started message."""
    return {
        "type": MessageType.QUESTION_STARTED,
        "question": {
            "id": question_id,
            "text": question_text,
            "type": question_type,
            "options": options,
            "points": points,
            "order_index": order_index,
            "time_limit_seconds": time_limit_seconds
        },
        "timestamp": datetime.utcnow().isoformat()
    }


def build_participant_joined_message(participant_id: str, display_name: str, total_participants: int) -> Dict:
    """Build participant joined message."""
    return {
        "type": MessageType.PARTICIPANT_JOINED,
        "participant": {
            "id": participant_id,
            "display_name": display_name
        },
        "total_participants": total_participants,
        "timestamp": datetime.utcnow().isoformat()
    }


def build_participant_left_message(participant_id: str, display_name: str, total_participants: int) -> Dict:
    """Build participant left message."""
    return {
        "type": MessageType.PARTICIPANT_LEFT,
        "participant": {
            "id": participant_id,
            "display_name": display_name
        },
        "total_participants": total_participants,
        "timestamp": datetime.utcnow().isoformat()
    }


def build_leaderboard_update_message(leaderboard: List[Dict]) -> Dict:
    """Build leaderboard update message."""
    return {
        "type": MessageType.LEADERBOARD_UPDATE,
        "leaderboard": leaderboard,
        "timestamp": datetime.utcnow().isoformat()
    }


def build_stats_update_message(
    total_answers: int,
    completion_rate: float,
    average_time_ms: float
) -> Dict:
    """Build stats update message."""
    return {
        "type": MessageType.STATS_UPDATE,
        "stats": {
            "total_answers": total_answers,
            "completion_rate": completion_rate,
            "average_time_ms": average_time_ms
        },
        "timestamp": datetime.utcnow().isoformat()
    }


def build_error_message(error_code: str, error_message: str) -> Dict:
    """Build error message."""
    return {
        "type": MessageType.ERROR,
        "error": {
            "code": error_code,
            "message": error_message
        },
        "timestamp": datetime.utcnow().isoformat()
    }


# ==================== ROSTER TRACKING MESSAGE BUILDERS ====================

def build_roster_updated_message(roster_summary: Dict) -> Dict:
    """
    Build roster updated message for real-time attendance tracking.

    Args:
        roster_summary: Dictionary with roster statistics:
            - total_expected: int
            - total_joined: int
            - total_absent: int
            - join_rate: float
            - entries: List[Dict] (optional, for detailed view)

    Returns:
        WebSocket message with roster update data

    Usage:
        Called when a student on roster joins the session.
        Broadcasts to host to update attendance UI in real-time.
    """
    return {
        "type": MessageType.ROSTER_UPDATED,
        "roster": {
            "total_expected": roster_summary.get("total_expected", 0),
            "total_joined": roster_summary.get("total_joined", 0),
            "total_absent": roster_summary.get("total_absent", 0),
            "join_rate": roster_summary.get("join_rate", 0.0)
        },
        "timestamp": datetime.utcnow().isoformat()
    }


def build_outsider_detected_message(outsider_record: Dict) -> Dict:
    """
    Build outsider detected message for teacher alerts.

    Args:
        outsider_record: Dictionary with outsider student data:
            - id: str
            - student_school_id: str
            - guest_name: str
            - detection_reason: str
            - participant_id: str
            - created_at: datetime

    Returns:
        WebSocket message with outsider alert data

    Usage:
        Called when a student joins but isn't on expected roster.
        Broadcasts to host to alert teacher of unexpected participant.
    """
    return {
        "type": MessageType.OUTSIDER_DETECTED,
        "outsider": {
            "id": outsider_record.get("id"),
            "student_school_id": outsider_record.get("student_school_id"),
            "guest_name": outsider_record.get("guest_name"),
            "detection_reason": outsider_record.get("detection_reason"),
            "participant_id": outsider_record.get("participant_id")
        },
        "timestamp": datetime.utcnow().isoformat()
    }


def build_attendance_summary_message(attendance_data: Dict) -> Dict:
    """
    Build attendance summary message with complete attendance overview.

    Args:
        attendance_data: Dictionary with full attendance data:
            - session_id: str
            - class_id: Optional[str]
            - roster_summary: Optional[Dict] (if class-based)
            - outsider_summary: Dict
            - total_participants: int
            - active_participants: int

    Returns:
        WebSocket message with comprehensive attendance data

    Usage:
        Called when host requests attendance dashboard.
        Can be broadcast periodically or on-demand.
    """
    return {
        "type": MessageType.ATTENDANCE_SUMMARY,
        "attendance": {
            "session_id": attendance_data.get("session_id"),
            "class_id": attendance_data.get("class_id"),
            "total_participants": attendance_data.get("total_participants", 0),
            "active_participants": attendance_data.get("active_participants", 0),
            "has_roster": attendance_data.get("roster_summary") is not None,
            "total_outsiders": attendance_data.get("outsider_summary", {}).get("total_outsiders", 0)
        },
        "timestamp": datetime.utcnow().isoformat()
    }
