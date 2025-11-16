// /src/pages/quizzes/QuizHost.jsx

// --- Core React Imports ---
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

// --- MUI Component Imports ---
import {
  Box,
  Button,
  Typography,
  Paper,
  Card,
  CardContent,
  Grid,
  Chip,
  LinearProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Avatar,
  Divider,
  IconButton,
  Tooltip,
  Fade,
  Switch,
  FormControlLabel,
  TextField
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import SkipNextIcon from '@mui/icons-material/SkipNext';
import PeopleIcon from '@mui/icons-material/People';
import QrCode2Icon from '@mui/icons-material/QrCode2';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import LeaderboardIcon from '@mui/icons-material/Leaderboard';
import BarChartIcon from '@mui/icons-material/BarChart';
import CloseIcon from '@mui/icons-material/Close';
import EmojiEventsIcon from '@mui/icons-material/EmojiEvents';
import TimerIcon from '@mui/icons-material/Timer';

// --- Service Import ---
import quizService from '../../services/quizService';

// --- QR Code Import ---
import { QRCodeSVG } from 'qrcode.react';

/**
 * Leaderboard Component
 */
const Leaderboard = ({ participants }) => {
  const getMedalColor = (rank) => {
    switch (rank) {
      case 1: return '#FFD700'; // Gold
      case 2: return '#C0C0C0'; // Silver
      case 3: return '#CD7F32'; // Bronze
      default: return 'primary';
    }
  };

  return (
    <List sx={{ width: '100%' }}>
      {participants.slice(0, 10).map((participant, index) => (
        <Fade in key={participant.participant_id} timeout={300 * (index + 1)}>
          <ListItem
            sx={{
              mb: 1,
              borderRadius: 2,
              backgroundColor: index < 3 ? 'action.hover' : 'transparent',
              border: index < 3 ? 2 : 1,
              borderColor: index < 3 ? getMedalColor(index + 1) : 'divider'
            }}
          >
            <ListItemAvatar>
              <Avatar
                sx={{
                  bgcolor: getMedalColor(index + 1),
                  fontWeight: 'bold',
                  fontSize: '1.2rem'
                }}
              >
                {index < 3 ? <EmojiEventsIcon /> : index + 1}
              </Avatar>
            </ListItemAvatar>
            <ListItemText
              primary={
                <Typography variant="h6" sx={{ fontWeight: index < 3 ? 600 : 400 }}>
                  {participant.display_name}
                </Typography>
              }
              secondary={
                <Box sx={{ display: 'flex', gap: 2, mt: 0.5 }}>
                  <Chip
                    label={`${participant.score} pts`}
                    size="small"
                    color="primary"
                    variant={index < 3 ? 'filled' : 'outlined'}
                  />
                  <Chip
                    label={`${participant.correct_answers} correct`}
                    size="small"
                    color="success"
                    variant="outlined"
                  />
                  <Chip
                    label={`${(participant.total_time_ms / 1000).toFixed(1)}s`}
                    size="small"
                    variant="outlined"
                  />
                </Box>
              }
              secondaryTypographyProps={{ component: 'div' }}
            />
          </ListItem>
        </Fade>
      ))}
    </List>
  );
};

/**
 * Main Quiz Host Control Panel
 */
const QuizHost = () => {
  const navigate = useNavigate();
  const { sessionId } = useParams();
  const wsRef = useRef(null);

  const [session, setSession] = useState(null);
  const [quiz, setQuiz] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Real-time state
  const [participants, setParticipants] = useState([]);
  const [leaderboard, setLeaderboard] = useState([]);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [answersReceived, setAnswersReceived] = useState(0);
  const [wsConnected, setWsConnected] = useState(false);

  // FIX Issue 2: Auto-advance state - DEFAULT TO TRUE so scheduler is enabled
  const [autoAdvanceEnabled, setAutoAdvanceEnabled] = useState(true);
  const [cooldownSeconds, setCooldownSeconds] = useState(10);

  // Timer state for teacher display
  const [timeRemaining, setTimeRemaining] = useState(0);
  const [cooldownRemaining, setCooldownRemaining] = useState(0);
  const timerRef = useRef(null);

  // Dialogs
  const [endDialog, setEndDialog] = useState(false);

  // Load session data
  useEffect(() => {
    console.log('[QuizHost] Mounting component, sessionId:', sessionId);
    loadSession();

    // FIX #3: Cleanup function to prevent memory leaks
    return () => {
      console.log('[QuizHost] Component unmounting, cleaning up WebSocket');
      if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [sessionId]);

  // Connect WebSocket - FIX #3: Only reconnect when session.id changes, not entire object
  useEffect(() => {
    if (!session?.id) {
      console.log('[QuizHost] No session ID, skipping WebSocket connection');
      return;
    }

    console.log('[QuizHost] Session loaded, connecting WebSocket for session:', session.id);
    connectWebSocket();

    // FIX #3: Cleanup function to close WebSocket when effect re-runs or unmounts
    return () => {
      console.log('[QuizHost] WebSocket effect cleanup');
      if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
        console.log('[QuizHost] Closing WebSocket connection');
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [session?.id]); // Only re-run when session.id changes, not entire session object

  // FIX: Load auto-advance settings from session config
  useEffect(() => {
    if (session?.config_snapshot) {
      const config = session.config_snapshot;
      if (config.auto_advance_enabled !== undefined) {
        setAutoAdvanceEnabled(config.auto_advance_enabled);
      }
      if (config.cooldown_seconds !== undefined) {
        setCooldownSeconds(config.cooldown_seconds);
      }
    }
  }, [session?.config_snapshot]);

  // 🔥 CRITICAL FIX: Auto-enable auto-advance when session is created
  // This ensures the backend scheduler job is created when quiz starts
  useEffect(() => {
    const enableAutoAdvance = async () => {
      // Only enable if:
      // 1. Session exists and is in 'waiting' status (not started yet)
      // 2. Config doesn't already have auto_advance_enabled set to true
      if (session && session.status === 'waiting') {
        const currentConfig = session.config_snapshot || {};

        // If auto-advance isn't explicitly set, or is set to false, enable it
        if (currentConfig.auto_advance_enabled !== true) {
          console.log('[QuizHost] 🚀 Auto-enabling auto-advance for session:', sessionId);
          console.log('[QuizHost] Current config:', currentConfig);

          try {
            await quizService.toggleAutoAdvance(sessionId, true, cooldownSeconds);
            console.log('[QuizHost] ✅ Auto-advance enabled successfully');
          } catch (err) {
            console.error('[QuizHost] ❌ Failed to auto-enable auto-advance:', err);
          }
        } else {
          console.log('[QuizHost] Auto-advance already enabled in config');
        }
      }
    };

    enableAutoAdvance();
  }, [session?.id, session?.status, sessionId, cooldownSeconds]); // Run when session loads or status changes

  const loadSession = async () => {
    try {
      setIsLoading(true);
      const sessionData = await quizService.getSession(sessionId);
      setSession(sessionData);

      // Load quiz details
      const quizData = await quizService.getQuizById(sessionData.quiz_id);
      setQuiz(quizData);

      // Load initial leaderboard
      const leaderboardData = await quizService.getLeaderboard(sessionId);
      console.log('[QuizHost] Leaderboard API response:', leaderboardData);
      // FIX: Extract entries array from LeaderboardResponse object
      setLeaderboard(leaderboardData.entries || []);

      setError(null);
    } catch (err) {
      console.error("Failed to load session:", err);
      setError(err.message || "Failed to load quiz session.");
    } finally {
      setIsLoading(false);
    }
  };

  const connectWebSocket = () => {
    const token = localStorage.getItem('authToken');
    if (!token) {
      setError("Authentication token not found.");
      return;
    }

    try {
      const ws = quizService.connectWebSocket(sessionId, token, true);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket connected');
        setWsConnected(true);
      };

      ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handleWebSocketMessage(message);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setWsConnected(false);
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setWsConnected(false);
        // Attempt reconnection after 3 seconds
        setTimeout(() => {
          if (session && session.status !== 'completed') {
            connectWebSocket();
          }
        }, 3000);
      };
    } catch (err) {
      console.error("Failed to connect WebSocket:", err);
      setError("Failed to establish real-time connection.");
    }
  };

  const handleWebSocketMessage = (message) => {
    console.log('WebSocket message:', message);

    switch (message.type) {
      case 'connection_established':
        console.log('Connection established');
        break;

      case 'participant_joined':
        // Update participant count
        loadSession();
        break;

      case 'participant_left':
        // Update participant count
        loadSession();
        break;

      case 'participant_answered':
        // Increment answers received
        setAnswersReceived(prev => prev + 1);
        break;

      case 'stats_update':
        // FIX: Update real-time stats from backend
        console.log('Stats update received:', message);
        setAnswersReceived(message.answers_received || 0);
        // Optionally update session with new participant count
        if (message.total_participants !== undefined) {
          setSession(prev => ({
            ...prev,
            total_participants: message.total_participants
          }));
        }
        break;

      case 'leaderboard_update':
        // Update leaderboard
        setLeaderboard(message.leaderboard || []);
        break;

      case 'question_started':
        // New question started
        setCurrentQuestion(message.question);
        setAnswersReceived(0);
        // FIX: Update session's current_question_index so counter displays correctly
        setSession(prev => ({
          ...prev,
          current_question_index: message.question.order_index
        }));
        // Start timer for teacher display
        if (message.question.time_limit_seconds) {
          startTimer(message.question.time_limit_seconds);
        }
        break;

      case 'auto_advance_updated':
        // FIX Issue 2: Auto-advance setting changed
        setAutoAdvanceEnabled(message.enabled);
        setCooldownSeconds(message.cooldown_seconds);
        console.log('[QuizHost] Auto-advance updated:', message.enabled, message.cooldown_seconds);
        break;

      case 'question_ended':
        // FIX BUG #2: Question ended, cooldown starting
        console.log('[QuizHost] Question ended, cooldown starting:', message.cooldown_seconds);
        setTimeRemaining(0);
        setCooldownRemaining(message.cooldown_seconds);
        break;

      case 'cooldown_started':
        // FIX BUG #1: Cooldown started from backend
        console.log('[QuizHost] Cooldown started:', message.cooldown_seconds);
        setCooldownSeconds(message.cooldown_seconds);
        setCooldownRemaining(message.cooldown_seconds);
        break;

      case 'session_ended':
        // FIX BUG #3: Handle session ended (from auto-advance after last question)
        console.log('[QuizHost] Session ended via websocket:', message.reason);
        setSession(prev => ({
          ...prev,
          status: message.final_status || 'completed',
          ended_at: new Date().toISOString()
        }));

        // Clear any pending timers
        if (timerRef.current) {
          clearInterval(timerRef.current);
        }

        // Navigate to analytics after 2 seconds
        setTimeout(() => {
          console.log('[QuizHost] Navigating to analytics...');
          navigate(`/quizzes/${session.quiz_id}/sessions/${sessionId}/analytics`);
        }, 2000);
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

  // FIX Issue 2: Handle auto-advance toggle
  const handleToggleAutoAdvance = async (enabled, cooldownOverride = null) => {
    try {
      const cooldownToUse = cooldownOverride !== null ? cooldownOverride : cooldownSeconds;
      await quizService.toggleAutoAdvance(sessionId, enabled, cooldownToUse);
      setAutoAdvanceEnabled(enabled);
    } catch (err) {
      console.error("Failed to toggle auto-advance:", err);
      setError(err.message || "Failed to toggle auto-advance.");
    }
  };

  // Timer functions for teacher display
  const startTimer = (duration) => {
    console.log('[QuizHost] Starting timer:', duration, 'seconds');

    if (timerRef.current) {
      clearInterval(timerRef.current);
    }

    let remaining = duration;
    setTimeRemaining(remaining);
    setCooldownRemaining(0);

    timerRef.current = setInterval(() => {
      remaining -= 1;
      setTimeRemaining(remaining);

      if (remaining <= 0) {
        console.log('[QuizHost] Timer expired');
        clearInterval(timerRef.current);
      }
    }, 1000);
  };

  // Start cooldown timer when question time expires and auto-advance is enabled
  useEffect(() => {
    if (timeRemaining === 0 && autoAdvanceEnabled && currentQuestion && session?.status === 'active') {
      console.log('[QuizHost] Starting cooldown countdown:', cooldownSeconds, 'seconds');
      let cooldownLeft = cooldownSeconds;
      setCooldownRemaining(cooldownLeft);

      const cooldownInterval = setInterval(() => {
        cooldownLeft -= 1;
        setCooldownRemaining(cooldownLeft);

        if (cooldownLeft <= 0) {
          console.log('[QuizHost] Cooldown finished');
          clearInterval(cooldownInterval);
          setCooldownRemaining(0);
        }
      }, 1000);

      return () => {
        clearInterval(cooldownInterval);
      };
    }
  }, [timeRemaining, autoAdvanceEnabled, cooldownSeconds, currentQuestion, session?.status]);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, []);

  // FIX Issue 6: Auto-navigate to analytics when quiz ends
  useEffect(() => {
    if (session?.status === 'completed') {
      console.log('[QuizHost] Quiz completed, navigating to analytics after 3 seconds...');
      const navigateTimer = setTimeout(() => {
        navigate(`/quizzes/${session.quiz_id}/sessions/${sessionId}/analytics`);
      }, 3000); // Give teacher 3 seconds to see completion message

      return () => clearTimeout(navigateTimer);
    }
  }, [session?.status, session?.quiz_id, sessionId, navigate]);

  const handleStart = async () => {
    try {
      await quizService.startSession(sessionId);
      await loadSession();
    } catch (err) {
      console.error("Failed to start session:", err);
      setError(err.message || "Failed to start quiz session.");
    }
  };

  const handleNextQuestion = async () => {
    try {
      await quizService.nextQuestion(sessionId);
      setAnswersReceived(0);
    } catch (err) {
      console.error("Failed to advance question:", err);
      setError(err.message || "Failed to advance to next question.");
    }
  };

  const handleEnd = async () => {
    try {
      await quizService.endSession(sessionId);
      setEndDialog(false);
      navigate('/quizzes');
    } catch (err) {
      console.error("Failed to end session:", err);
      setError(err.message || "Failed to end quiz session.");
      setEndDialog(false);
    }
  };

  const copyRoomCode = () => {
    if (session?.room_code) {
      navigator.clipboard.writeText(session.room_code);
    }
  };

  // Generate join URL for students
  const getJoinUrl = () => {
    if (!session?.room_code) return '';
    const baseUrl = window.location.origin;
    return `${baseUrl}/quiz/join/${session.room_code}`;
  };

  // Copy join URL to clipboard
  const copyJoinUrl = () => {
    const url = getJoinUrl();
    if (url) {
      navigator.clipboard.writeText(url);
      console.log('[QuizHost] Join URL copied to clipboard:', url);
    }
  };

  const getCompletionRate = () => {
    if (!session || session.total_participants === 0) return 0;
    return Math.round((answersReceived / session.total_participants) * 100);
  };

  if (isLoading) {
    return (
      <Box sx={{ p: 3 }}>
        <LinearProgress />
        <Typography sx={{ mt: 2 }}>Loading quiz session...</Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{error}</Alert>
        <Button onClick={() => navigate('/quizzes')} sx={{ mt: 2 }}>
          Back to Quizzes
        </Button>
      </Box>
    );
  }

  return (
    <Box>
      {/* Header with Room Code and QR Code */}
      <Paper
        sx={{
          p: 4,
          mb: 3,
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          color: 'white'
        }}
      >
        <Typography variant="h3" sx={{ mb: 3, fontWeight: 700, textAlign: 'center' }}>
          {quiz?.title}
        </Typography>

        <Grid container spacing={4} alignItems="center">
          {/* Left: Room Code and Join Link */}
          <Grid item xs={12} md={8}>
            <Box sx={{ textAlign: 'center' }}>
              {/* Room Code */}
              <Typography variant="h6" sx={{ mb: 2 }}>
                Room Code:
              </Typography>
              <Box
                sx={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 1,
                  backgroundColor: 'rgba(255, 255, 255, 0.2)',
                  borderRadius: 2,
                  px: 3,
                  py: 1.5,
                  border: '3px dashed rgba(255, 255, 255, 0.5)',
                  mb: 3
                }}
              >
                <Typography
                  variant="h2"
                  sx={{
                    fontWeight: 900,
                    letterSpacing: 8,
                    fontFamily: 'monospace'
                  }}
                >
                  {session?.room_code}
                </Typography>
                <Tooltip title="Copy room code">
                  <IconButton onClick={copyRoomCode} sx={{ color: 'white' }}>
                    <ContentCopyIcon />
                  </IconButton>
                </Tooltip>
              </Box>

              {/* Join Link */}
              <Box>
                <Typography variant="subtitle2" sx={{ mb: 1, opacity: 0.9 }}>
                  Student Join Link:
                </Typography>
                <Box
                  sx={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 1,
                    backgroundColor: 'rgba(255, 255, 255, 0.15)',
                    borderRadius: 1,
                    px: 2,
                    py: 1,
                    maxWidth: '100%'
                  }}
                >
                  <Typography
                    variant="body2"
                    sx={{
                      fontFamily: 'monospace',
                      fontSize: '0.9rem',
                      wordBreak: 'break-all'
                    }}
                  >
                    {getJoinUrl()}
                  </Typography>
                  <Tooltip title="Copy join link">
                    <IconButton onClick={copyJoinUrl} size="small" sx={{ color: 'white' }}>
                      <ContentCopyIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Box>
              </Box>
            </Box>
          </Grid>

          {/* Right: QR Code */}
          <Grid item xs={12} md={4}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Scan to Join:
              </Typography>
              <Box
                sx={{
                  display: 'inline-block',
                  p: 2,
                  backgroundColor: 'white',
                  borderRadius: 2,
                  boxShadow: 3
                }}
              >
                <QRCodeSVG
                  value={getJoinUrl()}
                  size={180}
                  level="H"
                  includeMargin={true}
                />
              </Box>
              <Typography variant="caption" sx={{ display: 'block', mt: 1, opacity: 0.9 }}>
                Students can scan this QR code to join
              </Typography>
            </Box>
          </Grid>
        </Grid>

        <Box sx={{ textAlign: 'center', mt: 2 }}>
          <Chip
            label={wsConnected ? '🟢 Live Connected' : '🔴 Disconnected'}
            sx={{ backgroundColor: 'rgba(255, 255, 255, 0.2)', color: 'white' }}
          />
        </Box>
      </Paper>

      {/* Main Content Grid */}
      <Grid container spacing={3}>
        {/* Left Column - Session Info and Controls */}
        <Grid item xs={12} md={4}>
          {/* Participants */}
          <Card sx={{ mb: 2 }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <PeopleIcon sx={{ mr: 1, fontSize: 40, color: 'primary.main' }} />
                <Box>
                  <Typography variant="h4" sx={{ fontWeight: 700 }}>
                    {session?.total_participants || 0}
                  </Typography>
                  <Typography color="text.secondary">Participants</Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>

          {/* Timer Display - Show question timer and cooldown timer */}
          {currentQuestion && session?.status === 'active' && (
            <Card sx={{ mb: 2 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>Question Timer</Typography>

                {cooldownRemaining > 0 ? (
                  // Cooldown Timer
                  <Box sx={{ textAlign: 'center', py: 2 }}>
                    <Alert severity="info" sx={{ mb: 2 }}>
                      <Typography variant="subtitle2" sx={{ mb: 1 }}>
                        Next Question Starting In
                      </Typography>
                      <Typography variant="h2" sx={{ fontWeight: 700, color: 'primary.main' }}>
                        {cooldownRemaining}s
                      </Typography>
                    </Alert>
                  </Box>
                ) : (
                  // Question Timer
                  <Box sx={{ textAlign: 'center', py: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', mb: 2 }}>
                      <TimerIcon sx={{ mr: 1, color: timeRemaining > 10 ? 'success.main' : timeRemaining > 5 ? 'warning.main' : 'error.main' }} />
                      <Typography
                        variant="h3"
                        color={timeRemaining > 10 ? 'success.main' : timeRemaining > 5 ? 'warning.main' : 'error.main'}
                        sx={{ fontWeight: 700 }}
                      >
                        {timeRemaining}s
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={(timeRemaining / (currentQuestion?.time_limit_seconds || 30)) * 100}
                      color={timeRemaining > 10 ? 'success' : timeRemaining > 5 ? 'warning' : 'error'}
                      sx={{ height: 8, borderRadius: 1 }}
                    />
                  </Box>
                )}
              </CardContent>
            </Card>
          )}

          {/* Current Question */}
          <Card sx={{ mb: 2 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>Current Question</Typography>
              <Typography variant="h3" color="primary" sx={{ fontWeight: 700 }}>
                {session?.current_question_index !== null
                  ? session.current_question_index + 1
                  : '-'}
              </Typography>
              <Typography color="text.secondary">
                of {session?.questions?.length || 0}
              </Typography>

              {session?.status === 'active' && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Answers Received: {answersReceived} / {session?.total_participants || 0}
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={getCompletionRate()}
                    sx={{ height: 8, borderRadius: 1 }}
                  />
                  <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>
                    {getCompletionRate()}% complete
                  </Typography>
                </Box>
              )}
            </CardContent>
          </Card>

          {/* Controls */}
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Session Controls</Typography>

              {/* FIX Issue 2: Auto-Advance Controls - Only show BEFORE quiz starts */}
              {session?.status === 'waiting' && (
                <Box sx={{ mb: 2, p: 2, border: '1px solid #e0e0e0', borderRadius: 1, backgroundColor: '#f9f9f9' }}>
                  <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
                    ⚙️ Auto-Advance Settings (Configure Before Starting)
                  </Typography>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={autoAdvanceEnabled}
                        onChange={(e) => handleToggleAutoAdvance(e.target.checked)}
                        color="primary"
                      />
                    }
                    label="Enable Auto-Advance"
                  />
                  <TextField
                    label="Cooldown (seconds)"
                    type="number"
                    value={cooldownSeconds}
                    onChange={(e) => {
                      const val = Math.max(1, parseInt(e.target.value) || 10);
                      setCooldownSeconds(val);
                      // FIX: Pass new value directly to avoid React state timing issue
                      if (autoAdvanceEnabled) {
                        handleToggleAutoAdvance(true, val);
                      }
                    }}
                    disabled={!autoAdvanceEnabled}
                    size="small"
                    sx={{ ml: 2, width: 150 }}
                    inputProps={{ min: 1, max: 60 }}
                  />
                  <Typography variant="caption" display="block" sx={{ mt: 1, color: 'text.secondary' }}>
                    Auto-advance will automatically move to the next question after the timer + cooldown period.
                  </Typography>
                </Box>
              )}

              {/* Show read-only auto-advance status during active quiz */}
              {session?.status === 'active' && autoAdvanceEnabled && (
                <Alert severity="info" sx={{ mb: 2 }}>
                  🚀 Auto-Advance Enabled ({cooldownSeconds}s cooldown)
                </Alert>
              )}

              {session?.status === 'waiting' && (
                <Button
                  fullWidth
                  variant="contained"
                  size="large"
                  startIcon={<PlayArrowIcon />}
                  onClick={handleStart}
                  sx={{ mb: 1 }}
                >
                  Start Quiz
                </Button>
              )}

              {session?.status === 'active' && (
                <>
                  <Button
                    fullWidth
                    variant="contained"
                    size="large"
                    startIcon={<SkipNextIcon />}
                    onClick={handleNextQuestion}
                    disabled={
                      session.current_question_index === null ||
                      session.current_question_index >= (session?.questions?.length || 0) - 1
                    }
                    sx={{ mb: 1 }}
                  >
                    Next Question
                  </Button>
                  <Button
                    fullWidth
                    variant="outlined"
                    size="large"
                    color="error"
                    startIcon={<StopIcon />}
                    onClick={() => setEndDialog(true)}
                  >
                    End Quiz
                  </Button>
                </>
              )}

              {session?.status === 'completed' && (
                <Alert severity="success" sx={{ mt: 2 }}>
                  Quiz completed! Results are available.
                </Alert>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Right Column - Leaderboard */}
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
                <LeaderboardIcon sx={{ mr: 1, fontSize: 32, color: 'primary.main' }} />
                <Typography variant="h5" sx={{ fontWeight: 600 }}>
                  Live Leaderboard
                </Typography>
              </Box>

              {leaderboard.length === 0 ? (
                <Box sx={{ textAlign: 'center', py: 8 }}>
                  <PeopleIcon sx={{ fontSize: 80, color: 'text.disabled', mb: 2 }} />
                  <Typography color="text.secondary">
                    Waiting for participants to join...
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    Share the room code: <strong>{session?.room_code}</strong>
                  </Typography>
                </Box>
              ) : (
                <Leaderboard participants={leaderboard} />
              )}
            </CardContent>
          </Card>

          {/* Question Preview (if active) */}
          {currentQuestion && (
            <Card sx={{ mt: 2 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>Current Question Preview</Typography>
                <Typography variant="h5" sx={{ mb: 2 }}>
                  {currentQuestion.text}
                </Typography>
                {currentQuestion.options && (
                  <Grid container spacing={2}>
                    {currentQuestion.options.map((option, index) => (
                      <Grid item xs={12} sm={6} key={index}>
                        <Paper
                          sx={{
                            p: 2,
                            backgroundColor: 'action.hover',
                            border: 1,
                            borderColor: 'divider'
                          }}
                        >
                          <Typography>{option}</Typography>
                        </Paper>
                      </Grid>
                    ))}
                  </Grid>
                )}
              </CardContent>
            </Card>
          )}
        </Grid>
      </Grid>

      {/* End Session Dialog */}
      <Dialog open={endDialog} onClose={() => setEndDialog(false)}>
        <DialogTitle>End Quiz Session?</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to end this quiz session? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEndDialog(false)}>Cancel</Button>
          <Button onClick={handleEnd} color="error" variant="contained">
            End Session
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default QuizHost;
