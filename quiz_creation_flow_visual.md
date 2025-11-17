# Quiz Creation Frontend Flow - Visual Guides & Code Examples

## User Journey Flow Diagram

```
START: User on Quizzes Page (/quizzes)
  |
  └─> Click "Create New Quiz" Button
        |
        └─> Navigate to /quizzes/new (QuizBuilder Component)
              |
              ├─> Load Component (useEffect)
              │   └─> Fetch classes via classService.getAllClasses()
              │
              ├─> STEP 0: Quiz Information (Title & Description)
              │   ├─> User enters quiz title
              │   ├─> User enters description
              │   ├─> [NEW] User selects class (optional)
              │   └─> Click "Next: Add Questions"
              │
              ├─> STEP 1: Add Questions
              │   ├─> Click "Add Question"
              │   │   └─> Creates new question object with defaults
              │   │
              │   ├─> For each question:
              │   │   ├─> Select question type
              │   │   ├─> Enter question text
              │   │   ├─> Configure options/answers based on type
              │   │   ├─> Set points (0-100)
              │   │   ├─> Set time limit (5-300 seconds)
              │   │   └─> [Duplicate/Delete buttons]
              │   │
              │   └─> Click "Next: Settings"
              │
              ├─> STEP 2: Quiz Settings
              │   ├─> Toggle: Shuffle Questions
              │   ├─> Toggle: Shuffle Answer Options
              │   ├─> Toggle: Show Correct Answers After Each Question
              │   ├─> Toggle: Allow Participants to Review Answers
              │   └─> Click "Save Quiz" or "Publish Quiz"
              │
              ├─> SAVE ACTION
              │   ├─> Validate quiz data (validateQuiz function)
              │   │   └─> Check: title, questions count, question validity
              │   │
              │   ├─> If new quiz:
              │   │   └─> POST /api/quizzes (with all data including class_id)
              │   │       └─> Response: Quiz object with ID
              │   │       └─> Navigate to /quizzes/{quizId}/edit
              │   │
              │   └─> If editing:
              │       └─> PUT /api/quizzes/{quizId} (with updates)
              │           └─> Update local state
              │
              ├─> PUBLISH ACTION
              │   ├─> Show confirmation dialog
              │   ├─> If confirmed:
              │   │   ├─> Save quiz first (if new)
              │   │   └─> POST /api/quizzes/{quizId}/publish
              │   │       └─> Redirect to /quizzes
              │   └─> If cancelled:
              │       └─> Stay on current view
              │
              └─> Back to Quizzes List Page (/quizzes)
                  └─> Quiz appears in list with status
                      ├─> Draft: Shows "Edit Quiz" button
                      └─> Published: Shows "Start Session" button
```

## Question Type Decision Tree

```
Question Type Selection
├─ MULTIPLE_CHOICE (☑️)
│  ├─ Needs 2-6 options
│  ├─ Needs exactly 1 correct answer (index-based)
│  ├─ Correct answer selection via Switch control
│  ├─ Points: 0-100 (default 10)
│  └─ UI: Option A [✓] [Delete]
│         Option B [ ] [Delete]
│         ...
│         [+ Add Option] (if < 6)
│
├─ TRUE_FALSE (✓✗)
│  ├─ No options needed
│  ├─ Correct answer: True or False (boolean)
│  ├─ Correct answer selection via dropdown
│  ├─ Points: 0-100 (default 10)
│  └─ UI: [Select dropdown] "True" / "False"
│
├─ SHORT_ANSWER (✍️)
│  ├─ No options
│  ├─ Correct answer: Array of keywords (case-insensitive)
│  ├─ Keywords: one per line OR comma-separated
│  ├─ Points: 0-100 (default 10)
│  └─ UI: Multiline TextField
│         "Paris
│          france
│          european capital"
│
└─ POLL (📊 - No scoring)
   ├─ Needs 2-10 options
   ├─ NO correct answer (always [])
   ├─ Points: 0 (forced)
   ├─ For feedback/engagement only
   └─ UI: Option A [Delete]
          Option B [Delete]
          ...
```

## Component Lifecycle

### Component Mount (Initial Load)
```
QuizBuilder Component Mount
  |
  ├─> Check if editing (quizId in params)
  │   └─> If YES: Call loadQuiz() 
  │       ├─> Fetch quiz data via quizService.getQuizById()
  │       ├─> Set quizTitle, quizDescription, quizSettings
  │       ├─> Set questions array with sorted questions
  │       └─> Set loading state to false
  │
  ├─> Load classes (regardless of new or edit)
  │   └─> Fetch via classService.getAllClasses()
  │       ├─> Set classes state
  │       └─> Handle errors gracefully
  │
  └─> Render UI with loaded/default data
```

### State Changes Flow

```
User Interaction
  |
  ├─> Changes Quiz Title
  │   └─> setQuizTitle(newValue)
  │
  ├─> Changes Description
  │   └─> setQuizDescription(newValue)
  │
  ├─> Changes Class Selection
  │   └─> setSelectedClassId(classId)
  │
  ├─> Changes Quiz Settings
  │   └─> setQuizSettings({ ...quizSettings, field: newValue })
  │
  ├─> Adds Question
  │   └─> setQuestions([...questions, newQuestion])
  │
  ├─> Updates Question
  │   └─> handleQuestionChange(index, updatedQuestion)
  │       └─> setQuestions([...newQuestions]) at index
  │
  ├─> Deletes Question
  │   └─> deleteQuestion(index)
  │       └─> setQuestions(questions.filter((_, i) => i !== index))
  │
  └─> Duplicates Question
      └─> duplicateQuestion(index)
          └─> setQuestions([...withDuplicate at index+1])
```

## API Request-Response Examples

### Create New Quiz (POST /api/quizzes)

**REQUEST**:
```javascript
{
  title: "Introduction to Biology",
  description: "Basic concepts in biology - Chapter 1",
  class_id: "class-123",  // <-- NEW FIELD
  settings: {
    shuffle_questions: false,
    shuffle_options: true,
    show_correct_answers: true,
    allow_review: true
  },
  questions: [
    {
      question_type: "multiple_choice",
      question_text: "What is the basic unit of life?",
      options: ["Cell", "Atom", "Molecule", "Organism"],
      correct_answer: [0],  // Index 0 = "Cell"
      points: 10,
      time_limit_seconds: 30,
      order_index: 0
    },
    {
      question_type: "true_false",
      question_text: "Mitochondria is the powerhouse of the cell.",
      options: [],
      correct_answer: [true],
      points: 5,
      time_limit_seconds: 20,
      order_index: 1
    },
    {
      question_type: "short_answer",
      question_text: "Name the process by which plants convert sunlight to energy.",
      options: [],
      correct_answer: ["photosynthesis", "photo synthesis"],
      points: 15,
      time_limit_seconds: 60,
      order_index: 2
    }
  ]
}
```

**RESPONSE** (201 Created):
```javascript
{
  id: "quiz-uuid-12345",
  title: "Introduction to Biology",
  description: "Basic concepts in biology - Chapter 1",
  user_id: "user-uuid",
  class_id: "class-123",
  status: "draft",
  settings: {
    shuffle_questions: false,
    shuffle_options: true,
    show_correct_answers: true,
    allow_review: true
  },
  questions: [
    {
      id: "question-uuid-1",
      quiz_id: "quiz-uuid-12345",
      question_type: "multiple_choice",
      question_text: "What is the basic unit of life?",
      options: ["Cell", "Atom", "Molecule", "Organism"],
      correct_answer: [0],
      points: 10,
      time_limit_seconds: 30,
      order_index: 0,
      created_at: "2024-11-17T10:00:00Z"
    }
    // ... more questions
  ],
  created_at: "2024-11-17T10:00:00Z",
  updated_at: "2024-11-17T10:00:00Z"
}
```

### Update Quiz (PUT /api/quizzes/quiz-uuid-12345)

**REQUEST** (for class selection change):
```javascript
{
  class_id: "class-456"  // Change class association
}
```

**RESPONSE** (200 OK):
```javascript
{
  // Full quiz object with updated class_id
  ...
  class_id: "class-456",
  ...
}
```

### Publish Quiz (POST /api/quizzes/quiz-uuid-12345/publish)

**REQUEST**:
```javascript
// Empty body
{}
```

**RESPONSE** (200 OK):
```javascript
{
  // Full quiz object with updated status
  id: "quiz-uuid-12345",
  status: "published",  // Changed from "draft"
  ...
}
```

## Code Location Reference

### QuizBuilder Main Component
**File**: `/home/user/ata-project/ata-frontend/src/pages/quizzes/QuizBuilder.jsx`

**Key Functions**:
- `loadQuiz()` - Line 411-428: Loads existing quiz data
- `validateQuiz()` - Line 465-505: Validates all quiz data before save
- `handleSave()` - Line 507-550: Saves quiz as draft
- `handlePublish()` - Line 552-591: Publishes quiz
- `handleQuestionChange()` - Line 430-434: Updates question in array
- `addQuestion()` - Line 436-449: Adds new question
- `deleteQuestion()` - Line 451-453: Removes question
- `duplicateQuestion()` - Line 455-463: Duplicates question

### QuestionEditor Sub-Component
**File**: `/home/user/ata-project/ata-frontend/src/pages/quizzes/QuizBuilder.jsx`
**Lines**: 62-364

**Key Features**:
- Question type selector with conditional rendering
- Options handler for multiple choice/poll
- Correct answer configuration
- Points and time limit inputs
- Type-specific validation

### Quiz Service
**File**: `/home/user/ata-project/ata-frontend/src/services/quizService.js`

**Key Methods**:
- `createQuiz()` - POST /api/quizzes
- `updateQuiz()` - PUT /api/quizzes/{id}
- `publishQuiz()` - POST /api/quizzes/{id}/publish
- `getQuizById()` - GET /api/quizzes/{id}
- `getAllQuizzes()` - GET /api/quizzes

### Class Service
**File**: `/home/user/ata-project/ata-frontend/src/services/classService.js`

**Key Method for Quiz Creation**:
- `getAllClasses()` - GET /api/classes (needed for dropdown)

## Integration Points for Class Selection

### 1. Import Required Service
```javascript
// At top of QuizBuilder.jsx
import classService from '../../services/classService';
```

### 2. Add State Variables
```javascript
// In QuizBuilder component
const [classes, setClasses] = useState([]);
const [selectedClassId, setSelectedClassId] = useState(null);
const [isLoadingClasses, setIsLoadingClasses] = useState(false);
```

### 3. Load Classes on Mount
```javascript
// Add to useEffect hooks
useEffect(() => {
  const loadClasses = async () => {
    try {
      setIsLoadingClasses(true);
      const data = await classService.getAllClasses();
      setClasses(data || []);
      setError(null);
    } catch (err) {
      console.error("Failed to load classes:", err);
      // Don't block creation if classes fail to load
      setClasses([]);
    } finally {
      setIsLoadingClasses(false);
    }
  };
  loadClasses();
}, []); // Run once on mount
```

### 4. Add to Quiz Data on Save
```javascript
// In handleSave function, before API call
const quizData = {
  title: quizTitle,
  description: quizDescription,
  class_id: selectedClassId || null,  // <-- ADD THIS
  settings: quizSettings,
  questions: questions.map((q, index) => ({
    ...q,
    order_index: index,
    correct_answer: q.question_type === 'poll' ? [] : q.correct_answer
  }))
};
```

### 5. Add UI Component in Step 0
```jsx
// In activeStep === 0 section, after description field
<Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 3, mb: 3 }}>
  <FormControl sx={{ minWidth: 250 }}>
    <InputLabel>Class (Optional)</InputLabel>
    <Select
      value={selectedClassId || ''}
      label="Class (Optional)"
      onChange={(e) => setSelectedClassId(e.target.value || null)}
      disabled={isLoadingClasses}
    >
      <MenuItem value="">
        <em>No Class Selected</em>
      </MenuItem>
      {classes.map((cls) => (
        <MenuItem key={cls.id} value={cls.id}>
          {cls.name}
        </MenuItem>
      ))}
    </Select>
  </FormControl>
</Box>
```

### 6. Import Required MUI Components
```javascript
// Add to imports at top
import {
  // ... existing imports ...
  FormControl,  // ADD
  InputLabel,   // ADD
  Select,       // ADD
  MenuItem      // ADD
};
```

## Current Code Snippets

### Quiz Creation Data Structure (from QuizBuilder.jsx)
```javascript
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

const [quizSettings, setQuizSettings] = useState({
  shuffle_questions: false,
  shuffle_options: false,
  show_correct_answers: true,
  allow_review: true
});
```

### Quiz Validation (from QuizBuilder.jsx, lines 465-505)
```javascript
const validateQuiz = () => {
  if (!quizTitle.trim()) {
    return "Quiz title is required.";
  }
  if (questions.length === 0) {
    return "At least one question is required.";
  }
  for (let i = 0; i < questions.length; i++) {
    const q = questions[i];
    if (!q.question_text.trim()) {
      return `Question ${i + 1}: Question text is required.`;
    }
    // ... more validations for each question type
  }
  return null; // Valid
};
```

### Save Handler (from QuizBuilder.jsx, lines 507-550)
```javascript
const handleSave = async () => {
  const validationError = validateQuiz();
  if (validationError) {
    setError(validationError);
    return null;
  }

  try {
    setIsSaving(true);
    setError(null);

    const quizData = {
      title: quizTitle,
      description: quizDescription,
      settings: quizSettings,
      questions: questions.map((q, index) => ({
        ...q,
        order_index: index,
        correct_answer: q.question_type === 'poll' ? [] : q.correct_answer
      }))
    };

    if (isEditMode) {
      await quizService.updateQuiz(quizId, quizData);
      return quizId;
    } else {
      const created = await quizService.createQuiz(quizData);
      navigate(`/quizzes/${created.id}/edit`);
      return created.id;
    }
  } catch (err) {
    console.error("Failed to save quiz:", err);
    setError(err.message || "Failed to save quiz.");
    return null;
  } finally {
    setIsSaving(false);
  }
};
```

## Error Handling Patterns

### Class Loading Error
```javascript
try {
  const data = await classService.getAllClasses();
  setClasses(data || []);
} catch (err) {
  console.error("Failed to load classes:", err);
  setClasses([]);  // Fallback to empty array
  // Don't show error - class selection is optional
}
```

### Quiz Save Error
```javascript
try {
  // ... save logic
} catch (err) {
  console.error("Failed to save quiz:", err);
  console.error("Error details:", err.response?.data);
  setError(err.message || "Failed to save quiz.");
  return null;
}
```

### Question Validation Error
```javascript
if (q.question_type === 'multiple_choice') {
  if (!q.options || q.options.length < 2) {
    return `Question ${i + 1}: At least 2 options are required.`;
  }
  if (q.options.some(opt => !opt.trim())) {
    return `Question ${i + 1}: All options must have text.`;
  }
  if (!q.correct_answer || q.correct_answer.length === 0) {
    return `Question ${i + 1}: Please select the correct answer.`;
  }
}
```
