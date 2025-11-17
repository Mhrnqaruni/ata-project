# Quiz Creation Frontend Flow - Comprehensive Analysis

## Overview
The quiz creation system uses a **3-step wizard pattern** with Material-UI components. Teachers can create quizzes, add/edit questions, configure settings, and publish for live sessions.

## Current Quiz Creation UI Flow

### Entry Point
- **Route**: `/quizzes/new` (new quiz) or `/quizzes/{quizId}/edit` (edit existing)
- **Component**: `/src/pages/quizzes/QuizBuilder.jsx`
- **Navigation**: "Create New Quiz" button on `/quizzes` page

### Wizard Steps

```
Step 0: Quiz Information
    ↓
Step 1: Questions
    ↓
Step 2: Settings
    ↓
Save/Publish
```

## Component Structure & Hierarchy

```
Quizzes (Main Quiz List Page)
├── EmptyState (when no quizzes exist)
├── QuizCard (individual quiz card)
│   └── Menu (with Edit, Duplicate, Delete, Publish options)
│
QuizBuilder (Quiz Creation/Edit Page)
├── Stepper Navigation
├── Step 0: QuizInformation Section (TextField for title/description)
├── Step 1: Questions Section (QuestionEditor components)
│   └── QuestionEditor (repeated for each question)
│       ├── Question Type Selector (FormControl + Select)
│       ├── Points Input (TextField)
│       ├── Time Limit Input (TextField)
│       ├── Question Text (TextField)
│       ├── Options Handler
│       │   ├── Multiple Choice: Switch + TextField for each option
│       │   ├── True/False: Select dropdown
│       │   ├── Short Answer: Multiline TextField for keywords
│       │   └── Poll: TextFields (no correct answer)
│       └── Question Controls (Duplicate, Delete buttons)
├── Step 2: Quiz Settings Section
│   ├── Shuffle Questions (FormControlLabel + Switch)
│   ├── Shuffle Options (FormControlLabel + Switch)
│   ├── Show Correct Answers (FormControlLabel + Switch)
│   └── Allow Review (FormControlLabel + Switch)
├── Header Actions
│   ├── Back Button
│   ├── Save Draft Button
│   └── Publish Quiz Button
└── Dialogs
    └── Publish Confirmation Dialog

Classes (Related Component)
├── ClassCard (individual class card)
├── AddClassModal (for creating classes)
└── ClassEditModal (for editing classes)
```

## Form Fields Captured During Quiz Creation

### Step 0: Quiz Information
| Field | Type | Required | Validation | Current Value |
|-------|------|----------|-----------|---------------|
| `title` | string | Yes | min=1, max=200 chars | quizTitle state |
| `description` | string | No | max=5000 chars | quizDescription state |
| `class_id` | string | No | Foreign key to classes | **NOT CURRENTLY IMPLEMENTED** |

### Step 1: Questions (Array of Question Objects)

#### Per Question Object:
| Field | Type | Required | Varies By Type |
|-------|------|----------|-----------------|
| `question_type` | enum | Yes | multiple_choice \| true_false \| short_answer \| poll |
| `question_text` | string | Yes | Text shown to students |
| `options` | array[string] | Conditional | MC, Poll only |
| `correct_answer` | array | Conditional | MC: [index], TF: [boolean], SA: [keywords], Poll: [] |
| `points` | integer | Yes | 0-100, polls default to 0 |
| `time_limit_seconds` | integer | Yes | 5-300 seconds, defaults to 30 |
| `order_index` | integer | Yes | Auto-assigned, 0-indexed |

### Step 2: Quiz Settings
| Field | Type | Current Value |
|-------|------|----------------|
| `shuffle_questions` | boolean | quizSettings.shuffle_questions |
| `shuffle_options` | boolean | quizSettings.shuffle_options |
| `show_correct_answers` | boolean | quizSettings.show_correct_answers |
| `allow_review` | boolean | quizSettings.allow_review |

## State Management Pattern

### QuizBuilder Component State:

```javascript
// Step/UI State
const [activeStep, setActiveStep] = useState(0);
const [isSaving, setIsSaving] = useState(false);
const [error, setError] = useState(null);
const [publishDialog, setPublishDialog] = useState(false);

// Quiz Metadata
const [quizTitle, setQuizTitle] = useState('');
const [quizDescription, setQuizDescription] = useState('');

// Quiz Settings
const [quizSettings, setQuizSettings] = useState({
  shuffle_questions: false,
  shuffle_options: false,
  show_correct_answers: true,
  allow_review: true
});

// Questions Array
const [questions, setQuestions] = useState([
  {
    question_type: 'multiple_choice',
    question_text: '',
    options: ['', '', '', ''],
    correct_answer: [],
    points: 10,
    time_limit_seconds: 30,
    order_index: 0
  }
]);
```

**State Update Patterns:**
- Direct state setters (setText, setSettings)
- Array mapping for questions (handleQuestionChange)
- Functional updates for complex operations

## API Endpoints Called During Quiz Creation

### Endpoint: POST /api/quizzes
**Purpose**: Create new quiz with optional questions

**Request Body**:
```json
{
  "title": "string",
  "description": "string (optional)",
  "settings": {
    "shuffle_questions": boolean,
    "shuffle_options": boolean,
    "show_correct_answers": boolean,
    "allow_review": boolean
  },
  "questions": [
    {
      "question_type": "multiple_choice|true_false|short_answer|poll",
      "question_text": "string",
      "options": ["string"],
      "correct_answer": [any],
      "points": integer,
      "time_limit_seconds": integer,
      "order_index": integer
    }
  ],
  "class_id": "string (optional)" // <- FIELD EXISTS BUT NOT USED IN FRONTEND
}
```

**Response**:
```json
{
  "id": "quiz_uuid",
  "title": "string",
  "description": "string",
  "user_id": "uuid",
  "status": "draft|published|completed|archived",
  "settings": object,
  "questions": [...],
  "created_at": "datetime",
  "updated_at": "datetime",
  "class_id": "string|null"
}
```

### Endpoint: PUT /api/quizzes/{quiz_id}
**Purpose**: Update existing quiz (title, description, settings)

**Request Body** (all optional):
```json
{
  "title": "string",
  "description": "string",
  "settings": object,
  "status": "string",
  "class_id": "string"
}
```

### Endpoint: POST /api/quizzes/{quiz_id}/publish
**Purpose**: Publish quiz (move from draft to published)

**Preconditions**:
- Quiz must have at least 1 question
- All questions must be valid

### Related Question Endpoints:
- POST `/api/quizzes/{quiz_id}/questions` - Add single question
- PUT `/api/quizzes/{quiz_id}/questions/{question_id}` - Update question
- DELETE `/api/quizzes/{quiz_id}/questions/{question_id}` - Delete question
- PUT `/api/quizzes/{quiz_id}/questions/reorder` - Reorder questions

## Where to Add Class Selection

### Current Gap
The backend Quiz model already has `class_id` field and supports it, but the frontend doesn't capture it during creation.

### Recommended Implementation Location

**Option 1: Add to Step 0 (Quiz Information)**
```
Step 0: Quiz Information
├── Title TextField [Required]
├── Description TextField [Optional]
└── Class Selection Dropdown [Optional]  <-- NEW
    └── Dropdown with list of user's classes
        ├── No Class Selected (default)
        ├── Class A
        ├── Class B
        └── Class C
```

**Option 2: New Step Between Step 0 and Step 1**
```
Step 0: Quiz Information
  ↓
Step 0.5: Class & Settings (NEW)
  ├── Class Selection
  ├── Quiz Settings (moved from Step 2)
  ↓
Step 1: Questions (was Step 1)
  ↓
Step 2: Review (was Step 2)
```

### Implementation Changes Required

#### 1. Add State for Classes
```javascript
const [classes, setClasses] = useState([]);
const [selectedClassId, setSelectedClassId] = useState(null);
const [isLoadingClasses, setIsLoadingClasses] = useState(false);
```

#### 2. Load Classes on Component Mount
```javascript
useEffect(() => {
  const loadClasses = async () => {
    try {
      const data = await classService.getAllClasses();
      setClasses(data);
    } catch (err) {
      console.error("Failed to load classes:", err);
    }
  };
  loadClasses();
}, []);
```

#### 3. Update Quiz Data Object on Save
```javascript
const quizData = {
  title: quizTitle,
  description: quizDescription,
  class_id: selectedClassId,  // <- ADD THIS
  settings: quizSettings,
  questions: questions.map((q, index) => ({ ...q, order_index: index }))
};
```

#### 4. Add FormControl in Step 0
```jsx
<FormControl fullWidth sx={{ mb: 3 }}>
  <InputLabel>Class (Optional)</InputLabel>
  <Select
    value={selectedClassId || ''}
    label="Class (Optional)"
    onChange={(e) => setSelectedClassId(e.target.value || null)}
    disabled={isLoadingClasses}
  >
    <MenuItem value="">No Class</MenuItem>
    {classes.map((cls) => (
      <MenuItem key={cls.id} value={cls.id}>
        {cls.name}
      </MenuItem>
    ))}
  </Select>
</FormControl>
```

## Service Layer (quizService.js)

### Main CRUD Methods:
```javascript
quizService.getAllQuizzes()           // GET /api/quizzes
quizService.getQuizById(quizId)       // GET /api/quizzes/{id}
quizService.createQuiz(quizData)      // POST /api/quizzes
quizService.updateQuiz(quizId, data)  // PUT /api/quizzes/{id}
quizService.deleteQuiz(quizId)        // DELETE /api/quizzes/{id}
quizService.duplicateQuiz(quizId)     // POST /api/quizzes/{id}/duplicate
quizService.publishQuiz(quizId)       // POST /api/quizzes/{id}/publish
```

## Key Features & Validations

### Frontend Validation (validateQuiz function):
- Quiz title required
- At least 1 question required
- Question text required
- Multiple choice: 2+ options, all with text, correct answer selected
- True/False: correct answer selected
- Short Answer: at least 1 keyword
- Poll: 2+ options, no correct answer
- Each question: points 0-100, time 5-300 seconds

### Automatic Behavior:
- Auto-load quiz data if editing
- Auto-navigate to edit view after creation
- Auto-focus on next step after saving
- Auto-reset form when closing duplicate dialog
- Default settings on new quiz

## Form Pattern Examples in Codebase

### Similar Pattern: AddClassModal
Located at: `/src/components/classes/AddClassModal.jsx`
- Uses tabbed interface
- Form submission via handler
- Error/loading state management
- Dialog with cancel/submit buttons

### Similar Pattern: Assessment Creation Wizard
Located at: `/src/pages/assessments/NewAssessmentV2.jsx`
- Multi-step wizard pattern
- Step-by-step navigation
- Complex nested forms

## Database Schema (Backend)

### Quiz Table
```sql
quizzes {
  id: STRING PRIMARY KEY,
  user_id: UUID FOREIGN KEY (required),
  class_id: STRING FOREIGN KEY (nullable),  -- <-- Already exists!
  title: VARCHAR(200) NOT NULL,
  description: TEXT,
  settings: JSONB,
  status: VARCHAR(20) DEFAULT 'draft',
  created_at: TIMESTAMP DEFAULT now(),
  updated_at: TIMESTAMP DEFAULT now(),
  deleted_at: TIMESTAMP (soft delete)
}
```

## Recommended Implementation Priority

1. **Phase 1 - Basic Class Selection**
   - Add class dropdown to Step 0
   - Include in API request
   - Load classes on component mount

2. **Phase 2 - Enhanced UX**
   - Show selected class in quiz summary
   - Add class filtering on Quizzes page
   - Show quiz in class details

3. **Phase 3 - Advanced Features**
   - Bulk class assignment
   - Class-specific quiz templates
   - Automatic student enrollment

## File Locations Summary

| Component | Path |
|-----------|------|
| Main Quiz List | `/src/pages/Quizzes.jsx` |
| Quiz Builder (Create/Edit) | `/src/pages/quizzes/QuizBuilder.jsx` |
| Quiz Service | `/src/services/quizService.js` |
| Class Service | `/src/services/classService.js` |
| API Client | `/src/services/api.js` |
| Add Class Modal | `/src/components/classes/AddClassModal.jsx` |
| Quiz Router (Backend) | `/app/routers/quiz_router.py` |
| Quiz Model Schema | `/app/models/quiz_model.py` |
| Quiz DB Model | `/app/db/models/quiz_models.py` |

