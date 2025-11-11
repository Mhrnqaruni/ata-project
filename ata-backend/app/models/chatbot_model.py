# /ata-backend/app/models/chatbot_model.py (DEFINITIVELY CORRECTED & MODERNIZED)

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime

class ChatMessage(BaseModel):
    # This tells Pydantic to allow creating this model from an object's attributes.
    model_config = ConfigDict(from_attributes=True)

    role: str = Field(..., description="The role of the message author, either 'user' or 'bot'.")
    content: str = Field(..., description="The text content of the message.")
    file_id: Optional[str] = Field(None, description="An optional ID for a file associated with this message.")

class ChatSessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="The unique ID of the chat session.")
    name: str = Field(..., description="The auto-generated name of the chat session.")
    created_at: datetime = Field(..., description="The timestamp when the session was created.")

class ChatSessionDetail(ChatSessionSummary):
    # This model inherits the config from ChatSessionSummary, so it's also covered.
    history: List[ChatMessage] = Field(..., description="The complete list of messages in the conversation.")

class NewChatSessionRequest(BaseModel):
    """
    Defines the request body for creating a new chat session.
    PURPOSE: Used by the POST /api/chat/sessions endpoint.
    """
    # --- [THE FIX IS HERE] ---
    # This is the complete and correct Pydantic V2 configuration.
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "firstMessage": "What was the class average on the Mid-Term Exam?",
                "fileId": "file_abc123"
            }
        }
    )
    # --- [END OF FIX] ---

    first_message: str = Field(..., alias="firstMessage")
    file_id: Optional[str] = Field(None, alias="fileId")

class CreateChatSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sessionId: str = Field(..., description="The unique ID of the newly created chat session.")