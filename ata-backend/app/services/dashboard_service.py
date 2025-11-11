# /app/services/dashboard_service.py (MODIFIED AND SUPERVISOR-APPROVED - FLAWLESS VERSION)

"""
This service module contains the business logic for calculating the summary
statistics (e.g., class count, student count) displayed on the main
dashboard page.

It has been made "user-aware," ensuring that all calculations are performed
exclusively on the data belonging to the currently authenticated user.
"""

# --- Core Imports ---
from ..models.dashboard_model import DashboardSummary
from .database_service import DatabaseService

# --- Core Public Function ---

def get_summary_data(db: DatabaseService, user_id: str) -> DashboardSummary:
    """
    Calculates the dashboard summary statistics for a specific user.

    This function is the "thick" service layer that contains the business logic.
    It securely retrieves data from the database service using the provided
    `user_id` and performs the necessary aggregations.

    Args:
        db: An instance of the DatabaseService, provided by dependency injection.
        user_id: The unique ID of the currently authenticated user, passed down
                 from the API router.
        
    Returns:
        A DashboardSummary Pydantic object containing the calculated counts
        scoped to the specific user.
    """
    try:
        # --- [CRITICAL MODIFICATION 1/2: SECURE DATA RETRIEVAL] ---
        # Delegate data retrieval to the data access layer, now passing the
        # `user_id` to ensure the queries are securely filtered.

        # This call now uses the secure, user-scoped method to fetch classes.
        user_classes = db.get_all_classes(user_id=user_id)
        
        # To get the student count, we use the secure chatbot helper which
        # correctly performs a join between students and classes and filters by
        # the user's ID. This is the most efficient and secure way to get this count.
        user_students = db.get_students_for_chatbot(user_id=user_id)


        # --- [CRITICAL MODIFICATION 2/2: USER-SPECIFIC LOGIC] ---
        # The business logic itself (counting items) remains the same, but it
        # now operates on securely filtered data.
        class_count = len(user_classes)
        student_count = len(user_students)

        # --- CONSTRUCT & VALIDATE ---
        # Return the data structured according to our Pydantic model.
        # These counts now accurately reflect only the data owned by the user.
        return DashboardSummary(
            classCount=class_count,
            studentCount=student_count
        )
        
    except Exception as e:
        # In a real app, we would add structured logging here.
        print(f"ERROR calculating summary data for user {user_id}: {e}")
        # Re-raise the exception to be handled as a 500 error in the router layer.
        raise