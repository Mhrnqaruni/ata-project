# Quiz Database Models and Structure - Comprehensive Analysis

## Executive Summary

The quiz system uses a well-designed database schema with 5 core tables and comprehensive student/participant tracking. The architecture supports both registered students (with accounts) and anonymous guests, with built-in analytics and session management.

---

## Core Quiz Tables

### 1. **Quizzes Table** (`quizzes`)
**Purpose:** Stores quiz definitions created by teachers

**Column Structure:**
| Column | Type | Properties | Description |
|--------|------|-----------|-------------|
| `id` | String (UUID) | PRIMARY KEY | Unique quiz identifier |
| `user_id` | UUID | FK → users.id, NOT NULL | Teacher/owner of the quiz |
| `class_id` | String | FK → classes.id, NULLABLE | Associated class (optional) |
| `title` | String(200) | NOT NULL, INDEXED | Quiz title |
| `description` | Text | NULLABLE | Extended quiz description |
| `settings` | JSONB | Server Default: '{}' | Flexible settings (shuffle, time limits, etc.) |
| `status` | String(20) | DEFAULT: "draft" | Status: draft, published, completed, archived |
| `deleted_at` | DateTime | NULLABLE | Soft delete timestamp |
| `last_room_code` | String(10) | NULLABLE | Most recent room code for quick rejoin |
| `created_at` | DateTime | Server Generated | Creation timestamp |
| `updated_at` | DateTime | Server Generated | Last update timestamp |

**Key Features:**
- Soft delete support (preserves historical data for analytics)
- JSONB settings column for flexible configuration
- Tracks last room code for quick session rejoin
- Composite indexes on (user_id, status) and (class_id) for fast lookups

**Relationships:**
- One-to-many with QuizQuestion (cascade delete)
- One-to-many with QuizSession (cascade delete)
- Back-reference to User (owner)

---

### 2. **Quiz Questions Table** (`quiz_questions`)
**Purpose:** Individual questions within a quiz

**Column Structure:**
| Column | Type | Properties | Description |
|--------|------|-----------|-------------|
| `id` | String (UUID) | PRIMARY KEY | Unique question identifier |
| `quiz_id` | String | FK → quizzes.id, NOT NULL | Parent quiz |
| `question_type` | String(20) | NOT NULL, INDEXED | Type: multiple_choice, true_false, short_answer, poll |
| `question_text` | Text | NOT NULL | The actual question content |
| `options` | JSONB | Server Default: '[]' | Answer options (array of strings) |
| `correct_answer` | JSONB | Server Default: '[]' | Correct answer(s) for grading |
| `points` | Integer | DEFAULT: 10 | Points awarded for correct answer |
| `time_limit_seconds` | Integer | NULLABLE | Time limit for this question (5-300 secs) |
| `order_index` | Integer | DEFAULT: 0 | Display order (0-indexed) |
| `explanation` | Text | NULLABLE | Explanation shown after answer submission |
| `media_url` | String | NULLABLE | URL to supporting image/video |
| `created_at` | DateTime | Server Generated | Creation timestamp |

**Question Type Examples:**
- **Multiple Choice:** `{"options": ["A", "B", "C"], "correct_answer": ["A"] or [0]}`
- **True/False:** `{"options": [], "correct_answer": [true]}`
- **Short Answer:** `{"options": [], "correct_answer": ["keyword1", "keyword2"]}`
- **Poll:** `{"options": ["A", "B"], "correct_answer": []}` (no scoring)

**Indexes:**
- Composite index on (quiz_id, order_index) for efficient ordering

**Relationships:**
- Many-to-one with Quiz
- One-to-many with QuizResponse (cascade delete)

---

### 3. **Quiz Sessions Table** (`quiz_sessions`)
**Purpose:** Live instances of quizzes being run by teachers

**Column Structure:**
| Column | Type | Properties | Description |
|--------|------|-----------|-------------|
| `id` | String (UUID) | PRIMARY KEY | Unique session identifier |
| `quiz_id` | String | FK → quizzes.id, NOT NULL | The quiz being run |
| `user_id` | UUID | FK → users.id, NOT NULL | Teacher/host of session |
| `room_code` | String(10) | UNIQUE, NOT NULL | 6-char join code (e.g., "AB3K7Q") |
| `status` | String(20) | DEFAULT: "waiting" | Status: waiting, active, completed, cancelled |
| `current_question_index` | Integer | NULLABLE | Current question (0-indexed) |
| `config_snapshot` | JSONB | Server Default: '{}' | Quiz config at session creation time |
| `timeout_hours` | Integer | DEFAULT: 2 | Auto-end timeout duration |
| `started_at` | DateTime | NULLABLE | When session status changed to active |
| `ended_at` | DateTime | NULLABLE | When session completed/cancelled |
| `auto_ended_at` | DateTime | NULLABLE | When session auto-ended due to timeout |
| `question_started_at` | DateTime | NULLABLE | When current question started (for time limits) |
| `created_at` | DateTime | Server Generated | Creation timestamp |

**Session Status Lifecycle:**
1. `waiting` - Created but not started yet
2. `active` - In progress
3. `completed` - Finished normally
4. `cancelled` - Ended prematurely

**Key Features:**
- Config snapshot prevents quiz changes from affecting active sessions
- Tracks question timing for time limit enforcement
- Auto-end mechanism with timeout tracking
- Room code is unique for easy participant joining

**Indexes:**
- Composite index on (status, created_at) for finding active sessions
- Composite index on (user_id, status) for teacher's session queries
- UNIQUE index on room_code

**Relationships:**
- Many-to-one with Quiz
- Back-reference to User (host)
- One-to-many with QuizParticipant (cascade delete)
- One-to-many with QuizResponse (cascade delete)

---

### 4. **Quiz Participants Table** (`quiz_participants`)
**Purpose:** Tracks students and guests participating in a quiz session

**Column Structure:**
| Column | Type | Properties | Description |
|--------|------|-----------|-------------|
| `id` | String (UUID) | PRIMARY KEY | Unique participant identifier |
| `session_id` | String | FK → quiz_sessions.id, NOT NULL | Session they joined |
| `student_id` | String | NULLABLE, INDEXED | School/registered student ID |
| `guest_name` | String(50) | NULLABLE | Display name for anonymous guests |
| `guest_token` | String(64) | UNIQUE, NULLABLE | 32-byte hex token for guest auth |
| `score` | Integer | DEFAULT: 0 | Cached total score |
| `correct_answers` | Integer | DEFAULT: 0 | Count of correct answers |
| `total_time_ms` | Integer | DEFAULT: 0 | Total time spent (milliseconds) |
| `is_active` | Boolean | DEFAULT: True | Currently connected? |
| `anonymized_at` | DateTime | NULLABLE | GDPR anonymization timestamp |
| `joined_at` | DateTime | Server Generated | When participant joined |
| `last_seen_at` | DateTime | Server Generated | Last heartbeat timestamp |

**Three Identity Patterns (enforced by CHECK constraint):**

1. **Registered Student:** `student_id` set, `guest_name/guest_token` NULL
   - Student has an account in the system
   - Can rejoin with student credentials

2. **Pure Guest:** `student_id` NULL, `guest_name + guest_token` set
   - Anonymous participant
   - Uses token for reconnection
   - Eligible for GDPR anonymization

3. **Identified Guest:** ALL THREE fields set (`student_id + guest_name + guest_token`)
   - Student without account (common in K-12)
   - Tracked by school student ID
   - Has display name
   - Uses token for authentication

**CHECK Constraint:**
```sql
(student_id IS NOT NULL AND guest_name IS NULL AND guest_token IS NULL) OR
(student_id IS NULL AND guest_name IS NOT NULL AND guest_token IS NOT NULL) OR
(student_id IS NOT NULL AND guest_name IS NOT NULL AND guest_token IS NOT NULL)
```

**Indexes:**
- Composite index on (session_id, score DESC) for leaderboard queries
- Composite index on (session_id, is_active) for active participant queries
- GDPR cleanup index on (joined_at, anonymized_at) where guest_token IS NOT NULL
- UNIQUE index on guest_token for authentication

**Relationships:**
- Many-to-one with QuizSession
- One-to-many with QuizResponse (cascade delete)

---

### 5. **Quiz Responses Table** (`quiz_responses`)
**Purpose:** Individual answer submissions with grading and timing

**Column Structure:**
| Column | Type | Properties | Description |
|--------|------|-----------|-------------|
| `id` | String (UUID) | PRIMARY KEY | Unique response identifier |
| `session_id` | String | FK → quiz_sessions.id, NOT NULL | Session this response belongs to |
| `participant_id` | String | FK → quiz_participants.id, NOT NULL | Who answered |
| `question_id` | String | FK → quiz_questions.id, NOT NULL | Which question |
| `answer` | JSONB | NOT NULL | The submitted answer |
| `is_correct` | Boolean | NULLABLE | Correctness (NULL for polls) |
| `points_earned` | Integer | DEFAULT: 0 | Points awarded |
| `time_taken_ms` | Integer | NOT NULL | Time to answer (milliseconds) |
| `answered_at` | DateTime | Server Generated | Submission timestamp |

**Answer Format Examples:**
- Multiple Choice: `["A"]` or `[0]` (index)
- True/False: `[true]` or `[false]`
- Short Answer: `["submitted text"]`
- Poll: `["B"]`

**Key Constraints:**
- UNIQUE constraint on (session_id, participant_id, question_id) - one answer per participant per question
- Prevents duplicate submissions

**Indexes:**
- Composite index on (session_id, is_correct, points_earned) for leaderboard calculations
- Composite index on (question_id, is_correct, time_taken_ms) for question analytics

**Relationships:**
- Many-to-one with QuizSession
- Many-to-one with QuizParticipant
- Many-to-one with QuizQuestion

---

## Related Tables (Relationships)

### Users Table (`users`)
- Owns quizzes and sessions
- One-to-many relationship with Quiz via `user_id`
- One-to-many relationship with QuizSession via `user_id`

### Classes Table (`classes`)
- Optional association with quizzes via `class_id`
- Can have students enrolled via `student_class_memberships` junction table
- Owned by teachers (User)

### Students Table (`students`)
- Can participate in quizzes via `student_id` field in QuizParticipant
- NOTE: `student_id` in QuizParticipant is NOT a foreign key
- Can be arbitrary school IDs, not just registered students
- Enrolled in classes via `student_class_memberships`

### Student Class Membership (`student_class_memberships`)
- Junction table for many-to-many relationship between Students and Classes
- Enables students to belong to multiple classes

---

## Current Participant/Student Tracking Mechanisms

### 1. **Real-Time Tracking**
- `is_active` field tracks current connection status
- `last_seen_at` field updated on every heartbeat (for timeout detection)
- Composite index on (session_id, is_active) for quick active participant lookup

### 2. **Performance Tracking**
Cached on QuizParticipant:
- `score` - Total points earned
- `correct_answers` - Count of correct responses
- `total_time_ms` - Total time spent

Detailed tracking in QuizResponse:
- Individual answer data
- Correctness of each answer
- Points per question
- Time per question

### 3. **Leaderboard System**
- Indexed by (session_id, score DESC, total_time_ms)
- Faster time breaks ties
- Real-time calculation possible with materialized view design

### 4. **Analytics Metrics** (Calculated in quiz_analytics_service.py)
**Session-level:**
- Completion rate (participants who answered all questions)
- Average score and percentage
- Median, min, max scores
- Standard deviation
- Accuracy rate

**Question-level:**
- Total responses
- Correct/incorrect counts
- Accuracy rate
- Average time per question
- Difficulty index
- Option distribution (for multiple choice/polls)

**Participant-level:**
- Individual score and rank
- Accuracy rate
- Average time per question
- Completion status (full, partial, no response)

### 5. **GDPR Compliance**
- Guest anonymization mechanism
- `anonymized_at` field tracks when guest data was anonymized
- Cleanup job scheduled for guests older than 30 days
- Guest names replaced with "Anonymous User {ID}"

### 6. **Identity Tracking**
- Supports registered students with accounts
- Supports anonymous guests with tokens
- Supports identified guests (students without accounts)
- Can track students by student_id for school integration

---

## Database Indexes Summary

### Quizzes Table
- `idx_quizzes_user_status_not_deleted` (user_id, status) WHERE deleted_at IS NULL
- `idx_quizzes_class_not_deleted` (class_id) WHERE deleted_at IS NULL
- Single column indexes: user_id, status, title, class_id, last_room_code

### Quiz Questions
- `idx_quiz_questions_quiz_order` (quiz_id, order_index)
- Single column: quiz_id, question_type

### Quiz Sessions
- `idx_quiz_sessions_status_created` (status, created_at)
- `idx_quiz_sessions_user_status` (user_id, status)
- Single column: quiz_id, room_code (UNIQUE), status, user_id

### Quiz Participants
- `idx_participants_session_score` (session_id, score DESC)
- `idx_participants_session_active` (session_id, is_active)
- `idx_participants_gdpr_cleanup` (joined_at, anonymized_at) WHERE guest_token IS NOT NULL
- Single column: session_id, student_id, guest_token (UNIQUE)

### Quiz Responses
- `idx_responses_leaderboard` (session_id, is_correct, points_earned)
- `idx_responses_question_analytics` (question_id, is_correct, time_taken_ms)
- Single column: session_id, participant_id, question_id

---

## Data Access Patterns

### Quiz Repository (quiz_repository_sql.py)
- Quiz CRUD with user ownership validation
- Question CRUD with cascade delete
- Soft delete support
- Quiz duplication with all questions

### Quiz Session Repository (quiz_session_repository_sql.py)
- Session CRUD with user ownership validation
- Participant management (add, update, retrieve)
- Response submission and retrieval
- Leaderboard queries
- Real-time score updates with row-level locking (pessimistic locking)
- GDPR anonymization of old guests
- Participant ranking calculation

---

## Key Design Decisions

1. **JSONB for Flexibility**
   - Settings, options, and answers stored as JSONB
   - Allows different question types without schema changes
   - Supports flexible quiz configuration

2. **Soft Delete**
   - Quizzes use soft delete to preserve analytics
   - Filtered out by default with composite indexes

3. **Config Snapshot**
   - Quiz config captured at session creation
   - Prevents quiz changes from affecting active sessions

4. **Pessimistic Locking**
   - Score updates use SELECT FOR UPDATE
   - Prevents race conditions in concurrent submissions
   - Ensures atomic score calculation

5. **Guest Token Pattern**
   - 32-byte hex token (64 characters) for guest authentication
   - Unique index for O(1) lookups
   - Enables guest reconnection

6. **Three Identity Pattern**
   - Single table supports registered students, guests, and identified guests
   - CHECK constraint enforces valid combinations
   - Flexible without complex joins

7. **Session Room Codes**
   - Unique 6-character codes (e.g., "AB3K7Q")
   - Enables easy participant joining
   - Tracked on Quiz for quick rejoin

---

## SQL Query Examples

### Get Leaderboard
```sql
SELECT * FROM quiz_participants
WHERE session_id = ? AND is_active = true
ORDER BY score DESC, total_time_ms ASC
LIMIT 10;
```

### Get Question Analytics
```sql
SELECT 
  COUNT(*) as total,
  COUNT(CASE WHEN is_correct = true THEN 1 END) as correct,
  AVG(time_taken_ms) as avg_time
FROM quiz_responses
WHERE question_id = ?;
```

### Get Participant Rank
```sql
SELECT COUNT(*) + 1 as rank
FROM quiz_participants p1
WHERE p1.session_id = ? 
AND (
  p1.score > (SELECT score FROM quiz_participants WHERE id = ?)
  OR (
    p1.score = (SELECT score FROM quiz_participants WHERE id = ?)
    AND p1.total_time_ms < (SELECT total_time_ms FROM quiz_participants WHERE id = ?)
  )
);
```

### Check Participant Already Joined
```sql
SELECT * FROM quiz_participants
WHERE session_id = ? AND student_id = ?;
```

---

## Migration History

**Current Migration:** `018e9779debd` - Initial database schema
- All tables created in single migration
- Comprehensive indexes for performance
- Constraints for data integrity
- Foreign keys with CASCADE delete

---

## Summary of What's Tracked

### Per Quiz Session
- Participant list with identity information
- Each participant's score, correct answers, and time
- Whether participant is currently active
- Individual question responses with timing and correctness
- Session status and timeline
- Leaderboard rankings

### Per Student/Participant
- Identity (registered student, guest, or identified guest)
- Performance metrics (score, accuracy)
- Time spent
- Individual answers to each question
- Activity status

### Per Question
- Response statistics (total, correct, incorrect)
- Accuracy rate
- Average response time
- Option distribution (for MC/polls)

This comprehensive tracking enables real-time leaderboards, detailed analytics, and student progress monitoring.
