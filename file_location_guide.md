# Quiz Backend Services - File Location Reference Guide

## Core Service Files

### Service Layer

| File | Location | Purpose |
|------|----------|---------|
| **Quiz Service** | `/home/user/ata-project/ata-backend/app/services/quiz_service.py` | Quiz CRUD, session management, participant join flows, grading, auto-advance, analytics calculation |
| **Quiz Analytics Service** | `/home/user/ata-project/ata-backend/app/services/quiz_analytics_service.py` | Session/question/participant analytics, difficulty/discrimination metrics |
| **Database Service (Facade)** | `/home/user/ata-project/ata-backend/app/services/database_service.py` | Central coordinator for all repositories, exposes unified interface |

### Repository Layer (Data Access)

| File | Location | Purpose |
|------|----------|---------|
| **Quiz Repository** | `/home/user/ata-project/ata-backend/app/services/database_helpers/quiz_repository_sql.py` | Quiz & Question CRUD with user ownership validation |
| **Quiz Session Repository** | `/home/user/ata-project/ata-backend/app/services/database_helpers/quiz_session_repository_sql.py` | Session/Participant/Response CRUD, leaderboard queries, pessimistic locking |
| **Class Student Repository** | `/home/user/ata-project/ata-backend/app/services/database_helpers/class_student_repository_sql.py` | Class/Student management, roster operations |

### Core Utilities

| File | Location | Purpose |
|------|----------|---------|
| **Quiz Auth** | `/home/user/ata-project/ata-backend/app/core/quiz_auth.py` | Room code generation, guest tokens, name sanitization |
| **Quiz Config** | `/home/user/ata-project/ata-backend/app/core/quiz_config.py` | Configuration settings (participants/sessions limits, timeouts, GDPR) |
| **Quiz Shuffling** | `/home/user/ata-project/ata-backend/app/core/quiz_shuffling.py` | Question/answer randomization logic |
| **Quiz WebSocket** | `/home/user/ata-project/ata-backend/app/core/quiz_websocket.py` | Real-time message broadcasting |

### Database Models

| File | Location | Purpose |
|------|----------|---------|
| **Quiz Models** | `/home/user/ata-project/ata-backend/app/db/models/quiz_models.py` | SQLAlchemy ORM: Quiz, QuizQuestion, QuizSession, QuizParticipant, QuizResponse |
| **Class/Student Models** | `/home/user/ata-project/ata-backend/app/db/models/class_student_models.py` | SQLAlchemy ORM: User, Class, Student, StudentClassMembership |

### API Routers

| File | Location | Purpose |
|------|----------|---------|
| **Quiz Router** | `/home/user/ata-project/ata-backend/app/routers/quiz_router.py` | Quiz CRUD endpoints (authenticated) |
| **Quiz Session Router** | `/home/user/ata-project/ata-backend/app/routers/quiz_session_router.py` | Session management, participant join, answer submission, analytics |
| **Quiz WebSocket Router** | `/home/user/ata-project/ata-backend/app/routers/quiz_websocket_router.py` | WebSocket endpoint for real-time session management |
| **Quiz Analytics Router** | `/home/user/ata-project/ata-backend/app/routers/quiz_analytics_router.py` | Analytics endpoints |

---

## Key Code Sections for Integration

### WHERE TO ADD ROSTER CHECKING

**Primary Location**:
- File: `/home/user/ata-project/ata-backend/app/services/quiz_service.py`
- Function: `join_session_as_identified_guest()` (Lines 842-941)
- Line Number: After line 913 (after checking participant limit, before deduplication)

**What to Add**:
```python
# NEW: After line 913
if quiz and quiz.class_id:
    student = db.get_student_by_student_id(student_id)
    if not student:
        raise ValueError(f"Student {student_id} not found")
    is_in_class = db.is_student_in_class(student_id, quiz.class_id)
    if not is_in_class:
        raise ValueError(f"Student not enrolled in class")
```

**Secondary Locations**:
- Quiz publish validation: Line 178-219
- Session creation: Line 248-325

### PARTICIPANT TRACKING CODE

**Location**: `/home/user/ata-project/ata-backend/app/services/database_helpers/quiz_session_repository_sql.py`

**Key Methods**:
- Line 256: `add_participant()` - Create new participant
- Line 310: `get_participants_by_session()` - Get all participants in session
- Line 331: `get_participant_by_student_in_session()` - Check if student already in session
- Line 353: `get_participant_names_in_session()` - Get display names for duplicate detection
- Line 384: `update_participant()` - Update participant fields
- Line 404: `update_participant_score()` - Score update with pessimistic locking (line 427-432)
- Line 473: `get_leaderboard()` - Get ranking for display

### LEADERBOARD & DISPLAY NAME RESOLUTION

**Location**: `/home/user/ata-project/ata-backend/app/services/quiz_service.py`

**Display Name Lookup** (Lines 641-671):
```python
for rank, p in enumerate(leaderboard_participants, start=1):
    display_name = "Unknown"
    if p.guest_name:
        display_name = p.guest_name
    elif p.student_id:
        try:
            student = db.get_student_by_student_id(p.student_id)
            display_name = student.name if student else f"Student {p.student_id}"
        except:
            display_name = f"Student {p.student_id}"
```

---

## Database Schema Quick Reference

### QuizParticipant Table Fields

```
id (String, PK)
session_id (String, FK → quiz_sessions)
student_id (String, nullable) - School student ID
guest_name (String, nullable) - Display name
guest_token (String, nullable, unique) - Auth token
score (Integer)
correct_answers (Integer)
total_time_ms (Integer)
is_active (Boolean)
anonymized_at (DateTime, nullable)
joined_at (DateTime)
last_seen_at (DateTime)

CHECK CONSTRAINT (triple identity pattern):
  (student_id NOT NULL AND guest_name NULL AND guest_token NULL) OR
  (student_id NULL AND guest_name NOT NULL AND guest_token NOT NULL) OR
  (student_id NOT NULL AND guest_name NOT NULL AND guest_token NOT NULL)

INDEXES:
  idx_participants_session_score (session_id, score DESC)
  idx_participants_session_active (session_id, is_active)
  idx_participants_gdpr_cleanup (joined_at, anonymized_at WHERE guest_token IS NOT NULL)
```

### Quiz Table Fields (Relevant for Roster)

```
id (String, PK)
user_id (UUID, FK → users) - Teacher owner
class_id (String, FK → classes, nullable) - CLASS ASSOCIATION FOR ROSTER
title (String)
description (Text)
settings (JSONB)
status (String)
deleted_at (DateTime, nullable)
created_at (DateTime)
updated_at (DateTime)

INDEXES:
  idx_quizzes_user_status_not_deleted (user_id, status WHERE deleted_at IS NULL)
  idx_quizzes_class_not_deleted (class_id WHERE deleted_at IS NULL)
```

---

## Import Paths for Key Services/Repositories

```python
# Services
from app.services.quiz_service import (
    create_quiz_with_questions,
    create_session_with_room_code,
    start_session,
    join_session_as_identified_guest,
    submit_answer_with_grading,
    get_session_analytics,
    ...
)

from app.services.quiz_analytics_service import (
    calculate_session_analytics,
    calculate_question_analytics,
    calculate_participant_analytics,
    ...
)

# Repositories (accessed through DatabaseService)
from app.services.database_service import DatabaseService
db = DatabaseService(db_session)

# Direct repository usage (rare)
from app.services.database_helpers.quiz_repository_sql import QuizRepositorySQL
from app.services.database_helpers.quiz_session_repository_sql import QuizSessionRepositorySQL
from app.services.database_helpers.class_student_repository_sql import ClassStudentRepositorySQL
```

---

## Testing Key Flows

### Test 1: Quiz Creation with Class Association
- File: `/home/user/ata-project/ata-backend/app/services/quiz_service.py`
- Function: `create_quiz_with_questions()` (Line 83)
- Expected: Quiz.class_id should be set

### Test 2: Participant Join with Roster Validation (WHERE TO ADD)
- File: `/home/user/ata-project/ata-backend/app/routers/quiz_session_router.py`
- Endpoint: POST `/api/quiz-sessions/join`
- Current: Validates room code, status, capacity, duplicate name
- Add: Roster validation if quiz.class_id set

### Test 3: Leaderboard Display with Student Names
- File: `/home/user/ata-project/ata-backend/app/services/quiz_service.py`
- Function: `auto_advance_question()` (Line 641-671)
- Check: Display name resolution from student_id

### Test 4: Analytics by Class
- File: `/home/user/ata-project/ata-backend/app/services/quiz_analytics_service.py`
- Function: `calculate_session_analytics()` (Line 36)
- Potential: Filter participants by class membership

---

## Architecture Visualization

```
HTTP Request to POST /api/quiz-sessions/join
    ↓
quiz_session_router.py::join_session() [Public endpoint]
    ↓
quiz_service.py::join_session_as_identified_guest()
    │
    ├─ db.get_quiz_session_by_room_code(room_code)
    │   └─ quiz_session_repository_sql.py::get_session_by_room_code()
    │
    ├─ db.get_quiz_by_id(quiz_id, user_id)
    │   └─ quiz_repository_sql.py::get_quiz_by_id()
    │
    ├─ [NEW] db.is_student_in_class(student_id, class_id)  ← ADD THIS
    │   └─ class_student_repository_sql.py::is_student_in_class()
    │
    ├─ db.get_participants_by_session(session_id)
    │   └─ quiz_session_repository_sql.py::get_participants_by_session()
    │
    ├─ db.add_quiz_participant(participant_data)
    │   └─ quiz_session_repository_sql.py::add_participant()
    │
    └─ return {participant_id, guest_token}
```

---

## Quick Command Reference

### Find all quiz service functions
```bash
grep "^def " /home/user/ata-project/ata-backend/app/services/quiz_service.py
```

### Find all repository methods
```bash
grep "def " /home/user/ata-project/ata-backend/app/services/database_helpers/quiz_session_repository_sql.py
```

### Find roster-related code
```bash
grep -r "class_id\|student_id\|is_in_class" /home/user/ata-project/ata-backend/app/
```

### Find error handling patterns
```bash
grep -B2 -A2 "raise ValueError\|raise HTTPException" /home/user/ata-project/ata-backend/app/services/quiz_service.py | head -50
```
