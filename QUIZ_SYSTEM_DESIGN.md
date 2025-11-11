# ATA Quiz System - Comprehensive Design Document

## Executive Summary

This document outlines the complete design for adding a real-time quiz system to the ATA (Adaptive Teaching Assistant) platform. The quiz system will allow teachers to create interactive quizzes, generate shareable links, and host live quiz sessions where students (including non-registered users) can participate in real-time. The system includes live leaderboards, instant feedback, comprehensive analytics, and seamless integration with existing classroom management features.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Core Features](#core-features)
3. [Database Schema](#database-schema)
4. [Backend Architecture](#backend-architecture)
5. [Frontend Architecture](#frontend-architecture)
6. [Authentication Strategy](#authentication-strategy)
7. [Real-Time Communication](#real-time-communication)
8. [API Endpoints](#api-endpoints)
9. [User Flows](#user-flows)
10. [Integration Points](#integration-points)
11. [Analytics & Reporting](#analytics--reporting)
12. [Implementation Phases](#implementation-phases)

---

## 1. System Overview

### 1.1 Purpose
Enable teachers to create and host live, interactive quizzes with real-time participation from students (registered and guest users).

### 1.2 Key Capabilities
- Quiz creation with multiple question types
- Real-time quiz rooms with WebSocket communication
- Guest/anonymous user participation
- Live leaderboards and instant scoring
- Comprehensive analytics and reports
- Integration with existing class rosters

### 1.3 Technical Stack Alignment
- **Backend**: FastAPI (Python) with WebSocket support
- **Frontend**: React 18 with Material-UI
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Real-time**: WebSockets (FastAPI + React)
- **Authentication**: JWT + Session tokens for guests

---

## 2. Core Features

### 2.1 Teacher Features
1. **Quiz Creation**
   - Question builder (multiple choice, true/false, short answer)
   - Time limits per question
   - Point values and scoring
   - Answer key configuration
   - Question shuffling options
   - CSV bulk import support

2. **Quiz Management**
   - Start/stop quiz sessions
   - Monitor live participation
   - View real-time leaderboard
   - Control question progression (manual/auto)
   - Kick participants if needed

3. **Analytics Dashboard**
   - Overall quiz statistics
   - Question-wise analysis
   - Student performance breakdown
   - Time analysis
   - Export results (CSV, PDF)

### 2.2 Student Features
1. **Join Quiz**
   - Join via shareable link or room code
   - Enter name (no registration required)
   - Wait in lobby until quiz starts

2. **Participate**
   - Answer questions in real-time
   - See timer countdown
   - View own score progression
   - See position on leaderboard

3. **Results**
   - View final score
   - See correct answers
   - Compare with others
   - Download personal report

### 2.3 Question Types

#### Supported Types:
1. **Multiple Choice**
   - Single correct answer
   - 2-6 options
   - Shuffle options capability

2. **True/False**
   - Binary choice
   - Fast-paced rounds

3. **Short Answer**
   - Text input
   - Manual or keyword matching grading
   - Case-sensitive option

4. **Poll (No correct answer)**
   - Opinion gathering
   - No points awarded
   - Results shown immediately

---

## 3. Database Schema

### 3.1 New Tables

#### Table: `quizzes`
```python
id = Column(String, primary_key=True)  # UUID
user_id = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)
class_id = Column(String, ForeignKey("classes.id"), nullable=True, index=True)  # Optional class association
title = Column(String, nullable=False, index=True)
description = Column(String, nullable=True)
instructions = Column(Text, nullable=True)
settings = Column(JSON, nullable=False)  # Quiz-level settings
status = Column(Enum: draft | published | archived)
room_code = Column(String(6), unique=True, index=True)  # 6-char alphanumeric
created_at = Column(DateTime(timezone=True), server_default=func.now())
updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# settings JSON structure:
{
  "auto_advance": boolean,  # Auto-advance to next question
  "show_leaderboard": boolean,
  "shuffle_questions": boolean,
  "shuffle_options": boolean,
  "allow_review": boolean,  # Show correct answers after quiz
  "max_participants": integer | null,
  "question_time_default": integer  # seconds
}

# Relationships:
owner → User
class → Class (nullable)
questions → List[QuizQuestion]
sessions → List[QuizSession]
```

#### Table: `quiz_questions`
```python
id = Column(String, primary_key=True)
quiz_id = Column(String, ForeignKey("quizzes.id"), nullable=False, index=True)
question_text = Column(Text, nullable=False)
question_type = Column(Enum: multiple_choice | true_false | short_answer | poll)
order_index = Column(Integer, nullable=False)  # Question order
points = Column(Integer, default=10)
time_limit = Column(Integer, nullable=True)  # seconds, null = use default
options = Column(JSON, nullable=False)  # Question-specific options
correct_answer = Column(JSON, nullable=False)  # Correct answer(s)
explanation = Column(Text, nullable=True)  # Shown after answer
media_url = Column(String, nullable=True)  # Future: images
created_at = Column(DateTime(timezone=True), server_default=func.now())

# options JSON structure (for multiple_choice):
{
  "choices": [
    {"id": "a", "text": "Option A"},
    {"id": "b", "text": "Option B"},
    {"id": "c", "text": "Option C"},
    {"id": "d", "text": "Option D"}
  ],
  "shuffle_options": boolean
}

# correct_answer JSON:
# For multiple_choice: {"answer": "b"}
# For true_false: {"answer": true}
# For short_answer: {"answer": "text", "case_sensitive": false, "keywords": ["word1", "word2"]}
# For poll: {} (no correct answer)

# Relationships:
quiz → Quiz
responses → List[QuizResponse]
```

#### Table: `quiz_sessions`
```python
id = Column(String, primary_key=True)
quiz_id = Column(String, ForeignKey("quizzes.id"), nullable=False, index=True)
user_id = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)  # Quiz host
status = Column(Enum: waiting | in_progress | completed | cancelled)
current_question_index = Column(Integer, default=0)
started_at = Column(DateTime(timezone=True), nullable=True)
ended_at = Column(DateTime(timezone=True), nullable=True)
created_at = Column(DateTime(timezone=True), server_default=func.now())
session_config = Column(JSON, nullable=False)  # Snapshot of quiz settings at session start

# Relationships:
quiz → Quiz
host → User
participants → List[QuizParticipant]
responses → List[QuizResponse]
```

#### Table: `quiz_participants`
```python
id = Column(String, primary_key=True)
session_id = Column(String, ForeignKey("quiz_sessions.id"), nullable=False, index=True)
student_id = Column(String, ForeignKey("students.id"), nullable=True, index=True)  # Registered student
guest_name = Column(String, nullable=True)  # For non-registered users
guest_token = Column(String, unique=True, index=True, nullable=True)  # Session-specific token
joined_at = Column(DateTime(timezone=True), server_default=func.now())
left_at = Column(DateTime(timezone=True), nullable=True)
is_active = Column(Boolean, default=True)
score = Column(Integer, default=0)
correct_answers = Column(Integer, default=0)
total_time_ms = Column(Integer, default=0)  # Total response time

# Constraints:
# Must have either student_id OR guest_name (not both)
CheckConstraint(
    '(student_id IS NOT NULL AND guest_name IS NULL) OR '
    '(student_id IS NULL AND guest_name IS NOT NULL)',
    name='chk_participant_identity'
)

# Relationships:
session → QuizSession
student → Student (nullable)
responses → List[QuizResponse]
```

#### Table: `quiz_responses`
```python
id = Column(String, primary_key=True)
session_id = Column(String, ForeignKey("quiz_sessions.id"), nullable=False, index=True)
participant_id = Column(String, ForeignKey("quiz_participants.id"), nullable=False, index=True)
question_id = Column(String, ForeignKey("quiz_questions.id"), nullable=False, index=True)
answer = Column(JSON, nullable=False)  # User's answer
is_correct = Column(Boolean, nullable=True)  # Null for poll questions
points_earned = Column(Integer, default=0)
time_taken_ms = Column(Integer, nullable=False)  # Milliseconds to answer
answered_at = Column(DateTime(timezone=True), server_default=func.now())

# answer JSON structure:
# For multiple_choice: {"selected": "b"}
# For true_false: {"selected": true}
# For short_answer: {"text": "user answer"}
# For poll: {"selected": "option_id"}

# Relationships:
session → QuizSession
participant → QuizParticipant
question → QuizQuestion
```

### 3.2 Database Indexes
```sql
-- Performance optimization indexes
CREATE INDEX idx_quizzes_user_status ON quizzes(user_id, status);
CREATE INDEX idx_quiz_questions_quiz_order ON quiz_questions(quiz_id, order_index);
CREATE INDEX idx_quiz_sessions_status ON quiz_sessions(status);
CREATE INDEX idx_quiz_participants_session_active ON quiz_participants(session_id, is_active);
CREATE INDEX idx_quiz_responses_session_question ON quiz_responses(session_id, question_id);
```

### 3.3 Relationships Summary
```
User (1) → (N) Quiz → (N) QuizQuestion
User (1) → (N) QuizSession
Quiz (1) → (N) QuizSession
Class (1) → (N) Quiz [optional]
QuizSession (1) → (N) QuizParticipant
QuizSession (1) → (N) QuizResponse
QuizParticipant (1) → (N) QuizResponse
QuizQuestion (1) → (N) QuizResponse
Student (1) → (N) QuizParticipant [optional]
```

---

## 4. Backend Architecture

### 4.1 Directory Structure
```
ata-backend/
├── app/
│   ├── db/
│   │   └── models/
│   │       └── quiz_models.py         # All quiz ORM models
│   │
│   ├── models/
│   │   └── quiz_model.py              # Pydantic request/response models
│   │
│   ├── routers/
│   │   ├── quiz_router.py             # REST API endpoints
│   │   └── quiz_websocket_router.py   # WebSocket endpoints
│   │
│   ├── services/
│   │   ├── quiz_service.py            # Quiz business logic
│   │   ├── quiz_session_service.py    # Session management
│   │   ├── quiz_room_manager.py       # WebSocket room management
│   │   └── quiz_analytics_service.py  # Analytics and reporting
│   │
│   └── core/
│       └── quiz_auth.py               # Guest token generation/validation
```

### 4.2 Service Layer Architecture

#### QuizService (`quiz_service.py`)
```python
class QuizService:
    """Handles quiz CRUD operations"""

    def create_quiz(user_id, quiz_data, db) -> Quiz
    def get_user_quizzes(user_id, db, status=None) -> List[Quiz]
    def get_quiz_by_id(quiz_id, user_id, db) -> Quiz
    def update_quiz(quiz_id, user_id, updates, db) -> Quiz
    def delete_quiz(quiz_id, user_id, db) -> bool
    def duplicate_quiz(quiz_id, user_id, db) -> Quiz
    def import_questions_from_csv(quiz_id, file, db) -> int
    def publish_quiz(quiz_id, user_id, db) -> Quiz
```

#### QuizSessionService (`quiz_session_service.py`)
```python
class QuizSessionService:
    """Manages quiz session lifecycle"""

    def start_session(quiz_id, user_id, db) -> QuizSession
    def get_session_status(session_id, db) -> SessionStatus
    def advance_question(session_id, user_id, db) -> QuestionData
    def end_session(session_id, user_id, db) -> SessionResults
    def get_live_leaderboard(session_id, db) -> List[ParticipantScore]
    def add_participant(session_id, name_or_student_id, is_guest, db) -> Participant
    def remove_participant(session_id, participant_id, db) -> bool
    def submit_answer(session_id, participant_id, question_id, answer, time_ms, db) -> AnswerResult
```

#### QuizRoomManager (`quiz_room_manager.py`)
```python
class QuizRoomManager:
    """Manages WebSocket connections and broadcasts"""

    def __init__(self):
        # {session_id: {websocket: participant_data}}
        self.active_rooms: Dict[str, Dict[WebSocket, dict]] = {}
        self.lock = asyncio.Lock()

    async def connect(session_id, websocket, participant_id)
    async def disconnect(session_id, websocket)
    async def broadcast_to_room(session_id, message, exclude_ws=None)
    async def send_to_participant(session_id, participant_id, message)
    async def get_room_participants(session_id) -> List[dict]
    async def close_room(session_id)
```

#### QuizAnalyticsService (`quiz_analytics_service.py`)
```python
class QuizAnalyticsService:
    """Generates analytics and reports"""

    def get_session_summary(session_id, db) -> SessionSummary
    def get_question_statistics(session_id, question_id, db) -> QuestionStats
    def get_participant_report(session_id, participant_id, db) -> ParticipantReport
    def export_results_csv(session_id, db) -> bytes
    def get_quiz_history(quiz_id, db) -> List[SessionSummary]
```

### 4.3 Guest Authentication

#### File: `core/quiz_auth.py`
```python
from datetime import datetime, timedelta, timezone
import secrets

def generate_guest_token(session_id: str, participant_name: str) -> str:
    """
    Generate a secure, session-specific token for guest participants.

    Format: {random_32_chars}
    Stored in quiz_participants.guest_token
    Valid only for the specific session
    """
    return secrets.token_urlsafe(32)

def validate_guest_token(token: str, session_id: str, db) -> Optional[str]:
    """
    Validate a guest token and return participant_id if valid.

    Returns:
        participant_id if token is valid for the session
        None if invalid or expired
    """
    participant = db.query(QuizParticipant).filter(
        QuizParticipant.guest_token == token,
        QuizParticipant.session_id == session_id,
        QuizParticipant.is_active == True
    ).first()

    if participant:
        return participant.id
    return None
```

---

## 5. Frontend Architecture

### 5.1 Directory Structure
```
ata-frontend/
├── src/
│   ├── pages/
│   │   ├── quiz/
│   │   │   ├── QuizDashboard.jsx         # Teacher: List of quizzes
│   │   │   ├── QuizCreator.jsx           # Teacher: Create/edit quiz
│   │   │   ├── QuizSessionMonitor.jsx    # Teacher: Monitor live session
│   │   │   ├── QuizResults.jsx           # Teacher: View results
│   │   │   ├── QuizJoin.jsx              # Student: Join quiz (public)
│   │   │   ├── QuizLobby.jsx             # Student: Wait for start
│   │   │   ├── QuizPlay.jsx              # Student: Play quiz
│   │   │   └── QuizComplete.jsx          # Student: View results
│   │
│   ├── components/
│   │   ├── quiz/
│   │   │   ├── QuestionBuilder.jsx       # Create/edit questions
│   │   │   ├── QuestionCard.jsx          # Display question
│   │   │   ├── AnswerOptions.jsx         # Answer selection UI
│   │   │   ├── LiveLeaderboard.jsx       # Real-time leaderboard
│   │   │   ├── QuizTimer.jsx             # Countdown timer
│   │   │   ├── ParticipantList.jsx       # List of participants
│   │   │   ├── QuizCard.jsx              # Quiz summary card
│   │   │   └── QuizAnalytics.jsx         # Analytics charts
│   │
│   ├── services/
│   │   └── quizService.js                # Quiz API calls
│   │
│   └── hooks/
│       └── useQuizWebSocket.js           # WebSocket hook for quiz
```

### 5.2 Route Structure
```javascript
// Teacher Routes (Protected)
/quiz                              # Quiz dashboard
/quiz/create                       # Create new quiz
/quiz/:quizId/edit                # Edit quiz
/quiz/:quizId/questions           # Manage questions
/quiz/:quizId/session/:sessionId  # Monitor live session
/quiz/:quizId/results             # All session results

// Public Routes (No auth required)
/quiz/join                        # Join quiz landing page
/quiz/join/:roomCode              # Join specific quiz
/quiz/play/:sessionId/:token      # Play quiz (with guest token)
/quiz/complete/:sessionId/:token  # View personal results
```

### 5.3 Key Components

#### QuizCreator Component
```javascript
// Features:
- Stepper UI (Info → Questions → Settings → Review)
- Question builder with live preview
- Drag-and-drop question reordering
- CSV import dialog
- Duplicate quiz option
- Publish confirmation dialog
```

#### QuizPlay Component
```javascript
// Features:
- WebSocket connection to session
- Real-time question updates
- Answer submission
- Timer display
- Score updates
- Leaderboard sidebar (optional)
```

#### LiveLeaderboard Component
```javascript
// Features:
- Real-time score updates via WebSocket
- Animated position changes
- Highlight current user
- Top 10 display with scroll
```

---

## 6. Authentication Strategy

### 6.1 Teacher/Host Authentication
- Use existing JWT authentication (`get_current_active_user`)
- All quiz management endpoints protected
- Teacher must own quiz to modify/delete
- Teacher must host session to control it

### 6.2 Guest/Student Authentication

#### For Registered Students:
1. Student logs in with existing account
2. Can join quiz using student_id
3. Responses linked to student record
4. Results available in student profile

#### For Guest Users (NEW):
1. **Join Flow**:
   ```
   User enters room code →
   User enters name →
   Backend validates room code →
   Backend generates guest_token →
   Frontend stores token in sessionStorage →
   User can participate
   ```

2. **Token Structure**:
   - 32-character URL-safe random string
   - Stored in `quiz_participants.guest_token`
   - Valid only for specific session
   - Expires when session ends

3. **WebSocket Authentication**:
   ```javascript
   // Guest token passed as query param
   ws://backend/api/quiz/ws/{sessionId}?token={guestToken}

   // Backend validates:
   - Token exists
   - Token matches session
   - Participant is active
   ```

4. **Security Considerations**:
   - No persistent user account created
   - Token cannot be reused across sessions
   - No access to other platform features
   - Participant data deleted after 30 days (GDPR)

---

## 7. Real-Time Communication

### 7.1 WebSocket Message Types

#### Client → Server
```javascript
{
  type: "join_room",
  payload: {
    participant_id: "string",
    name: "string"
  }
}

{
  type: "submit_answer",
  payload: {
    question_id: "string",
    answer: {...},  // Question-specific format
    time_taken_ms: integer
  }
}

{
  type: "heartbeat",
  payload: {}
}
```

#### Server → Client (Broadcast to Room)
```javascript
{
  type: "participant_joined",
  payload: {
    participant_id: "string",
    name: "string",
    total_participants: integer
  }
}

{
  type: "quiz_started",
  payload: {
    started_at: "ISO timestamp"
  }
}

{
  type: "new_question",
  payload: {
    question_index: integer,
    question: {
      id: "string",
      text: "string",
      type: "multiple_choice",
      options: [...],
      time_limit: integer,
      points: integer
    }
  }
}

{
  type: "question_ended",
  payload: {
    question_id: "string",
    correct_answer: {...},  // Shown if settings allow
    explanation: "string"
  }
}

{
  type: "leaderboard_update",
  payload: {
    leaderboard: [
      {
        participant_id: "string",
        name: "string",
        score: integer,
        correct_answers: integer,
        rank: integer
      }
    ]
  }
}

{
  type: "quiz_ended",
  payload: {
    ended_at: "ISO timestamp",
    final_leaderboard: [...]
  }
}

{
  type: "participant_left",
  payload: {
    participant_id: "string",
    total_participants: integer
  }
}

{
  type: "error",
  payload: {
    message: "string",
    code: "string"
  }
}
```

#### Server → Client (Individual)
```javascript
{
  type: "answer_result",
  payload: {
    is_correct: boolean,
    points_earned: integer,
    new_score: integer,
    correct_answer: {...}  // If settings allow immediate feedback
  }
}
```

### 7.2 Room Management Architecture

```python
# Singleton instance
quiz_room_manager = QuizRoomManager()

# WebSocket endpoint
@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),  # Guest token or JWT
    db: DatabaseService = Depends(get_db_service)
):
    # 1. Authenticate
    participant_id = await authenticate_quiz_participant(token, session_id, db)
    if not participant_id:
        await websocket.close(code=1008, reason="Authentication failed")
        return

    # 2. Validate session
    session = db.get_quiz_session(session_id)
    if not session or session.status == "completed":
        await websocket.close(code=1008, reason="Session invalid")
        return

    # 3. Connect to room
    await websocket.accept()
    await quiz_room_manager.connect(session_id, websocket, participant_id)

    # 4. Notify others
    await quiz_room_manager.broadcast_to_room(
        session_id,
        {"type": "participant_joined", "payload": {...}},
        exclude_ws=websocket
    )

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle message types
            if message["type"] == "submit_answer":
                result = await handle_answer_submission(
                    session_id, participant_id, message["payload"], db
                )
                # Send individual result
                await websocket.send_json({
                    "type": "answer_result",
                    "payload": result
                })
                # Broadcast leaderboard update
                leaderboard = await get_live_leaderboard(session_id, db)
                await quiz_room_manager.broadcast_to_room(
                    session_id,
                    {"type": "leaderboard_update", "payload": leaderboard}
                )

    except WebSocketDisconnect:
        await quiz_room_manager.disconnect(session_id, websocket)
        # Notify others
        await quiz_room_manager.broadcast_to_room(
            session_id,
            {"type": "participant_left", "payload": {...}}
        )
```

---

## 8. API Endpoints

### 8.1 Quiz Management (Protected)

```
GET /api/quiz
  - Get all quizzes for current user
  - Query params: status (draft|published|archived), class_id
  - Response: List[QuizSummary]

POST /api/quiz
  - Create new quiz
  - Body: QuizCreate
  - Response: Quiz

GET /api/quiz/{quiz_id}
  - Get quiz details
  - Response: QuizDetail (includes questions)

PUT /api/quiz/{quiz_id}
  - Update quiz metadata
  - Body: QuizUpdate
  - Response: Quiz

DELETE /api/quiz/{quiz_id}
  - Delete quiz (soft delete if has sessions)
  - Response: 204 No Content

POST /api/quiz/{quiz_id}/duplicate
  - Create a copy of quiz
  - Response: Quiz

POST /api/quiz/{quiz_id}/publish
  - Publish draft quiz
  - Response: Quiz

POST /api/quiz/{quiz_id}/questions
  - Add question to quiz
  - Body: QuestionCreate
  - Response: QuizQuestion

PUT /api/quiz/{quiz_id}/questions/{question_id}
  - Update question
  - Body: QuestionUpdate
  - Response: QuizQuestion

DELETE /api/quiz/{quiz_id}/questions/{question_id}
  - Delete question
  - Response: 204 No Content

POST /api/quiz/{quiz_id}/questions/reorder
  - Reorder questions
  - Body: {question_ids: [string]}
  - Response: Quiz

POST /api/quiz/{quiz_id}/questions/import-csv
  - Import questions from CSV
  - Body: multipart/form-data (file)
  - Response: {imported: integer}
```

### 8.2 Quiz Sessions (Protected for hosts)

```
POST /api/quiz/{quiz_id}/sessions
  - Start new quiz session
  - Response: QuizSession

GET /api/quiz/sessions/{session_id}
  - Get session details
  - Response: SessionDetail

POST /api/quiz/sessions/{session_id}/advance
  - Move to next question (manual mode)
  - Response: {question_index: integer}

POST /api/quiz/sessions/{session_id}/end
  - End session
  - Response: SessionResults

GET /api/quiz/sessions/{session_id}/participants
  - Get list of participants
  - Response: List[Participant]

DELETE /api/quiz/sessions/{session_id}/participants/{participant_id}
  - Kick participant
  - Response: 204 No Content

GET /api/quiz/sessions/{session_id}/leaderboard
  - Get current leaderboard
  - Response: List[ParticipantScore]
```

### 8.3 Quiz Participation (Public/Guest)

```
GET /api/quiz/join/{room_code}
  - Validate room code and get session info
  - Response: {session_id, quiz_title, status}

POST /api/quiz/join/{room_code}
  - Join quiz session
  - Body: {name: string, student_id: string (optional)}
  - Response: {participant_id, guest_token, session_id}

WebSocket /api/quiz/ws/{session_id}?token={guest_token}
  - Real-time quiz participation
  - See section 7 for message types
```

### 8.4 Quiz Results & Analytics (Protected)

```
GET /api/quiz/{quiz_id}/sessions
  - Get all sessions for quiz
  - Response: List[SessionSummary]

GET /api/quiz/sessions/{session_id}/results
  - Get detailed session results
  - Response: SessionResults (all participants)

GET /api/quiz/sessions/{session_id}/participants/{participant_id}/report
  - Get individual participant report
  - Response: ParticipantReport

GET /api/quiz/sessions/{session_id}/export
  - Export results as CSV
  - Response: CSV file download

GET /api/quiz/sessions/{session_id}/analytics
  - Get session analytics
  - Response: SessionAnalytics (charts data)
```

---

## 9. User Flows

### 9.1 Teacher Creates Quiz
```
1. Navigate to /quiz
2. Click "Create New Quiz"
3. Step 1: Enter title, description, select class (optional)
4. Step 2: Add questions
   - Choose question type
   - Enter question text
   - Add answer options
   - Set correct answer
   - Set points and time limit
   - Add explanation (optional)
   - Click "Add Question"
   - Repeat for all questions
5. Step 3: Configure settings
   - Auto-advance questions
   - Show leaderboard
   - Shuffle questions/options
   - Allow answer review
6. Step 4: Review and publish
7. Quiz is now available with room code
```

### 9.2 Teacher Hosts Live Quiz
```
1. Go to Quiz Dashboard (/quiz)
2. Click "Start Session" on published quiz
3. Backend creates session, generates room code
4. Share room code with students (display on screen, link, etc.)
5. Navigate to Session Monitor page
6. See participants joining in real-time
7. When ready, click "Start Quiz"
8. Questions advance automatically or manually
9. Monitor leaderboard in real-time
10. When all questions answered, session ends
11. View results and analytics
```

### 9.3 Student Joins & Plays Quiz (Guest)
```
1. Receive room code from teacher
2. Navigate to /quiz/join
3. Enter room code → Submit
4. Backend validates code
5. Enter name → Submit
6. Backend generates guest token, creates participant
7. Redirect to /quiz/play/{sessionId}/{token}
8. WebSocket connects with guest token
9. Wait in lobby (see other participants joining)
10. Quiz starts → Receive first question via WebSocket
11. Timer starts counting down
12. Select answer → Submit
13. Receive immediate feedback (if enabled)
14. See score update
15. Wait for next question
16. Repeat until all questions answered
17. See final score and leaderboard
18. Option to view detailed results
```

### 9.4 Student Joins & Plays Quiz (Registered)
```
1. Student logs in to platform
2. Navigate to /quiz/join OR click link in class page
3. Enter room code OR room code pre-filled from link
4. Submit (no name required, uses student profile)
5. Backend links participant to student_id
6. Same flow as guest from step 7 onwards
7. Results automatically saved to student profile
```

---

## 10. Integration Points

### 10.1 Integration with Classes
```python
# Link quiz to class
quiz.class_id = class_id

# When starting session, auto-populate registered students
def start_session_for_class(quiz_id, user_id, db):
    quiz = get_quiz(quiz_id, user_id, db)
    if quiz.class_id:
        # Get class roster
        students = get_class_students(quiz.class_id, user_id, db)
        # Generate invite links for each student
        # Send notifications (future feature)
```

### 10.2 Integration with Student Profiles
```python
# Quiz results appear in student transcript
def get_student_transcript(student_id, user_id, db):
    # Existing: assessment results
    assessments = get_student_assessments(student_id, db)

    # New: quiz results
    quiz_results = db.query(QuizParticipant).join(QuizSession).filter(
        QuizParticipant.student_id == student_id
    ).all()

    return {
        "assessments": assessments,
        "quiz_results": quiz_results
    }
```

### 10.3 Navigation Integration
```javascript
// Update Sidebar.jsx
const navigationItems = [
  { text: 'Home', icon: <HomeOutlined />, path: '/' },
  { text: 'Your Classes', icon: <SchoolOutlined />, path: '/classes' },
  { text: 'AI Tools', icon: <AutoAwesomeOutlined />, path: '/tools' },
  { text: 'Assessments', icon: <GradingOutlined />, path: '/assessments' },
  { text: 'Quiz', icon: <QuizOutlined />, path: '/quiz' },  // NEW
  { text: 'Chatbot', icon: <SmartToyOutlined />, path: '/chat' },
];
```

### 10.4 Dashboard Integration
```javascript
// Update Home.jsx dashboard
const dashboardStats = {
  classes: classCount,
  students: studentCount,
  assessments: assessmentCount,
  quizzes: quizCount,  // NEW
  activeQuizSessions: activeSessionCount  // NEW
};
```

---

## 11. Analytics & Reporting

### 11.1 Quiz-Level Analytics
```javascript
{
  quiz_id: "string",
  total_sessions: integer,
  total_participants: integer,
  average_score: float,
  average_completion_time: integer,  // seconds
  question_statistics: [
    {
      question_id: "string",
      question_text: "string",
      total_attempts: integer,
      correct_percentage: float,
      average_time_ms: integer,
      answer_distribution: {
        "option_a": 15,
        "option_b": 45,
        "option_c": 20,
        "option_d": 20
      }
    }
  ]
}
```

### 11.2 Session-Level Analytics
```javascript
{
  session_id: "string",
  quiz_title: "string",
  started_at: "ISO timestamp",
  ended_at: "ISO timestamp",
  duration_seconds: integer,
  total_participants: integer,
  completed_participants: integer,
  average_score: float,
  median_score: float,
  highest_score: integer,
  lowest_score: integer,
  score_distribution: {
    "0-20": 2,
    "21-40": 5,
    "41-60": 8,
    "61-80": 10,
    "81-100": 15
  },
  leaderboard: [...]
}
```

### 11.3 Participant-Level Report
```javascript
{
  participant_id: "string",
  name: "string",
  score: integer,
  correct_answers: integer,
  total_questions: integer,
  accuracy_percentage: float,
  total_time_ms: integer,
  rank: integer,
  responses: [
    {
      question_id: "string",
      question_text: "string",
      user_answer: {...},
      correct_answer: {...},
      is_correct: boolean,
      points_earned: integer,
      time_taken_ms: integer
    }
  ]
}
```

---

## 12. Implementation Phases

### Phase 1: Database & Backend Foundation
**Duration: 3-4 days**

Tasks:
1. Create SQLAlchemy models (`quiz_models.py`)
2. Create Alembic migration
3. Test database schema
4. Implement guest authentication (`quiz_auth.py`)
5. Create Pydantic models for API (`quiz_model.py`)
6. Write unit tests for models

### Phase 2: Quiz CRUD & Session Management
**Duration: 3-4 days**

Tasks:
1. Implement `QuizService` class
2. Implement `QuizSessionService` class
3. Create REST API endpoints (`quiz_router.py`)
4. Add input validation and error handling
5. Write integration tests for API
6. Test with Postman/curl

### Phase 3: Real-Time WebSocket System
**Duration: 4-5 days**

Tasks:
1. Implement `QuizRoomManager` class
2. Create WebSocket router (`quiz_websocket_router.py`)
3. Implement message handlers
4. Test room broadcasting
5. Test connection management
6. Load testing with multiple clients

### Phase 4: Analytics & Reporting
**Duration: 2-3 days**

Tasks:
1. Implement `QuizAnalyticsService` class
2. Create analytics endpoints
3. Implement CSV export
4. Create report generation logic
5. Test analytics calculations

### Phase 5: Frontend - Teacher Quiz Creation
**Duration: 4-5 days**

Tasks:
1. Create `quizService.js` API client
2. Build Quiz Dashboard page
3. Build Quiz Creator wizard
4. Build Question Builder component
5. Implement question reordering
6. Implement CSV import UI
7. Add form validation
8. Test quiz creation flow

### Phase 6: Frontend - Live Session Monitoring
**Duration: 3-4 days**

Tasks:
1. Build Session Monitor page
2. Build Participant List component
3. Build Live Leaderboard component
4. Implement WebSocket connection for host
5. Add session controls (start, advance, end)
6. Test real-time updates

### Phase 7: Frontend - Student Participation
**Duration: 5-6 days**

Tasks:
1. Create `useQuizWebSocket.js` hook
2. Build Quiz Join page (public)
3. Build Quiz Lobby page
4. Build Quiz Play page
5. Build Question Card component
6. Build Answer Options component
7. Build Quiz Timer component
8. Build Quiz Complete page
9. Test guest authentication flow
10. Test real-time quiz play

### Phase 8: Frontend - Results & Analytics
**Duration: 3-4 days**

Tasks:
1. Build Quiz Results page
2. Build Quiz Analytics dashboard
3. Implement charts (using Recharts or Chart.js)
4. Build export functionality
5. Build participant report view
6. Test analytics display

### Phase 9: Integration & Polish
**Duration: 3-4 days**

Tasks:
1. Add Quiz to sidebar navigation
2. Integrate with class management
3. Integrate with student profiles
4. Add quiz cards to Home dashboard
5. Implement responsive design
6. Add loading states and error handling
7. Improve UI/UX based on testing

### Phase 10: Testing & Documentation
**Duration: 2-3 days**

Tasks:
1. End-to-end testing
2. Cross-browser testing
3. Mobile responsiveness testing
4. Performance testing
5. Security testing
6. Write user documentation
7. Write API documentation
8. Bug fixes and refinements

**Total Estimated Duration: 32-42 days (6-8 weeks)**

---

## 13. Security Considerations

### 13.1 Data Protection
- Guest tokens are session-specific and cannot be reused
- Participant data encrypted in transit (WSS protocol)
- Quiz answers stored securely in database
- GDPR compliance: Guest data deleted after 30 days

### 13.2 Authorization
- Teachers can only access their own quizzes
- Participants can only submit answers for their own session
- Room codes are unique and unpredictable (6-char alphanumeric)
- WebSocket connections validated for each message

### 13.3 Rate Limiting
- Limit answer submissions per participant per question (1 submission)
- Limit quiz creation per user (prevent spam)
- Limit WebSocket connections per IP (prevent DDoS)

### 13.4 Input Validation
- Sanitize all user inputs (quiz titles, questions, answers)
- Validate question types and formats
- Validate time limits and point values
- Prevent XSS attacks in quiz content

---

## 14. Performance Optimization

### 14.1 Database
- Proper indexing on frequently queried columns
- Connection pooling for concurrent sessions
- Caching of published quiz configurations
- Batch inserts for responses

### 14.2 WebSocket
- Connection pooling
- Message queuing for high-traffic rooms
- Heartbeat mechanism to detect dead connections
- Graceful degradation if WebSocket fails

### 14.3 Frontend
- Code splitting for quiz pages
- Lazy loading of components
- Memoization of expensive calculations (leaderboard sorting)
- Debouncing of user inputs

---

## 15. Future Enhancements

### 15.1 Advanced Question Types
- Image-based questions
- Audio/video questions
- Code challenges (syntax highlighting)
- Drawing/annotation questions

### 15.2 Gamification
- Badges and achievements
- Streak bonuses
- Power-ups (50/50, time extension)
- Team mode (collaborative quizzes)

### 15.3 Advanced Analytics
- Learning curve tracking
- Question difficulty estimation
- Participant engagement metrics
- Predictive performance analysis

### 15.4 Integration Features
- LMS integration (Canvas, Moodle, etc.)
- Calendar integration for scheduled quizzes
- Email notifications
- Mobile app

### 15.5 Accessibility
- Screen reader support
- Keyboard navigation
- Color-blind friendly themes
- High contrast mode

---

## Conclusion

This design document provides a comprehensive blueprint for implementing a production-ready, real-time quiz system into the ATA platform. The system is designed to:

1. **Leverage existing patterns**: Uses established authentication, database, and WebSocket patterns from the current codebase
2. **Support guest users**: Enables participation without registration while maintaining security
3. **Scale effectively**: Designed for multiple concurrent quiz sessions with many participants
4. **Provide rich analytics**: Comprehensive reporting for teachers and students
5. **Integrate seamlessly**: Works with existing classes and student management features

The phased implementation approach ensures steady progress with testable milestones at each stage.
