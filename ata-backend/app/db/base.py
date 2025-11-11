# /ata-backend/app/db/base.py

"""
This module acts as the central registry for all SQLAlchemy ORM models.

Its sole purpose is to import all model classes into a single namespace. This
ensures that the shared `Base.metadata` object is fully populated with all
table definitions before being inspected by Alembic for database migration
generation.

Any new SQLAlchemy model created for the application MUST be imported here.
"""

# Import the Base class that all models inherit from. This provides the
# declarative base and the metadata container.
from .base_class import Base

# --- Application-Specific Model Imports ---

# Import all existing models to register them with the Base metadata.
from .models.class_student_models import Class, Student
from .models.assessment_models import Assessment, Result
from .models.ai_model_run import AIModelRun
from .models.chat_models import ChatSession, ChatMessage
from .models.generation_models import Generation

# --- [CRITICAL MODIFICATION FOR AUTHENTICATION] ---
# Import the new User model. This is the essential change that makes Alembic
# aware of the new `users` table, allowing it to correctly generate the
# database migration script for creating the table and linking foreign keys to it.
from .models.user_model import User