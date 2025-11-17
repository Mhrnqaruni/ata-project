# CLASS-BASED QUIZ STUDENT TRACKING - COMPREHENSIVE IMPLEMENTATION PLAN

**Project**: ATA Quiz System Enhancement
**Feature**: Class-Based Student Roster Tracking with Attendance Monitoring
**Date**: 2025-11-17
**Status**: Planning Phase - No Implementation Yet

---

## 📋 TABLE OF CONTENTS

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Requirements Overview](#requirements-overview)
4. [Database Schema Changes](#database-schema-changes)
5. [Backend Implementation Plan](#backend-implementation-plan)
6. [Frontend Implementation Plan](#frontend-implementation-plan)
7. [WebSocket Real-Time Updates](#websocket-real-time-updates)
8. [API Endpoints Changes](#api-endpoints-changes)
9. [Service Layer Changes](#service-layer-changes)
10. [Repository Layer Changes](#repository-layer-changes)
11. [Testing Strategy](#testing-strategy)
12. [Migration Strategy](#migration-strategy)
13. [Implementation Roadmap](#implementation-roadmap)
14. [Risk Assessment](#risk-assessment)
15. [File Inventory](#file-inventory)

---

## 1. EXECUTIVE SUMMARY

### 1.1 Project Goal

Enhance the ATA quiz system to support **class-based student roster tracking** with real-time attendance monitoring. This will enable teachers to:

1. **Select a class** when creating a quiz
2. **See expected roster** of students from that class
3. **Track attendance** in real-time during the quiz waiting room
4. **Distinguish outsider students** who join but aren't in the class
5. **Maintain analytics** for both roster and outsider students

### 1.2 Current State

✅ **Already Implemented:**
- Quiz model already has `class_id` field (database ready)
- Assessment service already has outsider student tracking pattern
- Class/Student models with many-to-many relationship via junction table
- Quiz participant tracking with triple identity pattern (registered, guest, identified)
- WebSocket infrastructure for real-time updates
- Comprehensive analytics and leaderboard systems

❌ **Missing:**
- Frontend UI for class selection during quiz creation
- Backend validation of class ownership during quiz creation
- Student roster synchronization to quiz sessions
- Real-time roster vs. actual participant comparison
- Outsider student detection and tracking for quizzes
- UI for displaying roster status (joined/absent) in waiting room
- Separate outsider list in waiting room

### 1.3 Implementation Scope

**Estimated Effort**: 15-20 development hours (2-3 sprints)
**Complexity**: Medium
**Risk Level**: Low (building on existing patterns)

**Files to Modify**: 15
**New Files to Create**: 6
**Database Tables to Add**: 2
**API Endpoints to Add**: 8
**Frontend Components to Add**: 4

---

## 2. CURRENT STATE ANALYSIS

### 2.1 Database Schema (Current)

#### Quiz Table
```sql
quizzes (
    id VARCHAR PRIMARY KEY,
    title VARCHAR NOT NULL,
    description TEXT,
    user_id UUID FK(users.id) NOT NULL,
    class_id VARCHAR FK(classes.id),  -- ✅ ALREADY EXISTS!
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
```

#### QuizParticipant Table (Current)
```sql
quiz_participants (
    id VARCHAR PRIMARY KEY,
    session_id VARCHAR FK(quiz_sessions.id) NOT NULL,
    student_id VARCHAR,  -- Can be school student ID or DB student ID
    guest_name VARCHAR,
    guest_token VARCHAR UNIQUE,
    score INTEGER DEFAULT 0,
    correct_answers INTEGER DEFAULT 0,
    total_time_ms INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    joined_at TIMESTAMP,
    last_seen_at TIMESTAMP
)
```

**Current Triple Identity Pattern:**
1. **Pure Guest**: `guest_name` + `guest_token`, no `student_id`
2. **Registered Student**: `student_id` only (has account in system)
3. **Identified Guest**: All three fields (student without account)

### 2.2 Assessment Service Pattern (Reference Implementation)

The assessment service already implements outsider tracking:

**Assessment Model:**
```python
class Assessment:
    class_id: FK to classes  # ✅ Already links to class

class Result:
    student_id: FK to students (nullable)
    outsider_student_id: FK to outsider_students (nullable)
    # CHECK constraint: EXACTLY one must be set
```

**OutsiderStudent Model:**
```python
class OutsiderStudent:
    id: String (PK)
    name: String
    studentId: String (unique)
    extracted_from: String  # "vision_ai" or "manual"
    created_at: DateTime
```

**File Matching Logic:**
- Uses Vision AI to extract student names from documents
- Fuzzy matching against class roster
- Auto-creates OutsiderStudent if no match
- Tracks both types uniformly in results

### 2.3 Current Quiz Flow

**Teacher Side:**
1. Create quiz → Add questions → Set settings → Publish
2. Start session → Generate room code → Share with students
3. Wait in lobby → Start quiz → Progress through questions
4. View leaderboard → End session → Review analytics

**Student Side:**
1. Enter room code → Join as guest (name + student ID)
2. Wait in lobby → Teacher starts → Answer questions
3. See score → View final rank

**Current Waiting Room:**
- Shows total participant count only
- Shows top 10 leaderboard (score-ranked)
- No full participant list
- No roster comparison
- No distinction between student types

---

## 3. REQUIREMENTS OVERVIEW

### 3.1 Functional Requirements

#### FR-1: Class Selection During Quiz Creation
- **As a** teacher
- **I want to** select which class this quiz is for
- **So that** the system knows which students should attend

**Acceptance Criteria:**
- Dropdown shows only classes owned by the teacher
- Class selection is optional (quiz can be class-independent)
- Selected class is stored in `quiz.class_id`
- UI shows class selection on Step 0 of quiz builder

#### FR-2: Student Roster Synchronization
- **As a** teacher
- **I want** the system to load the class roster when I start a session
- **So that** I can track which students joined

**Acceptance Criteria:**
- When session starts, load all students from selected class
- Create "expected participant" records
- Store roster snapshot at session creation time
- Handle students who drop/add after quiz creation

#### FR-3: Real-Time Attendance Tracking
- **As a** teacher
- **I want to** see which students have joined vs. are absent
- **So that** I can ensure everyone is present before starting

**Acceptance Criteria:**
- Waiting room shows full roster with join status
- Status updates in real-time as students join
- Shows: Student Name, Student ID, Status (Joined/Absent), Join Time
- WebSocket broadcasts attendance changes immediately

#### FR-4: Outsider Student Detection
- **As a** teacher
- **I want** to see students who joined but aren't in my class roster
- **So that** I can identify unauthorized participants or registration errors

**Acceptance Criteria:**
- Detect when `student_id` from join request doesn't match roster
- Create outsider record automatically
- Display outsiders in separate list section
- Include outsiders in analytics and leaderboard

#### FR-5: Roster Status Display
- **As a** teacher
- **I want** a clear visual display of attendance status
- **So that** I can quickly assess participation

**Acceptance Criteria:**
- "Class Roster" section shows expected students
- Green checkmark for joined, red X for absent
- "Outsider Students" section shows unexpected participants
- Count badges: "Roster: 8/10 joined" + "Outsiders: 2"

### 3.2 Non-Functional Requirements

#### NFR-1: Performance
- Roster loading must complete within 500ms for classes up to 100 students
- Real-time updates must propagate within 200ms
- Leaderboard queries must remain under 100ms

#### NFR-2: Security
- Enforce teacher ownership of class during quiz creation
- Validate student roster access permissions
- Prevent cross-tenant data access

#### NFR-3: Data Integrity
- Roster snapshot must be immutable after session starts
- Outsider student records must be unique by `studentId`
- Foreign key constraints must prevent orphaned records

#### NFR-4: Scalability
- Support quizzes for classes up to 200 students
- Handle 50 concurrent quiz sessions
- Maintain real-time performance with 1000+ active connections

---

## 4. DATABASE SCHEMA CHANGES

### 4.1 New Tables Required

#### Table 1: `quiz_session_roster`

**Purpose**: Store snapshot of expected students at session creation time

```sql
CREATE TABLE quiz_session_roster (
    id VARCHAR PRIMARY KEY,
    session_id VARCHAR NOT NULL,
    student_id VARCHAR NOT NULL,
    student_name VARCHAR NOT NULL,          -- Denormalized for performance
    student_school_id VARCHAR NOT NULL,     -- Denormalized studentId field
    enrollment_status VARCHAR(20) DEFAULT 'expected',  -- expected, dropped, added
    joined BOOLEAN DEFAULT FALSE,
    joined_at TIMESTAMP NULL,
    participant_id VARCHAR NULL,            -- FK to quiz_participants when joined
    created_at TIMESTAMP DEFAULT NOW(),

    FOREIGN KEY (session_id) REFERENCES quiz_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (participant_id) REFERENCES quiz_participants(id) ON DELETE SET NULL,

    UNIQUE (session_id, student_id)
);

CREATE INDEX idx_session_roster_session ON quiz_session_roster(session_id);
CREATE INDEX idx_session_roster_joined ON quiz_session_roster(session_id, joined);
CREATE INDEX idx_session_roster_student ON quiz_session_roster(student_id);
```

**Columns Explained:**
- `id`: Primary key (UUID)
- `session_id`: Which quiz session this roster entry belongs to
- `student_id`: Reference to students table (DB student ID)
- `student_name`: Cached name for performance (avoid joins)
- `student_school_id`: Cached studentId (the user-provided ID like "S12345")
- `enrollment_status`: Track if student was in roster at creation, or added/dropped later
- `joined`: Boolean flag for quick filtering
- `joined_at`: Timestamp of when student joined session
- `participant_id`: Links to quiz_participants when student joins
- `created_at`: Roster snapshot timestamp

**Why This Table?**
- Immutable snapshot of roster at session creation
- Handles roster changes between quiz creation and session start
- Fast queries for "who's missing" without complex joins
- Denormalized fields avoid N+1 query problems

#### Table 2: `quiz_outsider_students`

**Purpose**: Track students who join but aren't on the expected roster

```sql
CREATE TABLE quiz_outsider_students (
    id VARCHAR PRIMARY KEY,
    session_id VARCHAR NOT NULL,
    student_school_id VARCHAR NOT NULL,      -- The studentId they entered when joining
    guest_name VARCHAR NOT NULL,             -- The name they entered
    participant_id VARCHAR NOT NULL,         -- FK to quiz_participants
    detection_reason VARCHAR(50) NOT NULL,   -- 'not_in_class', 'no_class_set', 'student_not_found'
    flagged_by_teacher BOOLEAN DEFAULT FALSE,
    teacher_notes TEXT NULL,
    created_at TIMESTAMP DEFAULT NOW(),

    FOREIGN KEY (session_id) REFERENCES quiz_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (participant_id) REFERENCES quiz_participants(id) ON DELETE CASCADE,

    UNIQUE (session_id, participant_id)
);

CREATE INDEX idx_outsider_session ON quiz_outsider_students(session_id);
CREATE INDEX idx_outsider_student_id ON quiz_outsider_students(student_school_id);
CREATE INDEX idx_outsider_participant ON quiz_outsider_students(participant_id);
```

**Columns Explained:**
- `id`: Primary key (UUID)
- `session_id`: Which quiz session detected this outsider
- `student_school_id`: The student ID they entered (like "S12345")
- `guest_name`: The name they provided when joining
- `participant_id`: Link to their quiz_participants record
- `detection_reason`: Why they were flagged as outsider
  - `not_in_class`: Student ID found in DB but not in this class
  - `no_class_set`: Quiz has no class_id set (all are outsiders)
  - `student_not_found`: Student ID doesn't exist in any class
- `flagged_by_teacher`: Teacher can manually mark as acceptable
- `teacher_notes`: Optional notes (e.g., "Transfer student, approved")
- `created_at`: When outsider was detected

**Why This Table?**
- Separate from QuizParticipant (keeps participant model clean)
- Audit trail for unauthorized access attempts
- Analytics: track which students frequently join wrong quizzes
- Teacher can review and approve/reject after quiz
- Historical data for compliance and security

### 4.2 Existing Table Modifications

#### Modify: `quiz_sessions`

**Add Column:**
```sql
ALTER TABLE quiz_sessions
ADD COLUMN class_id VARCHAR NULL,
ADD FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE SET NULL;
```

**Reasoning:**
- Currently, `quiz_sessions` doesn't store `class_id`
- Need to denormalize from `quizzes.class_id` for performance
- Allows session to persist class association even if quiz is deleted
- Enables faster roster queries without joining through quizzes table

**Migration Impact**: Low (nullable, defaults to NULL for existing sessions)

#### Modify: `quiz_participants`

**Add Columns:**
```sql
ALTER TABLE quiz_participants
ADD COLUMN is_outsider BOOLEAN DEFAULT FALSE,
ADD COLUMN roster_entry_id VARCHAR NULL,
ADD FOREIGN KEY (roster_entry_id) REFERENCES quiz_session_roster(id) ON DELETE SET NULL;

CREATE INDEX idx_participants_outsider ON quiz_participants(session_id, is_outsider);
```

**Columns Explained:**
- `is_outsider`: Quick flag for filtering (avoid complex joins)
- `roster_entry_id`: Link back to expected roster entry (if applicable)

**Reasoning:**
- Fast queries for "show me only outsiders"
- Bi-directional link between roster and participants
- Index enables efficient filtering in leaderboard queries

**Migration Impact**: Low (defaults to FALSE for existing participants)

### 4.3 Database Migration Files to Create

**File**: `ata-backend/alembic/versions/YYYYMMDD_add_quiz_roster_tracking.py`

```python
"""Add quiz roster tracking tables

Revision ID: <generated>
Revises: <previous_revision>
Create Date: YYYY-MM-DD

"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Create quiz_session_roster table
    op.create_table(
        'quiz_session_roster',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('student_id', sa.String(), nullable=False),
        sa.Column('student_name', sa.String(), nullable=False),
        sa.Column('student_school_id', sa.String(), nullable=False),
        sa.Column('enrollment_status', sa.String(20), server_default='expected'),
        sa.Column('joined', sa.Boolean(), server_default='false'),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('participant_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['session_id'], ['quiz_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['participant_id'], ['quiz_participants.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id', 'student_id', name='uq_session_student')
    )
    op.create_index('idx_session_roster_session', 'quiz_session_roster', ['session_id'])
    op.create_index('idx_session_roster_joined', 'quiz_session_roster', ['session_id', 'joined'])
    op.create_index('idx_session_roster_student', 'quiz_session_roster', ['student_id'])

    # Create quiz_outsider_students table
    op.create_table(
        'quiz_outsider_students',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('student_school_id', sa.String(), nullable=False),
        sa.Column('guest_name', sa.String(), nullable=False),
        sa.Column('participant_id', sa.String(), nullable=False),
        sa.Column('detection_reason', sa.String(50), nullable=False),
        sa.Column('flagged_by_teacher', sa.Boolean(), server_default='false'),
        sa.Column('teacher_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['session_id'], ['quiz_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['participant_id'], ['quiz_participants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id', 'participant_id', name='uq_session_outsider')
    )
    op.create_index('idx_outsider_session', 'quiz_outsider_students', ['session_id'])
    op.create_index('idx_outsider_student_id', 'quiz_outsider_students', ['student_school_id'])
    op.create_index('idx_outsider_participant', 'quiz_outsider_students', ['participant_id'])

    # Modify quiz_sessions table
    op.add_column('quiz_sessions', sa.Column('class_id', sa.String(), nullable=True))
    op.create_foreign_key('fk_quiz_sessions_class_id', 'quiz_sessions', 'classes', ['class_id'], ['id'], ondelete='SET NULL')

    # Modify quiz_participants table
    op.add_column('quiz_participants', sa.Column('is_outsider', sa.Boolean(), server_default='false'))
    op.add_column('quiz_participants', sa.Column('roster_entry_id', sa.String(), nullable=True))
    op.create_foreign_key('fk_quiz_participants_roster', 'quiz_participants', 'quiz_session_roster', ['roster_entry_id'], ['id'], ondelete='SET NULL')
    op.create_index('idx_participants_outsider', 'quiz_participants', ['session_id', 'is_outsider'])

def downgrade():
    # Reverse all changes
    op.drop_index('idx_participants_outsider', 'quiz_participants')
    op.drop_constraint('fk_quiz_participants_roster', 'quiz_participants', type_='foreignkey')
    op.drop_column('quiz_participants', 'roster_entry_id')
    op.drop_column('quiz_participants', 'is_outsider')

    op.drop_constraint('fk_quiz_sessions_class_id', 'quiz_sessions', type_='foreignkey')
    op.drop_column('quiz_sessions', 'class_id')

    op.drop_index('idx_outsider_participant', 'quiz_outsider_students')
    op.drop_index('idx_outsider_student_id', 'quiz_outsider_students')
    op.drop_index('idx_outsider_session', 'quiz_outsider_students')
    op.drop_table('quiz_outsider_students')

    op.drop_index('idx_session_roster_student', 'quiz_session_roster')
    op.drop_index('idx_session_roster_joined', 'quiz_session_roster')
    op.drop_index('idx_session_roster_session', 'quiz_session_roster')
    op.drop_table('quiz_session_roster')
```

---

## 5. BACKEND IMPLEMENTATION PLAN

### 5.1 Database Models (SQLAlchemy)

#### File: `ata-backend/app/db/models/quiz_models.py`

**Modify Existing Models:**

```python
# Add to QuizSession model
class QuizSession(Base):
    __tablename__ = "quiz_sessions"

    # ... existing columns ...

    # NEW COLUMN
    class_id = Column(String, ForeignKey("classes.id", ondelete="SET NULL"), nullable=True, index=True)

    # NEW RELATIONSHIPS
    class_ = relationship("Class", back_populates="quiz_sessions")
    roster_entries = relationship("QuizSessionRoster", back_populates="session", cascade="all, delete-orphan")
    outsider_students = relationship("QuizOutsiderStudent", back_populates="session", cascade="all, delete-orphan")


# Add to QuizParticipant model
class QuizParticipant(Base):
    __tablename__ = "quiz_participants"

    # ... existing columns ...

    # NEW COLUMNS
    is_outsider = Column(Boolean, nullable=False, default=False, index=True)
    roster_entry_id = Column(String, ForeignKey("quiz_session_roster.id", ondelete="SET NULL"), nullable=True)

    # NEW RELATIONSHIPS
    roster_entry = relationship("QuizSessionRoster", back_populates="participant")
    outsider_record = relationship("QuizOutsiderStudent", back_populates="participant", uselist=False)
```

**New Models:**

```python
class QuizSessionRoster(Base):
    """
    Snapshot of expected students for a quiz session.
    Created when session starts from the class roster.
    """
    __tablename__ = "quiz_session_roster"

    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("quiz_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    student_name = Column(String, nullable=False)
    student_school_id = Column(String, nullable=False)
    enrollment_status = Column(String(20), nullable=False, default="expected")
    joined = Column(Boolean, nullable=False, default=False, index=True)
    joined_at = Column(DateTime(timezone=True), nullable=True)
    participant_id = Column(String, ForeignKey("quiz_participants.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("QuizSession", back_populates="roster_entries")
    student = relationship("Student")
    participant = relationship("QuizParticipant", back_populates="roster_entry")

    # Table args
    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_session_student"),
        Index("idx_session_roster_joined", "session_id", "joined"),
    )


class QuizOutsiderStudent(Base):
    """
    Tracks students who joined a quiz session but weren't on the expected roster.
    Used for analytics, security, and compliance.
    """
    __tablename__ = "quiz_outsider_students"

    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("quiz_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    student_school_id = Column(String, nullable=False, index=True)
    guest_name = Column(String, nullable=False)
    participant_id = Column(String, ForeignKey("quiz_participants.id", ondelete="CASCADE"), nullable=False, unique=True)
    detection_reason = Column(String(50), nullable=False)
    flagged_by_teacher = Column(Boolean, nullable=False, default=False)
    teacher_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("QuizSession", back_populates="outsider_students")
    participant = relationship("QuizParticipant", back_populates="outsider_record")

    # Table args
    __table_args__ = (
        UniqueConstraint("session_id", "participant_id", name="uq_session_outsider"),
    )
```

#### File: `ata-backend/app/db/models/class_student_models.py`

**Modify Class model:**

```python
class Class(Base):
    __tablename__ = "classes"

    # ... existing columns ...

    # NEW RELATIONSHIP
    quiz_sessions = relationship("QuizSession", back_populates="class_")
```

### 5.2 Pydantic Schemas

#### File: `ata-backend/app/models/quiz_model.py`

**Add New Schemas:**

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# ========== ROSTER SCHEMAS ==========

class QuizSessionRosterEntry(BaseModel):
    """Single roster entry for a student expected in the session."""
    id: str
    session_id: str
    student_id: str
    student_name: str
    student_school_id: str
    enrollment_status: str
    joined: bool
    joined_at: Optional[datetime] = None
    participant_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class QuizSessionRosterSummary(BaseModel):
    """Summary of roster status for display."""
    total_expected: int
    total_joined: int
    total_absent: int
    join_rate: float  # Percentage
    entries: List[QuizSessionRosterEntry]


# ========== OUTSIDER SCHEMAS ==========

class QuizOutsiderStudentRecord(BaseModel):
    """Record of a student who joined but wasn't on roster."""
    id: str
    session_id: str
    student_school_id: str
    guest_name: str
    participant_id: str
    detection_reason: str
    flagged_by_teacher: bool
    teacher_notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class OutsiderStudentSummary(BaseModel):
    """Summary of outsider students for display."""
    total_outsiders: int
    records: List[QuizOutsiderStudentRecord]


# ========== COMBINED ATTENDANCE SCHEMAS ==========

class ParticipantWithStatus(BaseModel):
    """Participant info with roster/outsider status."""
    participant_id: str
    display_name: str
    student_school_id: Optional[str] = None
    is_outsider: bool
    is_on_roster: bool
    joined_at: datetime
    score: int
    correct_answers: int

    class Config:
        from_attributes = True


class SessionAttendanceSummary(BaseModel):
    """Complete attendance overview for a session."""
    session_id: str
    class_id: Optional[str] = None
    class_name: Optional[str] = None

    # Roster metrics
    roster_summary: Optional[QuizSessionRosterSummary] = None

    # Outsider metrics
    outsider_summary: OutsiderStudentSummary

    # Combined metrics
    total_participants: int
    active_participants: int

    class Config:
        from_attributes = True


# ========== UPDATE EXISTING SCHEMAS ==========

class QuizSessionResponse(BaseModel):
    """Response model for quiz session (updated)."""
    id: str
    quiz_id: str
    user_id: str
    room_code: str
    status: str
    current_question_index: Optional[int] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: datetime

    # NEW FIELD
    class_id: Optional[str] = None

    class Config:
        from_attributes = True


class QuizParticipantResponse(BaseModel):
    """Response model for quiz participant (updated)."""
    id: str
    session_id: str
    student_id: Optional[str] = None
    guest_name: Optional[str] = None
    score: int
    correct_answers: int
    total_time_ms: int
    is_active: bool
    joined_at: datetime
    last_seen_at: datetime

    # NEW FIELDS
    is_outsider: bool = False
    roster_entry_id: Optional[str] = None

    class Config:
        from_attributes = True
```

---

## 6. FRONTEND IMPLEMENTATION PLAN

### 6.1 Quiz Creation - Class Selection

#### File: `ata-frontend/src/pages/quizzes/QuizBuilder.jsx`

**Location**: Step 0 (Quiz Information section)
**After**: Description field (around line 548)

**Changes Required:**

1. **Add State Variables:**
```javascript
const [classes, setClasses] = useState([]);
const [selectedClassId, setSelectedClassId] = useState('');
const [loadingClasses, setLoadingClasses] = useState(false);
```

2. **Load Classes on Mount:**
```javascript
useEffect(() => {
  loadClasses();
}, []);

const loadClasses = async () => {
  setLoadingClasses(true);
  try {
    const data = await classService.getClasses();
    setClasses(data);

    // If editing existing quiz, set selected class
    if (quiz && quiz.class_id) {
      setSelectedClassId(quiz.class_id);
    }
  } catch (error) {
    console.error('Failed to load classes:', error);
    alert('Failed to load classes. Please refresh the page.');
  } finally {
    setLoadingClasses(false);
  }
};
```

3. **Add UI Component (After description field):**
```javascript
{/* Class Selection */}
<FormControl fullWidth margin="normal">
  <InputLabel id="class-select-label">
    Class (Optional)
  </InputLabel>
  <Select
    labelId="class-select-label"
    id="class-select"
    value={selectedClassId}
    label="Class (Optional)"
    onChange={(e) => setSelectedClassId(e.target.value)}
    disabled={loadingClasses}
  >
    <MenuItem value="">
      <em>No class (open to all students)</em>
    </MenuItem>
    {classes.map((cls) => (
      <MenuItem key={cls.id} value={cls.id}>
        {cls.name}
      </MenuItem>
    ))}
  </Select>
  <FormHelperText>
    Select a class to track attendance and roster
  </FormHelperText>
</FormControl>
```

4. **Include in API Payload:**
```javascript
const handleSave = async () => {
  const quizPayload = {
    title,
    description,
    class_id: selectedClassId || null,  // NEW FIELD
    questions: questions.map(q => ({
      // ... existing question mapping
    })),
    settings: {
      // ... existing settings
    }
  };

  if (isEditMode) {
    await quizService.updateQuiz(quizId, quizPayload);
  } else {
    await quizService.createQuiz(quizPayload);
  }
};
```

**Estimated Changes**: ~60 lines added, 0 lines removed

### 6.2 Quiz Host - Roster Display

#### File: `ata-frontend/src/pages/quizzes/QuizHost.jsx`

**New Section**: Between "Participant Count" card and "Timer" card

**Changes Required:**

1. **Add State Variables:**
```javascript
const [rosterSummary, setRosterSummary] = useState(null);
const [outsiderSummary, setOutsiderSummary] = useState(null);
const [attendanceSummary, setAttendanceSummary] = useState(null);
const [showRosterDetails, setShowRosterDetails] = useState(false);
const [showOutsiderDetails, setShowOutsiderDetails] = useState(false);
```

2. **Load Attendance Data:**
```javascript
const loadAttendanceData = async () => {
  if (!sessionId) return;

  try {
    const data = await quizService.getSessionAttendance(sessionId);
    setAttendanceSummary(data);
    setRosterSummary(data.roster_summary);
    setOutsiderSummary(data.outsider_summary);
  } catch (error) {
    console.error('Failed to load attendance:', error);
  }
};

useEffect(() => {
  if (session && session.class_id) {
    loadAttendanceData();
  }
}, [session]);
```

3. **Handle WebSocket Updates:**
```javascript
// Add to handleWebSocketMessage function
case 'roster_updated':
    loadAttendanceData();
    break;
case 'outsider_detected':
    loadAttendanceData();
    showNotification(`Outsider student joined: ${message.guest_name}`);
    break;
```

4. **Add Roster Card UI:**
```javascript
{/* Class Roster Card - Only show if quiz has class_id */}
{session?.class_id && rosterSummary && (
  <Card sx={{ mb: 2 }}>
    <CardContent>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
        <PeopleIcon sx={{ mr: 1, color: 'primary.main' }} />
        <Typography variant="h6">
          Class Roster
        </Typography>
        <Chip
          label={`${rosterSummary.total_joined}/${rosterSummary.total_expected}`}
          color={rosterSummary.join_rate >= 80 ? 'success' : 'warning'}
          size="small"
          sx={{ ml: 'auto' }}
        />
      </Box>

      {/* Progress Bar */}
      <LinearProgress
        variant="determinate"
        value={rosterSummary.join_rate}
        sx={{ mb: 2, height: 8, borderRadius: 4 }}
      />

      {/* Toggle Details Button */}
      <Button
        size="small"
        onClick={() => setShowRosterDetails(!showRosterDetails)}
        endIcon={showRosterDetails ? <ExpandLessIcon /> : <ExpandMoreIcon />}
      >
        {showRosterDetails ? 'Hide' : 'Show'} Student List
      </Button>

      {/* Detailed Student List */}
      <Collapse in={showRosterDetails}>
        <List dense sx={{ mt: 1 }}>
          {rosterSummary.entries.map((entry) => (
            <ListItem
              key={entry.id}
              sx={{
                bgcolor: entry.joined ? 'success.light' : 'error.light',
                borderRadius: 1,
                mb: 0.5,
                opacity: entry.joined ? 1 : 0.7
              }}
            >
              <ListItemIcon>
                {entry.joined ? (
                  <CheckCircleIcon color="success" />
                ) : (
                  <CancelIcon color="error" />
                )}
              </ListItemIcon>
              <ListItemText
                primary={entry.student_name}
                secondary={`ID: ${entry.student_school_id}${entry.joined_at ? ' • Joined at ' + new Date(entry.joined_at).toLocaleTimeString() : ''}`}
              />
              {entry.joined && (
                <Chip
                  label="Present"
                  color="success"
                  size="small"
                />
              )}
            </ListItem>
          ))}
        </List>
      </Collapse>
    </CardContent>
  </Card>
)}
```

5. **Add Outsider Card UI:**
```javascript
{/* Outsider Students Card */}
{outsiderSummary && outsiderSummary.total_outsiders > 0 && (
  <Card sx={{ mb: 2, bgcolor: 'warning.light' }}>
    <CardContent>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
        <WarningIcon sx={{ mr: 1, color: 'warning.dark' }} />
        <Typography variant="h6">
          Outsider Students
        </Typography>
        <Chip
          label={outsiderSummary.total_outsiders}
          color="warning"
          size="small"
          sx={{ ml: 'auto' }}
        />
      </Box>

      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        Students not in class roster
      </Typography>

      {/* Toggle Details Button */}
      <Button
        size="small"
        onClick={() => setShowOutsiderDetails(!showOutsiderDetails)}
        endIcon={showOutsiderDetails ? <ExpandLessIcon /> : <ExpandMoreIcon />}
      >
        {showOutsiderDetails ? 'Hide' : 'Show'} Outsider List
      </Button>

      {/* Detailed Outsider List */}
      <Collapse in={showOutsiderDetails}>
        <List dense sx={{ mt: 1 }}>
          {outsiderSummary.records.map((record) => (
            <ListItem
              key={record.id}
              sx={{
                bgcolor: 'background.paper',
                borderRadius: 1,
                mb: 0.5,
                border: '1px solid',
                borderColor: 'warning.main'
              }}
            >
              <ListItemIcon>
                <PersonOffIcon color="warning" />
              </ListItemIcon>
              <ListItemText
                primary={record.guest_name}
                secondary={`ID: ${record.student_school_id} • ${record.detection_reason}`}
              />
              <Chip
                label="Outsider"
                color="warning"
                size="small"
              />
            </ListItem>
          ))}
        </List>
      </Collapse>
    </CardContent>
  </Card>
)}
```

**Estimated Changes**: ~250 lines added

### 6.3 New Service Methods

#### File: `ata-frontend/src/services/quizService.js`

**Add New API Methods:**

```javascript
/**
 * Get attendance summary for a quiz session
 * @param {string} sessionId - The session ID
 * @returns {Promise<SessionAttendanceSummary>}
 */
async getSessionAttendance(sessionId) {
  const response = await api.get(`/api/quiz-sessions/${sessionId}/attendance`);
  return response.data;
}

/**
 * Get roster entries for a session
 * @param {string} sessionId - The session ID
 * @returns {Promise<QuizSessionRosterSummary>}
 */
async getSessionRoster(sessionId) {
  const response = await api.get(`/api/quiz-sessions/${sessionId}/roster`);
  return response.data;
}

/**
 * Get outsider students for a session
 * @param {string} sessionId - The session ID
 * @returns {Promise<OutsiderStudentSummary>}
 */
async getSessionOutsiders(sessionId) {
  const response = await api.get(`/api/quiz-sessions/${sessionId}/outsiders`);
  return response.data;
}

/**
 * Flag an outsider student as approved
 * @param {string} sessionId - The session ID
 * @param {string} outsiderId - The outsider record ID
 * @param {boolean} approved - Whether to approve
 * @param {string} notes - Optional teacher notes
 * @returns {Promise<void>}
 */
async flagOutsiderStudent(sessionId, outsiderId, approved, notes = null) {
  await api.put(`/api/quiz-sessions/${sessionId}/outsiders/${outsiderId}/flag`, {
    flagged_by_teacher: approved,
    teacher_notes: notes
  });
}
```

**Estimated Changes**: ~50 lines added

---

## 7. WEBSOCKET REAL-TIME UPDATES

### 7.1 Backend WebSocket Changes

#### File: `ata-backend/app/core/quiz_websocket.py`

**Add New Message Builder Functions:**

```python
def build_roster_updated_message(
    roster_summary: Dict,
    timestamp: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build message when roster status changes (student joins/leaves).

    Args:
        roster_summary: Dictionary with roster statistics
        timestamp: ISO timestamp (auto-generated if not provided)

    Returns:
        WebSocket message dictionary
    """
    return {
        "type": "roster_updated",
        "roster": roster_summary,
        "timestamp": timestamp or datetime.utcnow().isoformat()
    }


def build_outsider_detected_message(
    outsider_record: Dict,
    timestamp: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build message when an outsider student joins.

    Args:
        outsider_record: Dictionary with outsider student info
        timestamp: ISO timestamp

    Returns:
        WebSocket message dictionary
    """
    return {
        "type": "outsider_detected",
        "outsider": outsider_record,
        "timestamp": timestamp or datetime.utcnow().isoformat()
    }


def build_attendance_summary_message(
    attendance_data: Dict,
    timestamp: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build complete attendance summary message.

    Args:
        attendance_data: Full attendance summary
        timestamp: ISO timestamp

    Returns:
        WebSocket message dictionary
    """
    return {
        "type": "attendance_summary",
        "data": attendance_data,
        "timestamp": timestamp or datetime.utcnow().isoformat()
    }
```

**Estimated Changes**: ~60 lines added

#### File: `ata-backend/app/routers/quiz_websocket_router.py`

**Modify WebSocket Connect Handler:**

```python
@router.websocket("/ws/quiz-session/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    guest_token: Optional[str] = None,
    token: Optional[str] = None,
    db: Session = Depends(get_db)
):
    # ... existing authentication logic ...

    # AFTER successful connection
    await connection_manager.connect(
        session_id=session_id,
        websocket=websocket,
        role=role,
        client_id=client_id
    )

    # NEW: If participant joined and session has roster, update roster
    if role == ParticipantRole.PARTICIPANT and participant:
        # Check if session has class roster
        session = db_service.get_session_by_id(session_id)
        if session and session.class_id:
            # Update roster entry or create outsider record
            await handle_participant_roster_status(
                db=db,
                session_id=session_id,
                participant=participant
            )

    # ... existing message loop ...


async def handle_participant_roster_status(
    db: Session,
    session_id: str,
    participant: QuizParticipant
):
    """
    Check if participant is on roster and update accordingly.
    Broadcast roster/outsider status to hosts.
    """
    from app.services.quiz_roster_service import QuizRosterService

    roster_service = QuizRosterService(db)

    # Check roster status
    is_on_roster, roster_entry = roster_service.check_participant_roster_status(
        session_id=session_id,
        participant_id=str(participant.id),
        student_school_id=participant.student_id
    )

    if is_on_roster and roster_entry:
        # Update roster entry as joined
        roster_service.mark_roster_entry_joined(
            roster_entry_id=str(roster_entry.id),
            participant_id=str(participant.id)
        )

        # Broadcast roster update to hosts
        roster_summary = roster_service.get_roster_summary(session_id)
        message = build_roster_updated_message(roster_summary)
        await connection_manager.broadcast_to_hosts(session_id, message)

    else:
        # Create outsider record
        outsider_record = roster_service.create_outsider_record(
            session_id=session_id,
            participant_id=str(participant.id),
            student_school_id=participant.student_id or "UNKNOWN",
            guest_name=participant.guest_name or "Unknown Guest",
            detection_reason=_determine_detection_reason(participant, roster_entry)
        )

        # Broadcast outsider alert to hosts
        message = build_outsider_detected_message({
            "id": str(outsider_record.id),
            "guest_name": outsider_record.guest_name,
            "student_school_id": outsider_record.student_school_id,
            "detection_reason": outsider_record.detection_reason
        })
        await connection_manager.broadcast_to_hosts(session_id, message)
```

**Estimated Changes**: ~100 lines added

### 7.2 Frontend WebSocket Changes

#### File: `ata-frontend/src/pages/quizzes/QuizHost.jsx`

**Add WebSocket Message Handlers:**

```javascript
const handleWebSocketMessage = (message) => {
  console.log('WebSocket message received:', message);

  switch (message.type) {
    // ... existing cases ...

    case 'roster_updated':
      // Update roster summary state
      setRosterSummary(message.roster);
      break;

    case 'outsider_detected':
      // Show notification and update outsider list
      showNotification(
        `Outsider student joined: ${message.outsider.guest_name} (ID: ${message.outsider.student_school_id})`,
        'warning'
      );
      loadAttendanceData();
      break;

    case 'attendance_summary':
      // Full attendance refresh
      setAttendanceSummary(message.data);
      setRosterSummary(message.data.roster_summary);
      setOutsiderSummary(message.data.outsider_summary);
      break;

    default:
      console.log('Unknown message type:', message.type);
  }
};
```

**Add Notification System:**

```javascript
const [notifications, setNotifications] = useState([]);

const showNotification = (message, severity = 'info') => {
  const id = Date.now();
  setNotifications(prev => [...prev, { id, message, severity }]);

  // Auto-dismiss after 5 seconds
  setTimeout(() => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  }, 5000);
};

// In JSX, add Snackbar component
<Box>
  {notifications.map(notification => (
    <Snackbar
      key={notification.id}
      open={true}
      autoHideDuration={5000}
      anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
    >
      <Alert severity={notification.severity} sx={{ width: '100%' }}>
        {notification.message}
      </Alert>
    </Snackbar>
  ))}
</Box>
```

**Estimated Changes**: ~50 lines added

---

## 8. API ENDPOINTS CHANGES

### 8.1 New Endpoints to Add

#### File: `ata-backend/app/routers/quiz_session_router.py`

**Endpoint 1: Get Session Attendance**

```python
@router.get(
    "/{session_id}/attendance",
    response_model=SessionAttendanceSummary,
    summary="Get attendance summary for a session"
)
async def get_session_attendance(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get complete attendance summary including roster and outsider students.

    - **session_id**: Quiz session ID

    Returns:
    - Roster summary (expected vs. joined)
    - Outsider student list
    - Combined metrics
    """
    from app.services.quiz_roster_service import QuizRosterService

    # Verify ownership
    session = db_service.get_session_by_id(session_id)
    if not session or str(session.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Session not found")

    roster_service = QuizRosterService(db)
    attendance_data = roster_service.get_attendance_summary(
        session_id=session_id,
        user_id=str(current_user.id)
    )

    return attendance_data
```

**Endpoint 2: Get Session Roster**

```python
@router.get(
    "/{session_id}/roster",
    response_model=QuizSessionRosterSummary,
    summary="Get roster entries for a session"
)
async def get_session_roster(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get expected student roster for a quiz session.

    - **session_id**: Quiz session ID

    Returns list of expected students with join status.
    """
    from app.services.quiz_roster_service import QuizRosterService

    # Verify ownership
    session = db_service.get_session_by_id(session_id)
    if not session or str(session.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Session not found")

    roster_service = QuizRosterService(db)
    roster_summary = roster_service.get_roster_summary(session_id)

    return roster_summary
```

**Endpoint 3: Get Session Outsiders**

```python
@router.get(
    "/{session_id}/outsiders",
    response_model=OutsiderStudentSummary,
    summary="Get outsider students for a session"
)
async def get_session_outsiders(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of outsider students who joined but weren't on roster.

    - **session_id**: Quiz session ID

    Returns list of outsider student records.
    """
    from app.services.quiz_roster_service import QuizRosterService

    # Verify ownership
    session = db_service.get_session_by_id(session_id)
    if not session or str(session.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Session not found")

    roster_service = QuizRosterService(db)
    outsider_summary = roster_service.get_outsider_summary(session_id)

    return outsider_summary
```

**Endpoint 4: Flag Outsider Student**

```python
@router.put(
    "/{session_id}/outsiders/{outsider_id}/flag",
    summary="Flag or approve an outsider student"
)
async def flag_outsider_student(
    session_id: str,
    outsider_id: str,
    flagged_by_teacher: bool = Body(...),
    teacher_notes: Optional[str] = Body(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark an outsider student as approved or flagged.

    - **session_id**: Quiz session ID
    - **outsider_id**: Outsider record ID
    - **flagged_by_teacher**: True to approve, False to unflag
    - **teacher_notes**: Optional notes from teacher
    """
    from app.services.quiz_roster_service import QuizRosterService

    # Verify ownership
    session = db_service.get_session_by_id(session_id)
    if not session or str(session.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Session not found")

    roster_service = QuizRosterService(db)
    roster_service.flag_outsider_student(
        outsider_id=outsider_id,
        flagged_by_teacher=flagged_by_teacher,
        teacher_notes=teacher_notes
    )

    return {"message": "Outsider student flagged successfully"}
```

**Endpoint 5: Sync Roster from Class**

```python
@router.post(
    "/{session_id}/roster/sync",
    summary="Sync roster from class"
)
async def sync_roster_from_class(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually sync roster from the associated class.
    Useful if class roster changed after session creation.

    - **session_id**: Quiz session ID
    """
    from app.services.quiz_roster_service import QuizRosterService

    # Verify ownership
    session = db_service.get_session_by_id(session_id)
    if not session or str(session.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.class_id:
        raise HTTPException(
            status_code=400,
            detail="Session has no associated class"
        )

    roster_service = QuizRosterService(db)
    roster_service.sync_roster_from_class(
        session_id=session_id,
        class_id=session.class_id,
        user_id=str(current_user.id)
    )

    return {"message": "Roster synced successfully"}
```

**Estimated Changes**: ~200 lines added

### 8.2 Modify Existing Endpoints

#### Modify: `POST /api/quiz-sessions` (Create Session)

**File**: `ata-backend/app/routers/quiz_session_router.py`

**Change**: Initialize roster when session is created

```python
@router.post("/", response_model=QuizSessionResponse)
async def create_quiz_session(
    quiz_id: str = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new quiz session with room code."""

    # ... existing validation ...

    # Create session
    session = quiz_service.create_session_with_room_code(
        db=db,
        quiz_id=quiz_id,
        user_id=str(current_user.id)
    )

    # NEW: If quiz has class_id, initialize roster
    if session.class_id:
        from app.services.quiz_roster_service import QuizRosterService
        roster_service = QuizRosterService(db)
        roster_service.initialize_roster_from_class(
            session_id=str(session.id),
            class_id=session.class_id,
            user_id=str(current_user.id)
        )

    return session
```

**Estimated Changes**: ~10 lines added

---

## 9. SERVICE LAYER CHANGES

### 9.1 New Service: Quiz Roster Service

#### File: `ata-backend/app/services/quiz_roster_service.py` (NEW FILE)

**Purpose**: Handle all roster-related business logic

```python
"""
Quiz Roster Service

Handles business logic for:
- Initializing rosters from class memberships
- Tracking student attendance (joined/absent)
- Detecting and managing outsider students
- Providing roster summaries and analytics
"""

from typing import Optional, List, Tuple, Dict
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from app.db.models.quiz_models import (
    QuizSession,
    QuizParticipant,
    QuizSessionRoster,
    QuizOutsiderStudent
)
from app.db.models.class_student_models import Student, StudentClassMembership
from app.services.database_helpers.class_student_repository_sql import ClassStudentRepository


class QuizRosterService:
    """Service for managing quiz session rosters and attendance."""

    def __init__(self, db: Session):
        self.db = db
        self.class_repo = ClassStudentRepository(db)


    # ========== ROSTER INITIALIZATION ==========

    def initialize_roster_from_class(
        self,
        session_id: str,
        class_id: str,
        user_id: str
    ) -> int:
        """
        Initialize roster from class membership.
        Creates roster entries for all students in the class.

        Args:
            session_id: Quiz session ID
            class_id: Class ID to pull roster from
            user_id: User ID (for authorization)

        Returns:
            Number of roster entries created

        Raises:
            ValueError: If session/class not found or user doesn't own class
        """
        # Verify session exists
        session = self.db.query(QuizSession).filter(
            QuizSession.id == session_id
        ).first()
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Get students in class (with ownership check)
        students = self.class_repo.get_students_by_class_id(
            class_id=class_id,
            user_id=user_id
        )

        if not students:
            return 0

        # Create roster entries
        entries_created = 0
        for student in students:
            roster_entry = QuizSessionRoster(
                id=str(uuid.uuid4()),
                session_id=session_id,
                student_id=student.id,
                student_name=student.name,
                student_school_id=student.studentId,
                enrollment_status="expected",
                joined=False
            )
            self.db.add(roster_entry)
            entries_created += 1

        self.db.commit()
        return entries_created


    def sync_roster_from_class(
        self,
        session_id: str,
        class_id: str,
        user_id: str
    ) -> Dict[str, int]:
        """
        Re-sync roster from current class membership.
        Handles students added/dropped after initial roster creation.

        Args:
            session_id: Quiz session ID
            class_id: Class ID
            user_id: User ID (for authorization)

        Returns:
            Dictionary with counts: {added: X, dropped: Y, unchanged: Z}
        """
        # Get current roster
        current_roster = self.db.query(QuizSessionRoster).filter(
            QuizSessionRoster.session_id == session_id
        ).all()
        current_student_ids = {entry.student_id for entry in current_roster}

        # Get current class students
        students = self.class_repo.get_students_by_class_id(
            class_id=class_id,
            user_id=user_id
        )
        class_student_ids = {student.id for student in students}

        # Calculate differences
        added_ids = class_student_ids - current_student_ids
        dropped_ids = current_student_ids - class_student_ids

        # Add new students
        for student in students:
            if student.id in added_ids:
                roster_entry = QuizSessionRoster(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    student_id=student.id,
                    student_name=student.name,
                    student_school_id=student.studentId,
                    enrollment_status="added",
                    joined=False
                )
                self.db.add(roster_entry)

        # Mark dropped students
        for entry in current_roster:
            if entry.student_id in dropped_ids:
                entry.enrollment_status = "dropped"

        self.db.commit()

        return {
            "added": len(added_ids),
            "dropped": len(dropped_ids),
            "unchanged": len(current_student_ids & class_student_ids)
        }


    # ========== ATTENDANCE TRACKING ==========

    def mark_roster_entry_joined(
        self,
        roster_entry_id: str,
        participant_id: str
    ) -> None:
        """
        Mark a roster entry as joined and link to participant.

        Args:
            roster_entry_id: Roster entry ID
            participant_id: Quiz participant ID
        """
        roster_entry = self.db.query(QuizSessionRoster).filter(
            QuizSessionRoster.id == roster_entry_id
        ).first()

        if not roster_entry:
            raise ValueError(f"Roster entry {roster_entry_id} not found")

        roster_entry.joined = True
        roster_entry.joined_at = datetime.utcnow()
        roster_entry.participant_id = participant_id

        # Also update participant record
        participant = self.db.query(QuizParticipant).filter(
            QuizParticipant.id == participant_id
        ).first()

        if participant:
            participant.is_outsider = False
            participant.roster_entry_id = roster_entry_id

        self.db.commit()


    def check_participant_roster_status(
        self,
        session_id: str,
        participant_id: str,
        student_school_id: Optional[str]
    ) -> Tuple[bool, Optional[QuizSessionRoster]]:
        """
        Check if a participant is on the expected roster.

        Args:
            session_id: Quiz session ID
            participant_id: Participant ID
            student_school_id: Student's school ID (e.g., "S12345")

        Returns:
            Tuple of (is_on_roster: bool, roster_entry: QuizSessionRoster or None)
        """
        if not student_school_id:
            return (False, None)

        # Look for roster entry with matching student_school_id
        roster_entry = self.db.query(QuizSessionRoster).filter(
            QuizSessionRoster.session_id == session_id,
            QuizSessionRoster.student_school_id == student_school_id
        ).first()

        if roster_entry:
            return (True, roster_entry)
        else:
            return (False, None)


    # ========== OUTSIDER MANAGEMENT ==========

    def create_outsider_record(
        self,
        session_id: str,
        participant_id: str,
        student_school_id: str,
        guest_name: str,
        detection_reason: str
    ) -> QuizOutsiderStudent:
        """
        Create a record for an outsider student.

        Args:
            session_id: Quiz session ID
            participant_id: Participant ID
            student_school_id: Student's school ID
            guest_name: Name they provided
            detection_reason: Why they were flagged

        Returns:
            Created QuizOutsiderStudent record
        """
        outsider = QuizOutsiderStudent(
            id=str(uuid.uuid4()),
            session_id=session_id,
            student_school_id=student_school_id,
            guest_name=guest_name,
            participant_id=participant_id,
            detection_reason=detection_reason,
            flagged_by_teacher=False
        )
        self.db.add(outsider)

        # Mark participant as outsider
        participant = self.db.query(QuizParticipant).filter(
            QuizParticipant.id == participant_id
        ).first()
        if participant:
            participant.is_outsider = True

        self.db.commit()
        return outsider


    def flag_outsider_student(
        self,
        outsider_id: str,
        flagged_by_teacher: bool,
        teacher_notes: Optional[str] = None
    ) -> None:
        """
        Flag or approve an outsider student.

        Args:
            outsider_id: Outsider record ID
            flagged_by_teacher: True to approve, False to unflag
            teacher_notes: Optional notes
        """
        outsider = self.db.query(QuizOutsiderStudent).filter(
            QuizOutsiderStudent.id == outsider_id
        ).first()

        if not outsider:
            raise ValueError(f"Outsider {outsider_id} not found")

        outsider.flagged_by_teacher = flagged_by_teacher
        if teacher_notes:
            outsider.teacher_notes = teacher_notes

        self.db.commit()


    # ========== SUMMARY & ANALYTICS ==========

    def get_roster_summary(
        self,
        session_id: str
    ) -> Dict:
        """
        Get roster summary for a session.

        Args:
            session_id: Quiz session ID

        Returns:
            Dictionary with roster statistics and entries
        """
        entries = self.db.query(QuizSessionRoster).filter(
            QuizSessionRoster.session_id == session_id
        ).order_by(QuizSessionRoster.student_name).all()

        total_expected = len(entries)
        total_joined = sum(1 for e in entries if e.joined)
        total_absent = total_expected - total_joined
        join_rate = (total_joined / total_expected * 100) if total_expected > 0 else 0

        return {
            "total_expected": total_expected,
            "total_joined": total_joined,
            "total_absent": total_absent,
            "join_rate": round(join_rate, 2),
            "entries": [
                {
                    "id": str(e.id),
                    "session_id": e.session_id,
                    "student_id": e.student_id,
                    "student_name": e.student_name,
                    "student_school_id": e.student_school_id,
                    "enrollment_status": e.enrollment_status,
                    "joined": e.joined,
                    "joined_at": e.joined_at.isoformat() if e.joined_at else None,
                    "participant_id": e.participant_id,
                    "created_at": e.created_at.isoformat()
                }
                for e in entries
            ]
        }


    def get_outsider_summary(
        self,
        session_id: str
    ) -> Dict:
        """
        Get outsider student summary for a session.

        Args:
            session_id: Quiz session ID

        Returns:
            Dictionary with outsider statistics and records
        """
        outsiders = self.db.query(QuizOutsiderStudent).filter(
            QuizOutsiderStudent.session_id == session_id
        ).order_by(QuizOutsiderStudent.created_at).all()

        return {
            "total_outsiders": len(outsiders),
            "records": [
                {
                    "id": str(o.id),
                    "session_id": o.session_id,
                    "student_school_id": o.student_school_id,
                    "guest_name": o.guest_name,
                    "participant_id": o.participant_id,
                    "detection_reason": o.detection_reason,
                    "flagged_by_teacher": o.flagged_by_teacher,
                    "teacher_notes": o.teacher_notes,
                    "created_at": o.created_at.isoformat()
                }
                for o in outsiders
            ]
        }


    def get_attendance_summary(
        self,
        session_id: str,
        user_id: str
    ) -> Dict:
        """
        Get complete attendance summary (roster + outsiders).

        Args:
            session_id: Quiz session ID
            user_id: User ID (for authorization)

        Returns:
            Complete attendance summary dictionary
        """
        # Get session and class info
        session = self.db.query(QuizSession).filter(
            QuizSession.id == session_id
        ).first()

        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Authorization check
        if str(session.user_id) != str(user_id):
            raise PermissionError("Not authorized to access this session")

        # Get class name if applicable
        class_name = None
        if session.class_id:
            class_obj = self.class_repo.get_class_by_id(
                class_id=session.class_id,
                user_id=user_id
            )
            if class_obj:
                class_name = class_obj.name

        # Get roster and outsider summaries
        roster_summary = None
        if session.class_id:
            roster_summary = self.get_roster_summary(session_id)

        outsider_summary = self.get_outsider_summary(session_id)

        # Get total participant count
        total_participants = self.db.query(QuizParticipant).filter(
            QuizParticipant.session_id == session_id
        ).count()

        active_participants = self.db.query(QuizParticipant).filter(
            QuizParticipant.session_id == session_id,
            QuizParticipant.is_active == True
        ).count()

        return {
            "session_id": session_id,
            "class_id": session.class_id,
            "class_name": class_name,
            "roster_summary": roster_summary,
            "outsider_summary": outsider_summary,
            "total_participants": total_participants,
            "active_participants": active_participants
        }
```

**Estimated Lines**: ~450 lines (new file)

### 9.2 Modify Existing Service

#### File: `ata-backend/app/services/quiz_service.py`

**Modify Function**: `create_session_with_room_code`

**Add**: Copy `class_id` from quiz to session

```python
def create_session_with_room_code(
    db: Session,
    quiz_id: str,
    user_id: str
) -> QuizSession:
    """
    Create a new quiz session with a unique room code.

    Args:
        db: Database session
        quiz_id: Quiz ID
        user_id: User ID (must own the quiz)

    Returns:
        Created QuizSession

    Raises:
        ValueError: If quiz not found or user doesn't own it
    """
    # Verify quiz exists and user owns it
    quiz = db_service.get_quiz_by_id(quiz_id, user_id)
    if not quiz:
        raise ValueError(f"Quiz {quiz_id} not found or access denied")

    # Generate unique room code
    room_code = generate_unique_room_code(db)

    # Create session
    session = QuizSession(
        id=str(uuid.uuid4()),
        quiz_id=quiz_id,
        user_id=uuid.UUID(user_id),
        room_code=room_code,
        status="waiting",
        class_id=quiz.class_id  # NEW: Copy class_id from quiz
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return session
```

**Estimated Changes**: 1 line added

---

## 10. REPOSITORY LAYER CHANGES

### 10.1 New Repository Methods

#### File: `ata-backend/app/services/database_helpers/quiz_session_repository_sql.py`

**Add Methods for Roster Queries:**

```python
# ========== ROSTER QUERIES ==========

def get_roster_entries_by_session(
    self,
    session_id: str
) -> List[QuizSessionRoster]:
    """Get all roster entries for a session."""
    return (
        self.db.query(QuizSessionRoster)
        .filter(QuizSessionRoster.session_id == session_id)
        .order_by(QuizSessionRoster.student_name)
        .all()
    )


def get_roster_entry_by_student(
    self,
    session_id: str,
    student_school_id: str
) -> Optional[QuizSessionRoster]:
    """Get roster entry for a specific student in a session."""
    return (
        self.db.query(QuizSessionRoster)
        .filter(
            QuizSessionRoster.session_id == session_id,
            QuizSessionRoster.student_school_id == student_school_id
        )
        .first()
    )


def get_absent_students(
    self,
    session_id: str
) -> List[QuizSessionRoster]:
    """Get all students who haven't joined yet."""
    return (
        self.db.query(QuizSessionRoster)
        .filter(
            QuizSessionRoster.session_id == session_id,
            QuizSessionRoster.joined == False
        )
        .order_by(QuizSessionRoster.student_name)
        .all()
    )


def get_joined_students(
    self,
    session_id: str
) -> List[QuizSessionRoster]:
    """Get all students who have joined."""
    return (
        self.db.query(QuizSessionRoster)
        .filter(
            QuizSessionRoster.session_id == session_id,
            QuizSessionRoster.joined == True
        )
        .order_by(QuizSessionRoster.joined_at.desc())
        .all()
    )


# ========== OUTSIDER QUERIES ==========

def get_outsider_students_by_session(
    self,
    session_id: str
) -> List[QuizOutsiderStudent]:
    """Get all outsider students for a session."""
    return (
        self.db.query(QuizOutsiderStudent)
        .filter(QuizOutsiderStudent.session_id == session_id)
        .order_by(QuizOutsiderStudent.created_at)
        .all()
    )


def get_outsider_by_participant(
    self,
    participant_id: str
) -> Optional[QuizOutsiderStudent]:
    """Get outsider record by participant ID."""
    return (
        self.db.query(QuizOutsiderStudent)
        .filter(QuizOutsiderStudent.participant_id == participant_id)
        .first()
    )


def get_unflagged_outsiders(
    self,
    session_id: str
) -> List[QuizOutsiderStudent]:
    """Get outsiders not yet reviewed by teacher."""
    return (
        self.db.query(QuizOutsiderStudent)
        .filter(
            QuizOutsiderStudent.session_id == session_id,
            QuizOutsiderStudent.flagged_by_teacher == False
        )
        .all()
    )


# ========== COMBINED QUERIES ==========

def get_participants_with_roster_status(
    self,
    session_id: str
) -> List[Dict]:
    """
    Get all participants with their roster status.
    Includes both roster and outsider participants.
    """
    from sqlalchemy import outerjoin

    participants = (
        self.db.query(QuizParticipant)
        .filter(QuizParticipant.session_id == session_id)
        .all()
    )

    result = []
    for p in participants:
        result.append({
            "participant_id": str(p.id),
            "display_name": p.guest_name or f"Student {p.student_id}",
            "student_school_id": p.student_id,
            "is_outsider": p.is_outsider,
            "is_on_roster": bool(p.roster_entry_id),
            "joined_at": p.joined_at,
            "score": p.score,
            "correct_answers": p.correct_answers,
            "is_active": p.is_active
        })

    return result
```

**Estimated Changes**: ~150 lines added

---

## 11. TESTING STRATEGY

### 11.1 Unit Tests

#### Test File: `ata-backend/tests/services/test_quiz_roster_service.py` (NEW)

**Test Cases:**

```python
import pytest
from app.services.quiz_roster_service import QuizRosterService
from app.db.models.quiz_models import QuizSession, QuizParticipant
from app.db.models.class_student_models import Class, Student, StudentClassMembership


class TestQuizRosterService:
    """Unit tests for QuizRosterService"""

    def test_initialize_roster_from_class(self, db_session, sample_class, sample_students):
        """Test roster initialization from class"""
        service = QuizRosterService(db_session)
        session = create_test_session(db_session, class_id=sample_class.id)

        count = service.initialize_roster_from_class(
            session_id=str(session.id),
            class_id=sample_class.id,
            user_id=str(sample_class.user_id)
        )

        assert count == len(sample_students)

        roster_entries = service.get_roster_summary(str(session.id))
        assert roster_entries["total_expected"] == len(sample_students)
        assert roster_entries["total_joined"] == 0


    def test_mark_roster_entry_joined(self, db_session, sample_roster_entry, sample_participant):
        """Test marking a roster entry as joined"""
        service = QuizRosterService(db_session)

        service.mark_roster_entry_joined(
            roster_entry_id=str(sample_roster_entry.id),
            participant_id=str(sample_participant.id)
        )

        # Verify roster entry updated
        db_session.refresh(sample_roster_entry)
        assert sample_roster_entry.joined == True
        assert sample_roster_entry.joined_at is not None
        assert sample_roster_entry.participant_id == str(sample_participant.id)

        # Verify participant updated
        db_session.refresh(sample_participant)
        assert sample_participant.is_outsider == False
        assert sample_participant.roster_entry_id == str(sample_roster_entry.id)


    def test_check_participant_roster_status_on_roster(self, db_session, sample_roster_entry):
        """Test checking if participant is on roster"""
        service = QuizRosterService(db_session)

        is_on_roster, roster_entry = service.check_participant_roster_status(
            session_id=sample_roster_entry.session_id,
            participant_id="test_participant",
            student_school_id=sample_roster_entry.student_school_id
        )

        assert is_on_roster == True
        assert roster_entry.id == sample_roster_entry.id


    def test_check_participant_roster_status_outsider(self, db_session, sample_session):
        """Test checking outsider participant"""
        service = QuizRosterService(db_session)

        is_on_roster, roster_entry = service.check_participant_roster_status(
            session_id=str(sample_session.id),
            participant_id="test_participant",
            student_school_id="UNKNOWN_STUDENT"
        )

        assert is_on_roster == False
        assert roster_entry is None


    def test_create_outsider_record(self, db_session, sample_session, sample_participant):
        """Test creating outsider record"""
        service = QuizRosterService(db_session)

        outsider = service.create_outsider_record(
            session_id=str(sample_session.id),
            participant_id=str(sample_participant.id),
            student_school_id="OUTSIDER123",
            guest_name="Outsider Student",
            detection_reason="not_in_class"
        )

        assert outsider.session_id == str(sample_session.id)
        assert outsider.student_school_id == "OUTSIDER123"
        assert outsider.detection_reason == "not_in_class"

        # Verify participant marked as outsider
        db_session.refresh(sample_participant)
        assert sample_participant.is_outsider == True


    def test_sync_roster_from_class_add_student(self, db_session, sample_class, sample_session):
        """Test syncing roster when new student added to class"""
        service = QuizRosterService(db_session)

        # Initialize with 2 students
        initial_students = create_test_students(db_session, sample_class, count=2)
        service.initialize_roster_from_class(
            session_id=str(sample_session.id),
            class_id=sample_class.id,
            user_id=str(sample_class.user_id)
        )

        # Add a new student to class
        new_student = create_test_student(db_session, sample_class)

        # Sync roster
        result = service.sync_roster_from_class(
            session_id=str(sample_session.id),
            class_id=sample_class.id,
            user_id=str(sample_class.user_id)
        )

        assert result["added"] == 1
        assert result["dropped"] == 0
        assert result["unchanged"] == 2

        # Verify roster updated
        roster_summary = service.get_roster_summary(str(sample_session.id))
        assert roster_summary["total_expected"] == 3


    def test_get_attendance_summary(self, db_session, sample_session_with_roster):
        """Test getting complete attendance summary"""
        service = QuizRosterService(db_session)

        summary = service.get_attendance_summary(
            session_id=str(sample_session_with_roster.id),
            user_id=str(sample_session_with_roster.user_id)
        )

        assert "roster_summary" in summary
        assert "outsider_summary" in summary
        assert "total_participants" in summary
        assert summary["session_id"] == str(sample_session_with_roster.id)
```

**Estimated Lines**: ~200 lines (new file)

### 11.2 Integration Tests

#### Test File: `ata-backend/tests/routers/test_quiz_session_router.py`

**Add Test Cases:**

```python
def test_get_session_attendance(client, auth_headers, sample_session_with_roster):
    """Test GET /api/quiz-sessions/{session_id}/attendance"""
    response = client.get(
        f"/api/quiz-sessions/{sample_session_with_roster.id}/attendance",
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()

    assert "roster_summary" in data
    assert "outsider_summary" in data
    assert data["session_id"] == str(sample_session_with_roster.id)


def test_get_session_roster(client, auth_headers, sample_session_with_roster):
    """Test GET /api/quiz-sessions/{session_id}/roster"""
    response = client.get(
        f"/api/quiz-sessions/{sample_session_with_roster.id}/roster",
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()

    assert "total_expected" in data
    assert "total_joined" in data
    assert "entries" in data
    assert isinstance(data["entries"], list)


def test_sync_roster_from_class(client, auth_headers, sample_session_with_class):
    """Test POST /api/quiz-sessions/{session_id}/roster/sync"""
    response = client.post(
        f"/api/quiz-sessions/{sample_session_with_class.id}/roster/sync",
        headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Roster synced successfully"


def test_flag_outsider_student(client, auth_headers, sample_outsider_record):
    """Test PUT /api/quiz-sessions/{session_id}/outsiders/{outsider_id}/flag"""
    response = client.put(
        f"/api/quiz-sessions/{sample_outsider_record.session_id}/outsiders/{sample_outsider_record.id}/flag",
        headers=auth_headers,
        json={
            "flagged_by_teacher": True,
            "teacher_notes": "Approved - transfer student"
        }
    )

    assert response.status_code == 200
```

**Estimated Changes**: ~80 lines added

### 11.3 Frontend Tests

#### Test File: `ata-frontend/src/pages/quizzes/__tests__/QuizHost.test.jsx`

**Add Test Cases:**

```javascript
describe('QuizHost - Roster Display', () => {
  test('displays roster summary when session has class', async () => {
    const mockSession = {
      id: 'session1',
      class_id: 'class1',
      status: 'waiting'
    };

    const mockRosterSummary = {
      total_expected: 10,
      total_joined: 7,
      total_absent: 3,
      join_rate: 70,
      entries: [
        {
          id: 'entry1',
          student_name: 'John Doe',
          student_school_id: 'S001',
          joined: true,
          joined_at: '2024-11-17T10:00:00Z'
        },
        {
          id: 'entry2',
          student_name: 'Jane Smith',
          student_school_id: 'S002',
          joined: false
        }
      ]
    };

    quizService.getSessionAttendance.mockResolvedValue({
      roster_summary: mockRosterSummary,
      outsider_summary: { total_outsiders: 0, records: [] }
    });

    render(<QuizHost sessionId="session1" />);

    await waitFor(() => {
      expect(screen.getByText('Class Roster')).toBeInTheDocument();
      expect(screen.getByText('7/10')).toBeInTheDocument();
      expect(screen.getByText('John Doe')).toBeInTheDocument();
      expect(screen.getByText('Jane Smith')).toBeInTheDocument();
    });
  });


  test('displays outsider students when detected', async () => {
    const mockOutsiderSummary = {
      total_outsiders: 2,
      records: [
        {
          id: 'outsider1',
          guest_name: 'Unknown Student',
          student_school_id: 'S999',
          detection_reason: 'not_in_class'
        }
      ]
    };

    quizService.getSessionAttendance.mockResolvedValue({
      roster_summary: null,
      outsider_summary: mockOutsiderSummary
    });

    render(<QuizHost sessionId="session1" />);

    await waitFor(() => {
      expect(screen.getByText('Outsider Students')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText('Unknown Student')).toBeInTheDocument();
    });
  });


  test('handles WebSocket roster update', async () => {
    const { rerender } = render(<QuizHost sessionId="session1" />);

    // Simulate WebSocket message
    const wsMessage = {
      type: 'roster_updated',
      roster: {
        total_expected: 10,
        total_joined: 8,
        total_absent: 2,
        join_rate: 80
      }
    };

    act(() => {
      mockWebSocket.simulateMessage(wsMessage);
    });

    await waitFor(() => {
      expect(screen.getByText('8/10')).toBeInTheDocument();
    });
  });
});
```

**Estimated Changes**: ~100 lines added

---

## 12. MIGRATION STRATEGY

### 12.1 Database Migration Steps

**Step 1: Create Migration File**
```bash
cd ata-backend
alembic revision -m "add_quiz_roster_tracking"
```

**Step 2: Edit Migration File**
- Copy content from Section 4.3 above
- Test migration on development database
```bash
alembic upgrade head
```

**Step 3: Verify Schema**
```bash
psql -d ata_dev -c "\d quiz_session_roster"
psql -d ata_dev -c "\d quiz_outsider_students"
```

**Step 4: Production Deployment**
```bash
# Run migration on staging first
alembic -c alembic_staging.ini upgrade head

# Verify no errors, then production
alembic -c alembic_production.ini upgrade head
```

### 12.2 Backwards Compatibility

**Existing Quizzes:**
- Quizzes without `class_id` will continue to work normally
- Roster tracking simply won't activate for them
- Frontend handles `class_id === null` gracefully

**Existing Sessions:**
- Active sessions won't have roster data
- New columns default to appropriate values (NULL, FALSE)
- No disruption to ongoing quizzes

**Rollback Plan:**
```bash
# If issues arise, rollback migration
alembic downgrade -1

# Verify data integrity
psql -d ata_production -c "SELECT COUNT(*) FROM quiz_participants"
```

### 12.3 Data Migration

**No data migration needed** - all new features are opt-in:
- New tables start empty
- Existing data remains unchanged
- Feature activates only when teacher selects a class

---

## 13. IMPLEMENTATION ROADMAP

### 13.1 Sprint 1: Database & Backend Core (5-6 hours)

**Day 1-2:**
- [ ] Create database migration file
- [ ] Add new SQLAlchemy models (QuizSessionRoster, QuizOutsiderStudent)
- [ ] Modify existing models (QuizSession, QuizParticipant)
- [ ] Run migration on dev database
- [ ] Create Pydantic schemas for new models
- [ ] Write unit tests for models

**Deliverables:**
- Migration file completed
- Database schema updated
- Models tested

### 13.2 Sprint 2: Service Layer (6-7 hours)

**Day 3-4:**
- [ ] Create `QuizRosterService` with all methods
- [ ] Add roster initialization logic
- [ ] Implement roster checking and outsider detection
- [ ] Add repository query methods
- [ ] Write comprehensive unit tests for service
- [ ] Test edge cases (empty rosters, class changes, etc.)

**Deliverables:**
- QuizRosterService fully functional
- All service methods tested
- Repository queries optimized

### 13.3 Sprint 3: API Endpoints (4-5 hours)

**Day 5:**
- [ ] Add 5 new endpoints to quiz_session_router
- [ ] Modify session creation endpoint
- [ ] Add authentication and authorization checks
- [ ] Write integration tests for all endpoints
- [ ] Test with Postman/curl

**Deliverables:**
- All endpoints functional
- API documentation updated
- Postman collection created

### 13.4 Sprint 4: WebSocket Integration (3-4 hours)

**Day 6:**
- [ ] Add WebSocket message builders
- [ ] Modify WebSocket connection handler
- [ ] Implement roster update broadcasts
- [ ] Add outsider detection broadcasts
- [ ] Test real-time updates with multiple clients

**Deliverables:**
- Real-time updates working
- WebSocket messages tested
- Multi-client scenarios validated

### 13.5 Sprint 5: Frontend - Quiz Creation (2-3 hours)

**Day 7:**
- [ ] Add class selection to QuizBuilder
- [ ] Load classes on component mount
- [ ] Update quiz creation payload
- [ ] Test quiz creation with/without class
- [ ] Add frontend validation

**Deliverables:**
- Class selection working
- Quiz creation tested
- UI polished

### 13.6 Sprint 6: Frontend - Roster Display (6-7 hours)

**Day 8-9:**
- [ ] Add roster card to QuizHost
- [ ] Implement roster entry list
- [ ] Add outsider card
- [ ] Connect to API endpoints
- [ ] Add WebSocket handlers
- [ ] Implement real-time updates
- [ ] Add notification system
- [ ] Write frontend tests

**Deliverables:**
- Roster display fully functional
- Outsider detection working
- Real-time updates smooth
- UI responsive and polished

### 13.7 Sprint 7: Testing & Polish (3-4 hours)

**Day 10:**
- [ ] End-to-end testing (full quiz flow)
- [ ] Performance testing (100 students)
- [ ] Cross-browser testing
- [ ] Mobile responsiveness
- [ ] Fix bugs and edge cases
- [ ] Code review and refactoring
- [ ] Documentation updates

**Deliverables:**
- All tests passing
- Performance benchmarks met
- Documentation complete

### 13.8 Sprint 8: Deployment (2-3 hours)

**Day 11:**
- [ ] Deploy backend to staging
- [ ] Run database migration
- [ ] Deploy frontend to staging
- [ ] QA testing on staging
- [ ] Fix any deployment issues
- [ ] Deploy to production
- [ ] Monitor for errors

**Deliverables:**
- Feature live in production
- No critical bugs
- Monitoring in place

---

## 14. RISK ASSESSMENT

### 14.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Database migration fails in production | Low | High | Test thoroughly on staging; have rollback plan ready |
| WebSocket broadcast performance degrades | Medium | Medium | Optimize queries; add indexes; test with 100+ students |
| Frontend state management becomes complex | Medium | Low | Use clear state structure; add comments; write tests |
| Roster sync conflicts with concurrent updates | Low | Medium | Use database transactions; add pessimistic locking |
| Outsider detection false positives | Medium | Low | Allow teacher to approve; add clear detection reasons |

### 14.2 Product Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Teachers don't understand new features | Medium | Medium | Add tooltips, help text, and onboarding guide |
| Students join with wrong student ID | High | Low | Add confirmation step; show student name after ID entry |
| Roster changes between quiz creation and session | Medium | Low | Add manual sync button; show warning if roster outdated |
| Too many outsiders clutter the UI | Low | Low | Add filter/collapse options; paginate if needed |

### 14.3 Schedule Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Implementation takes longer than estimated | Medium | Medium | Prioritize core features; defer nice-to-haves |
| Bugs discovered during QA | High | Low | Budget extra time for bug fixes; test incrementally |
| Dependencies delayed (other features) | Low | Low | Feature is mostly isolated; minimal dependencies |

---

## 15. FILE INVENTORY

### 15.1 Files to Modify

**Backend:**
1. `ata-backend/app/db/models/quiz_models.py` - Add QuizSessionRoster, QuizOutsiderStudent models
2. `ata-backend/app/db/models/class_student_models.py` - Add relationship to QuizSession
3. `ata-backend/app/models/quiz_model.py` - Add Pydantic schemas
4. `ata-backend/app/routers/quiz_session_router.py` - Add endpoints, modify session creation
5. `ata-backend/app/routers/quiz_websocket_router.py` - Add roster update broadcasts
6. `ata-backend/app/core/quiz_websocket.py` - Add message builders
7. `ata-backend/app/services/quiz_service.py` - Modify session creation
8. `ata-backend/app/services/database_helpers/quiz_session_repository_sql.py` - Add queries

**Frontend:**
9. `ata-frontend/src/pages/quizzes/QuizBuilder.jsx` - Add class selection
10. `ata-frontend/src/pages/quizzes/QuizHost.jsx` - Add roster/outsider display
11. `ata-frontend/src/services/quizService.js` - Add API methods

**Database:**
12. `ata-backend/alembic/versions/YYYYMMDD_add_quiz_roster_tracking.py` - Migration

**Tests:**
13. `ata-backend/tests/services/test_quiz_roster_service.py` - Unit tests
14. `ata-backend/tests/routers/test_quiz_session_router.py` - Integration tests
15. `ata-frontend/src/pages/quizzes/__tests__/QuizHost.test.jsx` - Frontend tests

### 15.2 New Files to Create

1. `ata-backend/app/services/quiz_roster_service.py` - New service (~450 lines)
2. `ata-backend/tests/services/test_quiz_roster_service.py` - Tests (~200 lines)
3. Database migration file (~150 lines)

**Total New Code**: ~800 lines
**Total Modified Code**: ~600 lines
**Total Code Changes**: ~1,400 lines

---

## 16. SUCCESS METRICS

### 16.1 Functional Metrics

- [ ] Teachers can select class during quiz creation
- [ ] Roster loads automatically when session starts
- [ ] Teacher sees real-time join status for all students
- [ ] Outsider students are detected and listed separately
- [ ] All roster data persists for analytics
- [ ] WebSocket updates propagate within 200ms

### 16.2 Performance Metrics

- [ ] Roster loading completes in < 500ms for 100 students
- [ ] Leaderboard queries remain under 100ms
- [ ] Page load time increases by < 10%
- [ ] WebSocket message size remains reasonable (< 10KB)

### 16.3 Quality Metrics

- [ ] Test coverage > 80% for new code
- [ ] Zero critical bugs in production
- [ ] All API endpoints documented
- [ ] Frontend accessibility standards met

---

## 17. NEXT STEPS

### Before Starting Implementation

1. **Review this plan** with team and stakeholders
2. **Approve database schema** changes
3. **Set up development environment** with test database
4. **Create GitHub issues** for each sprint
5. **Schedule daily standups** during implementation

### During Implementation

1. **Commit frequently** with clear messages
2. **Write tests first** (TDD approach)
3. **Review code** before merging
4. **Update documentation** as you go
5. **Test on staging** after each sprint

### After Implementation

1. **Monitor production** for errors
2. **Gather user feedback** from teachers
3. **Iterate on UX** based on feedback
4. **Plan Phase 2** enhancements (see below)

---

## 18. FUTURE ENHANCEMENTS (Phase 2)

**Not in Scope for Initial Release:**

1. **Email/SMS Reminders**: Notify absent students
2. **Attendance Reports**: Export roster data to CSV
3. **Historical Analytics**: Track student participation trends
4. **Auto-Enrollment**: Automatically add students when they join first time
5. **Roster Comparison View**: Side-by-side expected vs. actual
6. **Late Join Penalties**: Reduce points for late joiners
7. **Roster Locking**: Prevent joins after quiz starts
8. **Student Self-Registration**: Students can register their own IDs
9. **Multiple Class Support**: Quiz can be for multiple classes
10. **Roster Import**: Upload CSV of students

---

## CONCLUSION

This implementation plan provides a **comprehensive roadmap** for adding class-based student roster tracking to the ATA quiz system. The feature builds on existing patterns (assessment outsider tracking) and infrastructure (WebSocket, class/student models), minimizing risk and complexity.

**Key Takeaways:**
- **Scope**: Medium complexity, 15-20 development hours
- **Risk**: Low (building on proven patterns)
- **Value**: High (enables attendance tracking and analytics)
- **Dependencies**: Minimal (mostly isolated feature)

**Ready to proceed** with database migration as first step!

---

**Document Version**: 1.0
**Last Updated**: 2025-11-17
**Author**: Claude (AI Assistant)
**Status**: Planning Phase - Awaiting Approval
