# Quiz API - Quick Reference Guide

## File Locations
- **Quiz Router**: `/ata-backend/app/routers/quiz_router.py` (498 lines)
- **Session Router**: `/ata-backend/app/routers/quiz_session_router.py` (1277 lines)
- **Models/Schemas**: `/ata-backend/app/models/quiz_model.py` (583 lines)
- **DB Models**: `/ata-backend/app/db/models/quiz_models.py` (437 lines)
- **Auth Core**: `/ata-backend/app/core/quiz_auth.py` (349 lines)
- **Dependencies**: `/ata-backend/app/core/deps.py` (140 lines)

---

## API Endpoints by Category

### Quiz Management (11 endpoints)
```
GET    /api/quizzes                           - List all (with class_id filter)
POST   /api/quizzes                           - Create new
GET    /api/quizzes/{quiz_id}                 - Get details
PUT    /api/quizzes/{quiz_id}                 - Update
DELETE /api/quizzes/{quiz_id}                 - Delete (soft or hard)
POST   /api/quizzes/{quiz_id}/publish         - Publish
POST   /api/quizzes/{quiz_id}/duplicate       - Duplicate
POST   /api/quizzes/{quiz_id}/questions       - Add question
PUT    /api/quizzes/{quiz_id}/questions/{qid} - Update question
DELETE /api/quizzes/{quiz_id}/questions/{qid} - Delete question
PUT    /api/quizzes/{quiz_id}/questions/reorder - Reorder questions
```

### Session Management (9 endpoints)
```
POST   /api/quiz-sessions                              - Create session
GET    /api/quiz-sessions                              - List sessions
GET    /api/quiz-sessions/{session_id}                 - Get session
POST   /api/quiz-sessions/{session_id}/start           - Start session
POST   /api/quiz-sessions/{session_id}/end             - End session
POST   /api/quiz-sessions/{session_id}/next-question   - Next question
POST   /api/quiz-sessions/{session_id}/toggle-auto-advance - Configure auto-advance
GET    /api/quiz-sessions/{session_id}/participants    - Get participants
GET    /api/quiz-sessions/{session_id}/leaderboard     - Get leaderboard
```

### Participant Endpoints (4 endpoints)
```
POST   /api/quiz-sessions/join                         - Join session (public)
GET    /api/quiz-sessions/{session_id}/current-question - Get current Q (public)
POST   /api/quiz-sessions/{session_id}/submit-answer   - Submit answer (token auth)
GET    /api/quiz-sessions/{session_id}/my-stats        - Get stats (token auth)
```

### Analytics (4 endpoints)
```
GET    /api/quiz-sessions/{session_id}/analytics       - Session analytics
GET    /api/quiz-sessions/{session_id}/participant-analytics - All participants
GET    /api/quiz-sessions/{session_id}/participant-analytics/{pid} - One participant
GET    /api/quiz-sessions/{session_id}/export/csv      - Export CSV
```

---

## Security Model (Three-Layer Defense)

### Layer 1: Router
- Validates JWT Bearer token from Authorization header
- Dependency: `get_current_active_user`
- Extracts `current_user.id` for user-scoped operations

### Layer 2: Service
- All functions require explicit `user_id` parameter
- Example: `create_quiz(quiz_data, user_id, db)`
- Passes user_id to repository layer

### Layer 3: Repository (SQL)
- Every query includes WHERE clause filtering by user_id
- Example: `WHERE quiz.user_id = :user_id AND quiz.id = :quiz_id`
- Database enforces at constraint level

**Result**: Cross-user data access impossible

---

## Authentication Patterns

### Teachers/Quiz Creators
```
1. Login with email + password
2. Receive JWT token (contains user_id)
3. Include in Authorization: "Bearer {token}"
4. All quiz/session endpoints require this
```

### Students/Quiz Participants
```
JOIN ENDPOINT (Public):
1. POST /api/quiz-sessions/join with room_code + optional student_id/guest_name
2. Get back: session info + participant_id + guest_token (if guest)

SUBMIT ANSWER (Token Auth):
1. Include header: X-Guest-Token: {64_char_hex_token}
2. POST to submit-answer endpoint
3. Token extracted from header (not from request body)
```

---

## Data Models Summary

### Quiz
- `id` (string UUID)
- `user_id` (UUID, FK to users, mandatory)
- `class_id` (string, FK to classes, optional)
- `title`, `description`, `settings`
- `status` (draft|published|archived)
- `deleted_at` (soft delete timestamp)

### QuizSession
- `id` (string UUID)
- `quiz_id`, `user_id` (FKs)
- `room_code` (6-char unique code)
- `status` (waiting|active|completed|cancelled)
- `current_question_index` (0-indexed)
- `config_snapshot` (JSONB with auto-advance settings)
- `started_at`, `ended_at` (timestamps)

### QuizParticipant
- `id` (string UUID)
- `session_id` (FK)
- `student_id` (optional string - can be account ID OR arbitrary school ID)
- `guest_name` (optional string)
- `guest_token` (optional string, 64 hex chars)
- **Triple identity pattern**: Exactly one of three combinations valid
  1. `student_id` set, others NULL (registered student)
  2. `guest_name + guest_token` set, `student_id` NULL (pure guest)
  3. All three set (identified guest - K-12 student without account)
- `score`, `correct_answers`, `total_time_ms`
- `is_active` (connected/disconnected status)

### QuizResponse
- `id` (string UUID)
- `session_id`, `participant_id`, `question_id` (FKs)
- `answer` (JSONB - format depends on question type)
- `is_correct` (boolean, null for polls)
- `points_earned` (int)
- `time_taken_ms` (int)
- **Unique constraint**: (session_id, participant_id, question_id)

---

## Current class_id Implementation

### What Works
1. ✓ Can set `class_id` when creating quiz
2. ✓ Can filter GET /api/quizzes by class_id query param
3. ✓ class_id stored in database and returned in responses

### What's Missing
1. ✗ No validation that user owns the class
2. ✗ No automatic student enrollment based on class_id
3. ✗ Sessions don't track which class they're for
4. ✗ No roster enforcement (quiz open to all, not just class students)
5. ✗ No pre-population of session with class roster
6. ✗ No "participation by class" analytics

---

## Roster Tracking - Recommended Implementation

### New Endpoints to Add

1. **POST /api/quizzes/{quiz_id}/assign-class**
   - Validate quiz and class owned by user
   - Update quiz.class_id = class_id

2. **POST /api/quiz-sessions/{session_id}/sync-class-roster**
   - Get session's quiz → class_id
   - Get students in that class
   - Create QuizParticipant for each (awaiting connection)
   - Return synced count and participant list

3. **GET /api/quiz-sessions/{session_id}/roster**
   - Expected students from class
   - Actual participants (who joined)
   - Not participated (show names + reason)
   - Participation rate

4. **POST /api/quiz-sessions/{session_id}/send-reminder**
   - Send notifications to non-participating students
   - Target: not_participated or low_score

5. **GET /api/quizzes/{quiz_id}/class/{class_id}/roster-report**
   - Compare performance of class across multiple quiz sessions
   - Average scores, participation rates, accuracy rates

### DB Schema Changes Needed
```sql
ALTER TABLE quiz_participants ADD COLUMN enrollment_status 
  VARCHAR(20) CHECK (status IN ('expected', 'present', 'absent', 'excused'));

ALTER TABLE quiz_participants ADD COLUMN was_synced_from_roster BOOLEAN DEFAULT FALSE;

ALTER TABLE quiz_sessions ADD COLUMN class_id VARCHAR;  -- Track class per session

CREATE INDEX idx_participants_session_class 
  ON quiz_participants(session_id, enrollment_status)
  WHERE was_synced_from_roster = TRUE;
```

---

## User_ID Enforcement Examples

### Example 1: Creating a Quiz
```python
# Router (gets user from JWT)
@router.post("")
def create_quiz(quiz_data, current_user = Depends(get_current_active_user)):
    # current_user.id = "abc123" (from JWT)
    quiz = quiz_service.create_quiz_with_questions(
        quiz_data=quiz_data,
        user_id=current_user.id,  # ← Passed explicitly
        db=db
    )

# Service (passes to repository)
def create_quiz_with_questions(quiz_data, user_id, db):
    quiz_dict = {
        "user_id": user_id,  # ← Set from parameter
        "title": quiz_data.title,
        ...
    }
    return db.create_quiz(quiz_dict)

# Repository (enforces in SQL)
def get_quiz_by_id(self, quiz_id, user_id):
    return (
        self.db.query(Quiz)
        .filter(
            Quiz.id == quiz_id,
            Quiz.user_id == user_id  # ← SQL WHERE clause
        )
        .first()
    )
    # Returns None if user_id doesn't match
```

### Example 2: Guest Token Validation
```python
# Guest tokens are 256-bit cryptographically secure random values
# Hex-encoded: 64 characters
# Example: "a4c2f8d9e1b4a7c5f3d9e2a5b7c4d1f8a9e2b5c8d1f4a7b0c3d6e9f2a5b8c"

# Constant-time comparison prevents timing attacks
import hmac
is_valid = hmac.compare_digest(token_from_db, token_from_request)
# Takes same time regardless of where tokens differ
```

---

## Key Security Facts

1. **user_id is mandatory** for all authenticated endpoints
2. **Guest tokens are 256-bit random** (cryptographically secure)
3. **Token comparison is constant-time** (prevents timing attacks)
4. **Soft delete is supported** (deleted_at timestamp, not hard deletion)
5. **GDPR compliance built-in** (guest anonymization support)
6. **No cross-user data access possible** (three-layer enforcement)
7. **DB constraints enforce ownership** (not just app logic)

---

## Question Types

| Type | Options | Correct Answer | Points | Use Case |
|------|---------|-----------------|--------|----------|
| **multiple_choice** | 2-6 options | Exactly 1 | 1-100 | Standard Q&A |
| **true_false** | N/A | True or False | 1-100 | Binary questions |
| **short_answer** | N/A | 1+ keywords | 1-100 | Free response |
| **poll** | 2-10 options | None (no correct) | 0 | Surveys/opinions |

---

## Status Enums

### Quiz Status
- `draft` - Under development, not runnable
- `published` - Ready to run in sessions
- `archived` - Hidden but historical data preserved
- (Soft deleted): `deleted_at IS NOT NULL`

### Session Status
- `waiting` - Created, not started yet
- `active` - In progress (participants answering)
- `completed` - Finished normally
- `cancelled` - Stopped early by host

---

## Response Models

### GET /api/quizzes (List)
Returns `QuizSummary[]`:
- id, user_id, class_id, title, description, settings
- status, question_count, created_at, updated_at, last_room_code

### GET /api/quizzes/{quiz_id} (Detail)
Returns `QuizDetail`:
- Same as above PLUS:
- questions[] (full QuizQuestionAdminResponse with correct answers)
- deleted_at

### POST /api/quiz-sessions (Create)
Returns `QuizSessionDetail`:
- id, quiz_id, user_id, room_code, status
- current_question_index, config_snapshot, timeout_hours
- started_at, ended_at, created_at, participant_count, questions[]

### POST /api/quiz-sessions/join (Join)
Returns `ParticipantJoinResponse`:
- session (nested): id, room_code, quiz_title, status, current_question_index
- participant (nested): id, display_name, guest_name, student_id, is_guest
- guest_token (null for registered students)

---

## Common Error Responses

| Status | Scenario |
|--------|----------|
| **401 UNAUTHORIZED** | Invalid/missing JWT OR invalid guest token |
| **403 FORBIDDEN** | Inactive user OR user doesn't own resource |
| **404 NOT_FOUND** | Quiz/session/question not found or not owned |
| **422 UNPROCESSABLE_ENTITY** | Validation error (e.g., publish with no questions) |
| **400 BAD_REQUEST** | Invalid request data or token mismatch |

---

## WebSocket Messages (Real-time Updates)

### Sent by Server
- `session_started` - Quiz session began
- `question_started` - New question displayed
- `question_ended` - Question time limit reached
- `participant_answered` - Student submitted answer (to teachers only)
- `stats_update` - Answer completion percentage (to teachers)
- `leaderboard_update` - Scores changed (to all)
- `session_ended` - Quiz finished
- `auto_advance_updated` - Auto-advance setting changed
- `participant_joined` - New student joined
- `participant_left` - Student disconnected
- `heartbeat_ping` - Keep-alive from server

### Sent by Client
- `submit_answer` - Student submits answer (also via REST)
- `heartbeat_pong` - Acknowledge keep-alive
- `request_current_state` - Recover state after reconnect

---

## Testing Checklist

### Quiz Endpoints
- [ ] Create quiz as teacher
- [ ] List quizzes with class_id filter
- [ ] Get quiz details (includes correct answers)
- [ ] Update quiz fields
- [ ] Publish quiz (validates questions)
- [ ] Duplicate quiz (creates draft copy)
- [ ] Add/update/delete questions
- [ ] Reorder questions
- [ ] Soft delete quiz
- [ ] Hard delete quiz

### Session Endpoints
- [ ] Create session (generates room code)
- [ ] Start session (broadcasts to WebSocket)
- [ ] Next question (handles missed responses)
- [ ] End session (final leaderboard + broadcast)
- [ ] Configure auto-advance (before start only)
- [ ] Get participants list
- [ ] Get leaderboard (top N)

### Participant Endpoints
- [ ] Join as identified guest (student_id + guest_name)
- [ ] Join as pure guest (guest_name only)
- [ ] Join as registered student (student_id only)
- [ ] Get current question (no correct answer shown)
- [ ] Submit answer (with grading)
- [ ] Get my stats (via guest token)

### Security
- [ ] JWT validation works
- [ ] User can't access other user's quizzes
- [ ] Guest token prevents cross-session answers
- [ ] Soft-deleted quizzes hidden by default
- [ ] Hard delete cascades properly
- [ ] Room code is truly unique

---

## Performance Considerations

### Indexes
- `idx_quizzes_user_status_not_deleted` (user_id, status) - Quiz listing
- `idx_quiz_questions_quiz_order` (quiz_id, order_index) - Question retrieval
- `idx_quiz_sessions_user_status` (user_id, status) - Session listing
- `idx_participants_session_score` (session_id, score DESC) - Leaderboard
- `idx_responses_leaderboard` (session_id, is_correct, points) - Analytics

### Query Optimization
- Leaderboard: Use index on (session_id, score)
- Questions: Retrieved via (quiz_id, order_index)
- Sessions: Filtered by (user_id, status)

---

## Future Enhancements

### Short-term (Roster Tracking)
1. Add class roster sync endpoints (sync, roster view, reminders)
2. Add class-level analytics
3. Add student enrollment validation
4. Add per-class participation reports

### Medium-term
1. Quiz randomization options (shuffle questions/answers)
2. Question banks / question library sharing
3. Quiz templates
4. Time limit enforcement for timed quizzes
5. Proctoring mode (prevent tab switching, etc.)

### Long-term
1. Adaptive questions based on performance
2. AI-generated quiz suggestions
3. Student misconception detection
4. Integration with LMS (Canvas, Blackboard, etc.)
5. Mobile app support

