
# /ata-backend/app/main.py (SUPERVISOR-APPROVED FLAWLESS VERSION)

"""
This module is the main entry point and central assembler for the ATA Backend FastAPI application.

It is responsible for:
1. Creating the main FastAPI application instance.
2. Configuring application-wide settings, such as CORS middleware.
3. Managing application lifecycle events (startup and shutdown) via the `lifespan` manager.
4. Importing and including all the API routers from the `app.routers` package,
   effectively building the complete API structure.
"""

# --- Core FastAPI Imports ---
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# --- Application-specific Router Imports ---
# Import all router objects that define the various API endpoint groups.
from .routers import (
    classes_router,
    assessments_router,
    assessment_review_router,
    tools_router,
    chatbot_router,
    dashboard_router,
    library_router,
    history_router,
    public_router,
    auth_router,
    students_router,
    page_count_router,
    admin_router
)

# --- Service Imports for Startup Logic ---
from .services import library_service
from .core import scheduler

# --- Application Lifecycle Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    An asynchronous context manager to handle application startup and shutdown events.
    """
    # This code runs ONCE when the application starts up.
    print("INFO:     Application startup: Initializing library cache...")
    library_service.initialize_library_cache()
    print("INFO:     Library cache initialized.")

    print("INFO:     Starting background scheduler...")
    scheduler.start_scheduler()
    print("INFO:     Background scheduler started.")

    yield  # The application runs while the context manager is active.

    # This code runs ONCE when the application shuts down.
    print("INFO:     Stopping background scheduler...")
    scheduler.stop_scheduler()
    print("INFO:     Application shutdown.")

# --- FastAPI Application Instance Creation ---
# This creates the main application object. The title, description, and version
# are used for the automatic OpenAPI (Swagger) documentation.
app = FastAPI(
    title="ATA Backend API",
    description="The intelligent engine for the AI Teaching Assistant platform.",
    version="1.0.0",
    lifespan=lifespan
)

# --- Middleware Configuration ---
# Configure Cross-Origin Resource Sharing (CORS) to allow requests from any
# origin. This is suitable for development and for a public API that will be
# consumed by a Vercel-hosted frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],  # Allow frontend to read this header for file downloads
)

# --- API Router Inclusion ---
# The order of inclusion here determines the order in the API documentation.

# --- [CRITICAL MODIFICATION 2/2: INCLUDE THE AUTH ROUTER] ---
# This line activates the /register and /token endpoints, making them live.
# They are placed first as they are the entry point for users.
app.include_router(auth_router.router, prefix="/api/auth", tags=["Authentication"])

# --- Admin Routes (Super Admin Only) ---
app.include_router(admin_router.router, prefix="/api/admin", tags=["Admin"])

# --- Protected API Routes (Require Authentication) ---
# All core business logic endpoints are grouped here. They are all protected
# by the `get_current_active_user` dependency defined within their respective files.
app.include_router(dashboard_router.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(classes_router.router, prefix="/api/classes", tags=["Classes & Students"])
app.include_router(students_router.router, prefix="/api/students", tags=["Students"])
app.include_router(assessment_review_router.router, prefix="/api/assessments", tags=["Assessments Review"])
app.include_router(assessments_router.router, prefix="/api/assessments", tags=["Assessments"])
app.include_router(tools_router.router, prefix="/api/tools", tags=["AI Tools"])
app.include_router(chatbot_router.router, prefix="/api/chatbot", tags=["Chatbot"])
app.include_router(library_router.router, prefix="/api/library", tags=["Curriculum Library"])
app.include_router(history_router.router, prefix="/api/history", tags=["Generation History"])
app.include_router(page_count_router.router, prefix="/api/page-count", tags=["Page Counting"])

# --- Publicly Accessible Routes (Do Not Require User Login) ---
# These routes are for resources that are intentionally public, like shareable reports.
app.include_router(public_router.router, prefix="/public", tags=["Public Resources"])

# --- Root / Health Check Endpoint ---
@app.get("/", tags=["Health Check"])
async def read_root():
    """
    A simple health check endpoint to confirm that the API is online and running.
    """
    return {"status": "ATA Backend is running!", "version": app.version}

