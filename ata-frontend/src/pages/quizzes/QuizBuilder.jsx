// /src/pages/quizzes/QuizBuilder.jsx

// --- Core React Imports ---
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

// --- MUI Component Imports ---
import {
  Box,
  Button,
  Typography,
  TextField,
  Paper,
  Card,
  CardContent,
  IconButton,
  Divider,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  Chip,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Skeleton,
  Stepper,
  Step,
  StepLabel,
  Grid,
  Tooltip
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import SaveIcon from '@mui/icons-material/Save';
import PublishIcon from '@mui/icons-material/Publish';
import PreviewIcon from '@mui/icons-material/Preview';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';

// --- Service Import ---
import quizService from '../../services/quizService';

/**
 * Question type options
 */
const QUESTION_TYPES = [
  { value: 'multiple_choice', label: 'Multiple Choice', icon: '☑️' },
  { value: 'true_false', label: 'True/False', icon: '✓✗' },
  { value: 'short_answer', label: 'Short Answer', icon: '✍️' },
  { value: 'poll', label: 'Poll (No correct answer)', icon: '📊' }
];

/**
 * Question Editor Component
 */
const QuestionEditor = ({ question, index, onChange, onDelete, onDuplicate }) => {
  const [localQuestion, setLocalQuestion] = useState(question);
  const [shortAnswerText, setShortAnswerText] = useState('');

  useEffect(() => {
    setLocalQuestion(question);
    // Initialize shortAnswerText when question changes
    if (question.question_type === 'short_answer' && question.correct_answer) {
      setShortAnswerText(question.correct_answer.join('\n'));
    }
  }, [question]);

  const handleChange = (field, value) => {
    const updated = { ...localQuestion, [field]: value };

    // FIX: When changing question type, reset correct_answer AND options appropriately
    if (field === 'question_type') {
      const previousType = localQuestion.question_type;

      if (value === 'poll') {
        updated.correct_answer = [];  // Polls have no correct answer
        updated.points = 0;  // Polls default to 0 points
        updated.options = ['', ''];  // Initialize with 2 empty options for polls
      } else if (value === 'true_false') {
        updated.correct_answer = [true];  // Default to true
        updated.options = [];  // True/false has no options (just true/false buttons)
        // If coming from poll (0 points), restore to 10
        if (previousType === 'poll' && updated.points === 0) {
          updated.points = 10;
        }
      } else if (value === 'multiple_choice') {
        updated.correct_answer = [];  // Will be set when user selects
        updated.options = ['', '', '', ''];  // Initialize with 4 empty options
        // If coming from poll (0 points), restore to 10
        if (previousType === 'poll' && updated.points === 0) {
          updated.points = 10;
        }
      } else if (value === 'short_answer') {
        updated.correct_answer = [];  // Will be set when user enters keywords
        updated.options = [];  // Short answer has no options (free text input)
        setShortAnswerText('');  // Reset the local text buffer
        // If coming from poll (0 points), restore to 10
        if (previousType === 'poll' && updated.points === 0) {
          updated.points = 10;
        }
      }
      console.log('[QuestionEditor] Question type changed to:', value, 'Reset correct_answer to:', updated.correct_answer, 'Options:', updated.options, 'Points:', updated.points);
    }

    setLocalQuestion(updated);
    onChange(index, updated);
  };

  const handleOptionChange = (optionIndex, value) => {
    const newOptions = [...(localQuestion.options || [])];
    newOptions[optionIndex] = value;
    handleChange('options', newOptions);
  };

  const addOption = () => {
    const newOptions = [...(localQuestion.options || []), ''];
    handleChange('options', newOptions);
  };

  const removeOption = (optionIndex) => {
    const newOptions = localQuestion.options.filter((_, i) => i !== optionIndex);
    handleChange('options', newOptions);

    // Update correct answer if it was the removed option
    if (localQuestion.question_type === 'multiple_choice') {
      const correctAnswerIndex = localQuestion.correct_answer?.[0];
      if (correctAnswerIndex === optionIndex) {
        handleChange('correct_answer', []);
      } else if (correctAnswerIndex > optionIndex) {
        handleChange('correct_answer', [correctAnswerIndex - 1]);
      }
    }
  };

  const handleCorrectAnswerChange = (value) => {
    if (localQuestion.question_type === 'multiple_choice') {
      handleChange('correct_answer', [parseInt(value)]);
    } else if (localQuestion.question_type === 'true_false') {
      handleChange('correct_answer', [value === 'true']);
    }
  };

  return (
    <Card sx={{ mb: 3, position: 'relative' }}>
      <CardContent>
        {/* Question Header */}
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <DragIndicatorIcon sx={{ color: 'text.secondary', cursor: 'grab', mr: 1 }} />
          <Typography variant="h6" sx={{ flex: 1 }}>
            Question {index + 1}
          </Typography>
          <Chip
            label={QUESTION_TYPES.find(t => t.value === localQuestion.question_type)?.label || 'Unknown'}
            size="small"
            sx={{ mr: 1 }}
          />
          <Tooltip title="Duplicate question">
            <IconButton size="small" onClick={() => onDuplicate(index)} sx={{ mr: 1 }}>
              <ContentCopyIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete question">
            <IconButton size="small" onClick={() => onDelete(index)} color="error">
              <DeleteIcon />
            </IconButton>
          </Tooltip>
        </Box>

        <Grid container spacing={2}>
          {/* Question Type */}
          <Grid item xs={12} md={6}>
            <FormControl fullWidth>
              <InputLabel>Question Type</InputLabel>
              <Select
                value={localQuestion.question_type || 'multiple_choice'}
                label="Question Type"
                onChange={(e) => handleChange('question_type', e.target.value)}
              >
                {QUESTION_TYPES.map((type) => (
                  <MenuItem key={type.value} value={type.value}>
                    {type.icon} {type.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          {/* Points */}
          <Grid item xs={12} md={3}>
            <TextField
              fullWidth
              type="number"
              label="Points"
              value={localQuestion.points !== undefined ? localQuestion.points : (localQuestion.question_type === 'poll' ? 0 : 10)}
              onChange={(e) => handleChange('points', parseInt(e.target.value) || 0)}
              InputProps={{ inputProps: { min: 0, max: 100 } }}
              helperText={localQuestion.question_type === 'poll' ? "Polls typically have 0 points" : ""}
            />
          </Grid>

          {/* Time Limit */}
          <Grid item xs={12} md={3}>
            <TextField
              fullWidth
              type="number"
              label="Time Limit (seconds)"
              value={localQuestion.time_limit_seconds || 30}
              onChange={(e) => handleChange('time_limit_seconds', parseInt(e.target.value) || 30)}
              InputProps={{ inputProps: { min: 5, max: 300 } }}
            />
          </Grid>

          {/* Question Text */}
          <Grid item xs={12}>
            <TextField
              fullWidth
              multiline
              rows={2}
              label="Question Text"
              value={localQuestion.question_text || ''}
              onChange={(e) => handleChange('question_text', e.target.value)}
              placeholder="Enter your question here..."
            />
          </Grid>

          {/* Multiple Choice Options */}
          {localQuestion.question_type === 'multiple_choice' && (
            <Grid item xs={12}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                Answer Options (Select the correct answer)
              </Typography>
              {(localQuestion.options || ['', '', '', '']).map((option, optionIndex) => (
                <Box key={optionIndex} sx={{ display: 'flex', gap: 1, mb: 1 }}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={localQuestion.correct_answer?.[0] === optionIndex}
                        onChange={() => handleCorrectAnswerChange(optionIndex)}
                        color="success"
                      />
                    }
                    label=""
                  />
                  <TextField
                    fullWidth
                    size="small"
                    label={`Option ${optionIndex + 1}`}
                    value={option}
                    onChange={(e) => handleOptionChange(optionIndex, e.target.value)}
                  />
                  {localQuestion.options.length > 2 && (
                    <IconButton
                      size="small"
                      onClick={() => removeOption(optionIndex)}
                      color="error"
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  )}
                </Box>
              ))}
              {localQuestion.options.length < 6 && (
                <Button
                  size="small"
                  startIcon={<AddIcon />}
                  onClick={addOption}
                  sx={{ mt: 1 }}
                >
                  Add Option
                </Button>
              )}
            </Grid>
          )}

          {/* True/False */}
          {localQuestion.question_type === 'true_false' && (
            <Grid item xs={12}>
              <FormControl fullWidth>
                <InputLabel>Correct Answer</InputLabel>
                <Select
                  value={localQuestion.correct_answer?.[0] === true ? 'true' : 'false'}
                  label="Correct Answer"
                  onChange={(e) => handleCorrectAnswerChange(e.target.value)}
                >
                  <MenuItem value="true">✓ True</MenuItem>
                  <MenuItem value="false">✗ False</MenuItem>
                </Select>
              </FormControl>
            </Grid>
          )}

          {/* Short Answer */}
          {localQuestion.question_type === 'short_answer' && (
            <Grid item xs={12}>
              <TextField
                fullWidth
                multiline
                rows={3}
                label="Correct Answer Keywords"
                value={shortAnswerText}
                onChange={(e) => setShortAnswerText(e.target.value)}
                onBlur={() => {
                  // Only update when field loses focus
                  const keywords = shortAnswerText
                    .split(/[\n,]/)
                    .map(s => s.trim())
                    .filter(s => s.length > 0);
                  handleChange('correct_answer', keywords);
                }}
                placeholder="Enter keywords (one per line or comma-separated):&#10;Paris&#10;france&#10;European capital"
                helperText="Enter keywords (one per line OR comma-separated). Spaces within keywords are allowed. Matching is case-insensitive."
              />
            </Grid>
          )}

          {/* Poll (no correct answer) */}
          {localQuestion.question_type === 'poll' && (
            <Grid item xs={12}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                Poll Options (No correct answer)
              </Typography>
              {(localQuestion.options || ['', '']).map((option, optionIndex) => (
                <Box key={optionIndex} sx={{ display: 'flex', gap: 1, mb: 1 }}>
                  <TextField
                    fullWidth
                    size="small"
                    label={`Option ${optionIndex + 1}`}
                    value={option}
                    onChange={(e) => handleOptionChange(optionIndex, e.target.value)}
                  />
                  {localQuestion.options.length > 2 && (
                    <IconButton
                      size="small"
                      onClick={() => removeOption(optionIndex)}
                      color="error"
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  )}
                </Box>
              ))}
              {localQuestion.options.length < 6 && (
                <Button
                  size="small"
                  startIcon={<AddIcon />}
                  onClick={addOption}
                  sx={{ mt: 1 }}
                >
                  Add Option
                </Button>
              )}
            </Grid>
          )}
        </Grid>
      </CardContent>
    </Card>
  );
};

/**
 * Main Quiz Builder Component
 */
const QuizBuilder = () => {
  const navigate = useNavigate();
  const { quizId } = useParams();
  const isEditMode = Boolean(quizId);

  const [activeStep, setActiveStep] = useState(0);
  const [isLoading, setIsLoading] = useState(isEditMode);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);

  // Quiz metadata
  const [quizTitle, setQuizTitle] = useState('');
  const [quizDescription, setQuizDescription] = useState('');
  const [quizSettings, setQuizSettings] = useState({
    shuffle_questions: false,
    shuffle_options: false,
    show_correct_answers: true,
    allow_review: true
  });

  // Questions
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

  const [publishDialog, setPublishDialog] = useState(false);

  // Load quiz if editing
  useEffect(() => {
    if (isEditMode) {
      loadQuiz();
    }
  }, [quizId]);

  const loadQuiz = async () => {
    try {
      setIsLoading(true);
      const quiz = await quizService.getQuizById(quizId);
      setQuizTitle(quiz.title);
      setQuizDescription(quiz.description || '');
      setQuizSettings(quiz.settings || quizSettings);
      if (quiz.questions && quiz.questions.length > 0) {
        setQuestions(quiz.questions.sort((a, b) => a.order_index - b.order_index));
      }
      setError(null);
    } catch (err) {
      console.error("Failed to load quiz:", err);
      setError(err.message || "Failed to load quiz.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuestionChange = (index, updatedQuestion) => {
    const newQuestions = [...questions];
    newQuestions[index] = updatedQuestion;
    setQuestions(newQuestions);
  };

  const addQuestion = () => {
    const newQuestion = {
      question_type: 'multiple_choice',
      question_text: '',
      options: ['', '', '', ''],
      correct_answer: [],  // Start with empty array
      points: 10,
      time_limit_seconds: 30,
      order_index: questions.length
    };

    console.log('[QuizBuilder] Adding new question:', newQuestion);
    setQuestions([...questions, newQuestion]);
  };

  const deleteQuestion = (index) => {
    setQuestions(questions.filter((_, i) => i !== index));
  };

  const duplicateQuestion = (index) => {
    const questionToDuplicate = { ...questions[index] };
    const newQuestions = [...questions];
    newQuestions.splice(index + 1, 0, {
      ...questionToDuplicate,
      order_index: index + 1
    });
    setQuestions(newQuestions);
  };

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
      if (q.question_type === 'true_false') {
        if (q.correct_answer === undefined || q.correct_answer.length === 0) {
          return `Question ${i + 1}: Please select True or False as the correct answer.`;
        }
      }
      if (q.question_type === 'short_answer') {
        if (!q.correct_answer || q.correct_answer.length === 0) {
          return `Question ${i + 1}: Please provide at least one correct answer keyword.`;
        }
      }
      if (q.question_type === 'poll') {
        if (!q.options || q.options.length < 2) {
          return `Question ${i + 1}: At least 2 options are required for a poll.`;
        }
      }
    }
    return null;
  };

  const handleSave = async () => {
    const validationError = validateQuiz();
    if (validationError) {
      setError(validationError);
      return null; // Return null to indicate failure
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
          // FIX: Ensure poll questions have empty correct_answer array
          correct_answer: q.question_type === 'poll' ? [] : q.correct_answer
        }))
      };

      console.log('[QuizBuilder] Saving quiz:', quizData);

      if (isEditMode) {
        await quizService.updateQuiz(quizId, quizData);
        console.log('[QuizBuilder] Quiz updated successfully');
        return quizId; // Return the current quiz ID
      } else {
        const created = await quizService.createQuiz(quizData);
        console.log('[QuizBuilder] Quiz created successfully:', created.id);
        navigate(`/quizzes/${created.id}/edit`);
        return created.id; // Return the new quiz ID
      }
    } catch (err) {
      console.error("[QuizBuilder] Failed to save quiz:", err);
      console.error("[QuizBuilder] Error details:", err.response?.data);
      setError(err.message || "Failed to save quiz.");
      return null; // Return null to indicate failure
    } finally {
      setIsSaving(false);
    }
  };

  const handlePublish = async () => {
    const validationError = validateQuiz();
    if (validationError) {
      setError(validationError);
      setPublishDialog(false);
      return;
    }

    try {
      setIsSaving(true);
      setError(null);

      let quizIdToPublish = quizId;

      // Save first if needed (creating new quiz)
      if (!isEditMode) {
        console.log('[QuizBuilder] Creating quiz before publishing...');
        const createdQuizId = await handleSave();
        if (!createdQuizId) {
          throw new Error('Failed to create quiz before publishing');
        }
        quizIdToPublish = createdQuizId;
        console.log('[QuizBuilder] Quiz created, now publishing:', quizIdToPublish);
      }

      // Then publish
      console.log('[QuizBuilder] Publishing quiz:', quizIdToPublish);
      await quizService.publishQuiz(quizIdToPublish);
      console.log('[QuizBuilder] Quiz published successfully');
      setPublishDialog(false);
      navigate('/quizzes');
    } catch (err) {
      console.error("[QuizBuilder] Failed to publish quiz:", err);
      console.error("[QuizBuilder] Error details:", err.response?.data);
      setError(err.message || "Failed to publish quiz.");
      setPublishDialog(false);
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <Box>
        <Skeleton variant="rectangular" height={60} sx={{ mb: 2 }} />
        <Skeleton variant="rectangular" height={400} />
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
        <IconButton onClick={() => navigate('/quizzes')} sx={{ mr: 2 }}>
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h2" sx={{ flex: 1 }}>
          {isEditMode ? 'Edit Quiz' : 'Create New Quiz'}
        </Typography>
        <Button
          variant="outlined"
          startIcon={<SaveIcon />}
          onClick={handleSave}
          disabled={isSaving}
          sx={{ mr: 1 }}
        >
          Save Draft
        </Button>
        <Button
          variant="contained"
          startIcon={<PublishIcon />}
          onClick={() => setPublishDialog(true)}
          disabled={isSaving}
        >
          Publish Quiz
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Stepper */}
      <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
        <Step>
          <StepLabel>Quiz Details</StepLabel>
        </Step>
        <Step>
          <StepLabel>Questions</StepLabel>
        </Step>
        <Step>
          <StepLabel>Settings</StepLabel>
        </Step>
      </Stepper>

      {/* Step Content */}
      {activeStep === 0 && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h5" sx={{ mb: 3 }}>Quiz Information</Typography>
          <TextField
            fullWidth
            label="Quiz Title"
            value={quizTitle}
            onChange={(e) => setQuizTitle(e.target.value)}
            sx={{ mb: 3 }}
            required
          />
          <TextField
            fullWidth
            multiline
            rows={4}
            label="Description (Optional)"
            value={quizDescription}
            onChange={(e) => setQuizDescription(e.target.value)}
            placeholder="Describe what this quiz is about..."
          />
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 3 }}>
            <Button variant="contained" onClick={() => setActiveStep(1)}>
              Next: Add Questions
            </Button>
          </Box>
        </Paper>
      )}

      {activeStep === 1 && (
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Typography variant="h5">Questions ({questions.length})</Typography>
            <Button variant="contained" startIcon={<AddIcon />} onClick={addQuestion}>
              Add Question
            </Button>
          </Box>

          {questions.map((question, index) => (
            <QuestionEditor
              key={index}
              question={question}
              index={index}
              onChange={handleQuestionChange}
              onDelete={deleteQuestion}
              onDuplicate={duplicateQuestion}
            />
          ))}

          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 3 }}>
            <Button onClick={() => setActiveStep(0)}>
              Back
            </Button>
            <Button variant="contained" onClick={() => setActiveStep(2)}>
              Next: Settings
            </Button>
          </Box>
        </Box>
      )}

      {activeStep === 2 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h5" sx={{ mb: 3 }}>Quiz Settings</Typography>

          <FormControlLabel
            control={
              <Switch
                checked={quizSettings.shuffle_questions}
                onChange={(e) => setQuizSettings({ ...quizSettings, shuffle_questions: e.target.checked })}
              />
            }
            label="Shuffle Questions"
            sx={{ display: 'block', mb: 2 }}
          />

          <FormControlLabel
            control={
              <Switch
                checked={quizSettings.shuffle_options}
                onChange={(e) => setQuizSettings({ ...quizSettings, shuffle_options: e.target.checked })}
              />
            }
            label="Shuffle Answer Options"
            sx={{ display: 'block', mb: 2 }}
          />

          <FormControlLabel
            control={
              <Switch
                checked={quizSettings.show_correct_answers}
                onChange={(e) => setQuizSettings({ ...quizSettings, show_correct_answers: e.target.checked })}
              />
            }
            label="Show Correct Answers After Each Question"
            sx={{ display: 'block', mb: 2 }}
          />

          <FormControlLabel
            control={
              <Switch
                checked={quizSettings.allow_review}
                onChange={(e) => setQuizSettings({ ...quizSettings, allow_review: e.target.checked })}
              />
            }
            label="Allow Participants to Review Answers"
            sx={{ display: 'block' }}
          />

          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4 }}>
            <Button onClick={() => setActiveStep(1)}>
              Back
            </Button>
            <Button variant="contained" onClick={handleSave} disabled={isSaving}>
              Save Quiz
            </Button>
          </Box>
        </Paper>
      )}

      {/* Publish Confirmation Dialog */}
      <Dialog open={publishDialog} onClose={() => setPublishDialog(false)}>
        <DialogTitle>Publish Quiz?</DialogTitle>
        <DialogContent>
          <Typography>
            Once published, you can start live quiz sessions with your students.
            You can still edit the quiz after publishing, but changes won't affect active sessions.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPublishDialog(false)}>Cancel</Button>
          <Button onClick={handlePublish} variant="contained" disabled={isSaving}>
            Publish
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default QuizBuilder;
