# Quiz Backend Services - Comprehensive Architecture Analysis

## Executive Summary

The quiz system uses a **layered architecture** with three main tiers:
1. **API Routers** - REST endpoints for teachers and participants
2. **Service Layer** - Business logic for quizzes, sessions, grading, and analytics
3. **Repository Layer** - Database access abstraction with security validation
4. **Database Service** - Facade coordinating all repositories

This architecture enables:
- **Security**: User ownership validation at repository level
- **Scalability**: Index-optimized queries, pessimistic locking for concurrency
- **Analytics**: Comprehensive session, question, and participant metrics
- **Flexibility**: JSONB columns for various question types
- **GDPR Compliance**: Guest data anonymization, soft deletes for audit trails

---

## 1. Service Layer Architecture

### Core Services

#### 1.1 Quiz Service (quiz_service.py)
**Location**: `/home/user/ata-project/ata-backend/app/services/quiz_service.py`

**Responsibilities**:
- Quiz CRUD with validation
- Session management and auto-advance scheduling
- Participant management (3 identity patterns)
- Answer grading engine
- Missed response tracking
- Analytics calculation

**Key Functions**:

| Function | Purpose | Key Business Logic |
|----------|---------|-------------------|
| `create_quiz_with_questions()` | Create quiz with questions | Validates max questions (100), starts as draft |
| `update_quiz_with_validation()` | Update quiz fields | Validates publish (needs ≥1 question) |
| `validate_publish_quiz()` | Pre-publish validation | Ensures questions have correct setup |
| `create_session_with_room_code()` | Create live session | Unique room code, config snapshot, auto-advance enabled |
| `start_session()` | Move session to active | Sets status, timestamps, question index |
| `end_session()` | Complete session | Updates status, optionally updates quiz status |
| `join_session_as_guest()` | Guest join flow | Name sanitization, duplicate handling, token generation |
| `join_session_as_identified_guest()` | Student + ID join | **Most common K-12 flow** - both name and student_id |
| `join_session_as_student()` | Registered student join | Handles rejoin/reactivation |
| `grade_answer()` | Answer grading | Supports MC, T/F, short answer (keyword matching), poll |
| `submit_answer_with_grading()` | Submit & grade answer | Time limit enforcement, duplicate prevention, score update |
| `schedule_auto_advance()` | APScheduler integration | Schedules question advancement |
| `auto_advance_question()` | Background job | Broadcasts messages, creates missed responses, schedules next |
| `create_missed_responses_for_question()` | Track non-participation | Creates empty responses for skipped questions |

**Error Handling Pattern**:
```python
try:
    # Validate business rules
    if condition:
        raise ValueError("Human-readable error")
    # Perform operations
    return result
except ValueError as e:
    # Services raise ValueError, routers convert to HTTP 422
    raise
except Exception as e:
    # Log unexpected errors
    logger.error(f"Operation failed: {e}", exc_info=True)
    raise
```

**Transaction Management**:
- Services don't explicitly manage transactions
- Repository layer handles commit/rollback via SQLAlchemy session
- Pessimistic locking in `update_participant_score()` prevents race conditions

---

#### 1.2 Quiz Analytics Service (quiz_analytics_service.py)
**Location**: `/home/user/ata-project/ata-backend/app/services/quiz_analytics_service.py`

**Metrics Provided**:

**Session Analytics**:
- Participation: total, active, completion rate
- Score statistics: mean, median, std dev, distribution
- Accuracy metrics: average correct, overall rate
- Time analytics: total, per-question
- Question breakdown with accuracy per question

**Question Analytics**:
- Difficulty index (% correct) - ideal: 0.3-0.7
- Discrimination index (differentiates high/low) - good: >0.3
- Response time distribution
- Answer choice distribution (for MC/polls)

**Participant Analytics**:
- Overall performance (score, rank, accuracy)
- Performance by question type
- Timing analysis
- Response details (correct/incorrect, time taken)

**Comparative Analytics**:
- Cross-session trends
- Question consistency across runs
- Overall aggregates

---

### How Services Interact with Repositories

```
Router (API Request)
    ↓
Service Layer (Business Logic)
    ↓
DatabaseService (Facade/Coordinator)
    ├→ QuizRepositorySQL (Quiz & Question CRUD)
    ├→ QuizSessionRepositorySQL (Session, Participant, Response CRUD)
    └→ ClassStudentRepositorySQL (User, Class, Student CRUD)
    ↓
SQLAlchemy ORM
    ↓
PostgreSQL Database
```

**Example Flow**: Create and Start Session
```python
# Router calls service
session = quiz_service.create_session_with_room_code(quiz_id, user_id, db)

# Service validates quiz
quiz = db.get_quiz_by_id(quiz_id, user_id)  # DatabaseService.quiz_repo.get_quiz_by_id()

# Service creates session
session = db.create_quiz_session(session_data)  # DatabaseService.quiz_session_repo.create_session()

# Service generates room code
room_code = generate_unique_room_code(db)
# Uses db.check_room_code_exists() → quiz_session_repo.check_room_code_exists()
```

---

## 2. Database Repository Layer

### 2.1 Quiz Repository (quiz_repository_sql.py)
**Location**: `/home/user/ata-project/ata-backend/app/services/database_helpers/quiz_repository_sql.py`

**Security Pattern**: User Ownership Validation
```python
def get_quiz_by_id(self, quiz_id: str, user_id: str) -> Optional[Quiz]:
    """Only returns if user owns the quiz"""
    return self.db.query(Quiz).filter(
        Quiz.id == quiz_id,
        Quiz.user_id == user_id,  # ← Ownership check
        Quiz.deleted_at.is_(None)  # ← Soft delete support
    ).first()
```

**Methods**:
- `create_quiz()` - Requires user_id in data
- `get_quiz_by_id()` - Validates ownership
- `get_all_quizzes()` - Filters by user_id
- `update_quiz()` - Validates ownership before update
- `delete_quiz()` - Soft or hard delete with ownership check
- `restore_quiz()` - Restore soft-deleted quiz
- `update_quiz_status()` - Draft → Published → Archived
- `update_last_room_code()` - Quick rejoin support
- `duplicate_quiz()` - Copy all questions to new quiz
- `add_question()` - Add question to quiz
- `update_question()` - Update with ownership validation
- `delete_question()` - Delete with ownership validation
- `reorder_questions()` - Change question order
- `get_questions_by_quiz_id()` - Ordered by order_index
- `get_question_count()` - Count for validation

**Indexes**:
```python
# Composite index for user's quizzes
Index("idx_quizzes_user_status_not_deleted", user_id, status, 
      postgresql_where=(deleted_at.is_(None)))

# Index for class association
Index("idx_quizzes_class_not_deleted", class_id, 
      postgresql_where=(deleted_at.is_(None)))

# For question retrieval in order
Index("idx_quiz_questions_quiz_order", quiz_id, order_index)
```

---

### 2.2 Quiz Session Repository (quiz_session_repository_sql.py)
**Location**: `/home/user/ata-project/ata-backend/app/services/database_helpers/quiz_session_repository_sql.py`

**Three Types of Database Operations**:

#### A. Session Management
```python
def create_session(session_data: Dict) -> QuizSession
def get_session_by_id(session_id: str, user_id: Optional[str]) -> Optional[QuizSession]
def get_session_by_room_code(room_code: str) -> Optional[QuizSession]  # Public join link
def get_all_sessions(user_id: str, status: Optional[str]) -> List[QuizSession]
def get_active_sessions(user_id: str) -> List[QuizSession]
def update_session(session_id: str, user_id: str, update_data: Dict) -> Optional[QuizSession]
def update_session_status(session_id: str, user_id: str, status: str) -> Optional[QuizSession]
def move_to_next_question(session_id: str, user_id: str) -> Optional[QuizSession]
def check_room_code_exists(room_code: str) -> bool  # For collision detection
def get_timed_out_sessions() -> List[QuizSession]  # For cleanup job
```

#### B. Participant Management (CRITICAL FOR ROSTER INTEGRATION)
```python
def add_participant(participant_data: Dict) -> QuizParticipant
def get_participant_by_id(participant_id: str) -> Optional[QuizParticipant]
def get_participant_by_guest_token(guest_token: str) -> Optional[QuizParticipant]
def get_participants_by_session(session_id: str, active_only: bool) -> List[QuizParticipant]
def get_participant_by_student_in_session(session_id: str, student_id: str) -> Optional[QuizParticipant]
def get_participant_names_in_session(session_id: str) -> List[str]
def update_participant(participant_id: str, update_data: Dict) -> Optional[QuizParticipant]
def update_participant_score(participant_id: str, points_earned: int, is_correct: bool, time_taken_ms: int) -> Optional[QuizParticipant]
def mark_participant_inactive(participant_id: str) -> bool
def get_leaderboard(session_id: str, limit: int) -> List[QuizParticipant]
def get_participant_rank(participant_id: str) -> Tuple[int, int]
def anonymize_old_guests(days: int) -> int
```

#### C. Response Management (Answer Tracking)
```python
def submit_response(response_data: Dict) -> QuizResponse
def get_response_by_id(response_id: str) -> Optional[QuizResponse]
def get_participant_response_for_question(participant_id: str, question_id: str) -> Optional[QuizResponse]
def get_responses_by_participant(participant_id: str) -> List[QuizResponse]
def get_responses_by_session(session_id: str) -> List[QuizResponse]
def get_responses_by_question(question_id: str) -> List[QuizResponse]
def get_question_response_count(session_id: str, question_id: str) -> int
def get_question_correctness_stats(question_id: str) -> Dict
```

**Concurrency Control** - Pessimistic Locking:
```python
def update_participant_score(self, participant_id: str, points_earned: int, is_correct: bool, time_taken_ms: int):
    # CRITICAL FIX #2: Lock prevents race conditions in concurrent submissions
    participant = self.db.query(QuizParticipant).filter(
        QuizParticipant.id == participant_id
    ).with_for_update().first()  # ← Pessimistic lock

    # Safely update while holding lock
    participant.score += points_earned
    if is_correct:
        participant.correct_answers += 1
    participant.total_time_ms += time_taken_ms
    
    self.db.commit()  # Lock released on commit
```

**Indexes for Performance**:
```python
# Leaderboard queries (session + score ranking)
Index("idx_participants_session_score", session_id, score.desc())

# Active participants filtering
Index("idx_participants_session_active", session_id, is_active)

# GDPR cleanup - find old guests
Index("idx_participants_gdpr_cleanup", joined_at, anonymized_at, 
      postgresql_where=(guest_token.isnot(None)))

# Response analytics
Index("idx_responses_leaderboard", session_id, is_correct, points_earned)
Index("idx_responses_question_analytics", question_id, is_correct, time_taken_ms)
```

---

### 2.3 Class/Student Repository (class_student_repository_sql.py)
**Location**: `/home/user/ata-project/ata-backend/app/services/database_helpers/class_student_repository_sql.py`

**Relevant Methods for Quiz Integration**:
```python
def get_students_by_class_id(self, class_id: str, user_id: str) -> List[Student]
    # Defense in depth: validates user owns class, then fetches students

def get_student_by_student_id(self, student_id: str) -> Optional[Student]
    # Global lookup - used for display name in leaderboard
    # No user_id check (public lookup)

def get_student_by_id(self, student_id: str, user_id: str) -> Optional[Student]
    # Secure lookup - validates class ownership

def add_student(record: Dict) -> Student
def update_student(student_id: str, user_id: str, data: Dict) -> Optional[Student]
def delete_student(student_id: str, user_id: str) -> bool
```

---

## 3. Transaction Management & Error Handling

### Transaction Patterns

**Explicit Transaction Management** (Rare):
```python
# Most operations use implicit transactions via SQLAlchemy session
# commit() happens automatically after successful operation
```

**Rollback on Error**:
```python
try:
    participant = self.db.query(QuizParticipant).with_for_update().first()
    # ... modifications ...
    self.db.commit()
except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)
    self.db.rollback()  # ← Explicit rollback
    raise
```

### Error Handling in Service Layer

**Validation Errors** → HTTP 422:
```python
# quiz_service.py
if not quiz:
    raise ValueError("Quiz not found")  # Service raises ValueError
    
# router catches and converts
except ValueError as e:
    raise HTTPException(status_code=422, detail=str(e))
```

**Business Rule Violations**:
```python
# Time limit enforcement
if elapsed_seconds > question.time_limit_seconds:
    raise ValueError("Time limit exceeded for this question")

# Duplicate answer prevention
existing = db.get_participant_response_for_question(participant_id, question_id)
if existing:
    raise ValueError("Question already answered")

# Session state validation
if session.status != SessionStatus.WAITING:
    raise ValueError("Can only start sessions in 'waiting' status")
```

**Recovery Strategies**:
- **Rejoin Allowed**: Students/guests can rejoin if disconnected
- **Reactivation**: Mark inactive participants as active on rejoin
- **Missed Response Creation**: Auto-track skipped questions

---

## 4. Participant Tracking Mechanisms

### Triple Identity Pattern (Innovative Design)

The system supports THREE participant types with single database table:

**Type 1: Pure Guest** (Anonymous)
```
student_id: NULL
guest_name: "Alice"
guest_token: "3f9d5c2e..." (64-char hex)
```

**Type 2: Registered Student** (Has account)
```
student_id: "uuid-12345"  (FK to users.id)
guest_name: NULL
guest_token: NULL
```

**Type 3: Identified Guest** (K-12 Most Common) ✨ NEW HOTSPOT
```
student_id: "123456"  (School ID, NOT FK)
guest_name: "John Smith"
guest_token: "3f9d5c2e..."  (For auth if device lost)
```

**Database Constraint** (CHECK):
```sql
-- Only one of these three patterns allowed
(student_id IS NOT NULL AND guest_name IS NULL AND guest_token IS NULL) OR
(student_id IS NULL AND guest_name IS NOT NULL AND guest_token IS NOT NULL) OR
(student_id IS NOT NULL AND guest_name IS NOT NULL AND guest_token IS NOT NULL)
```

### Participant Join Flow

**Endpoint**: `POST /api/quiz-sessions/join`

**join_session_as_identified_guest()** (Lines 842-941):
```python
# Most common K-12 flow
if join_data.guest_name and join_data.student_id:
    participant, guest_token = quiz_service.join_session_as_identified_guest(
        room_code=join_data.room_code,
        student_name=join_data.guest_name,
        student_id=join_data.student_id,
        db=db
    )
    return {
        "participant_id": participant.id,
        "guest_token": guest_token,
        "display_name": participant.guest_name
    }
```

**Validation Steps**:
1. Validate room code format
2. Find session by room code
3. Check session status (WAITING or ACTIVE)
4. Check participant limit (max 500)
5. Deduplicate student_id in session
6. Sanitize display name
7. Handle duplicate names
8. Generate secure guest token
9. Create participant record

**Display Name Resolution**:
```python
def get_participant_names_in_session(self, session_id: str) -> List[str]:
    for p in participants:
        if p.guest_name:
            names.append(p.guest_name)  # Use guest_name if available
        elif p.student_id:
            student = self.get_student_by_student_id(p.student_id)
            if student and student.name:
                names.append(student.name)  # Lookup full name
```

---

## 5. Leaderboard and Real-time Updates

### Leaderboard Calculation

**Query** (quiz_session_repository_sql.py, lines 473-495):
```python
def get_leaderboard(self, session_id: str, limit: int = 10) -> List[QuizParticipant]:
    return (
        self.db.query(QuizParticipant)
        .filter(QuizParticipant.session_id == session_id)
        .order_by(
            desc(QuizParticipant.score),      # Primary: Higher score first
            QuizParticipant.total_time_ms     # Tiebreaker: Faster time wins
        )
        .limit(limit)
        .all()
    )
```

**Ranking Algorithm**:
```python
def get_participant_rank(self, participant_id: str) -> Tuple[int, int]:
    higher_score = count(score > participant.score)
    same_score_faster = count(score == participant.score AND time < participant.time)
    rank = higher_score + same_score_faster + 1
```

**Real-time Broadcast** (After answer submission):
```python
# auto_advance_question() in quiz_service.py, lines 641-671
leaderboard_entries = []
leaderboard_participants = db.get_leaderboard(session_id, limit=100)
for rank, p in enumerate(leaderboard_participants, start=1):
    leaderboard_entries.append({
        "rank": rank,
        "participant_id": str(p.id),
        "display_name": get_display_name(p),  # Resolves student_id → name
        "score": p.score,
        "correct_answers": p.correct_answers,
        "total_time_ms": p.total_time_ms,
        "is_active": p.is_active
    })

asyncio.run(connection_manager.broadcast_to_room(
    session_id,
    {"type": "leaderboard_update", "leaderboard": leaderboard_entries}
))
```

---

## 6. WHERE TO ADD ROSTER CHECKING LOGIC

### Primary Integration Point: Join Session

**Location**: `quiz_service.join_session_as_identified_guest()` (Lines 842-941)

**Current Flow**:
```
1. Validate room code format ✓
2. Find session by room code ✓
3. Check session status ✓
4. Check participant limit ✓
5. [INSERT ROSTER CHECK HERE] ← NEW
6. Check duplicate student_id in session ✓
7. Sanitize and deduplicate names ✓
8. Generate token ✓
9. Create participant ✓
```

**Proposed Addition**:
```python
def join_session_as_identified_guest(room_code, student_name, student_id, db):
    # ... existing validation (1-4) ...
    
    # NEW: Roster validation
    session = db.get_quiz_session_by_room_code(room_code)
    quiz = db.get_quiz_by_id(session.quiz_id, session.user_id)
    
    # If quiz has class_id, validate student is in that class
    if quiz and quiz.class_id:
        student = db.get_student_by_student_id(student_id)
        if not student:
            raise ValueError(f"Student {student_id} not found in system")
        
        # Check if student is in the quiz's class
        is_in_class = db.is_student_in_class(student_id, quiz.class_id)
        if not is_in_class:
            raise ValueError(f"Student {student_id} is not in {quiz.class_id}")
        
        # Optionally check if student is active
        if not student.is_active:
            raise ValueError(f"Student {student_id} is inactive")
    
    # ... continue with existing join logic (6-9) ...
```

### Secondary Integration Point: Pre-Session Setup

**During Quiz Creation** (Lines 83-131):
- Teacher selects class → Quiz.class_id is set
- System can validate at publish time

**Before Session Start** (Lines 328-365):
- Teacher views participants
- System shows validation status

### Implementation Strategy

**Option A: Strict Roster (Recommended)**
```python
# Only enrolled students can join
if quiz.class_id:
    validate_student_in_class(student_id, quiz.class_id)
    raise ValueError("Student not enrolled")
```

**Option B: Soft Warning**
```python
# Allow join but flag if not in roster
if quiz.class_id:
    is_valid = validate_student_in_class(student_id, quiz.class_id)
    if not is_valid:
        logger.warning(f"Student {student_id} not in class but allowed to join")
```

**Option C: Configurable Per Quiz**
```python
quiz.settings = {
    "enforce_roster": true,  # If true, validate
    "shuffle_questions": false,
    ...
}
```

---

## 7. Database Models Overview

**File**: `/home/user/ata-project/ata-backend/app/db/models/quiz_models.py`

### Model Relationships

```
Quiz (teacher-owned)
├─ questions (1-many)
│  └─ QuizQuestion
│     └─ responses (1-many)
│        └─ QuizResponse
└─ sessions (1-many)
   └─ QuizSession
      ├─ participants (1-many)
      │  └─ QuizParticipant
      │     └─ responses (1-many)
      │        └─ QuizResponse
      └─ responses (1-many)
         └─ QuizResponse
```

### Key Fields

**Quiz**:
- `id` (UUID string)
- `user_id` (FK to User) - Ownership
- `class_id` (FK to Class, nullable) - CLASS ASSOCIATION FOR ROSTER
- `title`, `description`
- `settings` (JSONB) - Flexible config
- `status` (draft/published/archived)
- `deleted_at` (nullable) - Soft delete for GDPR

**QuizSession**:
- `id` (UUID string)
- `quiz_id` (FK to Quiz)
- `user_id` (FK to User) - Host/teacher
- `room_code` (unique, 6 chars) - Join link
- `status` (waiting/active/completed/cancelled)
- `current_question_index` (nullable)
- `config_snapshot` (JSONB) - Frozen quiz config
- `question_started_at` (nullable) - Time limit enforcement

**QuizParticipant** - THE HOTSPOT:
- `id` (UUID string)
- `session_id` (FK)
- `student_id` (string, nullable) - School student ID
- `guest_name` (string, nullable) - Display name
- `guest_token` (string, nullable) - Authentication token
- `score`, `correct_answers`, `total_time_ms`
- `is_active` (boolean) - Connection status
- CHECK constraint enforces triple identity pattern

**QuizResponse**:
- `id` (UUID string)
- `session_id`, `participant_id`, `question_id` (FKs)
- `answer` (JSONB) - Flexible answer format
- `is_correct` (boolean, nullable) - None for polls
- `points_earned`, `time_taken_ms`
- UNIQUE constraint: one answer per participant per question

---

## 8. Service Integration Example: Complete Join Flow

```python
# ROUTER: quiz_session_router.py
@router.post("/join", ...)
def join_session(join_data: ParticipantJoinRequest, db: DatabaseService):
    # Determine join mode based on request data
    if join_data.guest_name and join_data.student_id:
        # MODE 1: Identified Guest (K-12)
        participant, token = quiz_service.join_session_as_identified_guest(
            room_code=join_data.room_code,
            student_name=join_data.guest_name,
            student_id=join_data.student_id,
            db=db
        )
    elif join_data.guest_name:
        # MODE 2: Pure Guest
        participant, token = quiz_service.join_session_as_guest(
            room_code=join_data.room_code,
            guest_name=join_data.guest_name,
            db=db
        )
    elif join_data.student_id:
        # MODE 3: Registered Student
        participant = quiz_service.join_session_as_student(
            room_code=join_data.room_code,
            student_id=join_data.student_id,
            db=db
        )
        token = None
    
    return ParticipantJoinResponse(participant_id=participant.id, guest_token=token)

# SERVICE: quiz_service.py
def join_session_as_identified_guest(room_code, student_name, student_id, db):
    # 1. Validate room code format
    if not is_valid_room_code_format(room_code):
        raise ValueError("Invalid room code format")
    
    # 2. Find session
    session = db.get_quiz_session_by_room_code(room_code)
    if not session:
        raise ValueError("Session not found")
    
    # 3. Check session status
    if session.status not in [SessionStatus.WAITING, SessionStatus.ACTIVE]:
        raise ValueError(f"Cannot join session in '{session.status}' status")
    
    # 4. Check participant limit
    participants = db.get_participants_by_session(session.id, active_only=True)
    if len(participants) >= MAX_PARTICIPANTS:
        raise ValueError("Session is full")
    
    # [NEW] 5. Roster validation
    quiz = db.get_quiz_by_id(session.quiz_id, session.user_id)
    if quiz and quiz.class_id:
        # Validate student in class
        student = db.get_student_by_student_id(student_id)
        if not student or not db.is_student_in_class(student_id, quiz.class_id):
            raise ValueError("Student not enrolled in this class")
    
    # 6. Check for existing participant
    existing = db.get_participant_by_student_in_session(session.id, student_id)
    if existing:
        if not existing.is_active:
            return db.update_participant(existing.id, {"is_active": True}), existing.guest_token
        return existing, existing.guest_token
    
    # 7. Sanitize name, handle duplicates
    sanitized_name = sanitize_participant_name(student_name)
    existing_names = db.get_participant_names_in_session(session.id)
    unique_name = handle_duplicate_name(sanitized_name, existing_names)
    
    # 8. Generate token
    guest_token = generate_guest_token()
    
    # 9. Create participant
    participant = db.add_quiz_participant({
        "session_id": session.id,
        "student_id": student_id,
        "guest_name": unique_name,
        "guest_token": guest_token,
        "score": 0,
        "correct_answers": 0,
        "total_time_ms": 0,
        "is_active": True
    })
    
    return participant, guest_token

# DATABASE SERVICE: database_service.py
def get_quiz_by_id(self, quiz_id: str, user_id: str) -> Optional[Quiz]:
    return self.quiz_repo.get_quiz_by_id(quiz_id, user_id)

# REPOSITORY: quiz_repository_sql.py
def get_quiz_by_id(self, quiz_id: str, user_id: str) -> Optional[Quiz]:
    return self.db.query(Quiz).filter(
        Quiz.id == quiz_id,
        Quiz.user_id == user_id,  # ← Ownership check
        Quiz.deleted_at.is_(None)
    ).first()
```

---

## 9. Key Architectural Patterns

### 1. User Ownership Validation
Every repository method that touches user data requires `user_id`:
```python
def get_quiz_by_id(self, quiz_id: str, user_id: str):
    # Always validate: Quiz.user_id == user_id
```

### 2. Service-Repository Separation
- **Services**: Business logic, validation, orchestration
- **Repositories**: Pure data access, transaction management

### 3. Error Handling Hierarchy
- **Validation Errors** → ValueError (service) → HTTP 422 (router)
- **Business Rule Violations** → ValueError
- **Unexpected Errors** → Log & raise (let router convert to 500)

### 4. Soft Deletes & Audit Trails
```python
quiz.deleted_at = datetime.now()  # Soft delete
db.commit()  # Keep data for analytics
```

### 5. JSONB for Flexibility
- `Quiz.settings` → Question shuffling, time limits, etc.
- `QuizSession.config_snapshot` → Freeze quiz state at session start
- `QuizQuestion.options` → Flexible storage for different question types
- `QuizResponse.answer` → Store various answer formats

### 6. Pessimistic Locking for Concurrency
```python
participant = self.db.query(QuizParticipant) \
    .filter(...) \
    .with_for_update() \  # ← Exclusive lock
    .first()

participant.score += points  # Safe concurrent update
self.db.commit()  # Lock released
```

---

## 10. Summary: Architecture Strengths & Integration Points

### Strengths
✓ **Layered Architecture**: Clear separation of concerns
✓ **Security**: User ownership validation at repository level
✓ **Scalability**: Indexed queries, connection pooling ready
✓ **Flexibility**: JSONB columns for extensibility
✓ **Concurrency**: Pessimistic locking prevents race conditions
✓ **Analytics**: Comprehensive metrics at session/question/participant levels
✓ **GDPR Compliance**: Soft deletes, guest anonymization
✓ **Error Handling**: Clear validation and recovery

### Integration Points for Roster Checking
1. **Primary**: `quiz_service.join_session_as_identified_guest()` - Check student in class
2. **Secondary**: `Quiz.class_id` field already exists for association
3. **Repository**: Add methods: `is_student_in_class()`, `get_class_by_id()`
4. **Service Layer**: Coordinate class/student validation before participant creation

### Data Flow for New Feature
```
Teacher creates quiz
└─ Selects class → Quiz.class_id set
   └─ Teacher starts session
      └─ Student joins (POST /join)
         └─ SERVICE VALIDATION: is_student_in_class(student_id, quiz.class_id)
            └─ Create participant only if valid
               └─ Student answers questions
                  └─ Analytics track by student_id in class
```

