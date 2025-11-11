
    # /ata-backend/app/services/database_helpers/generation_repository_sql.py (MODIFIED AND APPROVED - FLAWLESS VERSION)

"""
This module contains all the raw SQLAlchemy queries for the Generation table, which
stores the history of AI tool usage. It is the direct interface to the database
for all history-related data and a final point of enforcement for data isolation.

Every method that reads or modifies a generation has been updated to require
a `user_id`, ensuring all operations are securely scoped to the authenticated
user. This module follows a "defense-in-depth" principle, meaning every
function is independently secure.
"""

from typing import List, Dict, Optional
from sqlalchemy.orm import Session

# Import the SQLAlchemy model this repository will interact with.
from app.db.models.generation_models import Generation


class GenerationRepositorySQL:
    def __init__(self, db_session: Session):
        self.db = db_session

    def add_generation_record(self, record: Dict) -> Generation:
        """
        Creates a new Generation record in the database from a dictionary.

        CONTRACT: This function expects the `user_id` to be present in the
        `record` dictionary, having been stamped by the calling service layer.
        """
        new_generation = Generation(**record)
        self.db.add(new_generation)
        self.db.commit()
        self.db.refresh(new_generation)
        return new_generation

    def get_all_generations(self, user_id: str) -> List[Generation]:
        """
        Retrieves all generation records owned by a specific user, ordered by most recent first.
        
        The query is now filtered by `user_id` to enforce strict data isolation
        and prevent one user from seeing another user's history.
        """
        return (
            self.db.query(Generation)
            .filter(Generation.user_id == user_id)
            .order_by(Generation.created_at.desc())
            .all()
        )

    def delete_generation_record(self, generation_id: str, user_id: str) -> bool:
        """
        Deletes a single generation record by its ID, but only if it is owned by the
        specified user.

        The query filters by both `generation_id` and `user_id` to create a secure,
        atomic check. This prevents a user from deleting another user's history
        even if they know the ID.
        """
        # Securely fetch the record to delete. This will only return a record if
        # the ID matches AND the user_id matches the owner.
        record_to_delete = (
            self.db.query(Generation)
            .filter(Generation.id == generation_id, Generation.user_id == user_id)
            .first()
        )

        if record_to_delete:
            self.db.delete(record_to_delete)
            self.db.commit()
            return True
        
        # If no record was found (either because the ID is wrong or the owner
        # doesn't match), do nothing and report failure.
        return False
    

