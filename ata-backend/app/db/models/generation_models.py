# /ata-backend/app/db/models/generation_models.py (MODIFIED AND APPROVED)

"""
This module defines the SQLAlchemy ORM model for the `Generation` entity,
which represents a saved output from one of the AI content generation tools.
"""

from sqlalchemy import Column, String, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
# --- [CRITICAL MODIFICATION] ---
# Import the UUID type from SQLAlchemy's PostgreSQL dialects. This is necessary
# to ensure the `user_id` foreign key column has the exact same data type as
# the `User.id` primary key it points to.
from sqlalchemy.dialects.postgresql import UUID

from ..base_class import Base

class Generation(Base):
    """
    SQLAlchemy model representing a single saved AI tool generation.

    This model is now linked to a User, ensuring that each piece of generated
    content in the history is privately owned.
    """
    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    tool_id = Column(String, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    settings_snapshot = Column(JSON, nullable=False)
    generated_content = Column(String, nullable=False)

    # --- [CRITICAL MODIFICATION 1/2: THE PHYSICAL LINK] ---
    # This column creates the foreign key relationship to the `users` table.
    # - UUID(as_uuid=True): Ensures type compatibility with the User.id primary key.
    # - ForeignKey("users.id"): The database-level constraint.
    # - nullable=False: Guarantees every saved generation has an owner.
    # - index=True: Optimizes database lookups for a user's history.
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # --- [CRITICAL MODIFICATION 2/2: THE LOGICAL LINK] ---
    # This SQLAlchemy relationship allows for easy, object-oriented access
    # to the owning User object from a Generation instance (e.g., `my_generation.owner`).
    # `back_populates="generations"` creates a two-way link with the `generations`
    # relationship defined in the `user_model.py` file.
    owner = relationship("User", back_populates="generations")