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
  const [isJoining, setIsJoining] = useState(false);
  const [error, setError] = useState(null);

  const handleJoin = async () => {
    if (!roomCode.trim() || !guestName.trim()) {
      setError("Please enter both room code and your name.");
      return;
    }

    try {
      setIsJoining(true);
      setError(null);
      const response = await quizService.joinSession(roomCode.toUpperCase(), guestName);
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
            Enter the room code provided by your teacher
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
              placeholder="Enter your name"
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
const QuestionDisplay = ({ question, onAnswer, timeRemaining }) => {
  const [selectedAnswer, setSelectedAnswer] = useState(null);
  const [isSubmitted, setIsSubmitted] = useState(false);

  const handleSelect = (answerIndex) => {
    if (!isSubmitted) {
      setSelectedAnswer(answerIndex);
    }
  };

  const handleSubmit = () => {
    if (selectedAnswer !== null && !isSubmitted) {
      setIsSubmitted(true);
      onAnswer(selectedAnswer);
    }
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
          {/* Timer */}
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

          {/* Answer Options */}
          <Grid container spacing={2}>
            {question.options && question.options.map((option, index) => (
              <Grid item xs={12} sm={6} key={index}>
                <Grow in timeout={300 * (index + 1)}>
                  <Button
                    fullWidth
                    variant={selectedAnswer === index ? 'contained' : 'outlined'}
                    size="large"
                    onClick={() => handleSelect(index)}
                    disabled={isSubmitted}
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

          {/* Submit Button */}
          {!isSubmitted && selectedAnswer !== null && (
            <Fade in>
              <Box sx={{ textAlign: 'center', mt: 4 }}>
                <Button
                  variant="contained"
                  size="large"
                  onClick={handleSubmit}
                  sx={{ px: 8, py: 2, fontSize: '1.2rem' }}
                >
                  Submit Answer
                </Button>
              </Box>
            </Fade>
          )}

          {isSubmitted && (
            <Fade in>
              <Alert severity="success" sx={{ mt: 4 }}>
                <Typography variant="h6">Answer submitted!</Typography>
                <Typography>Waiting for other participants...</Typography>
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

  const [phase, setPhase] = useState('join'); // join, waiting, question, leaderboard, finished
  const [session, setSession] = useState(null);
  const [participant, setParticipant] = useState(null);
  const [guestToken, setGuestToken] = useState(null);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [timeRemaining, setTimeRemaining] = useState(30);
  const [error, setError] = useState(null);

  useEffect(() => {
    return () => {
      // Cleanup WebSocket and timer
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, []);

  const handleJoin = (joinResponse) => {
    setSession(joinResponse.session);
    setParticipant(joinResponse.participant);
    setGuestToken(joinResponse.guest_token);
    setPhase('waiting');

    // Connect WebSocket
    connectWebSocket(joinResponse.session.id, joinResponse.guest_token);
  };

  const connectWebSocket = (sessionId, token) => {
    try {
      const ws = quizService.connectWebSocket(sessionId, token, false);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handleWebSocketMessage(message);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
      };
    } catch (err) {
      console.error("Failed to connect WebSocket:", err);
      setError("Failed to establish real-time connection.");
    }
  };

  const handleWebSocketMessage = (message) => {
    console.log('WebSocket message:', message);

    switch (message.type) {
      case 'session_started':
        setPhase('waiting');
        break;

      case 'question_started':
        setCurrentQuestion(message.question);
        setTimeRemaining(message.question.time_limit_seconds);
        setPhase('question');
        startTimer(message.question.time_limit_seconds);
        break;

      case 'leaderboard_update':
        setLeaderboard(message.leaderboard || []);
        setPhase('leaderboard');
        // Auto-advance to next question after 10 seconds
        setTimeout(() => {
          setPhase('waiting');
        }, 10000);
        break;

      case 'session_ended':
        setPhase('finished');
        break;

      case 'ping':
        // Respond to heartbeat
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: 'pong' }));
        }
        break;

      default:
        console.log('Unknown message type:', message.type);
    }
  };

  const startTimer = (duration) => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
    }

    let remaining = duration;
    setTimeRemaining(remaining);

    timerRef.current = setInterval(() => {
      remaining -= 1;
      setTimeRemaining(remaining);

      if (remaining <= 0) {
        clearInterval(timerRef.current);
      }
    }, 1000);
  };

  const handleAnswer = async (answerIndex) => {
    try {
      const timeTaken = (currentQuestion.time_limit_seconds - timeRemaining) * 1000;

      await quizService.submitAnswer(
        session.id,
        {
          question_id: currentQuestion.id,
          answer: [answerIndex],
          time_taken_ms: timeTaken
        },
        guestToken
      );

      // Clear timer
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    } catch (err) {
      console.error("Failed to submit answer:", err);
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
