# /ata-backend/app/db/models/chat_models.py (MODIFIED AND APPROVED)

"""
This module defines the SQLAlchemy ORM models for the `ChatSession` and
`ChatMessage` entities, which represent a user's conversation and its
individual messages, respectively.
"""

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
# --- [CRITICAL MODIFICATION] ---
# Import the UUID type from SQLAlchemy's PostgreSQL dialects. This is necessary
# to ensure the `user_id` foreign key column has the exact same data type as
# the `User.id` primary key it points to.
from sqlalchemy.dialects.postgresql import UUID

from ..base_class import Base

class ChatSession(Base):
    """
    SQLAlchemy model representing a top-level chat session.

    This model is now correctly linked to a User via a proper foreign key,
    enforcing data integrity and establishing ownership.
    """
    __tablename__ = "chatsessions" # Override automatic pluralization

    id = Column(String, primary_key=True, index=True)
    
    # --- [CRITICAL MODIFICATION 1/2: THE PHYSICAL LINK] ---
    # The original `user_id` column has been upgraded to a proper foreign key.
    # - UUID(as_uuid=True): Ensures type compatibility with the User.id primary key.
    # - ForeignKey("users.id"): The database-level constraint.
    # - nullable=False: Guarantees every chat session has an owner.
    # - index=True: Optimizes database lookups for a user's chat sessions.
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # --- [CRITICAL MODIFICATION 2/2: THE LOGICAL LINK] ---
    # This SQLAlchemy relationship allows for easy, object-oriented access
    # to the owning User object from a ChatSession instance (e.g., `my_session.owner`).
    # `back_populates="chat_sessions"` creates a two-way link with the `chat_sessions`
    # relationship defined in the `user_model.py` file.
    owner = relationship("User", back_populates="chat_sessions")

    # This relationship remains unchanged. When a ChatSession is deleted, all its
    # child ChatMessage records are also deleted due to the cascade option.
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


# --- [NO MODIFICATIONS REQUIRED FOR CHATMESSAGE MODEL] ---
# The ChatMessage model's ownership is correctly inferred through its parent
# ChatSession. It does not need a direct link to the user.
class ChatMessage(Base):
    """
    SQLAlchemy model representing a single message within a ChatSession.
    """
    __tablename__ = "chatmessages" # Override automatic pluralization

    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("chatsessions.id"), nullable=False)
    role = Column(String, nullable=False) # 'user' or 'bot'
    content = Column(String, nullable=False)
    file_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship to Session remains unchanged.
    session = relationship("ChatSession", back_populates="messages")