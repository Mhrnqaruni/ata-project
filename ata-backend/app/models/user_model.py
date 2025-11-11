# /ata-backend/app/models/user_model.py (FINAL, CORRECTED, AND FLAWLESS)

import uuid
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict
# --- [THE FIX IS HERE, STEP 1: Import the case converter] ---
from pydantic.alias_generators import to_camel

# --- User Models ---

class UserBase(BaseModel):
    """
    Base model containing shared properties for a user.
    It is now configured to automatically handle camelCase aliases for JSON.
    """
    email: EmailStr = Field(..., description="The user's unique email address.")
    full_name: Optional[str] = Field(None, description="The user's full name.")

    # --- [THE FIX IS HERE, STEP 2: ADD THE CONFIG TO THE BASE MODEL] ---
    model_config = ConfigDict(
        alias_generator=to_camel,   # Generate camelCase aliases from snake_case field names.
        populate_by_name=True,    # Allow populating fields by their name OR their alias.
    )
    # --- [END OF FIX] ---

class UserCreate(UserBase):
    """
    Pydantic model for data required to create a new user.
    This model inherits the camelCase configuration from UserBase, so it will correctly
    accept a "fullName" key from the JSON payload and map it to the "full_name" field.
    """
    password: str = Field(
        ...,
        min_length=8,
        description="The user's plain-text password (will be hashed before storage)."
    )


class User(UserBase):
    """
    Pydantic model for representing a user's data in API responses.
    This model also inherits the camelCase configuration. When FastAPI serializes
    this model to JSON, it will use the aliases, creating keys like "fullName"
    in the output, which is ideal for the JavaScript frontend.
    """
    id: uuid.UUID = Field(..., description="The unique, server-generated identifier for the user.")
    is_active: bool = Field(..., description="Indicates if the user's account is active.")
    
    # We must combine the configs. `from_attributes` is for reading from SQLAlchemy objects,
    # and the alias settings are for correctly formatting the outgoing JSON.
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

# --- Token Models (Unchanged, as their fields are standard snake_case) ---

class Token(BaseModel):
    access_token: str = Field(..., description="The JWT access token string.")
    token_type: str = Field("bearer", description="The type of the token (always 'bearer').")


class TokenData(BaseModel):
    user_id: Optional[str] = Field(None, description="The unique ID of the user (subject of the token).")