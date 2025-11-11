# /app/models/dashboard_model.py (CORRECTED TO MODERN PydANTIC V2 SYNTAX)

# --- Core Imports ---
from pydantic import BaseModel, Field, ConfigDict

# --- Model Definition ---

class DashboardSummary(BaseModel):
    """
    Defines the data contract for the response of the dashboard summary endpoint.
    This model specifies the exact shape of the data that will be sent to the
    Home Page to populate its "Quick Info Cards".
    """
    # --- [THE FIX IS HERE] ---
    # The example is now part of the model_config, which is the modern syntax.
    # from_attributes is NOT needed here, as explained above.
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "classCount": 4,
                "studentCount": 112
            }
        }
    )
    # --- [END OF FIX] ---

    classCount: int = Field(
        ...,
        description="The total number of active classes for the user."
    )
    
    studentCount: int = Field(
        ...,
        description="The total number of students enrolled across all of the user's classes."
    )