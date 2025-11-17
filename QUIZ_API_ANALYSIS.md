# Quiz Management Backend API - Comprehensive Analysis

## Executive Summary
The backend implements a **secure, user-scoped quiz management system** with JWT authentication, role-based access control, and three-tier architecture (router → service → repository). All endpoints enforce user ownership validation and use UUIDs for primary identifiers with string fallback for compatibility.

---

## Part 1: Quiz Router Endpoints (CRUD Operations)

### File: `/ata-backend/app/routers/quiz_router.py`

#### 1. **GET /api/quizzes** - List All Quizzes
```
Endpoint: GET /api/quizzes
Authentication: Required (JWT Bearer token)
Dependencies: get_current_active_user, DatabaseService

Query Parameters:
  - status: Optional[str] - Filter by status (draft/published/archived)
  - class_id: Optional[str] - Filter by associated class ID

Response Model: List[QuizSummary]
Status Code: 200

Returns:
  [
    {
      "id": "uuid",
      "user_id": "uuid",
      "class_id": "optional_string",
      "title": "Quiz Title",
      "description": "Optional description",
      "settings": {...},
      "status": "draft|published|archived",
      "question_count": 5,
      "created_at": "2024-01-01T12:00:00Z",
      "updated_at": "2024-01-01T12:00:00Z",
      "last_room_code": "AB3K7Q"
    }
  ]

Security: Only returns quizzes owned by current_user.id
Current user enforced at DB layer: db.get_all_quizzes(user_id=current_user.id, ...)
```

#### 2. **POST /api/quizzes** - Create New Quiz
```
Endpoint: POST /api/quizzes
Authentication: Required (JWT Bearer token)
Status Code: 201 CREATED
Response Model: QuizDetail

Request Body (QuizCreate):
{
  "title": "Quiz Title",                           // Required, max 200 chars
  "description": "Optional",                       // Optional, max 5000 chars
  "settings": {"shuffle_questions": true},        // Optional JSONB dict
  "class_id": "optional_class_uuid",               // Optional
  "questions": [                                   // Optional, max 100 questions
    {
      "question_type": "multiple_choice|true_false|short_answer|poll",
      "question_text": "What is 2+2?",
      "options": ["A", "B", "C", "D"],             // For MC/poll
      "correct_answer": ["A"],                     // Can be null for drafts
      "points": 10,                                // 0-100, default 10
      "time_limit_seconds": 30,                    // 5-300 seconds, optional
      "explanation": "Optional explanation",
      "media_url": "https://example.com/image.jpg",
      "order_index": 0
    }
  ]
}

Returns: QuizDetail with all questions

Validation:
  - Quiz title: 1-200 characters
  - Max 100 questions per quiz (quiz_settings.MAX_QUESTIONS_PER_QUIZ)
  - Questions validated via QuizQuestionBase validator
  
Security:
  - user_id set automatically from current_user.id
  - No cross-user quiz access possible
  - Soft validation during creation (strict validation on publish)
```

#### 3. **GET /api/quizzes/{quiz_id}** - Get Quiz Details
```
Endpoint: GET /api/quizzes/{quiz_id}
Authentication: Required
Response Model: QuizDetail

Path Parameters:
  - quiz_id: str - Quiz identifier

Returns:
{
  "id": "uuid",
  "user_id": "uuid",
  "class_id": "optional_uuid",
  "title": "Quiz Title",
  "description": "Description",
  "settings": {...},
  "status": "draft|published|archived",
  "questions": [QuizQuestionAdminResponse, ...],  // Full questions with answers
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z",
  "last_room_code": "AB3K7Q",
  "deleted_at": null
}

Error Responses:
  - 404 NOT_FOUND: If quiz not found or not owned by current_user
  
Security: DB enforces user_id match: db.get_quiz_by_id(quiz_id, current_user.id)
```

#### 4. **PUT /api/quizzes/{quiz_id}** - Update Quiz
```
Endpoint: PUT /api/quizzes/{quiz_id}
Authentication: Required
Status Code: 200
Response Model: QuizDetail

Request Body (QuizUpdate - all fields optional):
{
  "title": "New Title",
  "description": "New description",
  "settings": {"shuffle_questions": true},
  "status": "published|draft|archived",
  "class_id": "class_uuid_or_null"
}

Returns: Updated QuizDetail with questions

Validation:
  - If status → published: Must have at least 1 question
  - class_id can be null (removes class association)
  - Settings stored as JSONB (no schema enforcement)

Error Responses:
  - 404 NOT_FOUND: Quiz not found
  - 422 UNPROCESSABLE_ENTITY: Invalid status change (e.g., publish with no questions)
  
Security: User ownership validated via db.get_quiz_by_id(quiz_id, current_user.id)
```

#### 5. **DELETE /api/quizzes/{quiz_id}** - Delete Quiz
```
Endpoint: DELETE /api/quizzes/{quiz_id}
Authentication: Required
Status Code: 204 NO_CONTENT
Response: No content

Query Parameters:
  - hard_delete: bool = False - Permanently delete if true, soft delete if false

Behavior:
  - Default (soft_delete=True): Quiz marked as deleted (deleted_at timestamp set)
    - Soft-deleted quizzes excluded from GET queries by default
    - Include deleted quizzes: Pass include_deleted=True parameter
  - hard_delete=True: Permanently remove from database
    - Cascading delete of all questions (via database FK constraint)
    - Cascading delete of all sessions
    - Cascading delete of all responses

Use Cases:
  - Soft delete: Preserve quiz for analytics, hide from teacher view
  - Hard delete: Complete removal (GDPR compliance)

Error Responses:
  - 404 NOT_FOUND: Quiz not found or not owned
  
Security: User ownership enforced: db.delete_quiz(quiz_id, current_user.id, ...)
```

#### 6. **POST /api/quizzes/{quiz_id}/publish** - Publish Quiz
```
Endpoint: POST /api/quizzes/{quiz_id}/publish
Authentication: Required
Status Code: 200
Response Model: QuizDetail

Request Body: None

Behavior:
  1. Validate quiz can be published (see validation rules below)
  2. Update status to "published"
  3. Return full quiz with questions

Validation Performed (validate_publish_quiz):
  ✓ Quiz must have at least 1 question
  ✓ Multiple choice questions:
    - Must have 2-6 options
    - Must have exactly 1 correct answer
  ✓ True/False questions:
    - Must have exactly 1 correct answer (boolean)
  ✓ Short answer questions:
    - Must have at least 1 keyword in correct_answer
  ✓ Poll questions:
    - Must have 2-10 options
    - Must NOT have correct answers (correct_answer = [])
    - Points automatically set to 0

Error Responses:
  - 404 NOT_FOUND: Quiz not found
  - 422 UNPROCESSABLE_ENTITY: Validation failed
    - "Must have at least one question"
    - "Question must have exactly 1 correct answer"
    - etc.
  
Security: Validated via db.get_quiz_by_id(quiz_id, current_user.id)
```

#### 7. **POST /api/quizzes/{quiz_id}/duplicate** - Duplicate Quiz
```
Endpoint: POST /api/quizzes/{quiz_id}/duplicate
Authentication: Required
Status Code: 201 CREATED
Response Model: QuizDetail

Query Parameters:
  - new_title: Optional[str] - Custom title for copied quiz
    - Default: "Copy of {original_title}"

Returns:
  - New quiz in DRAFT status
  - All questions copied with same order_index
  - Settings copied
  - class_id NOT copied (new quiz unassociated)
  - New UUID generated

Error Responses:
  - 404 NOT_FOUND: Source quiz not found
  
Security: 
  - Source quiz must be owned by current_user
  - New quiz created with current_user as owner
```

---

### Question Management Endpoints

#### 8. **POST /api/quizzes/{quiz_id}/questions** - Add Question
```
Endpoint: POST /api/quizzes/{quiz_id}/questions
Authentication: Required
Status Code: 201 CREATED
Response Model: QuizQuestionAdminResponse

Path Parameters:
  - quiz_id: str

Request Body (QuizQuestionCreate):
{
  "question_type": "multiple_choice",
  "question_text": "What is the capital of France?",
  "options": ["Paris", "London", "Berlin"],
  "correct_answer": ["Paris"],
  "points": 10,
  "time_limit_seconds": 30,
  "explanation": "Paris is the capital",
  "media_url": "https://...",
  "order_index": 0
}

Constraints:
  - Max 100 questions per quiz
  - Question type validation (see validators in models)
  - Options validation per type
  - Correct answer validation per type

Returns: Created QuizQuestionAdminResponse

Error Responses:
  - 404 NOT_FOUND: Quiz not found
  - 422 UNPROCESSABLE_ENTITY: 
    - "Quiz already has maximum number of questions (100)"
    - Validation errors on question fields
  
Security: Quiz must be owned by current_user
```

#### 9. **PUT /api/quizzes/{quiz_id}/questions/{question_id}** - Update Question
```
Endpoint: PUT /api/quizzes/{quiz_id}/questions/{question_id}
Authentication: Required
Status Code: 200
Response Model: QuizQuestionAdminResponse

Request Body (QuizQuestionUpdate - all fields optional):
{
  "question_text": "Updated text",
  "options": ["A", "B"],
  "correct_answer": ["A"],
  "points": 20,
  "time_limit_seconds": 45,
  "question_type": "true_false",
  "explanation": "New explanation",
  "media_url": "https://...",
  "order_index": 1
}

Returns: Updated QuizQuestionAdminResponse

Error Responses:
  - 404 NOT_FOUND: Quiz or question not found
  
Security: Quiz must be owned by current_user
```

#### 10. **DELETE /api/quizzes/{quiz_id}/questions/{question_id}** - Delete Question
```
Endpoint: DELETE /api/quizzes/{quiz_id}/questions/{question_id}
Authentication: Required
Status Code: 204 NO_CONTENT

Behavior: Permanently removes question from quiz

Cascading Effects:
  - All QuizResponse records for this question deleted
  - Question analytics lost
  - other_questions' order_index unchanged

Error Responses:
  - 404 NOT_FOUND: Question not found
  
Security: Quiz must be owned by current_user
```

#### 11. **PUT /api/quizzes/{quiz_id}/questions/reorder** - Reorder Questions
```
Endpoint: PUT /api/quizzes/{quiz_id}/questions/reorder
Authentication: Required
Status Code: 200
Response Model: SuccessResponse

Request Body:
  List of question IDs in desired order
  ["q1_uuid", "q3_uuid", "q2_uuid"]

Behavior:
  - Updates order_index for each question
  - Must include all questions for quiz (or validation fails)
  - Commutative: reordering is instant for all participants

Returns:
{
  "message": "Questions reordered successfully",
  "data": {
    "quiz_id": "...",
    "question_count": 3
  }
}

Error Responses:
  - 404 NOT_FOUND: Quiz not found
  - 422 UNPROCESSABLE_ENTITY: Invalid question order (missing/extra questions)
  
Security: Quiz must be owned by current_user
```

---

## Part 2: Quiz Session Router Endpoints (Session Management)

### File: `/ata-backend/app/routers/quiz_session_router.py`

### Host Endpoints (Teacher/Quiz Creator)

#### 1. **POST /api/quiz-sessions** - Create Session
```
Endpoint: POST /api/quiz-sessions
Authentication: Required (Host must be current_user)
Status Code: 201 CREATED
Response Model: QuizSessionDetail

Request Body (QuizSessionCreate):
{
  "quiz_id": "published_quiz_uuid",
  "timeout_hours": 2                    // 1-24 hours, default 2
}

Returns:
{
  "id": "session_uuid",
  "quiz_id": "quiz_uuid",
  "quiz_title": "Quiz Title",
  "user_id": "current_user_uuid",
  "room_code": "AB3K7Q",                // Auto-generated unique code
  "status": "waiting",
  "current_question_index": null,
  "config_snapshot": {},                // Auto-advance settings stored here
  "timeout_hours": 2,
  "started_at": null,
  "ended_at": null,
  "auto_ended_at": null,
  "created_at": "2024-01-01T12:00:00Z",
  "participant_count": 0,
  "questions": []
}

Pre-Conditions:
  - Quiz must exist and be owned by current_user
  - Quiz must be PUBLISHED status
  - Quiz must have at least 1 question
  - Max active sessions check (configurable)

Room Code Generation:
  - 6 characters alphanumeric (A-Z except O,I; 2-9)
  - Collision handling: Auto-retry up to 10 times
  - Uniqueness enforced at DB level (UNIQUE constraint)
  - Stored in quiz.last_room_code for quick rejoin

Error Responses:
  - 404 NOT_FOUND: Quiz not found or not owned
  - 422 UNPROCESSABLE_ENTITY:
    - "Quiz is not published"
    - "Quiz has no questions"
    - "Too many active sessions for this quiz"
  - 500 INTERNAL_SERVER_ERROR: Failed to generate unique code
  
Security:
  - user_id set from current_user.id
  - Only creator can manage session
```

#### 2. **GET /api/quiz-sessions** - List User's Sessions
```
Endpoint: GET /api/quiz-sessions
Authentication: Required
Response Model: List[QuizSessionSummary]

Query Parameters:
  - status: Optional[str] - Filter by status (waiting/active/completed/cancelled)

Returns:
[
  {
    "id": "session_uuid",
    "quiz_id": "quiz_uuid",
    "quiz_title": "Quiz Title",
    "room_code": "AB3K7Q",
    "status": "active",
    "participant_count": 5,
    "current_question_index": 2,
    "started_at": "2024-01-01T12:05:00Z",
    "ended_at": null,
    "created_at": "2024-01-01T12:00:00Z"
  }
]

Security: Only returns sessions hosted by current_user
```

#### 3. **GET /api/quiz-sessions/{session_id}** - Get Session Details
```
Endpoint: GET /api/quiz-sessions/{session_id}
Authentication: Required
Response Model: QuizSessionDetail

Returns: Full session with questions and participant count

Security: Only accessible by session host (current_user)
```

#### 4. **POST /api/quiz-sessions/{session_id}/start** - Start Session
```
Endpoint: POST /api/quiz-sessions/{session_id}/start
Authentication: Required
Status Code: 200
Response Model: QuizSessionDetail

Behavior:
  1. Change status from "waiting" → "active"
  2. Set started_at timestamp
  3. Set current_question_index = 0
  4. Broadcast "session_started" to WebSocket room
  5. Broadcast first question to all participants
  6. Schedule auto-advance if enabled (config_snapshot.auto_advance_enabled)

WebSocket Messages Sent:
  - "session_started": Notifies all participants session has started
  - "question_started": Sends first question to participants
    Format: {
      "type": "question_started",
      "question_id": "...",
      "question_text": "...",
      "question_type": "multiple_choice",
      "options": [...],
      "points": 10,
      "order_index": 0,
      "time_limit_seconds": 30
    }

Auto-Advance Configuration:
  - Reads config_snapshot.auto_advance_enabled (boolean)
  - Reads config_snapshot.cooldown_seconds (integer, default 10)
  - If enabled: Schedules APScheduler job to auto-advance
  - Job cancels manually if user clicks "Next Question"
  - Job re-schedules after each question

Error Responses:
  - 404 NOT_FOUND: Session not found
  - 422 UNPROCESSABLE_ENTITY:
    - "Session already started"
    - "Session status is not waiting"

Security: Only session host can start
```

#### 5. **POST /api/quiz-sessions/{session_id}/end** - End Session
```
Endpoint: POST /api/quiz-sessions/{session_id}/end
Authentication: Required
Status Code: 200
Response Model: QuizSessionDetail

Request Body (QuizSessionEnd):
{
  "reason": "completed|cancelled|timeout"  // Optional
}

Behavior:
  1. Create "missed" responses for any non-answering participants on current question
  2. Set status to "completed"
  3. Set ended_at timestamp
  4. Broadcast final leaderboard to all participants
  5. Broadcast "session_ended" message to WebSocket room
  6. Cancel any pending auto-advance jobs

WebSocket Messages:
  - "leaderboard_update": Final leaderboard before end
  - "session_ended": Notifies all participants
    Format: {
      "type": "session_ended",
      "session_id": "...",
      "reason": "completed",
      "final_status": "completed"
    }

Missed Responses:
  - Any participant who didn't answer current question gets "missed" response
  - is_correct = False, points_earned = 0
  - Ensures fair leaderboard calculation

Error Responses:
  - 404 NOT_FOUND: Session not found
  - 422 UNPROCESSABLE_ENTITY: Session already ended

Security: Only session host can end
```

#### 6. **POST /api/quiz-sessions/{session_id}/next-question** - Advance to Next Question
```
Endpoint: POST /api/quiz-sessions/{session_id}/next-question
Authentication: Required
Status Code: 200
Response Model: QuizSessionDetail

Behavior:
  1. Create "missed" responses for participants who didn't answer current question
  2. Increment current_question_index
  3. Cancel any pending auto-advance job (manual takes precedence)
  4. Update question_started_at timestamp
  5. Broadcast new question to all participants
  6. Broadcast updated leaderboard
  7. Re-schedule auto-advance if enabled

WebSocket Messages:
  - "question_started": New question details
  - "leaderboard_update": Updated scores after question completion

Auto-Advance Handling:
  - Cancels existing job via quiz_service.cancel_auto_advance()
  - Reschedules with new question's time_limit
  - Falls back gracefully if scheduling fails

Error Responses:
  - 404 NOT_FOUND: Session not found
  - 422 UNPROCESSABLE_ENTITY:
    - "No more questions remaining"
    - "Session status is not active"

Security: Only session host can advance
```

#### 7. **POST /api/quiz-sessions/{session_id}/toggle-auto-advance** - Configure Auto-Advance
```
Endpoint: POST /api/quiz-sessions/{session_id}/toggle-auto-advance
Authentication: Required
Status Code: 200

Query Parameters:
  - enabled: bool - Enable/disable auto-advance
  - cooldown_seconds: int = 10 - Delay between auto-advances

Behavior:
  1. Validate session status is "waiting" (not started yet)
  2. Update config_snapshot with auto_advance_enabled and cooldown_seconds
  3. Broadcast setting change to connected clients

Returns:
{
  "success": true,
  "auto_advance_enabled": true,
  "cooldown_seconds": 10
}

Pre-Condition:
  - Can ONLY be configured before quiz starts (status != "waiting")
  - Once quiz starts, auto-advance is locked in

WebSocket Broadcast:
  Format: {
    "type": "auto_advance_updated",
    "enabled": true,
    "cooldown_seconds": 10
  }

Error Responses:
  - 404 NOT_FOUND: Session not found
  - 422 UNPROCESSABLE_ENTITY:
    - "Auto-advance settings can only be changed before the quiz starts"

Security: Only session host can configure
```

#### 8. **GET /api/quiz-sessions/{session_id}/participants** - Get Participants
```
Endpoint: GET /api/quiz-sessions/{session_id}/participants
Authentication: Required
Response Model: List[ParticipantSummary]

Query Parameters:
  - active_only: bool = False - Only active participants

Returns:
[
  {
    "id": "participant_uuid",
    "display_name": "John" | "John (2)" | "Student 12345",
    "is_guest": true | false,
    "score": 30,
    "correct_answers": 3,
    "total_time_ms": 45000,
    "is_active": true,
    "joined_at": "2024-01-01T12:05:30Z"
  }
]

Display Name Logic:
  1. If guest_name set → use guest_name (guest or identified guest)
  2. Else if student_id set → lookup student by ID, use student.name
  3. Fallback → "Unknown"

Participant Types:
  - Pure guest: guest_name set, student_id NULL
  - Identified guest: Both guest_name AND student_id set
  - Registered student: student_id set, guest_name NULL

Error Responses:
  - 404 NOT_FOUND: Session not found

Security: Only session host can view participants
```

#### 9. **GET /api/quiz-sessions/{session_id}/leaderboard** - Get Leaderboard
```
Endpoint: GET /api/quiz-sessions/{session_id}/leaderboard
Authentication: Required
Response Model: LeaderboardResponse

Query Parameters:
  - limit: int = 10 - Number of top participants to return

Returns:
{
  "session_id": "session_uuid",
  "entries": [
    {
      "rank": 1,
      "participant_id": "participant_uuid",
      "display_name": "John",
      "score": 100,
      "correct_answers": 10,
      "total_time_ms": 180000,
      "is_active": true
    }
  ],
  "total_participants": 25,
  "updated_at": "2024-01-01T12:15:00Z"
}

Ranking:
  - Sorted by score (descending)
  - Tie-breaker: total_time_ms (ascending - faster is better)

Error Responses:
  - 404 NOT_FOUND: Session not found

Security: Only session host can view
```

---

### Participant Endpoints (Public/Guest)

#### 10. **POST /api/quiz-sessions/join** - Join Session
```
Endpoint: POST /api/quiz-sessions/join
Authentication: NOT REQUIRED
Status Code: 200
Response Model: ParticipantJoinResponse

Request Body (ParticipantJoinRequest):
{
  "room_code": "AB3K7Q",                // Required
  "guest_name": "John",                 // Optional
  "student_id": "12345"                 // Optional
}

Join Modes (one of three patterns required):
  1. IDENTIFIED GUEST (MOST COMMON):
     - guest_name + student_id both provided
     - Use case: K-12 students without accounts
     - student_id is arbitrary string (not FK to users table)
     - Teacher can track by student_id in roster
     
  2. PURE GUEST:
     - Only guest_name provided
     - Use case: Anonymous participation
     - student_id remains NULL
     
  3. REGISTERED STUDENT:
     - Only student_id provided
     - Use case: Student with existing account
     - student_id must reference existing student

Returns:
{
  "session": {
    "id": "session_uuid",
    "room_code": "AB3K7Q",
    "quiz_title": "Quiz Title",
    "status": "waiting|active",
    "current_question_index": null | 2
  },
  "participant": {
    "id": "participant_uuid",
    "display_name": "John",
    "guest_name": "John",
    "student_id": "12345",
    "is_guest": true
  },
  "guest_token": "64_hex_char_token"    // Null for registered students
}

Guest Token Generation:
  - 32 bytes (256 bits) of cryptographically secure randomness
  - Hex-encoded (64 characters)
  - Stored in quiz_participants.guest_token
  - Used for all subsequent guest submissions (header: X-Guest-Token)

Duplicate Handling:
  - Same student_id can't join same session twice
  - Error: "Student already joined this session"
  - Identified guests checked by (session_id, student_id) pair

Name Deduplication:
  - Pure guests with duplicate names get suffix
  - "John" → "John (2)" → "John (3)"
  - Applies to guest_name only, not student_id

Error Responses:
  - 400 BAD_REQUEST:
    - "Invalid room code"
    - "Session not found"
    - "Session is full"
    - "Student already joined this session"
    - "Must provide either guest_name or student_id"

Security:
  - NO authentication required
  - Room code acts as access control
  - Token generated randomly (256-bit entropy)
  - Constant-time token validation (prevents timing attacks)
```

#### 11. **GET /api/quiz-sessions/{session_id}/current-question** - Get Current Question
```
Endpoint: GET /api/quiz-sessions/{session_id}/current-question
Authentication: NOT REQUIRED (public)
Response Model: QuizQuestionParticipantResponse

Returns:
{
  "id": "question_uuid",
  "question_type": "multiple_choice",
  "question_text": "What is 2+2?",
  "options": ["3", "4", "5"],
  "points": 10,
  "time_limit_seconds": 30,
  "media_url": "https://...",
  "order_index": 0
}

IMPORTANT: Correct answer NOT included (hidden from participants)

Error Responses:
  - 404 NOT_FOUND:
    - "Session not found"
    - "Session has not started yet"
    - "No current question"

Security: Public endpoint (no auth), room code already filters session
```

#### 12. **POST /api/quiz-sessions/{session_id}/submit-answer** - Submit Answer
```
Endpoint: POST /api/quiz-sessions/{session_id}/submit-answer
Authentication: REQUIRED (Guest token header)
Status Code: 200
Response Model: AnswerResult

Headers Required:
  X-Guest-Token: "64_hex_char_token"   // From join response

Request Body (AnswerSubmission):
{
  "question_id": "question_uuid",
  "answer": ["A"],                      // List format (always)
  "time_taken_ms": 5000                 // Client-reported time
}

Answer Formats by Question Type:
  - multiple_choice: ["A"] or ["option_text"]
  - true_false: [true] or [false]
  - short_answer: ["keyword1", "keyword2"]
  - poll: ["option_name"]

Grading Process:
  1. Validate answer format
  2. Compare against correct_answer from question
  3. Determine is_correct
  4. Award points if correct
  5. Update participant score, correct_answers, total_time
  6. Store QuizResponse record
  7. Broadcast participant_answered to teacher

Returns (AnswerResult):
{
  "response_id": "response_uuid",
  "question_id": "question_uuid",
  "is_correct": true,                   // Null for polls
  "points_earned": 10,
  "correct_answer": ["A"],              // Shown after submission
  "explanation": "That's correct!",
  "time_taken_ms": 5000
}

Grading Rules:
  - Multiple Choice: Exact match OR match by index
  - True/False: Boolean comparison
  - Short Answer: Case-insensitive substring/keyword matching
  - Poll: No correctness (is_correct = null), points = 0

Duplicate Prevention:
  - UNIQUE constraint: (session_id, participant_id, question_id)
  - Re-submission not allowed
  - Error: 400 if participant already answered

WebSocket Broadcasts (to teacher):
  - "participant_answered": Notifies teacher of new submission
    Format: {
      "type": "participant_answered",
      "participant_id": "...",
      "question_id": "...",
      "is_correct": true,
      "timestamp": "2024-01-01T12:10:30Z"
    }
    
  - "stats_update": Real-time answer completion tracking
    Format: {
      "type": "stats_update",
      "total_participants": 25,
      "answers_received": 18,
      "completion_percentage": 72.0
    }

Error Responses:
  - 401 UNAUTHORIZED:
    - "Guest token required"
    - "Invalid guest token"
  - 400 BAD_REQUEST:
    - "Token does not match session"
    - "Question not found"
    - "Participant already answered this question"

Security:
  - Token validation: constant-time comparison
  - Participant extracted from token (not from request)
  - Cannot answer for other participants
```

#### 13. **GET /api/quiz-sessions/{session_id}/my-stats** - Get Participant Stats
```
Endpoint: GET /api/quiz-sessions/{session_id}/my-stats
Authentication: REQUIRED (Guest token header)
Response Model: ParticipantDetail

Headers Required:
  X-Guest-Token: "64_hex_char_token"

Returns:
{
  "id": "participant_uuid",
  "session_id": "session_uuid",
  "student_id": "12345" | null,
  "display_name": "John",
  "is_guest": true,
  "score": 30,
  "correct_answers": 3,
  "total_time_ms": 45000,
  "is_active": true,
  "joined_at": "2024-01-01T12:05:30Z",
  "last_seen_at": "2024-01-01T12:15:45Z"
}

Error Responses:
  - 401 UNAUTHORIZED:
    - "Guest token required"
    - "Invalid guest token"
  - 400 BAD_REQUEST: "Token does not match session"

Security: Token must belong to current session
```

---

### Analytics Endpoints

#### 14. **GET /api/quiz-sessions/{session_id}/analytics** - Session Analytics
```
Endpoint: GET /api/quiz-sessions/{session_id}/analytics
Authentication: Required (Host only)
Response Model: SessionAnalytics

Returns comprehensive statistics:
{
  "session_id": "...",
  "quiz_title": "...",
  "room_code": "AB3K7Q",
  "status": "completed",
  "total_participants": 25,
  "active_participants": 24,
  "total_questions": 10,
  "questions_completed": 10,
  "average_score": 72.5,
  "median_score": 75,
  "highest_score": 100,
  "lowest_score": 20,
  "average_accuracy_rate": 0.78,
  "started_at": "2024-01-01T12:00:00Z",
  "ended_at": "2024-01-01T12:30:00Z",
  "duration_minutes": 30,
  "question_analytics": [
    {
      "question_id": "...",
      "question_text": "...",
      "question_type": "multiple_choice",
      "total_responses": 25,
      "correct_responses": 20,
      "accuracy_rate": 0.8,
      "average_time_ms": 8000,
      "options_distribution": {"A": 20, "B": 3, "C": 1, "D": 1}
    }
  ]
}

Security: Only session host can view
```

#### 15. **GET /api/quiz-sessions/{session_id}/participant-analytics** - All Participants Analytics
```
Endpoint: GET /api/quiz-sessions/{session_id}/participant-analytics
Authentication: Required (Host only)
Response Model: List[ParticipantAnalytics]

Returns list of all participant performance data sorted by rank

Security: Only session host can view
```

#### 16. **GET /api/quiz-sessions/{session_id}/participant-analytics/{participant_id}** - Individual Participant
```
Endpoint: GET /api/quiz-sessions/{session_id}/participant-analytics/{participant_id}
Authentication: Required (Host only)
Response Model: ParticipantAnalytics

Includes full response history for participant

Security: Only session host can view
```

#### 17. **GET /api/quiz-sessions/{session_id}/export/csv** - Export Session to CSV
```
Endpoint: GET /api/quiz-sessions/{session_id}/export/csv
Authentication: Required
Response: application/csv file download

CSV Columns:
  - Rank, Name, Score, Correct, Total, Accuracy%, Time, Avg Time/Q
  - Q1, Q2, Q3... (per question: ✓ for correct, ✗ for wrong, - for poll)

Returns: Binary file attachment
  Content-Disposition: attachment; filename=quiz_session_{session_id}_analytics.csv

Security: Only session host can export
```

---

## Part 3: Authentication & Authorization

### Authentication Mechanism

**File**: `/ata-backend/app/core/deps.py`

#### JWT Bearer Token Flow
```
1. Client requests /api/auth/token with credentials
2. Server validates credentials and returns JWT token
3. Client includes token in Authorization header: "Bearer {token}"
4. Server decodes token using security.decode_token()
5. Server fetches user from database
6. If user is active, request proceeds with current_user object

JWT Token Contents:
  - Payload: {"sub": user_id}  (subject = user ID)
  - Signature: HMAC-SHA256
  - Encoding: HS256 (symmetric)

Token Validation:
  - Signature verified
  - Expiration checked (if exp claim present)
  - User existence verified in database
  - User.is_active checked
```

#### Key Dependency Functions
```python
@router.get("/protected-endpoint")
def some_endpoint(
    current_user: UserModel = Depends(get_current_active_user)
):
    # current_user is guaranteed to be:
    # 1. Authenticated (valid JWT)
    # 2. Active (is_active = True)
    # 3. Database record fetched and verified
    pass
```

### Authorization Pattern: User-Scoped Data Access

**ALL quiz operations enforce ownership via user_id**:

```python
# Router level (first checkpoint)
@router.get("/{quiz_id}")
def get_quiz(
    quiz_id: str,
    current_user: UserModel = Depends(get_current_active_user)
):
    # current_user.id provides user context

# Service level (second checkpoint)
quiz = quiz_service.get_quiz_with_validation(
    quiz_id=quiz_id,
    user_id=current_user.id,  # ← Explicit user_id parameter
    db=db
)

# Repository level (third checkpoint - actual SQL enforcement)
def get_quiz_by_id(self, quiz_id: str, user_id: str) -> Optional[Quiz]:
    return (
        self.db.query(Quiz)
        .filter(
            Quiz.id == quiz_id,
            Quiz.user_id == user_id,  # ← SQL WHERE clause enforces ownership
            Quiz.deleted_at.is_(None)
        )
        .first()
    )
```

**Three-Layer Defense**:
1. **Router**: JWT validation, get current_user
2. **Service**: Explicit user_id parameter in function signature
3. **Repository (SQL)**: WHERE clause filters by user_id in database query

This prevents:
- Cross-user data access (SQL enforces)
- Unauthorized modifications (every update validates user_id)
- Token hijacking (token only grants access to own resources)

---

## Part 4: Request/Response Models (Pydantic Schemas)

**File**: `/ata-backend/app/models/quiz_model.py`

### Quiz Models

```python
# Creation
QuizCreate(BaseSchema):
  - title: str (1-200 chars, required)
  - description: Optional[str] (max 5000 chars)
  - settings: Dict (flexible JSONB settings)
  - class_id: Optional[str]
  - questions: List[QuizQuestionCreate] (max 100)

# Updates
QuizUpdate(BaseSchema):
  - title: Optional[str]
  - description: Optional[str]
  - settings: Optional[Dict]
  - status: Optional[QuizStatus]
  - class_id: Optional[str]

# Responses
QuizSummary(QuizBase):
  - id: str
  - user_id: UUID
  - status: QuizStatus
  - question_count: int
  - created_at: datetime
  - updated_at: datetime
  - last_room_code: Optional[str]

QuizDetail(QuizBase):
  - id: str
  - user_id: UUID
  - status: QuizStatus
  - questions: List[QuizQuestionAdminResponse]  # ← Includes correct answers
  - created_at: datetime
  - updated_at: datetime
  - deleted_at: Optional[datetime]
```

### Question Models

```python
QuizQuestionCreate(QuizQuestionBase):
  - question_type: QuestionType (enum)
  - question_text: str (1-2000 chars)
  - options: List[str] (max 6 for MC, 10 for poll)
  - correct_answer: List[Union[str, bool, int]]
  - points: int (0-100, default 10)
  - time_limit_seconds: Optional[int] (5-300)
  - explanation: Optional[str] (max 1000)
  - media_url: Optional[str]
  - order_index: int

# Admin view (with correct answers)
QuizQuestionAdminResponse(QuizQuestionResponse):
  - id: str
  - quiz_id: str
  - created_at: datetime
  # Includes correct_answer

# Participant view (no correct answers)
QuizQuestionParticipantResponse(BaseSchema):
  - id: str
  - question_type: QuestionType
  - question_text: str
  - options: List[str]
  - points: int
  - time_limit_seconds: Optional[int]
  - media_url: Optional[str]
  - order_index: int
  # NO correct_answer field
```

### Session Models

```python
QuizSessionCreate(BaseSchema):
  - quiz_id: str (required)
  - timeout_hours: int (1-24, default 2)

QuizSessionSummary(BaseSchema):
  - id: str
  - quiz_id: str
  - quiz_title: str
  - room_code: str
  - status: SessionStatus
  - participant_count: int
  - current_question_index: Optional[int]
  - started_at: Optional[datetime]
  - ended_at: Optional[datetime]
  - created_at: datetime

QuizSessionDetail(BaseSchema):
  - id: str
  - quiz_id: str
  - user_id: UUID
  - room_code: str
  - status: SessionStatus
  - current_question_index: Optional[int]
  - config_snapshot: Dict[str, Any]  # ← Auto-advance settings stored here
  - timeout_hours: int
  - started_at: Optional[datetime]
  - ended_at: Optional[datetime]
  - created_at: datetime
  - participant_count: int
  - questions: List[QuizQuestionAdminResponse]
```

### Participant Models

```python
ParticipantJoinRequest(BaseSchema):
  - room_code: str (6-10 chars, required)
  - student_id: Optional[str]  # For tracking in roster
  - guest_name: Optional[str]  # For anonymous participation

ParticipantJoinResponse(BaseSchema):
  - session: SessionInfo (nested)
  - participant: ParticipantInfo (nested)
  - guest_token: Optional[str]  # Only for guests

ParticipantSummary(BaseSchema):
  - id: str
  - display_name: str
  - is_guest: bool
  - score: int
  - correct_answers: int
  - total_time_ms: int
  - is_active: bool
  - joined_at: datetime

ParticipantDetail(ParticipantSummary):
  - session_id: str
  - student_id: Optional[str]
  - last_seen_at: datetime
```

### Answer Models

```python
AnswerSubmission(BaseSchema):
  - question_id: str (required)
  - answer: Union[List[str], List[bool], List[int]] (required)
  - time_taken_ms: int (0-600000, required)

AnswerResult(BaseSchema):
  - response_id: str
  - question_id: str
  - is_correct: Optional[bool]  # Null for polls
  - points_earned: int
  - correct_answer: Optional[List[Union[str, bool, int]]]
  - explanation: Optional[str]
  - time_taken_ms: int
```

### Enums

```python
QuestionType (str Enum):
  - MULTIPLE_CHOICE = "multiple_choice"
  - TRUE_FALSE = "true_false"
  - SHORT_ANSWER = "short_answer"
  - POLL = "poll"

QuizStatus (str Enum):
  - DRAFT = "draft"
  - PUBLISHED = "published"
  - COMPLETED = "completed"
  - ARCHIVED = "archived"

SessionStatus (str Enum):
  - WAITING = "waiting"
  - ACTIVE = "active"
  - COMPLETED = "completed"
  - CANCELLED = "cancelled"
```

---

## Part 5: Security - How user_id is Enforced

### 1. Database Layer Enforcement

**File**: `/ata-backend/app/db/models/quiz_models.py`

Every Quiz record has a mandatory `user_id` field:
```python
class Quiz(Base):
    # Foreign key to users table - every quiz has an owner
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), 
                    nullable=False, index=True)
    
    # Index for quick lookups: user's quizzes by status
    Index("idx_quizzes_user_status_not_deleted", user_id, status)
```

Every access query includes `user_id` filter:
```python
# File: quiz_repository_sql.py
def get_quiz_by_id(self, quiz_id: str, user_id: str) -> Optional[Quiz]:
    return (
        self.db.query(Quiz)
        .filter(
            Quiz.id == quiz_id,
            Quiz.user_id == user_id,  # ← Always included
            Quiz.deleted_at.is_(None)
        )
        .first()
    )
```

**Guarantees**:
- Cannot access quiz without knowing correct user_id
- Query returns None if user_id doesn't match
- Database enforces at constraint level

### 2. Service Layer Enforcement

Every service method requires explicit `user_id` parameter:
```python
# quiz_service.py
def create_quiz_with_questions(
    quiz_data: QuizCreate,
    user_id: str,          # ← Always required
    db: DatabaseService
) -> Quiz:
    quiz_dict = {
        "user_id": user_id,  # ← Passed to repository
        "title": quiz_data.title,
        ...
    }
    return db.create_quiz(quiz_dict)

def get_all_quizzes_with_counts(
    user_id: str,          # ← Always required
    db: DatabaseService,
    status: Optional[str] = None,
    class_id: Optional[str] = None
) -> List[Dict]:
    quizzes = db.get_all_quizzes(user_id, status, class_id)
    # ↑ user_id passed to repository
```

**Guarantees**:
- Service layer cannot be called without user_id
- user_id parameter is visible in function signature (not hidden)
- Easy to audit for security compliance

### 3. Router Layer Enforcement

All protected endpoints use dependency injection:
```python
@router.post("", response_model=quiz_model.QuizDetail)
def create_quiz(
    quiz_data: quiz_model.QuizCreate,
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)  # ← JWT validated
):
    """
    current_user is guaranteed to be:
    1. Authenticated (valid JWT signature)
    2. Active (is_active = True)
    3. Exists in database
    """
    quiz = quiz_service.create_quiz_with_questions(
        quiz_data=quiz_data,
        user_id=current_user.id,  # ← Extracted from JWT
        db=db
    )
    return quiz
```

**Guarantees**:
- `get_current_active_user` dependency validates JWT
- Returns actual User object from database
- Cannot forge user_id in request parameters
- user_id extracted from JWT payload only

### 4. Guest Token Security (for Participants)

Guests are authenticated via separate mechanism:
```python
# quiz_session_router.py
@router.post("/{session_id}/submit-answer")
async def submit_answer(
    session_id: str,
    answer_data: quiz_model.AnswerSubmission,
    guest_token: Optional[str] = Header(None, alias="X-Guest-Token"),
    db: DatabaseService = Depends(get_db_service)
):
    # Find participant by guest token
    participant = db.get_participant_by_guest_token(guest_token)
    if not participant:
        raise HTTPException(status_code=401, detail="Invalid guest token")
    
    # Extract participant_id from token (not from request)
    # Cannot answer on behalf of other participants
    result = quiz_service.submit_answer_with_grading(
        participant_id=participant.id,  # ← From token, not request
        question_id=answer_data.question_id,
        ...
    )
```

**Security Features**:
- Guest tokens are 256-bit cryptographically secure random values
- Tokens not predictable (can't brute force)
- Constant-time comparison prevents timing attacks
- Token extracted from header, not request body
- Cannot answer on behalf of other participants

---

## Part 6: Database Models & Schema

**File**: `/ata-backend/app/db/models/quiz_models.py`

### Quiz Table Schema
```sql
CREATE TABLE quizzes (
  id VARCHAR PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  class_id VARCHAR REFERENCES classes(id) ON DELETE SET NULL,
  
  -- Content
  title VARCHAR(200) NOT NULL,
  description TEXT,
  settings JSONB DEFAULT '{}',
  
  -- Status
  status VARCHAR(20) DEFAULT 'draft',  -- draft|published|archived
  deleted_at TIMESTAMP,  -- NULL = not deleted (soft delete)
  
  -- Session tracking
  last_room_code VARCHAR(10),
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now(),
  
  -- Indexes
  INDEX idx_quizzes_user_status_not_deleted (user_id, status)
    WHERE deleted_at IS NULL,
  INDEX idx_quizzes_class_not_deleted (class_id)
    WHERE deleted_at IS NULL
);
```

### QuizQuestion Table Schema
```sql
CREATE TABLE quiz_questions (
  id VARCHAR PRIMARY KEY,
  quiz_id VARCHAR NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
  
  -- Question content
  question_type VARCHAR(20) NOT NULL,  -- multiple_choice|true_false|short_answer|poll
  question_text TEXT NOT NULL,
  options JSONB DEFAULT '[]',  -- ["A", "B", "C"]
  correct_answer JSONB DEFAULT '[]',  -- Answer(s) to compare against
  
  -- Scoring & timing
  points INT DEFAULT 10,  -- 0-100
  time_limit_seconds INT,  -- 5-300
  
  -- Display
  order_index INT DEFAULT 0,  -- 0-indexed position in quiz
  explanation TEXT,
  media_url VARCHAR,
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT now(),
  
  -- Indexes
  INDEX idx_quiz_questions_quiz_order (quiz_id, order_index)
);
```

### QuizSession Table Schema
```sql
CREATE TABLE quiz_sessions (
  id VARCHAR PRIMARY KEY,
  quiz_id VARCHAR NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  
  -- Session identity
  room_code VARCHAR(10) UNIQUE NOT NULL,  -- "AB3K7Q"
  status VARCHAR(20) DEFAULT 'waiting',  -- waiting|active|completed|cancelled
  
  -- Current state
  current_question_index INT,  -- 0-indexed, NULL = not started
  question_started_at TIMESTAMP,  -- When current question started (for time limit)
  
  -- Configuration snapshot (immutable once session starts)
  config_snapshot JSONB DEFAULT '{}',  -- {"auto_advance_enabled": true, "cooldown_seconds": 10}
  
  -- Timing
  timeout_hours INT DEFAULT 2,  -- 1-24
  started_at TIMESTAMP,
  ended_at TIMESTAMP,
  auto_ended_at TIMESTAMP,  -- If timed out
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT now(),
  
  -- Indexes
  INDEX idx_quiz_sessions_user_status (user_id, status),
  INDEX idx_quiz_sessions_status_created (status, created_at)
);
```

### QuizParticipant Table Schema
```sql
CREATE TABLE quiz_participants (
  id VARCHAR PRIMARY KEY,
  session_id VARCHAR NOT NULL REFERENCES quiz_sessions(id) ON DELETE CASCADE,
  
  -- Triple identity pattern
  student_id VARCHAR,  -- Can be account student_id OR arbitrary school ID
  guest_name VARCHAR(50),  -- For guests
  guest_token VARCHAR(64) UNIQUE,  -- For secure guest auth (32 bytes hex)
  
  -- Scoring
  score INT DEFAULT 0,
  correct_answers INT DEFAULT 0,
  total_time_ms INT DEFAULT 0,
  
  -- Status
  is_active BOOLEAN DEFAULT true,  -- Connected / disconnected
  
  -- GDPR
  anonymized_at TIMESTAMP,  -- For guest data retention policy
  
  -- Timestamps
  joined_at TIMESTAMP DEFAULT now(),
  last_seen_at TIMESTAMP DEFAULT now(),
  
  -- Constraints
  CHECK (
    (student_id IS NOT NULL AND guest_name IS NULL AND guest_token IS NULL) OR
    (student_id IS NULL AND guest_name IS NOT NULL AND guest_token IS NOT NULL) OR
    (student_id IS NOT NULL AND guest_name IS NOT NULL AND guest_token IS NOT NULL)
  ),
  
  -- Indexes
  INDEX idx_participants_session_score (session_id, score DESC),
  INDEX idx_participants_session_active (session_id, is_active),
  INDEX idx_participants_gdpr_cleanup (joined_at, anonymized_at)
    WHERE guest_token IS NOT NULL
);
```

### QuizResponse Table Schema
```sql
CREATE TABLE quiz_responses (
  id VARCHAR PRIMARY KEY,
  session_id VARCHAR NOT NULL REFERENCES quiz_sessions(id) ON DELETE CASCADE,
  participant_id VARCHAR NOT NULL REFERENCES quiz_participants(id) ON DELETE CASCADE,
  question_id VARCHAR NOT NULL REFERENCES quiz_questions(id) ON DELETE CASCADE,
  
  -- Answer data
  answer JSONB NOT NULL,  -- ["A"] or [true] or ["keyword"]
  
  -- Grading
  is_correct BOOLEAN,  -- NULL for polls
  points_earned INT DEFAULT 0,
  
  -- Timing
  time_taken_ms INT NOT NULL,  -- Server-calculated
  
  -- Timestamps
  answered_at TIMESTAMP DEFAULT now(),
  
  -- Constraints
  UNIQUE (session_id, participant_id, question_id),  -- One answer per participant per question
  
  -- Indexes
  INDEX idx_responses_leaderboard (session_id, is_correct, points_earned),
  INDEX idx_responses_question_analytics (question_id, is_correct, time_taken_ms)
);
```

---

## Part 7: Current Class_ID Handling

### Quiz Creation with class_id

```python
# Router level (quiz_router.py)
def create_quiz(
    quiz_data: quiz_model.QuizCreate,  # Includes optional class_id
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    # class_id is passed as-is from request
    quiz = quiz_service.create_quiz_with_questions(
        quiz_data=quiz_data,  # Contains class_id
        user_id=current_user.id,
        db=db
    )

# Service level (quiz_service.py)
def create_quiz_with_questions(quiz_data: QuizCreate, user_id: str, db: DatabaseService):
    quiz_dict = {
        "user_id": user_id,
        "title": quiz_data.title,
        "description": quiz_data.description,
        "settings": quiz_data.settings,
        "status": "draft",
        "class_id": quiz_data.class_id  # ← Stored as-is
    }
    quiz = db.create_quiz(quiz_dict)
```

### Filtering Quizzes by class_id

```python
# Router level (quiz_router.py)
@router.get("", response_model=List[quiz_model.QuizSummary])
def get_all_quizzes(
    status_filter: Optional[str] = Query(None),
    class_id: Optional[str] = Query(None),  # ← Optional filter parameter
    db: DatabaseService = Depends(get_db_service),
    current_user: UserModel = Depends(get_current_active_user)
):
    quizzes = quiz_service.get_all_quizzes_with_counts(
        user_id=current_user.id,
        db=db,
        status=status_filter,
        class_id=class_id  # ← Passed to service
    )
    return quizzes

# Service level (quiz_service.py)
def get_all_quizzes_with_counts(
    user_id: str,
    db: DatabaseService,
    status: Optional[str] = None,
    class_id: Optional[str] = None  # ← Optional filter
):
    quizzes = db.get_all_quizzes(user_id, status, class_id)  # ← Passed to repository

# Repository level (quiz_repository_sql.py)
def get_all_quizzes(
    self,
    user_id: str,
    status: Optional[str] = None,
    class_id: Optional[str] = None,
    include_deleted: bool = False
) -> List[Quiz]:
    query = self.db.query(Quiz).filter(Quiz.user_id == user_id)
    
    if status:
        query = query.filter(Quiz.status == status)
    
    if class_id:  # ← If class_id provided, filter by it
        query = query.filter(Quiz.class_id == class_id)
    
    if not include_deleted:
        query = query.filter(Quiz.deleted_at.is_(None))
    
    return query.order_by(Quiz.updated_at.desc()).all()
```

### Current Limitations of class_id

1. **No validation**: class_id is stored as arbitrary string
   - No FK to classes table in quiz_models.py
   - No validation that user owns the class
   - No validation that class_id actually exists

2. **No roster enforcement**: 
   - Quiz doesn't automatically restrict to class participants
   - Sessions not filtered by class
   - No tracking of which students in class took the quiz

3. **No inclusion in session or participation**:
   - QuizSession doesn't track which class it's for
   - QuizParticipant doesn't track class affiliation
   - Roster tracking would need explicit implementation

---

## Part 8: Where to Add New Endpoints for Roster Tracking

### Recommended New Endpoints

#### 1. **POST /api/quizzes/{quiz_id}/assign-class**
```
Purpose: Associate quiz with a specific class
Path: /api/quizzes/{quiz_id}/assign-class
Method: POST
Auth: Required (quiz owner)
Body: {"class_id": "class_uuid"}

Behavior:
  - Validate quiz owned by current_user
  - Validate class owned by current_user
  - Update quiz.class_id = class_id
  - Mark as "assigned to class"

Response: Updated QuizDetail

Validation:
  - db.get_quiz_by_id(quiz_id, user_id)
  - db.get_class_by_id(class_id, user_id)
```

#### 2. **POST /api/quiz-sessions/{session_id}/sync-class-roster**
```
Purpose: Pre-populate session with students from assigned class
Path: /api/quiz-sessions/{session_id}/sync-class-roster
Method: POST
Auth: Required (session host)
Status: 201 CREATED

Behavior:
  - Get session's quiz
  - Get quiz's class_id
  - Get students in that class
  - For each student, create QuizParticipant:
    - student_id set to student's ID
    - guest_name set to student's name
    - guest_token generated (or NULL if registered student)
    - is_active = FALSE (awaiting connection)

Returns:
{
  "synced_count": 25,
  "participants": [
    {
      "id": "participant_uuid",
      "display_name": "John Doe",
      "student_id": "student_uuid",
      "is_active": false,
      "guest_token": null  // Only if registered student
    }
  ]
}

Pre-Conditions:
  - Session status must be "waiting"
  - Quiz must have class_id set
  - Class must exist and be owned by current_user
```

#### 3. **GET /api/quiz-sessions/{session_id}/roster**
```
Purpose: View expected vs actual participation for class
Path: /api/quiz-sessions/{session_id}/roster
Method: GET
Auth: Required (session host)
Response Model: RosterComparison

Returns:
{
  "class_id": "class_uuid",
  "class_name": "Biology 101",
  "total_students": 25,
  "participated": 20,
  "not_participated": 5,
  "participation_rate": 0.80,
  
  "participants": [
    {
      "student_id": "student_uuid",
      "name": "John Doe",
      "status": "participated|not_responded|absent",
      "joined_at": "2024-01-01T12:05:30Z",
      "last_answer_at": "2024-01-01T12:15:45Z",
      "score": 85,
      "accuracy": 0.90
    }
  ],
  
  "not_participated": [
    {
      "student_id": "student_uuid",
      "name": "Jane Smith",
      "reason": "never_joined|joined_but_no_answers"
    }
  ]
}
```

#### 4. **POST /api/quiz-sessions/{session_id}/send-reminder**
```
Purpose: Send notification to non-participating students
Path: /api/quiz-sessions/{session_id}/send-reminder
Method: POST
Auth: Required (session host)

Body:
{
  "target": "not_participated|low_score",  // Who to notify
  "message": "Optional custom message"
}

Behavior:
  - Get roster for session's class
  - Filter by target criteria
  - Send notifications (via email, SMS, etc.)
  - Return count of notifications sent

Note: Requires notification service integration
```

#### 5. **POST /api/quizzes/{quiz_id}/class/{class_id}/roster-report**
```
Purpose: Compare student performance across class
Path: /api/quizzes/{quiz_id}/class/{class_id}/roster-report
Method: POST  (or GET with params)
Auth: Required (quiz owner and class owner)

Returns:
{
  "quiz_id": "quiz_uuid",
  "quiz_title": "Quiz Title",
  "class_id": "class_uuid",
  "class_name": "Biology 101",
  "total_students": 25,
  
  "performance": [
    {
      "rank": 1,
      "student_id": "student_uuid",
      "name": "John Doe",
      "participation_count": 3,  // Sessions they took
      "avg_score": 85.5,
      "best_score": 100,
      "worst_score": 70,
      "accuracy_rate": 0.92,
      "total_time_ms": 450000
    }
  ]
}
```

### Database Changes Needed for Roster Tracking

```sql
-- Add enrollment status to QuizParticipant
ALTER TABLE quiz_participants ADD COLUMN enrollment_status VARCHAR(20)
  CHECK (enrollment_status IN ('expected', 'present', 'absent', 'excused'));

-- Add was_synced flag
ALTER TABLE quiz_participants ADD COLUMN was_synced_from_roster BOOLEAN DEFAULT FALSE;

-- Add class_id for quick filtering
ALTER TABLE quiz_sessions ADD COLUMN class_id VARCHAR;

-- Index for roster queries
CREATE INDEX idx_participants_session_class 
  ON quiz_participants(session_id, enrollment_status)
  WHERE was_synced_from_roster = TRUE;
```

### Service Layer Changes Needed

```python
# quiz_service.py - NEW FUNCTIONS

def sync_class_roster_to_session(
    session_id: str,
    user_id: str,
    db: DatabaseService
) -> List[QuizParticipant]:
    """Sync students from class to session participants."""
    session = db.get_quiz_session_by_id(session_id, user_id)
    quiz = db.get_quiz_by_id(session.quiz_id, user_id)
    
    if not quiz.class_id:
        raise ValueError("Quiz not assigned to a class")
    
    class_obj = db.get_class_by_id(quiz.class_id, user_id)
    students = db.get_students_by_class_id(quiz.class_id, user_id)
    
    participants = []
    for student in students:
        # Check if already in session
        existing = db.get_participant_by_student_in_session(session_id, student.student_id)
        if existing:
            continue
        
        # Create participant from roster
        participant_data = {
            "session_id": session_id,
            "student_id": student.student_id,
            "guest_name": student.name,
            "is_active": False,  # Awaiting connection
            "was_synced_from_roster": True,
            "enrollment_status": "expected"
        }
        participant = db.add_quiz_participant(participant_data)
        participants.append(participant)
    
    return participants


def get_roster_comparison(
    session_id: str,
    user_id: str,
    db: DatabaseService
) -> Dict:
    """Compare expected (class) vs actual (participated) students."""
    session = db.get_quiz_session_by_id(session_id, user_id)
    quiz = db.get_quiz_by_id(session.quiz_id, user_id)
    
    if not quiz.class_id:
        raise ValueError("Quiz not assigned to a class")
    
    class_students = db.get_students_by_class_id(quiz.class_id, user_id)
    participants = db.get_participants_by_session(session_id)
    
    # Build maps
    student_ids = {s.student_id for s in class_students}
    participant_ids = {p.student_id for p in participants if p.student_id}
    
    participated = participant_ids
    not_participated = student_ids - participant_ids
    
    # Format response
    return {
        "class_id": quiz.class_id,
        "total_students": len(class_students),
        "participated": len(participated),
        "not_participated": len(not_participated),
        "participation_rate": len(participated) / len(class_students) if class_students else 0,
        "participants": [... format participant data ...],
        "not_participated": [... format missing students ...]
    }
```

---

## Summary Table: All Quiz API Endpoints

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| **QUIZ MANAGEMENT** |
| GET | /api/quizzes | Yes | List quizzes |
| POST | /api/quizzes | Yes | Create quiz |
| GET | /api/quizzes/{quiz_id} | Yes | Get quiz details |
| PUT | /api/quizzes/{quiz_id} | Yes | Update quiz |
| DELETE | /api/quizzes/{quiz_id} | Yes | Delete quiz |
| POST | /api/quizzes/{quiz_id}/publish | Yes | Publish quiz |
| POST | /api/quizzes/{quiz_id}/duplicate | Yes | Duplicate quiz |
| **QUESTION MANAGEMENT** |
| POST | /api/quizzes/{quiz_id}/questions | Yes | Add question |
| PUT | /api/quizzes/{quiz_id}/questions/{question_id} | Yes | Update question |
| DELETE | /api/quizzes/{quiz_id}/questions/{question_id} | Yes | Delete question |
| PUT | /api/quizzes/{quiz_id}/questions/reorder | Yes | Reorder questions |
| **SESSION MANAGEMENT** |
| POST | /api/quiz-sessions | Yes | Create session |
| GET | /api/quiz-sessions | Yes | List sessions |
| GET | /api/quiz-sessions/{session_id} | Yes | Get session |
| POST | /api/quiz-sessions/{session_id}/start | Yes | Start session |
| POST | /api/quiz-sessions/{session_id}/end | Yes | End session |
| POST | /api/quiz-sessions/{session_id}/next-question | Yes | Next question |
| POST | /api/quiz-sessions/{session_id}/toggle-auto-advance | Yes | Configure auto-advance |
| GET | /api/quiz-sessions/{session_id}/participants | Yes | List participants |
| GET | /api/quiz-sessions/{session_id}/leaderboard | Yes | Get leaderboard |
| **PARTICIPANT ENDPOINTS** |
| POST | /api/quiz-sessions/join | No | Join session |
| GET | /api/quiz-sessions/{session_id}/current-question | No | Get current Q |
| POST | /api/quiz-sessions/{session_id}/submit-answer | No* | Submit answer |
| GET | /api/quiz-sessions/{session_id}/my-stats | No* | Get participant stats |
| **ANALYTICS** |
| GET | /api/quiz-sessions/{session_id}/analytics | Yes | Session analytics |
| GET | /api/quiz-sessions/{session_id}/participant-analytics | Yes | All participant analytics |
| GET | /api/quiz-sessions/{session_id}/participant-analytics/{participant_id} | Yes | Individual analytics |
| GET | /api/quiz-sessions/{session_id}/export/csv | Yes | Export to CSV |

*No: Requires guest token (X-Guest-Token header) OR student auth

