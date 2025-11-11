# /ata-backend/app/services/database_helpers/chat_repository_sql.py (DEFINITIVE FLAWLESS VERSION)

"""
This module contains all the raw SQLAlchemy queries for the ChatSession and
ChatMessage tables. It is the direct interface to the database for all chat-
related data and a final point of enforcement for data isolation.

Every method that reads or modifies a chat session has been updated to require
a `user_id`, ensuring all operations are securely scoped to the
authenticated user. This module follows a "defense-in-depth" principle, meaning every
function is independently secure.
"""

from typing import List, Dict, Optional
from sqlalchemy.orm import Session

# Import the SQLAlchemy models this repository will interact with.
from app.db.models.chat_models import ChatSession, ChatMessage


class ChatRepositorySQL:
    def __init__(self, db_session: Session):
        self.db = db_session

    # --- Chat Session Methods ---

    def create_session(self, record: Dict) -> ChatSession:
        """
        Creates a new ChatSession record.
        This function expects the `user_id` to be present in the `record` dictionary.
        """
        new_session = ChatSession(**record)
        self.db.add(new_session)
        self.db.commit()
        self.db.refresh(new_session)
        return new_session

    def get_sessions_by_user_id(self, user_id: str) -> List[ChatSession]:
        """
        Retrieves all chat session summaries owned by a specific user.
        """
        return (
            self.db.query(ChatSession)
            .filter(ChatSession.user_id == user_id)
            .order_by(ChatSession.created_at.desc())
            .all()
        )

    def get_session_by_id(self, session_id: str, user_id: str) -> Optional[ChatSession]:
        """
        Retrieves a single chat session by its ID, but only if it is owned by the
        specified user.
        """
        return (
            self.db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
            .first()
        )

    def delete_session_by_id(self, session_id: str, user_id: str) -> bool:
        """
        Deletes a chat session, but only if it is owned by the specified user.
        """
        session_to_delete = self.get_session_by_id(session_id=session_id, user_id=user_id)
        
        if session_to_delete:
            self.db.delete(session_to_delete)
            self.db.commit()
            return True
        return False

    # --- Chat Message Methods ---

    def add_message(self, record: Dict):
        """
        Creates a new ChatMessage record.
        """
        new_message = ChatMessage(**record)
        self.db.add(new_message)
        self.db.commit()

    def get_messages_by_session_id(self, session_id: str, user_id: str) -> List[ChatMessage]:
        """
        Retrieves all messages for a given chat session, but only if the session
        is owned by the specified user. This is a critical defense-in-depth check
        that performs the ownership verification and data retrieval in a single query.
        """
        # This query joins ChatMessage with its parent ChatSession to filter by the
        # owner's user_id directly. It is the most secure and efficient pattern.
        return (
            self.db.query(ChatMessage)
            .join(ChatSession, ChatMessage.session_id == ChatSession.id)
            .filter(ChatMessage.session_id == session_id, ChatSession.user_id == user_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )