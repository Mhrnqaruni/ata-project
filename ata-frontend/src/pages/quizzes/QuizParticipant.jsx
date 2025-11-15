// /src/pages/quizzes/QuizParticipant.jsx

// --- Core React Imports ---
import React, { useState, useEffect, useRef } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';

// --- MUI Component Imports ---
import {
  Box,
  Button,
  Typography,
  TextField,
  Paper,
  Card,
  CardContent,
  LinearProgress,
  Alert,
  Grid,
  Fade,
  Grow,
  Avatar,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Container,
  CircularProgress
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import TimerIcon from '@mui/icons-material/Timer';
import EmojiEventsIcon from '@mui/icons-material/EmojiEvents';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import LoginIcon from '@mui/icons-material/Login';

// --- Service Import ---
import quizService from '../../services/quizService';

/**
 * Join Screen Component
 */
const JoinScreen = ({ onJoin }) => {
  const { roomCode: urlRoomCode } = useParams();
  const [roomCode, setRoomCode] = useState(urlRoomCode || '');
  const [guestName, setGuestName] = useState('');
  const [studentId, setStudentId] = useState('');
  const [isJoining, setIsJoining] = useState(false);
  const [error, setError] = useState(null);

  const handleJoin = async () => {
    // Validation
    if (!roomCode.trim()) {
      setError("Please enter a room code.");
      return;
    }

    if (!guestName.trim()) {
      setError("Please enter your name.");
      return;
    }

    if (!studentId.trim()) {
      setError("Please enter your student ID.");
      return;
    }

    try {
      setIsJoining(true);
      setError(null);

      console.log('[JoinScreen] Joining with:', { roomCode, guestName, studentId });

      // Call new joinSession API with object (supports identified guests)
      const response = await quizService.joinSession({
        room_code: roomCode.toUpperCase().trim(),
        guest_name: guestName.trim(),
        student_id: studentId.trim()
      });

      console.log('[JoinScreen] Join successful:', response);
      onJoin(response);
    } catch (err) {
      console.error("Failed to join session:", err);
      setError(err.message || "Failed to join quiz. Please check the room code.");
    } finally {
      setIsJoining(false);
    }
  };

  return (
    <Container maxWidth="sm">
      <Fade in timeout={800}>
        <Box sx={{ mt: 8, textAlign: 'center' }}>
          <Typography variant="h2" sx={{ mb: 1, fontWeight: 700 }}>
            Join Quiz
          </Typography>
          <Typography variant="h6" color="text.secondary" sx={{ mb: 4 }}>
            Enter your information to join the quiz
          </Typography>

          <Paper sx={{ p: 4 }}>
            <TextField
              fullWidth
              label="Room Code"
              value={roomCode}
              onChange={(e) => setRoomCode(e.target.value.toUpperCase())}
              placeholder="ABC123"
              sx={{ mb: 3 }}
              inputProps={{
                style: {
                  fontSize: '2rem',
                  textAlign: 'center',
                  letterSpacing: 8,
                  fontWeight: 700,
                  fontFamily: 'monospace'
                },
                maxLength: 6
              }}
              autoFocus
            />

            <TextField
              fullWidth
              label="Your Name"
              value={guestName}
              onChange={(e) => setGuestName(e.target.value)}
              placeholder="e.g., John Doe"
              sx={{ mb: 3 }}
            />

            <TextField
              fullWidth
              label="Student ID"
              value={studentId}
              onChange={(e) => setStudentId(e.target.value)}
              placeholder="e.g., 12345"
              sx={{ mb: 3 }}
              onKeyPress={(e) => {
                if (e.key === 'Enter') {
                  handleJoin();
                }
              }}
            />

            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}

            <Button
              fullWidth
              variant="contained"
              size="large"
              onClick={handleJoin}
              disabled={isJoining || !roomCode.trim() || !guestName.trim()}
              startIcon={isJoining ? <CircularProgress size={20} /> : <LoginIcon />}
              sx={{ py: 2, fontSize: '1.2rem' }}
            >
              {isJoining ? 'Joining...' : 'Join Quiz'}
            </Button>
          </Paper>
        </Box>
      </Fade>
    </Container>
  );
};

/**
 * Waiting Room Component
 */
const WaitingRoom = ({ session, participantName }) => {
  return (
    <Container maxWidth="md">
      <Fade in timeout={800}>
        <Box sx={{ mt: 8, textAlign: 'center' }}>
          <HourglassEmptyIcon sx={{ fontSize: 120, color: 'primary.main', mb: 2 }} />
          <Typography variant="h3" sx={{ mb: 2, fontWeight: 700 }}>
            Welcome, {participantName}!
          </Typography>
          <Typography variant="h5" color="text.secondary" sx={{ mb: 4 }}>
            Waiting for the quiz to start...
          </Typography>

          <Paper sx={{ p: 4, mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Quiz: {session.quiz_title}
            </Typography>
            <Typography color="text.secondary">
              Room Code: <strong style={{ fontSize: '1.5rem', letterSpacing: 4 }}>{session.room_code}</strong>
            </Typography>
          </Paper>

          <LinearProgress />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            Your teacher will start the quiz soon
          </Typography>
        </Box>
      </Fade>
    </Container>
  );
};

/**
 * Question Display Component
 */
const QuestionDisplay = ({ question, onAnswer, timeRemaining, cooldownRemaining, autoAdvanceEnabled }) => {
  const [selectedAnswer, setSelectedAnswer] = useState(null);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [timeExpired, setTimeExpired] = useState(false);

  // FIX: Reset state when question changes (allows answering new questions)
  useEffect(() => {
    setSelectedAnswer(null);
    setIsSubmitted(false);
    setTimeExpired(false);
  }, [question.id]); // Reset when question ID changes

  // FIX Issue 1: Detect when time expires
  useEffect(() => {
    if (timeRemaining <= 0 && !isSubmitted) {
      setTimeExpired(true);
      setSelectedAnswer(null); // Clear any selection
    }
  }, [timeRemaining, isSubmitted]);

  const handleSelect = (answerIndex) => {
    if (!isSubmitted && !timeExpired) {
      setSelectedAnswer(answerIndex);
    }
  };

  const handleSubmit = () => {
    if (isSubmitted || timeExpired) return;

    let answerToSubmit = null;

    if (question.type === 'multiple_choice' || question.type === 'poll') {
      // Answer is an index number
      if (selectedAnswer === null) return;
      answerToSubmit = selectedAnswer;
    } else if (question.type === 'true_false') {
      // Answer is a boolean
      if (selectedAnswer === null) return;
      answerToSubmit = selectedAnswer;
    } else if (question.type === 'short_answer') {
      // Answer is a string
      if (!selectedAnswer || selectedAnswer.trim() === '') return;
      answerToSubmit = selectedAnswer.trim();
    }

    setIsSubmitted(true);
    onAnswer(answerToSubmit);
  };

  const getProgressColor = () => {
    if (timeRemaining > 15) return 'success';
    if (timeRemaining > 5) return 'warning';
    return 'error';
  };

  return (
    <Container maxWidth="lg">
      <Fade in timeout={500}>
        <Box sx={{ mt: 4 }}>
          {/* Timer - Show question timer or cooldown timer */}
          {cooldownRemaining > 0 ? (
            // Cooldown Timer
            <Box sx={{ textAlign: 'center', mb: 3 }}>
              <Alert severity="info" sx={{ py: 2 }}>
                <Typography variant="h6" sx={{ mb: 1 }}>
                  Next Question Starting In
                </Typography>
                <Typography variant="h3" sx={{ fontWeight: 700, color: 'primary.main' }}>
                  {cooldownRemaining}s
                </Typography>
              </Alert>
            </Box>
          ) : (
            // Question Timer
            <>
              <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', mb: 3 }}>
                <TimerIcon sx={{ mr: 1, color: getProgressColor() }} />
                <Typography variant="h5" color={`${getProgressColor()}.main`}>
                  {timeRemaining}s
                </Typography>
              </Box>

              <LinearProgress
                variant="determinate"
                value={(timeRemaining / question.time_limit_seconds) * 100}
                color={getProgressColor()}
                sx={{ height: 8, borderRadius: 1, mb: 4 }}
              />
            </>
          )}

          {/* Question */}
          <Paper sx={{ p: 4, mb: 4, textAlign: 'center' }}>
            <Chip
              label={`Question ${question.order_index + 1}`}
              color="primary"
              sx={{ mb: 2 }}
            />
            <Typography variant="h4" sx={{ fontWeight: 600 }}>
              {question.text}
            </Typography>
            <Typography variant="subtitle1" color="text.secondary" sx={{ mt: 1 }}>
              {question.points} points
            </Typography>
          </Paper>

          {/* Answer Options - Conditional rendering based on question type */}
          {(question.type === 'multiple_choice' || question.type === 'poll') && question.options && (
            <Grid container spacing={2}>
              {question.options.map((option, index) => (
                <Grid item xs={12} sm={6} key={index}>
                  <Grow in timeout={300 * (index + 1)}>
                    <Button
                      fullWidth
                      variant={selectedAnswer === index ? 'contained' : 'outlined'}
                      size="large"
                      onClick={() => handleSelect(index)}
                      disabled={isSubmitted || timeExpired}
                      sx={{
                        py: 3,
                        fontSize: '1.2rem',
                        textTransform: 'none',
                        borderWidth: 3,
                        '&:hover': {
                          borderWidth: 3,
                          transform: 'scale(1.02)',
                          transition: 'transform 0.2s'
                        }
                      }}
                    >
                      {option}
                    </Button>
                  </Grow>
                </Grid>
              ))}
            </Grid>
          )}

          {/* True/False Buttons */}
          {question.type === 'true_false' && (
            <Grid container spacing={3} sx={{ maxWidth: 600, mx: 'auto' }}>
              <Grid item xs={6}>
                <Grow in timeout={300}>
                  <Button
                    fullWidth
                    variant={selectedAnswer === true ? 'contained' : 'outlined'}
                    size="large"
                    color={selectedAnswer === true ? 'success' : 'primary'}
                    onClick={() => handleSelect(true)}
                    disabled={isSubmitted || timeExpired}
                    sx={{
                      py: 4,
                      fontSize: '1.5rem',
                      fontWeight: 700,
                      borderWidth: 3,
                      '&:hover': { borderWidth: 3, transform: 'scale(1.05)', transition: 'transform 0.2s' }
                    }}
                  >
                    ✓ True
                  </Button>
                </Grow>
              </Grid>
              <Grid item xs={6}>
                <Grow in timeout={400}>
                  <Button
                    fullWidth
                    variant={selectedAnswer === false ? 'contained' : 'outlined'}
                    size="large"
                    color={selectedAnswer === false ? 'error' : 'primary'}
                    onClick={() => handleSelect(false)}
                    disabled={isSubmitted || timeExpired}
                    sx={{
                      py: 4,
                      fontSize: '1.5rem',
                      fontWeight: 700,
                      borderWidth: 3,
                      '&:hover': { borderWidth: 3, transform: 'scale(1.05)', transition: 'transform 0.2s' }
                    }}
                  >
                    ✗ False
                  </Button>
                </Grow>
              </Grid>
            </Grid>
          )}

          {/* Short Answer Text Field */}
          {question.type === 'short_answer' && (
            <Grow in timeout={300}>
              <Box sx={{ maxWidth: 700, mx: 'auto' }}>
                <TextField
                  fullWidth
                  multiline
                  rows={4}
                  variant="outlined"
                  placeholder="Type your answer here..."
                  value={selectedAnswer || ''}
                  onChange={(e) => setSelectedAnswer(e.target.value)}
                  disabled={isSubmitted || timeExpired}
                  sx={{
                    '& .MuiOutlinedInput-root': {
                      fontSize: '1.2rem',
                      backgroundColor: 'background.paper'
                    }
                  }}
                  autoFocus
                />
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                  Your answer will be checked against the correct keywords
                </Typography>
              </Box>
            </Grow>
          )}

          {/* Submit Button - Show for all question types when answer is valid */}
          {!isSubmitted && !timeExpired && (
            (selectedAnswer !== null && selectedAnswer !== '' && (question.type !== 'short_answer' || (typeof selectedAnswer === 'string' && selectedAnswer.trim() !== '')))
          ) && (
            <Fade in>
              <Box sx={{ textAlign: 'center', mt: 4 }}>
                <Button
                  variant="contained"
                  size="large"
                  onClick={handleSubmit}
                  disabled={timeExpired}
                  sx={{ px: 8, py: 2, fontSize: '1.2rem' }}
                >
                  Submit Answer
                </Button>
              </Box>
            </Fade>
          )}

          {/* FIX BUG #1: Show cooldown timer for ALL students (even those who submitted) */}
          {cooldownRemaining > 0 && (
            <Fade in>
              <Alert severity="info" sx={{ mt: 4 }}>
                <Typography variant="h6">
                  {isSubmitted ? 'Answer submitted!' : 'Time expired!'}
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 700, color: 'primary.main', mt: 1 }}>
                  Next question in {cooldownRemaining}s
                </Typography>
              </Alert>
            </Fade>
          )}

          {/* Show success message when submitted (only if no cooldown yet) */}
          {isSubmitted && cooldownRemaining === 0 && (
            <Fade in>
              <Alert severity="success" sx={{ mt: 4 }}>
                <Typography variant="h6">Answer submitted!</Typography>
                <Typography>Waiting for other participants...</Typography>
              </Alert>
            </Fade>
          )}

          {/* Show missed message when time expired (only if no cooldown and not submitted) */}
          {timeExpired && !isSubmitted && cooldownRemaining === 0 && !autoAdvanceEnabled && (
            <Fade in>
              <Alert severity="error" sx={{ mt: 4 }}>
                ⏰ You missed this question - time expired!
              </Alert>
            </Fade>
          )}
        </Box>
      </Fade>
    </Container>
  );
};

/**
 * Results/Leaderboard Component
 */
const LeaderboardDisplay = ({ leaderboard, participantId }) => {
  const currentParticipant = leaderboard.find(p => p.participant_id === participantId);
  const currentRank = leaderboard.findIndex(p => p.participant_id === participantId) + 1;

  return (
    <Container maxWidth="md">
      <Fade in timeout={800}>
        <Box sx={{ mt: 4 }}>
          <Typography variant="h3" sx={{ textAlign: 'center', mb: 4, fontWeight: 700 }}>
            Leaderboard
          </Typography>

          {/* Current Participant Status */}
          {currentParticipant && (
            <Paper
              sx={{
                p: 3,
                mb: 4,
                textAlign: 'center',
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                color: 'white'
              }}
            >
              <Typography variant="h6" gutterBottom>Your Position</Typography>
              <Typography variant="h2" sx={{ fontWeight: 900 }}>
                #{currentRank}
              </Typography>
              <Typography variant="h5" sx={{ mt: 1 }}>
                {currentParticipant.score} points
              </Typography>
            </Paper>
          )}

          {/* Top Players */}
          <List>
            {leaderboard.slice(0, 5).map((participant, index) => (
              <Grow in timeout={200 * (index + 1)} key={participant.participant_id}>
                <ListItem
                  sx={{
                    mb: 2,
                    borderRadius: 2,
                    backgroundColor: participant.participant_id === participantId ? 'primary.light' : 'action.hover',
                    border: 2,
                    borderColor: index < 3 ? 'warning.main' : 'divider',
                    boxShadow: participant.participant_id === participantId ? 4 : 1
                  }}
                >
                  <ListItemAvatar>
                    <Avatar
                      sx={{
                        bgcolor: index === 0 ? '#FFD700' : index === 1 ? '#C0C0C0' : index === 2 ? '#CD7F32' : 'primary.main',
                        width: 56,
                        height: 56,
                        fontSize: '1.5rem',
                        fontWeight: 'bold'
                      }}
                    >
                      {index < 3 ? <EmojiEventsIcon fontSize="large" /> : index + 1}
                    </Avatar>
                  </ListItemAvatar>
                  <ListItemText
                    primary={
                      <Typography variant="h6" sx={{ fontWeight: 600 }}>
                        {participant.display_name}
                        {participant.participant_id === participantId && ' (You)'}
                      </Typography>
                    }
                    secondary={
                      <Box sx={{ display: 'flex', gap: 2, mt: 1 }}>
                        <Chip label={`${participant.score} pts`} size="small" color="primary" />
                        <Chip label={`${participant.correct_answers} correct`} size="small" color="success" />
                        <Chip label={`${(participant.total_time_ms / 1000).toFixed(1)}s`} size="small" />
                      </Box>
                    }
                  />
                </ListItem>
              </Grow>
            ))}
          </List>
        </Box>
      </Fade>
    </Container>
  );
};

/**
 * Main Quiz Participant Component
 */
const QuizParticipant = () => {
  const { roomCode: urlRoomCode } = useParams();
  const [searchParams] = useSearchParams();

  const wsRef = useRef(null);
  const timerRef = useRef(null);
  const leaderboardTimerRef = useRef(null); // FIX: Store leaderboard auto-advance timeout ID

  const [phase, setPhase] = useState('join'); // join, waiting, question, leaderboard, finished
  const [session, setSession] = useState(null);
  const [participant, setParticipant] = useState(null);
  const [guestToken, setGuestToken] = useState(null);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [timeRemaining, setTimeRemaining] = useState(30);
  const [error, setError] = useState(null);

  // FIX Issue 2: Auto-advance state
  const [autoAdvanceEnabled, setAutoAdvanceEnabled] = useState(false);
  const [cooldownSeconds, setCooldownSeconds] = useState(10);
  const [cooldownRemaining, setCooldownRemaining] = useState(0);

  // FIX #3: Cleanup WebSocket and timer on unmount to prevent memory leaks
  useEffect(() => {
    console.log('[QuizParticipant] Component mounted');

    return () => {
      console.log('[QuizParticipant] Component unmounting, cleaning up resources');

      // Cleanup WebSocket
      if (wsRef.current) {
        if (wsRef.current.readyState !== WebSocket.CLOSED) {
          console.log('[QuizParticipant] Closing WebSocket connection');
          wsRef.current.close();
        }
        wsRef.current = null;
      }

      // Cleanup timer
      if (timerRef.current) {
        console.log('[QuizParticipant] Clearing timer interval');
        clearInterval(timerRef.current);
        timerRef.current = null;
      }

      // Cleanup leaderboard timer
      if (leaderboardTimerRef.current) {
        console.log('[QuizParticipant] Clearing leaderboard timer');
        clearTimeout(leaderboardTimerRef.current);
        leaderboardTimerRef.current = null;
      }
    };
  }, []);

  const handleJoin = (joinResponse) => {
    console.log('[QuizParticipant] Join successful:', {
      sessionId: joinResponse.session.id,
      participantId: joinResponse.participant.id,
      participantName: joinResponse.participant.guest_name,
      roomCode: joinResponse.session.room_code
    });

    setSession(joinResponse.session);
    setParticipant(joinResponse.participant);
    setGuestToken(joinResponse.guest_token);
    setPhase('waiting');

    console.log('[QuizParticipant] Phase changed to: waiting');

    // Connect WebSocket
    connectWebSocket(joinResponse.session.id, joinResponse.guest_token);
  };

  const connectWebSocket = (sessionId, token) => {
    console.log('[QuizParticipant] Connecting WebSocket for session:', sessionId);

    try {
      const ws = quizService.connectWebSocket(sessionId, token, false);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        console.log('[QuizParticipant] WebSocket message received');
        const message = JSON.parse(event.data);
        handleWebSocketMessage(message);
      };

      ws.onerror = (error) => {
        console.error('[QuizParticipant] ❌ WebSocket error:', error);
      };

      ws.onclose = (event) => {
        console.log(`[QuizParticipant] 🔌 WebSocket disconnected - Code: ${event.code}, Clean: ${event.wasClean}`);
      };

      console.log('[QuizParticipant] WebSocket connection initiated');
    } catch (err) {
      console.error('[QuizParticipant] Failed to connect WebSocket:', err);
      setError("Failed to establish real-time connection.");
    }
  };

  const handleWebSocketMessage = (message) => {
    console.log('[QuizParticipant] Processing WebSocket message:', message.type);

    switch (message.type) {
      case 'session_started':
        console.log('[QuizParticipant] Session started');
        setPhase('waiting');
        break;

      case 'question_started':
        console.log('[QuizParticipant] Question started:', {
          questionId: message.question.id,
          questionText: message.question.text,
          timeLimit: message.question.time_limit_seconds,
          points: message.question.points
        });
        setCurrentQuestion(message.question);
        setTimeRemaining(message.question.time_limit_seconds);
        setPhase('question');
        startTimer(message.question.time_limit_seconds);
        break;

      case 'leaderboard_update':
        console.log('[QuizParticipant] Leaderboard update received:', {
          participantCount: message.leaderboard?.length || 0,
          sessionStatus: session?.status
        });
        setLeaderboard(message.leaderboard || []);

        // FIX Issue 1: Only show leaderboard if session is active
        // Don't show it on join (when session is still 'waiting')
        if (session?.status === 'active') {
          console.log('[QuizParticipant] Session is active, showing leaderboard');
          setPhase('leaderboard');

          // Clear any existing leaderboard timer
          if (leaderboardTimerRef.current) {
            clearTimeout(leaderboardTimerRef.current);
          }

          // Auto-advance to next question after 10 seconds
          leaderboardTimerRef.current = setTimeout(() => {
            console.log('[QuizParticipant] Auto-advancing from leaderboard to waiting');
            setPhase('waiting');
          }, 10000);
        } else {
          console.log('[QuizParticipant] Session not active, staying in current phase');
        }
        break;

      case 'session_ended':
        console.log('[QuizParticipant] Session ended');

        // FIX Issue 3: Clear leaderboard timer to prevent switching back to waiting
        if (leaderboardTimerRef.current) {
          console.log('[QuizParticipant] Clearing leaderboard timer on session end');
          clearTimeout(leaderboardTimerRef.current);
          leaderboardTimerRef.current = null;
        }

        setPhase('finished');
        break;

      case 'auto_advance_updated':
        // FIX Issue 2: Auto-advance setting changed
        console.log('[QuizParticipant] Auto-advance updated:', message.enabled, message.cooldown_seconds);
        setAutoAdvanceEnabled(message.enabled);
        setCooldownSeconds(message.cooldown_seconds);
        break;

      case 'question_ended':
        // FIX BUG #2: Question ended, cooldown starting
        console.log('[QuizParticipant] Question ended, cooldown starting:', message.cooldown_seconds);
        setTimeRemaining(0);
        setCooldownRemaining(message.cooldown_seconds);
        break;

      case 'cooldown_started':
        // FIX BUG #1: Cooldown started from backend (ALL students see this)
        console.log('[QuizParticipant] Cooldown started:', message.cooldown_seconds);
        setCooldownSeconds(message.cooldown_seconds);
        setCooldownRemaining(message.cooldown_seconds);
        break;

      case 'ping':
        console.log('[QuizParticipant] Heartbeat ping received, sending pong');
        // Respond to heartbeat
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: 'pong' }));
        }
        break;

      default:
        console.warn('[QuizParticipant] Unknown message type:', message.type);
    }
  };

  const startTimer = (duration) => {
    console.log('[QuizParticipant] Starting timer:', duration, 'seconds');

    if (timerRef.current) {
      console.log('[QuizParticipant] Clearing existing timer');
      clearInterval(timerRef.current);
    }

    // Reset cooldown
    setCooldownRemaining(0);

    let remaining = duration;
    setTimeRemaining(remaining);

    timerRef.current = setInterval(() => {
      remaining -= 1;
      setTimeRemaining(remaining);

      if (remaining <= 0) {
        console.log('[QuizParticipant] Timer expired');
        clearInterval(timerRef.current);
      }
    }, 1000);
  };

  // FIX Issue 2: Start cooldown when time expires and auto-advance is enabled
  useEffect(() => {
    if (timeRemaining === 0 && autoAdvanceEnabled && phase === 'question') {
      console.log('[QuizParticipant] Starting cooldown countdown:', cooldownSeconds, 'seconds');
      let cooldownLeft = cooldownSeconds;
      setCooldownRemaining(cooldownLeft);

      const cooldownInterval = setInterval(() => {
        cooldownLeft -= 1;
        setCooldownRemaining(cooldownLeft);

        if (cooldownLeft <= 0) {
          console.log('[QuizParticipant] Cooldown finished');
          clearInterval(cooldownInterval);
          setCooldownRemaining(0);
        }
      }, 1000);

      // Cleanup on unmount or when phase changes
      return () => {
        clearInterval(cooldownInterval);
      };
    }
  }, [timeRemaining, autoAdvanceEnabled, cooldownSeconds, phase]);

  const handleAnswer = async (answer) => {
    console.log('[QuizParticipant] Submitting answer:', {
      questionId: currentQuestion.id,
      questionType: currentQuestion.type,
      answer: answer,
      timeRemaining: timeRemaining
    });

    try {
      const timeTaken = (currentQuestion.time_limit_seconds - timeRemaining) * 1000;

      console.log('[QuizParticipant] Time taken:', timeTaken, 'ms');

      // Format answer as array based on question type
      let formattedAnswer;
      if (currentQuestion.type === 'multiple_choice' || currentQuestion.type === 'poll') {
        formattedAnswer = [answer]; // Index number
      } else if (currentQuestion.type === 'true_false') {
        formattedAnswer = [answer]; // Boolean
      } else if (currentQuestion.type === 'short_answer') {
        formattedAnswer = [answer]; // String
      } else {
        formattedAnswer = [answer]; // Fallback
      }

      console.log('[QuizParticipant] Formatted answer for API:', formattedAnswer);

      await quizService.submitAnswer(
        session.id,
        {
          question_id: currentQuestion.id,
          answer: formattedAnswer,
          time_taken_ms: timeTaken
        },
        guestToken
      );

      console.log('[QuizParticipant] ✅ Answer submitted successfully');

      // FIX Issue 1: Do NOT clear timer - it should continue running until time expires
      // This allows all students to see the same countdown and cooldown timing
    } catch (err) {
      console.error('[QuizParticipant] ❌ Failed to submit answer:', err);
      setError(err.message || "Failed to submit answer.");
    }
  };

  if (phase === 'join') {
    return <JoinScreen onJoin={handleJoin} />;
  }

  if (phase === 'waiting') {
    return <WaitingRoom session={session} participantName={participant?.guest_name || participant?.display_name} />;
  }

  if (phase === 'question' && currentQuestion) {
    return (
      <QuestionDisplay
        question={currentQuestion}
        onAnswer={handleAnswer}
        timeRemaining={timeRemaining}
        cooldownRemaining={cooldownRemaining}
        autoAdvanceEnabled={autoAdvanceEnabled}
      />
    );
  }

  if (phase === 'leaderboard') {
    return <LeaderboardDisplay leaderboard={leaderboard} participantId={participant?.id} />;
  }

  if (phase === 'finished') {
    return (
      <Container maxWidth="md">
        <Fade in timeout={800}>
          <Box sx={{ mt: 8, textAlign: 'center' }}>
            <EmojiEventsIcon sx={{ fontSize: 120, color: 'warning.main', mb: 2 }} />
            <Typography variant="h3" sx={{ mb: 2, fontWeight: 700 }}>
              Quiz Completed!
            </Typography>
            <Typography variant="h5" color="text.secondary" sx={{ mb: 4 }}>
              Thank you for participating
            </Typography>
            <LeaderboardDisplay leaderboard={leaderboard} participantId={participant?.id} />
          </Box>
        </Fade>
      </Container>
    );
  }

  return null;
};

export default QuizParticipant;
