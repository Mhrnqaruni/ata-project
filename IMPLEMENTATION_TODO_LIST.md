# CLASS-BASED QUIZ TRACKING - DETAILED TODO LIST

**Quick Reference Guide for Implementation Tasks**

---

## 📊 OVERVIEW

**Total Tasks**: 87
**Estimated Time**: 32-40 hours
**Complexity**: Medium
**Risk Level**: Low

---

## 🗂️ PHASE 1: DATABASE LAYER (Tasks 1-12)

### Database Schema Design

- [ ] **Task 1.1**: Design `quiz_session_roster` table schema
  - Define all columns (id, session_id, student_id, student_name, student_school_id, enrollment_status, joined, joined_at, participant_id, created_at)
  - Define foreign key constraints (session_id → quiz_sessions, student_id → students, participant_id → quiz_participants)
  - Define unique constraint (session_id, student_id)
  - Design indexes (idx_session_roster_session, idx_session_roster_joined, idx_session_roster_student)
  - **Time**: 1 hour
  - **File**: Database design document

- [ ] **Task 1.2**: Design `quiz_outsider_students` table schema
  - Define all columns (id, session_id, student_school_id, guest_name, participant_id, detection_reason, flagged_by_teacher, teacher_notes, created_at)
  - Define foreign key constraints (session_id → quiz_sessions, participant_id → quiz_participants)
  - Define unique constraint (session_id, participant_id)
  - Design indexes (idx_outsider_session, idx_outsider_student_id, idx_outsider_participant)
  - **Time**: 1 hour
  - **File**: Database design document

- [ ] **Task 1.3**: Plan modifications to `quiz_sessions` table
  - Add `class_id` column (VARCHAR, nullable, FK to classes.id)
  - Add foreign key constraint with ON DELETE SET NULL
  - **Time**: 30 minutes
  - **File**: Database design document

- [ ] **Task 1.4**: Plan modifications to `quiz_participants` table
  - Add `is_outsider` column (BOOLEAN, default FALSE)
  - Add `roster_entry_id` column (VARCHAR, nullable, FK to quiz_session_roster.id)
  - Add index (session_id, is_outsider)
  - **Time**: 30 minutes
  - **File**: Database design document

### Alembic Migration

- [ ] **Task 1.5**: Create Alembic migration file
  - Run: `alembic revision -m "add_quiz_roster_tracking"`
  - **Time**: 5 minutes
  - **File**: `ata-backend/alembic/versions/YYYYMMDD_add_quiz_roster_tracking.py`

- [ ] **Task 1.6**: Write upgrade function for migration
  - Create `quiz_session_roster` table with all columns and constraints
  - Create `quiz_outsider_students` table with all columns and constraints
  - Alter `quiz_sessions` to add `class_id` column and FK
  - Alter `quiz_participants` to add `is_outsider` and `roster_entry_id` columns
  - Create all indexes
  - **Time**: 1.5 hours
  - **File**: `ata-backend/alembic/versions/YYYYMMDD_add_quiz_roster_tracking.py`

- [ ] **Task 1.7**: Write downgrade function for migration
  - Drop all new indexes
  - Drop foreign keys
  - Drop new columns from quiz_sessions and quiz_participants
  - Drop quiz_outsider_students table
  - Drop quiz_session_roster table
  - **Time**: 45 minutes
  - **File**: `ata-backend/alembic/versions/YYYYMMDD_add_quiz_roster_tracking.py`

- [ ] **Task 1.8**: Test migration on development database
  - Run `alembic upgrade head`
  - Verify all tables created correctly
  - Verify all indexes exist
  - Test downgrade: `alembic downgrade -1`
  - Test re-upgrade
  - **Time**: 30 minutes
  - **Environment**: Development database

- [ ] **Task 1.9**: Write SQL verification queries
  - Query to check table existence
  - Query to check column definitions
  - Query to check foreign key constraints
  - Query to check indexes
  - **Time**: 30 minutes
  - **File**: `ata-backend/scripts/verify_roster_schema.sql`

### SQLAlchemy Models

- [ ] **Task 1.10**: Create `QuizSessionRoster` SQLAlchemy model
  - Define table name: `quiz_session_roster`
  - Define all columns with proper types
  - Define relationships (session, student, participant)
  - Define table args (unique constraint, indexes)
  - **Time**: 1 hour
  - **File**: `ata-backend/app/db/models/quiz_models.py`

- [ ] **Task 1.11**: Create `QuizOutsiderStudent` SQLAlchemy model
  - Define table name: `quiz_outsider_students`
  - Define all columns with proper types
  - Define relationships (session, participant)
  - Define table args (unique constraint)
  - **Time**: 1 hour
  - **File**: `ata-backend/app/db/models/quiz_models.py`

- [ ] **Task 1.12**: Modify existing SQLAlchemy models
  - Add `class_id` column to `QuizSession` model
  - Add relationships: `class_`, `roster_entries`, `outsider_students` to `QuizSession`
  - Add `is_outsider` and `roster_entry_id` columns to `QuizParticipant` model
  - Add relationships: `roster_entry`, `outsider_record` to `QuizParticipant`
  - Add `quiz_sessions` relationship to `Class` model in class_student_models.py
  - **Time**: 1 hour
  - **Files**:
    - `ata-backend/app/db/models/quiz_models.py`
    - `ata-backend/app/db/models/class_student_models.py`

---

## 🔧 PHASE 2: PYDANTIC SCHEMAS (Tasks 13-20)

- [ ] **Task 2.1**: Create `QuizSessionRosterEntry` Pydantic schema
  - Define all fields matching database model
  - Add `Config` class with `from_attributes = True`
  - **Time**: 30 minutes
  - **File**: `ata-backend/app/models/quiz_model.py`

- [ ] **Task 2.2**: Create `QuizSessionRosterSummary` schema
  - Fields: total_expected, total_joined, total_absent, join_rate, entries (list)
  - **Time**: 20 minutes
  - **File**: `ata-backend/app/models/quiz_model.py`

- [ ] **Task 2.3**: Create `QuizOutsiderStudentRecord` schema
  - Define all fields matching database model
  - Add `Config` class
  - **Time**: 30 minutes
  - **File**: `ata-backend/app/models/quiz_model.py`

- [ ] **Task 2.4**: Create `OutsiderStudentSummary` schema
  - Fields: total_outsiders, records (list)
  - **Time**: 15 minutes
  - **File**: `ata-backend/app/models/quiz_model.py`

- [ ] **Task 2.5**: Create `ParticipantWithStatus` schema
  - Fields: participant_id, display_name, student_school_id, is_outsider, is_on_roster, joined_at, score, correct_answers
  - **Time**: 30 minutes
  - **File**: `ata-backend/app/models/quiz_model.py`

- [ ] **Task 2.6**: Create `SessionAttendanceSummary` schema
  - Fields: session_id, class_id, class_name, roster_summary, outsider_summary, total_participants, active_participants
  - **Time**: 30 minutes
  - **File**: `ata-backend/app/models/quiz_model.py`

- [ ] **Task 2.7**: Modify `QuizSessionResponse` schema
  - Add `class_id` field (Optional[str])
  - **Time**: 5 minutes
  - **File**: `ata-backend/app/models/quiz_model.py`

- [ ] **Task 2.8**: Modify `QuizParticipantResponse` schema
  - Add `is_outsider` field (bool, default False)
  - Add `roster_entry_id` field (Optional[str])
  - **Time**: 10 minutes
  - **File**: `ata-backend/app/models/quiz_model.py`

---

## 🏗️ PHASE 3: REPOSITORY LAYER (Tasks 21-30)

**File**: `ata-backend/app/services/database_helpers/quiz_session_repository_sql.py`

### Roster Query Methods

- [ ] **Task 3.1**: Implement `get_roster_entries_by_session(session_id)`
  - Query quiz_session_roster by session_id
  - Order by student_name
  - Return List[QuizSessionRoster]
  - **Time**: 30 minutes

- [ ] **Task 3.2**: Implement `get_roster_entry_by_student(session_id, student_school_id)`
  - Query by session_id AND student_school_id
  - Return Optional[QuizSessionRoster]
  - **Time**: 20 minutes

- [ ] **Task 3.3**: Implement `get_absent_students(session_id)`
  - Query where session_id matches AND joined = False
  - Order by student_name
  - **Time**: 20 minutes

- [ ] **Task 3.4**: Implement `get_joined_students(session_id)`
  - Query where session_id matches AND joined = True
  - Order by joined_at descending
  - **Time**: 20 minutes

### Outsider Query Methods

- [ ] **Task 3.5**: Implement `get_outsider_students_by_session(session_id)`
  - Query quiz_outsider_students by session_id
  - Order by created_at
  - **Time**: 20 minutes

- [ ] **Task 3.6**: Implement `get_outsider_by_participant(participant_id)`
  - Query by participant_id
  - Return Optional[QuizOutsiderStudent]
  - **Time**: 15 minutes

- [ ] **Task 3.7**: Implement `get_unflagged_outsiders(session_id)`
  - Query where flagged_by_teacher = False
  - **Time**: 15 minutes

### Combined Query Methods

- [ ] **Task 3.8**: Implement `get_participants_with_roster_status(session_id)`
  - Query all participants with left join to roster
  - Return List[Dict] with participant + roster status
  - **Time**: 1 hour

### Repository Tests

- [ ] **Task 3.9**: Write unit tests for all roster query methods
  - Test get_roster_entries_by_session with sample data
  - Test get_roster_entry_by_student with valid and invalid IDs
  - Test get_absent_students and get_joined_students
  - **Time**: 1.5 hours
  - **File**: `ata-backend/tests/repositories/test_quiz_session_repository.py`

- [ ] **Task 3.10**: Write unit tests for all outsider query methods
  - Test get_outsider_students_by_session
  - Test get_outsider_by_participant
  - Test get_unflagged_outsiders
  - **Time**: 1 hour
  - **File**: `ata-backend/tests/repositories/test_quiz_session_repository.py`

---

## 💼 PHASE 4: SERVICE LAYER (Tasks 31-45)

**New File**: `ata-backend/app/services/quiz_roster_service.py`

### Class Setup

- [ ] **Task 4.1**: Create `QuizRosterService` class
  - Initialize with db: Session parameter
  - Create ClassStudentRepository instance
  - **Time**: 15 minutes

### Roster Initialization Methods

- [ ] **Task 4.2**: Implement `initialize_roster_from_class(session_id, class_id, user_id)`
  - Verify session exists
  - Get students from class (with ownership check)
  - Create QuizSessionRoster entries for each student
  - Commit transaction
  - Return count of entries created
  - **Time**: 1.5 hours

- [ ] **Task 4.3**: Implement `sync_roster_from_class(session_id, class_id, user_id)`
  - Get current roster entries
  - Get current class students
  - Calculate differences (added, dropped)
  - Add new students with enrollment_status='added'
  - Mark dropped students with enrollment_status='dropped'
  - Return counts dictionary
  - **Time**: 2 hours

### Attendance Tracking Methods

- [ ] **Task 4.4**: Implement `mark_roster_entry_joined(roster_entry_id, participant_id)`
  - Update roster entry: joined=True, joined_at=now, participant_id
  - Update participant: is_outsider=False, roster_entry_id
  - Commit transaction
  - **Time**: 45 minutes

- [ ] **Task 4.5**: Implement `check_participant_roster_status(session_id, participant_id, student_school_id)`
  - Query roster by session_id and student_school_id
  - Return tuple: (is_on_roster: bool, roster_entry: Optional)
  - **Time**: 30 minutes

### Outsider Management Methods

- [ ] **Task 4.6**: Implement `create_outsider_record(session_id, participant_id, student_school_id, guest_name, detection_reason)`
  - Create QuizOutsiderStudent record
  - Update participant: is_outsider=True
  - Commit transaction
  - Return created record
  - **Time**: 1 hour

- [ ] **Task 4.7**: Implement `flag_outsider_student(outsider_id, flagged_by_teacher, teacher_notes)`
  - Update outsider record: flagged_by_teacher, teacher_notes
  - Commit transaction
  - **Time**: 30 minutes

### Summary & Analytics Methods

- [ ] **Task 4.8**: Implement `get_roster_summary(session_id)`
  - Query all roster entries for session
  - Calculate: total_expected, total_joined, total_absent, join_rate
  - Return dictionary with stats and entry details
  - **Time**: 1 hour

- [ ] **Task 4.9**: Implement `get_outsider_summary(session_id)`
  - Query all outsider records for session
  - Return dictionary with total count and record details
  - **Time**: 30 minutes

- [ ] **Task 4.10**: Implement `get_attendance_summary(session_id, user_id)`
  - Get session and verify ownership
  - Get class name if applicable
  - Get roster summary (if class_id set)
  - Get outsider summary
  - Get participant counts
  - Return complete attendance dictionary
  - **Time**: 1.5 hours

### Service Unit Tests

- [ ] **Task 4.11**: Write tests for roster initialization
  - Test initialize_roster_from_class with valid class
  - Test with empty class
  - Test with unauthorized user
  - **Time**: 1.5 hours
  - **File**: `ata-backend/tests/services/test_quiz_roster_service.py`

- [ ] **Task 4.12**: Write tests for attendance tracking
  - Test mark_roster_entry_joined updates both tables
  - Test check_participant_roster_status for on-roster student
  - Test check_participant_roster_status for outsider
  - **Time**: 1.5 hours
  - **File**: `ata-backend/tests/services/test_quiz_roster_service.py`

- [ ] **Task 4.13**: Write tests for outsider management
  - Test create_outsider_record
  - Test flag_outsider_student
  - **Time**: 1 hour
  - **File**: `ata-backend/tests/services/test_quiz_roster_service.py`

- [ ] **Task 4.14**: Write tests for roster sync
  - Test sync_roster_from_class when students added
  - Test when students dropped
  - Test when no changes
  - **Time**: 2 hours
  - **File**: `ata-backend/tests/services/test_quiz_roster_service.py`

- [ ] **Task 4.15**: Write tests for summary methods
  - Test get_roster_summary
  - Test get_outsider_summary
  - Test get_attendance_summary
  - **Time**: 1.5 hours
  - **File**: `ata-backend/tests/services/test_quiz_roster_service.py`

---

## 🔌 PHASE 5: API ENDPOINTS (Tasks 46-55)

**File**: `ata-backend/app/routers/quiz_session_router.py`

### New Endpoint Implementation

- [ ] **Task 5.1**: Implement `GET /{session_id}/attendance` endpoint
  - Extract session_id from path
  - Get current_user from dependency
  - Get db session from dependency
  - Verify session exists and user owns it (404 if not)
  - Call QuizRosterService.get_attendance_summary()
  - Return SessionAttendanceSummary response
  - **Time**: 1 hour

- [ ] **Task 5.2**: Implement `GET /{session_id}/roster` endpoint
  - Verify session ownership
  - Call QuizRosterService.get_roster_summary()
  - Return QuizSessionRosterSummary response
  - **Time**: 45 minutes

- [ ] **Task 5.3**: Implement `GET /{session_id}/outsiders` endpoint
  - Verify session ownership
  - Call QuizRosterService.get_outsider_summary()
  - Return OutsiderStudentSummary response
  - **Time**: 45 minutes

- [ ] **Task 5.4**: Implement `PUT /{session_id}/outsiders/{outsider_id}/flag` endpoint
  - Extract session_id, outsider_id from path
  - Extract flagged_by_teacher, teacher_notes from body
  - Verify session ownership
  - Call QuizRosterService.flag_outsider_student()
  - Return success message
  - **Time**: 1 hour

- [ ] **Task 5.5**: Implement `POST /{session_id}/roster/sync` endpoint
  - Verify session ownership
  - Verify session has class_id (400 if not)
  - Call QuizRosterService.sync_roster_from_class()
  - Return success message with counts
  - **Time**: 45 minutes

### Modify Existing Endpoint

- [ ] **Task 5.6**: Modify `POST /` (create session) endpoint
  - After creating session, check if quiz has class_id
  - If yes, initialize roster using QuizRosterService.initialize_roster_from_class()
  - Handle errors gracefully
  - **Time**: 30 minutes

### API Integration Tests

- [ ] **Task 5.7**: Write integration test for GET /attendance endpoint
  - Create test session with roster
  - Make authenticated request
  - Verify response structure and data
  - Test 404 for non-existent session
  - Test 404 for unauthorized access
  - **Time**: 1 hour
  - **File**: `ata-backend/tests/routers/test_quiz_session_router.py`

- [ ] **Task 5.8**: Write integration test for GET /roster endpoint
  - Similar to above
  - **Time**: 45 minutes
  - **File**: `ata-backend/tests/routers/test_quiz_session_router.py`

- [ ] **Task 5.9**: Write integration test for GET /outsiders endpoint
  - Create session with outsiders
  - Verify response
  - **Time**: 45 minutes
  - **File**: `ata-backend/tests/routers/test_quiz_session_router.py`

- [ ] **Task 5.10**: Write integration test for PUT /outsiders/{id}/flag endpoint
  - Create outsider record
  - Flag it via API
  - Verify database updated
  - **Time**: 1 hour
  - **File**: `ata-backend/tests/routers/test_quiz_session_router.py`

---

## 📡 PHASE 6: WEBSOCKET UPDATES (Tasks 56-62)

### Backend WebSocket Changes

- [ ] **Task 6.1**: Add `build_roster_updated_message()` to quiz_websocket.py
  - Accept roster_summary dict parameter
  - Return message with type='roster_updated'
  - Include timestamp
  - **Time**: 20 minutes
  - **File**: `ata-backend/app/core/quiz_websocket.py`

- [ ] **Task 6.2**: Add `build_outsider_detected_message()` to quiz_websocket.py
  - Accept outsider_record dict parameter
  - Return message with type='outsider_detected'
  - Include timestamp
  - **Time**: 20 minutes
  - **File**: `ata-backend/app/core/quiz_websocket.py`

- [ ] **Task 6.3**: Add `build_attendance_summary_message()` to quiz_websocket.py
  - Accept attendance_data dict parameter
  - Return message with type='attendance_summary'
  - Include timestamp
  - **Time**: 15 minutes
  - **File**: `ata-backend/app/core/quiz_websocket.py`

- [ ] **Task 6.4**: Create `handle_participant_roster_status()` async function
  - Check if participant is on roster using QuizRosterService
  - If on roster: mark as joined, broadcast roster_updated
  - If outsider: create outsider record, broadcast outsider_detected
  - **Time**: 2 hours
  - **File**: `ata-backend/app/routers/quiz_websocket_router.py`

- [ ] **Task 6.5**: Modify WebSocket connect handler
  - After successful participant connection
  - Check if session has class_id
  - If yes, call handle_participant_roster_status()
  - Handle errors gracefully (log but don't disconnect)
  - **Time**: 1 hour
  - **File**: `ata-backend/app/routers/quiz_websocket_router.py`

### WebSocket Tests

- [ ] **Task 6.6**: Write WebSocket integration test for roster updates
  - Connect as host
  - Connect as participant on roster
  - Verify host receives roster_updated message
  - **Time**: 1.5 hours
  - **File**: `ata-backend/tests/websockets/test_quiz_websocket.py`

- [ ] **Task 6.7**: Write WebSocket integration test for outsider detection
  - Connect as host
  - Connect as participant NOT on roster
  - Verify host receives outsider_detected message
  - **Time**: 1.5 hours
  - **File**: `ata-backend/tests/websockets/test_quiz_websocket.py`

---

## 🎨 PHASE 7: FRONTEND - QUIZ CREATION (Tasks 63-68)

**File**: `ata-frontend/src/pages/quizzes/QuizBuilder.jsx`

- [ ] **Task 7.1**: Add state variables for class selection
  - Add: `const [classes, setClasses] = useState([])`
  - Add: `const [selectedClassId, setSelectedClassId] = useState('')`
  - Add: `const [loadingClasses, setLoadingClasses] = useState(false)`
  - **Time**: 5 minutes

- [ ] **Task 7.2**: Implement `loadClasses()` function
  - Set loadingClasses = true
  - Call classService.getClasses()
  - Update classes state
  - If editing, set selectedClassId from quiz.class_id
  - Handle errors
  - Set loadingClasses = false
  - **Time**: 30 minutes

- [ ] **Task 7.3**: Add useEffect to load classes on mount
  - Call loadClasses() when component mounts
  - **Time**: 5 minutes

- [ ] **Task 7.4**: Add class selection UI in Step 0 (after description)
  - Add FormControl with InputLabel "Class (Optional)"
  - Add Select dropdown with classes.map()
  - Add MenuItem for "No class (open to all students)"
  - Add FormHelperText with explanation
  - Bind to selectedClassId state
  - **Time**: 45 minutes

- [ ] **Task 7.5**: Modify handleSave to include class_id
  - Add class_id: selectedClassId || null to quiz payload
  - **Time**: 10 minutes

- [ ] **Task 7.6**: Write frontend test for class selection
  - Test classes load on mount
  - Test selecting a class
  - Test quiz creation includes class_id
  - **Time**: 1 hour
  - **File**: `ata-frontend/src/pages/quizzes/__tests__/QuizBuilder.test.jsx`

---

## 🖥️ PHASE 8: FRONTEND - ROSTER DISPLAY (Tasks 69-79)

**File**: `ata-frontend/src/pages/quizzes/QuizHost.jsx`

### State Management

- [ ] **Task 8.1**: Add state variables for roster tracking
  - Add: `const [rosterSummary, setRosterSummary] = useState(null)`
  - Add: `const [outsiderSummary, setOutsiderSummary] = useState(null)`
  - Add: `const [attendanceSummary, setAttendanceSummary] = useState(null)`
  - Add: `const [showRosterDetails, setShowRosterDetails] = useState(false)`
  - Add: `const [showOutsiderDetails, setShowOutsiderDetails] = useState(false)`
  - Add: `const [notifications, setNotifications] = useState([])`
  - **Time**: 10 minutes

### Data Loading

- [ ] **Task 8.2**: Implement `loadAttendanceData()` function
  - Call quizService.getSessionAttendance(sessionId)
  - Update attendanceSummary, rosterSummary, outsiderSummary states
  - Handle errors
  - **Time**: 30 minutes

- [ ] **Task 8.3**: Add useEffect to load attendance when session has class
  - Check if session && session.class_id
  - Call loadAttendanceData()
  - **Time**: 10 minutes

### WebSocket Handlers

- [ ] **Task 8.4**: Add WebSocket message handlers
  - Add case 'roster_updated': update rosterSummary
  - Add case 'outsider_detected': show notification, reload data
  - Add case 'attendance_summary': update all summaries
  - **Time**: 30 minutes

- [ ] **Task 8.5**: Implement notification system
  - Create showNotification(message, severity) function
  - Auto-dismiss after 5 seconds
  - Add Snackbar components to JSX
  - **Time**: 45 minutes

### Roster Card UI

- [ ] **Task 8.6**: Create Roster Card component
  - Card with "Class Roster" title
  - Chip showing "{joined}/{expected}"
  - LinearProgress bar showing join_rate
  - Toggle button to show/hide student list
  - **Time**: 1 hour

- [ ] **Task 8.7**: Create Roster Entry List component
  - Collapsible list of students
  - Each entry shows: name, student ID, join status
  - Green checkmark for joined, red X for absent
  - Show join timestamp for joined students
  - Color code based on status
  - **Time**: 1.5 hours

### Outsider Card UI

- [ ] **Task 8.8**: Create Outsider Card component
  - Card with "Outsider Students" title
  - Warning icon and color scheme
  - Chip showing count
  - Toggle button to show/hide list
  - **Time**: 45 minutes

- [ ] **Task 8.9**: Create Outsider Entry List component
  - List of outsider students
  - Show: name, student ID, detection reason
  - Warning color scheme
  - **Time**: 1 hour

### Styling & Polish

- [ ] **Task 8.10**: Add responsive styling
  - Ensure cards stack properly on mobile
  - Adjust spacing and padding
  - Test on different screen sizes
  - **Time**: 1 hour

- [ ] **Task 8.11**: Add loading states
  - Show skeleton loaders while data loads
  - Show spinner in cards when refreshing
  - **Time**: 30 minutes

---

## 🔧 PHASE 9: FRONTEND - API SERVICE (Tasks 80-83)

**File**: `ata-frontend/src/services/quizService.js`

- [ ] **Task 9.1**: Implement `getSessionAttendance(sessionId)` method
  - Make GET request to `/api/quiz-sessions/${sessionId}/attendance`
  - Return response.data
  - **Time**: 15 minutes

- [ ] **Task 9.2**: Implement `getSessionRoster(sessionId)` method
  - Make GET request to `/api/quiz-sessions/${sessionId}/roster`
  - Return response.data
  - **Time**: 15 minutes

- [ ] **Task 9.3**: Implement `getSessionOutsiders(sessionId)` method
  - Make GET request to `/api/quiz-sessions/${sessionId}/outsiders`
  - Return response.data
  - **Time**: 15 minutes

- [ ] **Task 9.4**: Implement `flagOutsiderStudent(sessionId, outsiderId, approved, notes)` method
  - Make PUT request to `/api/quiz-sessions/${sessionId}/outsiders/${outsiderId}/flag`
  - Include body: {flagged_by_teacher, teacher_notes}
  - Return response.data
  - **Time**: 20 minutes

---

## 🧪 PHASE 10: TESTING & QA (Tasks 84-87)

- [ ] **Task 10.1**: End-to-end testing
  - Create quiz with class selection
  - Start session
  - Join as student on roster (verify green checkmark)
  - Join as outsider student (verify warning)
  - Verify real-time updates work
  - Complete quiz and verify analytics
  - **Time**: 2 hours

- [ ] **Task 10.2**: Performance testing
  - Create class with 100 students
  - Create quiz for that class
  - Start session and verify roster loads quickly (< 500ms)
  - Simulate 50 students joining concurrently
  - Verify WebSocket updates remain fast
  - **Time**: 2 hours

- [ ] **Task 10.3**: Cross-browser testing
  - Test on Chrome, Firefox, Safari, Edge
  - Test on mobile browsers
  - Verify WebSocket connections work
  - Verify UI renders correctly
  - **Time**: 1.5 hours

- [ ] **Task 10.4**: Accessibility testing
  - Test keyboard navigation
  - Test screen reader compatibility
  - Verify color contrast ratios
  - Test focus indicators
  - **Time**: 1 hour

---

## 📦 PHASE 11: DEPLOYMENT (Not counted in main tasks)

- [ ] Run migration on staging database
- [ ] Deploy backend to staging
- [ ] Deploy frontend to staging
- [ ] QA testing on staging
- [ ] Fix any staging issues
- [ ] Deploy to production
- [ ] Monitor for errors
- [ ] Document release notes

---

## 📊 TASK SUMMARY BY CATEGORY

| Category | Tasks | Estimated Time |
|----------|-------|----------------|
| Database Layer | 12 | 7.5 hours |
| Pydantic Schemas | 8 | 2.5 hours |
| Repository Layer | 10 | 6 hours |
| Service Layer | 15 | 16 hours |
| API Endpoints | 10 | 9 hours |
| WebSocket | 7 | 7.5 hours |
| Frontend - Quiz Creation | 6 | 3 hours |
| Frontend - Roster Display | 11 | 7.5 hours |
| Frontend - API Service | 4 | 1 hour |
| Testing & QA | 4 | 6.5 hours |
| **TOTAL** | **87 tasks** | **66.5 hours** |

---

## 🎯 CRITICAL PATH

**Must Complete in Order:**

1. Database migration (Tasks 1.5-1.9)
2. SQLAlchemy models (Tasks 1.10-1.12)
3. Pydantic schemas (Tasks 2.1-2.8)
4. Repository methods (Tasks 3.1-3.8)
5. Service layer (Tasks 4.1-4.10)
6. API endpoints (Tasks 5.1-5.6)
7. WebSocket integration (Tasks 6.1-6.5)
8. Frontend implementation (Tasks 7.1-9.4)
9. Testing (Tasks 10.1-10.4)

**Can Parallelize:**

- Unit tests can be written alongside implementation
- Frontend work can start once APIs are defined (even if not fully implemented)
- Documentation can be written anytime

---

## 📋 CHECKLIST FORMAT FOR TRACKING

Copy this to your project management tool:

```
[PHASE 1] Database Layer
  [ ] 1.1 Design quiz_session_roster schema
  [ ] 1.2 Design quiz_outsider_students schema
  [ ] 1.3 Plan quiz_sessions modifications
  [ ] 1.4 Plan quiz_participants modifications
  [ ] 1.5 Create migration file
  [ ] 1.6 Write upgrade function
  [ ] 1.7 Write downgrade function
  [ ] 1.8 Test migration on dev
  [ ] 1.9 Write verification queries
  [ ] 1.10 Create QuizSessionRoster model
  [ ] 1.11 Create QuizOutsiderStudent model
  [ ] 1.12 Modify existing models

[PHASE 2] Pydantic Schemas
  [ ] 2.1 QuizSessionRosterEntry schema
  [ ] 2.2 QuizSessionRosterSummary schema
  [ ] 2.3 QuizOutsiderStudentRecord schema
  [ ] 2.4 OutsiderStudentSummary schema
  [ ] 2.5 ParticipantWithStatus schema
  [ ] 2.6 SessionAttendanceSummary schema
  [ ] 2.7 Modify QuizSessionResponse
  [ ] 2.8 Modify QuizParticipantResponse

... (continue for all phases)
```

---

**Document Version**: 1.0
**Last Updated**: 2025-11-17
**Total Estimated Time**: 66.5 hours (adjust based on team experience)
