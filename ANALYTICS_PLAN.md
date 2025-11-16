# QUIZ ANALYTICS SYSTEM - IMPLEMENTATION PLAN

## PHASE 2: Backend Analytics Endpoints

### Endpoint 1: Session Analytics Summary
**Route:** `GET /api/quiz-sessions/{session_id}/analytics`
**Purpose:** Overall session statistics and summary

**Query Logic:**
```python
# Join: quiz_sessions + quiz_participants + quiz_responses + quiz_questions
# Aggregate:
- Total participants (COUNT quiz_participants)
- Completion rate (COUNT is_active participants)
- Average score (AVG quiz_participants.score)
- Median score (PERCENTILE_CONT)
- High/low scores (MAX/MIN quiz_participants.score)
- Average time (AVG quiz_participants.total_time_ms)
- Duration (ended_at - started_at)
```

**Response Structure:**
```json
{
  "session": {
    "id": "uuid",
    "quiz_title": "Python Basics",
    "quiz_id": "uuid",
    "room_code": "ABC123",
    "status": "completed",
    "started_at": "2025-01-15T10:30:00Z",
    "ended_at": "2025-01-15T11:15:00Z",
    "duration_minutes": 45
  },
  "participation": {
    "total_joined": 25,
    "total_completed": 23,
    "completion_rate": 0.92,
    "total_questions": 10
  },
  "scores": {
    "average": 78.5,
    "median": 80.0,
    "std_deviation": 12.3,
    "high_score": 95.0,
    "high_scorer_name": "Sarah Johnson",
    "high_scorer_id": "12345",
    "low_score": 45.0,
    "distribution": {
      "90-100": 5,
      "80-89": 8,
      "70-79": 6,
      "60-69": 3,
      "0-59": 3
    }
  },
  "timing": {
    "average_time_seconds": 750,
    "fastest_time_seconds": 480,
    "slowest_time_seconds": 1200
  }
}
```

---

### Endpoint 2: Question Statistics
**Route:** `GET /api/quiz-sessions/{session_id}/question-stats`
**Purpose:** Question-level performance breakdown

**Query Logic:**
```python
# For each question:
# JOIN quiz_questions + quiz_responses
# Aggregate per question:
- Total responses (COUNT quiz_responses)
- Correct count (COUNT WHERE is_correct = true)
- Success rate (correct_count / total_responses)
- Average time (AVG time_taken_ms)
- Answer distribution (GROUP BY answer, COUNT)
```

**Response Structure:**
```json
{
  "questions": [
    {
      "question_id": "uuid",
      "order_index": 0,
      "question_text": "What is a variable?",
      "question_type": "multiple_choice",
      "points": 10,
      "options": ["A variable", "A function", "A class", "A module"],
      "correct_answer": ["A variable"],

      "statistics": {
        "total_responses": 25,
        "correct_count": 22,
        "incorrect_count": 3,
        "success_rate": 0.88,
        "average_time_seconds": 15,
        "difficulty": "easy"
      },

      "answer_distribution": [
        {"answer": "A variable", "count": 22, "percentage": 88},
        {"answer": "A function", "count": 2, "percentage": 8},
        {"answer": "A class", "count": 1, "percentage": 4}
      ],

      "top_wrong_answer": {
        "answer": "A function",
        "count": 2
      }
    }
  ]
}
```

---

### Endpoint 3: Participant Details
**Route:** `GET /api/quiz-sessions/{session_id}/participants-details`
**Purpose:** Individual student responses and performance

**Query Logic:**
```python
# For each participant:
# JOIN quiz_participants + quiz_responses + quiz_questions
# Include:
- Participant info (name, student_id, rank)
- Overall stats (score, correct_answers, time)
- Question-by-question breakdown (each response)
```

**Response Structure:**
```json
{
  "participants": [
    {
      "participant_id": "uuid",
      "display_name": "Sarah Johnson",
      "student_id": "12345",
      "is_guest": true,

      "overall": {
        "rank": 1,
        "score": 95,
        "max_score": 100,
        "percentage": 95.0,
        "correct_answers": 9,
        "incorrect_answers": 1,
        "total_time_seconds": 600,
        "average_time_per_question": 60
      },

      "question_responses": [
        {
          "question_id": "uuid",
          "question_text": "What is a variable?",
          "question_order": 1,
          "question_points": 10,
          "student_answer": ["A variable"],
          "correct_answer": ["A variable"],
          "is_correct": true,
          "points_earned": 10,
          "time_taken_seconds": 12,
          "answered_at": "2025-01-15T10:32:00Z"
        },
        {
          "question_id": "uuid",
          "question_text": "Explain list comprehension",
          "question_order": 2,
          "question_points": 10,
          "student_answer": ["A loop"],
          "correct_answer": ["List comprehension"],
          "is_correct": false,
          "points_earned": 0,
          "time_taken_seconds": 25,
          "answered_at": "2025-01-15T10:33:00Z"
        }
      ]
    }
  ]
}
```

---

### Endpoint 4: CSV Export
**Route:** `GET /api/quiz-sessions/{session_id}/export/csv`
**Purpose:** Download complete results as CSV file

**CSV Format:**
```csv
Rank,Name,Student ID,Score,Percentage,Correct,Incorrect,Time (min),Q1,Q2,Q3,Q4,Q5
1,Sarah Johnson,12345,95,95%,9,1,10.0,✓,✓,✗,✓,✓
2,Mike Chen,12346,90,90%,9,1,12.0,✓,✓,✓,✓,✓
3,Emma Davis,12347,85,85%,8,2,11.0,✓,✗,✓,✓,✓
```

**Headers:**
- `Content-Type: text/csv`
- `Content-Disposition: attachment; filename="quiz_results_ABC123.csv"`

---

## PHASE 3: Frontend Analytics Page

### Component Structure
```
src/pages/quizzes/
├── QuizAnalytics.jsx              // Main page component
└── components/
    ├── SessionSummaryCards.jsx    // 4 stat cards at top
    ├── QuestionBreakdown.jsx      // Question-level table
    ├── ParticipantTable.jsx       // Sortable results table
    ├── ParticipantDetailModal.jsx // Individual student modal
    └── AnalyticsCharts.jsx        // Charts with recharts
```

### Changes to Existing Files

**1. src/App.jsx**
```jsx
// Add analytics route
<Route path="/quizzes/:quizId/analytics/:sessionId"
       element={<QuizAnalytics />} />
```

**2. src/pages/quizzes/QuizList.jsx**
```jsx
// Add Review button for completed quizzes
{quiz.status === 'completed' && (
  <Button
    variant="outlined"
    onClick={() => navigate(`/quizzes/${quiz.id}/analytics/${quiz.last_session_id}`)}
  >
    Review Results
  </Button>
)}
```

**3. src/services/quizService.js**
```javascript
// Add analytics API calls
getSessionAnalytics: async (sessionId) => {...},
getQuestionStats: async (sessionId) => {...},
getParticipantDetails: async (sessionId) => {...},
exportSessionCSV: async (sessionId) => {...}
```

### Frontend Features

#### 1. Session Summary Cards (Top Section)
```
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
│ 👥 Participants     │ │ ✅ Completion       │ │ 📊 Average Score    │ │ ⏱️ Average Time     │
│                     │ │                     │ │                     │ │                     │
│ 25 / 30 joined      │ │ 92% completed       │ │ 78.5 / 100          │ │ 12 min 30 sec       │
│ (83%)               │ │ (23 / 25)           │ │                     │ │                     │
└─────────────────────┘ └─────────────────────┘ └─────────────────────┘ └─────────────────────┘
```

#### 2. Question Breakdown Table
```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ # │ Question                       │ Difficulty │ Success Rate │ Avg Time │ Details │
├───┼────────────────────────────────┼────────────┼──────────────┼──────────┼─────────┤
│ 1 │ What is a variable?            │ Easy ✅    │ 88% (22/25)  │ 15s      │ [View]  │
│ 2 │ Explain list comprehension     │ Hard ⚠️    │ 48% (12/25)  │ 45s      │ [View]  │
│ 3 │ What is a loop?                │ Medium 🟡  │ 72% (18/25)  │ 25s      │ [View]  │
└───┴────────────────────────────────┴────────────┴──────────────┴──────────┴─────────┘
```

#### 3. Participant Results Table (Sortable)
```
┌────────────────────────────────────────────────────────────────────────────────┐
│ Rank │ Name           │ Student ID │ Score │ % │ Correct │ Time  │ Actions  │
├──────┼────────────────┼────────────┼───────┼───┼─────────┼───────┼──────────┤
│  1   │ Sarah Johnson  │ 12345      │ 95    │95%│ 9/10    │ 10:00 │ [Detail] │
│  2   │ Mike Chen      │ 12346      │ 90    │90%│ 9/10    │ 12:00 │ [Detail] │
│  3   │ Emma Davis     │ 12347      │ 85    │85%│ 8/10    │ 11:00 │ [Detail] │
│ ...  │ ...            │ ...        │ ...   │...│ ...     │ ...   │ ...      │
└──────┴────────────────┴────────────┴───────┴───┴─────────┴───────┴──────────┘

Sort by: [Rank ▼] [Name] [Score] [Time]
```

#### 4. Individual Student Detail Modal
```
┌──────────────────────────────────────────────────────────────────┐
│ Student: Sarah Johnson (ID: 12345)                     [X Close] │
├──────────────────────────────────────────────────────────────────┤
│ Overall Performance:  95 / 100 points  (Rank #1)                │
│ Correct: 9 / 10  |  Time: 10:00                                 │
│                                                                  │
│ Question-by-Question Breakdown:                                 │
│ ┌──────────────────────────────────────────────────────────────┐│
│ │ Q1: What is a variable?              ✅ Correct (10 pts)     ││
│ │ Their answer: "A variable"           Time: 12s               ││
│ │                                                              ││
│ │ Q2: Explain list comprehension       ❌ Wrong (0 pts)       ││
│ │ Their answer: "A loop"               Time: 25s               ││
│ │ Correct answer: "List comprehension"                        ││
│ │                                                              ││
│ │ Q3: What is a function?              ✅ Correct (10 pts)     ││
│ │ Their answer: "A function"           Time: 15s               ││
│ └──────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────┘
```

#### 5. Charts Section (using recharts)
```
┌─────────────────────────────────────┐  ┌─────────────────────────────────────┐
│ Score Distribution                  │  │ Question Difficulty                 │
│                                     │  │                                     │
│    █                                │  │      88%    48%    72%    64%       │
│    █                                │  │       █      █      █      █        │
│    █  █                             │  │       █      █      █      █        │
│    █  █  █                          │  │       █      █      █      █        │
│ ───┴──┴──┴──┴──┴───                │  │      Q1     Q2     Q3     Q4        │
│ 0-59 60-69 70-79 80-89 90-100       │  │                                     │
└─────────────────────────────────────┘  └─────────────────────────────────────┘
```

#### 6. Export Buttons
```
┌──────────────────────────────────────────────────────────────────┐
│ Export Options:                                                  │
│ [📥 Download CSV] [📄 Print Report] [📧 Email Results]          │
└──────────────────────────────────────────────────────────────────┘
```

---

## DETAILED TODO LIST

### Backend Implementation (6-8 hours)

- [ ] **Create analytics service functions**
  - [ ] `get_session_analytics_summary(session_id, user_id, db)`
  - [ ] `get_question_statistics(session_id, user_id, db)`
  - [ ] `get_participant_details(session_id, user_id, db)`
  - [ ] `calculate_score_distribution(participants)`
  - [ ] `calculate_difficulty_rating(success_rate)`

- [ ] **Create analytics endpoints in quiz_session_router.py**
  - [ ] GET `/api/quiz-sessions/{id}/analytics`
  - [ ] GET `/api/quiz-sessions/{id}/question-stats`
  - [ ] GET `/api/quiz-sessions/{id}/participants-details`
  - [ ] GET `/api/quiz-sessions/{id}/export/csv`

- [ ] **Add Pydantic models for responses**
  - [ ] `SessionAnalyticsResponse`
  - [ ] `QuestionStatisticsResponse`
  - [ ] `ParticipantDetailsResponse`

- [ ] **Add authorization checks**
  - [ ] Verify user owns the quiz/session
  - [ ] Only allow access to completed sessions

### Frontend Implementation (8-10 hours)

- [ ] **Install dependencies**
  - [ ] `npm install recharts` (for charts)
  - [ ] `npm install @mui/icons-material` (already installed)
  - [ ] `npm install file-saver` (for CSV download)

- [ ] **Update service layer (quizService.js)**
  - [ ] Add `getSessionAnalytics(sessionId)`
  - [ ] Add `getQuestionStats(sessionId)`
  - [ ] Add `getParticipantDetails(sessionId)`
  - [ ] Add `exportSessionCSV(sessionId)`

- [ ] **Update routing (App.jsx)**
  - [ ] Add route: `/quizzes/:quizId/analytics/:sessionId`

- [ ] **Update QuizList.jsx**
  - [ ] Add "Review" button for completed quizzes
  - [ ] Store last_session_id when session ends
  - [ ] Different card styling for completed quizzes

- [ ] **Create main analytics page**
  - [ ] Create `QuizAnalytics.jsx`
  - [ ] Load all analytics data on mount
  - [ ] Handle loading states
  - [ ] Handle error states
  - [ ] Add breadcrumb navigation

- [ ] **Create SessionSummaryCards component**
  - [ ] 4 MUI Card components in Grid
  - [ ] Participants card
  - [ ] Completion rate card
  - [ ] Average score card
  - [ ] Average time card
  - [ ] Use CountUp animation

- [ ] **Create QuestionBreakdown component**
  - [ ] MUI Table with questions
  - [ ] Show question text (truncated)
  - [ ] Show difficulty badge
  - [ ] Show success rate
  - [ ] Show average time
  - [ ] "View Details" button expands row

- [ ] **Create QuestionDetailRow component**
  - [ ] Expandable row under each question
  - [ ] Show answer distribution chart
  - [ ] Show most common wrong answers
  - [ ] Show timing statistics

- [ ] **Create ParticipantTable component**
  - [ ] MUI DataGrid or Table with sorting
  - [ ] Rank, Name, Student ID, Score, %, Correct, Time columns
  - [ ] "View Detail" button for each row
  - [ ] Export selected button
  - [ ] Search/filter functionality

- [ ] **Create ParticipantDetailModal component**
  - [ ] MUI Dialog (full-screen on mobile)
  - [ ] Student header with overall stats
  - [ ] Question-by-question breakdown
  - [ ] Show their answer vs correct answer
  - [ ] Green check / red X icons
  - [ ] Time taken per question
  - [ ] Previous/Next student navigation

- [ ] **Create AnalyticsCharts component**
  - [ ] Score distribution bar chart
  - [ ] Question difficulty comparison chart
  - [ ] Time vs Score scatter plot
  - [ ] Use recharts library

- [ ] **Add export functionality**
  - [ ] CSV export button
  - [ ] Generate CSV from data
  - [ ] Trigger browser download
  - [ ] Show success notification

### Testing Checklist (2-3 hours)

- [ ] **Backend testing**
  - [ ] Test analytics endpoint with completed session
  - [ ] Test with session with no participants
  - [ ] Test with session with partial completion
  - [ ] Test authorization (only owner can access)
  - [ ] Test CSV export format

- [ ] **Frontend testing**
  - [ ] Test loading states
  - [ ] Test error states (session not found)
  - [ ] Test with different screen sizes
  - [ ] Test sorting/filtering in tables
  - [ ] Test modal navigation
  - [ ] Test CSV download
  - [ ] Test with real quiz data

- [ ] **End-to-end testing**
  - [ ] Create quiz with 5 questions
  - [ ] Run session with 5 students
  - [ ] Students answer with varying correctness
  - [ ] Teacher ends quiz
  - [ ] Verify status changes to "completed"
  - [ ] Click "Review" button
  - [ ] Verify all stats are correct
  - [ ] Verify charts render correctly
  - [ ] Download CSV and verify data
  - [ ] Test individual student details

---

## ESTIMATED TIME BREAKDOWN

| Phase | Task | Hours |
|-------|------|-------|
| **Phase 2** | Backend analytics service functions | 2-3 |
| | Backend API endpoints | 2-3 |
| | Pydantic models & validation | 1 |
| | CSV export functionality | 1 |
| **Phase 3** | Service layer & routing | 1 |
| | QuizList updates | 1 |
| | Main analytics page setup | 2 |
| | Summary cards component | 1-2 |
| | Question breakdown component | 2-3 |
| | Participant table component | 2-3 |
| | Detail modal component | 2 |
| | Charts component | 2-3 |
| | Export functionality | 1 |
| **Testing** | Backend & Frontend testing | 2-3 |
| **TOTAL** | | **20-30 hours** |

---

## SUCCESS CRITERIA

✅ **Backend:**
- [ ] All 4 analytics endpoints return correct data
- [ ] CSV export downloads properly formatted file
- [ ] Only session owner can access analytics
- [ ] Handles edge cases (no participants, incomplete sessions)

✅ **Frontend:**
- [ ] "Review" button appears on completed quizzes
- [ ] Analytics page loads and displays all sections
- [ ] All statistics match backend calculations
- [ ] Charts render correctly
- [ ] Tables are sortable and searchable
- [ ] Individual student details show correct responses
- [ ] CSV export works
- [ ] Responsive design (mobile + desktop)

✅ **Integration:**
- [ ] Complete quiz flow works end-to-end
- [ ] Status transitions: published → completed
- [ ] All data persists correctly
- [ ] No console errors
- [ ] Performance is acceptable (< 2s page load)

---

## NEXT STEPS

I'm ready to start implementing! Would you like me to:

1. **Option A:** Start with Phase 2 (Backend) - Build all 4 analytics endpoints
2. **Option B:** Start with Phase 3 (Frontend) - Build the analytics UI (assuming endpoints exist)
3. **Option C:** Build both phases sequentially (backend first, then frontend)

Let me know and I'll begin implementation! 🚀
