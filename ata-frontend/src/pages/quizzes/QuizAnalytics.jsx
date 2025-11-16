// /src/pages/quizzes/QuizAnalytics.jsx

import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  IconButton,
  Tooltip,
  Alert,
  AlertTitle,
  Skeleton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  LinearProgress,
  Divider
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import DownloadIcon from '@mui/icons-material/Download';
import PeopleIcon from '@mui/icons-material/People';
import QuizIcon from '@mui/icons-material/Quiz';
import ScoreIcon from '@mui/icons-material/Score';
import TimerIcon from '@mui/icons-material/Timer';
import VisibilityIcon from '@mui/icons-material/Visibility';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';

import quizService from '../../services/quizService';

/**
 * Summary stat cards component
 */
const SessionSummaryCards = ({ analytics }) => {
  const stats = [
    {
      title: 'Total Participants',
      value: analytics.total_participants,
      icon: <PeopleIcon fontSize="large" />,
      color: 'primary.main'
    },
    {
      title: 'Average Score',
      value: `${analytics.average_score.toFixed(1)} pts`,
      icon: <ScoreIcon fontSize="large" />,
      color: 'success.main'
    },
    {
      title: 'Questions Completed',
      value: `${analytics.questions_completed}/${analytics.total_questions}`,
      icon: <QuizIcon fontSize="large" />,
      color: 'info.main'
    },
    {
      title: 'Duration',
      value: analytics.duration_minutes ? `${analytics.duration_minutes.toFixed(1)} min` : 'N/A',
      icon: <TimerIcon fontSize="large" />,
      color: 'warning.main'
    }
  ];

  return (
    <Grid container spacing={3} sx={{ mb: 4 }}>
      {stats.map((stat, index) => (
        <Grid item xs={12} sm={6} md={3} key={index}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Box
                  sx={{
                    bgcolor: stat.color,
                    color: 'white',
                    p: 1,
                    borderRadius: 1,
                    mr: 2
                  }}
                >
                  {stat.icon}
                </Box>
                <Typography variant="h4" component="div">
                  {stat.value}
                </Typography>
              </Box>
              <Typography color="text.secondary">
                {stat.title}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      ))}
    </Grid>
  );
};

/**
 * Question breakdown table component
 */
const QuestionBreakdown = ({ questions }) => {
  return (
    <Card sx={{ mb: 4 }}>
      <CardContent>
        <Typography variant="h5" gutterBottom>
          Question Performance
        </Typography>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>#</TableCell>
                <TableCell>Question</TableCell>
                <TableCell>Type</TableCell>
                <TableCell align="right">Responses</TableCell>
                <TableCell align="right">Correct</TableCell>
                <TableCell align="right">Accuracy</TableCell>
                <TableCell align="right">Avg Time</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {questions.map((q, index) => (
                <TableRow key={q.question_id}>
                  <TableCell>{index + 1}</TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {q.question_text}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip label={q.question_type} size="small" variant="outlined" />
                  </TableCell>
                  <TableCell align="right">{q.total_responses}</TableCell>
                  <TableCell align="right">{q.correct_responses}</TableCell>
                  <TableCell align="right">
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
                      <Typography variant="body2" sx={{ mr: 1 }}>
                        {(q.accuracy_rate * 100).toFixed(1)}%
                      </Typography>
                      <LinearProgress
                        variant="determinate"
                        value={q.accuracy_rate * 100}
                        sx={{ width: 60 }}
                        color={q.accuracy_rate >= 0.7 ? 'success' : q.accuracy_rate >= 0.4 ? 'warning' : 'error'}
                      />
                    </Box>
                  </TableCell>
                  <TableCell align="right">{(q.average_time_ms / 1000).toFixed(1)}s</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </CardContent>
    </Card>
  );
};

/**
 * Participant results table component
 */
const ParticipantTable = ({ participants, onViewDetails }) => {
  return (
    <Card>
      <CardContent>
        <Typography variant="h5" gutterBottom>
          Participant Results
        </Typography>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Rank</TableCell>
                <TableCell>Name</TableCell>
                <TableCell align="right">Score</TableCell>
                <TableCell align="right">Correct</TableCell>
                <TableCell align="right">Total</TableCell>
                <TableCell align="right">Accuracy</TableCell>
                <TableCell align="right">Avg Time</TableCell>
                <TableCell align="center">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {participants.map((p) => (
                <TableRow key={p.participant_id}>
                  <TableCell>
                    <Chip
                      label={`#${p.rank}`}
                      color={p.rank === 1 ? 'primary' : 'default'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>{p.display_name}</TableCell>
                  <TableCell align="right">
                    <Typography variant="body1" fontWeight="bold">
                      {p.score}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">{p.correct_answers}</TableCell>
                  <TableCell align="right">{p.total_answers}</TableCell>
                  <TableCell align="right">
                    <Typography
                      color={
                        p.accuracy_rate >= 0.7 ? 'success.main' :
                        p.accuracy_rate >= 0.4 ? 'warning.main' : 'error.main'
                      }
                    >
                      {(p.accuracy_rate * 100).toFixed(1)}%
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    {(p.average_time_per_question_ms / 1000).toFixed(1)}s
                  </TableCell>
                  <TableCell align="center">
                    <Tooltip title="View detailed responses">
                      <IconButton
                        size="small"
                        onClick={() => onViewDetails(p.participant_id)}
                        color="primary"
                      >
                        <VisibilityIcon />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </CardContent>
    </Card>
  );
};

/**
 * Participant detail modal component
 */
const ParticipantDetailModal = ({ open, onClose, participantId, sessionId }) => {
  const [participantDetail, setParticipantDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (open && participantId && sessionId) {
      fetchParticipantDetail();
    }
  }, [open, participantId, sessionId]);

  const fetchParticipantDetail = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await quizService.getParticipantDetailAnalytics(sessionId, participantId);
      setParticipantDetail(data);
    } catch (err) {
      console.error('Error fetching participant details:', err);
      setError(err.message || 'Failed to load participant details');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        Participant Details
      </DialogTitle>
      <DialogContent>
        {loading && (
          <Box sx={{ py: 4 }}>
            <Skeleton variant="rectangular" height={200} />
          </Box>
        )}

        {error && (
          <Alert severity="error">
            <AlertTitle>Error</AlertTitle>
            {error}
          </Alert>
        )}

        {participantDetail && !loading && (
          <Box>
            {/* Participant Summary */}
            <Box sx={{ mb: 3 }}>
              <Typography variant="h6" gutterBottom>{participantDetail.display_name}</Typography>
              <Grid container spacing={2}>
                <Grid item xs={6} sm={3}>
                  <Typography variant="body2" color="text.secondary">Rank</Typography>
                  <Typography variant="h6">#{participantDetail.rank}</Typography>
                </Grid>
                <Grid item xs={6} sm={3}>
                  <Typography variant="body2" color="text.secondary">Score</Typography>
                  <Typography variant="h6">{participantDetail.score}</Typography>
                </Grid>
                <Grid item xs={6} sm={3}>
                  <Typography variant="body2" color="text.secondary">Accuracy</Typography>
                  <Typography variant="h6">{(participantDetail.accuracy_rate * 100).toFixed(1)}%</Typography>
                </Grid>
                <Grid item xs={6} sm={3}>
                  <Typography variant="body2" color="text.secondary">Avg Time</Typography>
                  <Typography variant="h6">{(participantDetail.average_time_per_question_ms / 1000).toFixed(1)}s</Typography>
                </Grid>
              </Grid>
            </Box>

            <Divider sx={{ my: 2 }} />

            {/* Individual Responses */}
            <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
              Individual Responses
            </Typography>
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Question</TableCell>
                    <TableCell align="center">Result</TableCell>
                    <TableCell align="right">Points</TableCell>
                    <TableCell align="right">Time</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {participantDetail.responses.map((response, index) => (
                    <TableRow key={response.response_id}>
                      <TableCell>Q{index + 1}</TableCell>
                      <TableCell align="center">
                        {response.is_correct === true ? (
                          <Tooltip title="Correct">
                            <CheckCircleIcon color="success" />
                          </Tooltip>
                        ) : response.is_correct === false ? (
                          <Tooltip title="Incorrect">
                            <CancelIcon color="error" />
                          </Tooltip>
                        ) : (
                          <Tooltip title="Poll question">
                            <Typography variant="body2">-</Typography>
                          </Tooltip>
                        )}
                      </TableCell>
                      <TableCell align="right">{response.points_earned}</TableCell>
                      <TableCell align="right">{(response.time_taken_ms / 1000).toFixed(1)}s</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};

/**
 * Main QuizAnalytics component
 */
const QuizAnalytics = () => {
  const { quizId } = useParams();
  const navigate = useNavigate();

  const [quiz, setQuiz] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [participants, setParticipants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Participant detail modal state
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [selectedParticipantId, setSelectedParticipantId] = useState(null);

  useEffect(() => {
    fetchAnalyticsData();
  }, [quizId]);

  const fetchAnalyticsData = async () => {
    setLoading(true);
    setError(null);

    try {
      // Get quiz details
      const quizData = await quizService.getQuizById(quizId);
      setQuiz(quizData);

      // Get all sessions for this quiz
      const allSessions = await quizService.getAllSessions();
      const quizSessions = allSessions.filter(s => s.quiz_id === quizId && s.status === 'completed');

      if (quizSessions.length === 0) {
        setError('No completed sessions found for this quiz.');
        return;
      }

      // Get the most recent completed session
      const latestSession = quizSessions.sort((a, b) =>
        new Date(b.ended_at) - new Date(a.ended_at)
      )[0];

      setSessionId(latestSession.id);

      // Fetch session analytics
      const analyticsData = await quizService.getSessionAnalytics(latestSession.id);
      setAnalytics(analyticsData);

      // Fetch participant analytics
      const participantData = await quizService.getParticipantAnalytics(latestSession.id);
      setParticipants(participantData);

    } catch (err) {
      console.error('Error loading analytics:', err);
      setError(err.message || 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  };

  const handleExportCSV = async () => {
    if (!sessionId) return;

    try {
      await quizService.exportSessionCSV(sessionId);
    } catch (err) {
      console.error('Error exporting CSV:', err);
      alert('Failed to export CSV: ' + err.message);
    }
  };

  const handleViewParticipantDetails = (participantId) => {
    setSelectedParticipantId(participantId);
    setDetailModalOpen(true);
  };

  const handleCloseDetailModal = () => {
    setDetailModalOpen(false);
    setSelectedParticipantId(null);
  };

  if (loading) {
    return (
      <Box sx={{ p: 3 }}>
        <Skeleton variant="text" width={300} height={60} />
        <Skeleton variant="rectangular" height={200} sx={{ mt: 2 }} />
        <Skeleton variant="rectangular" height={400} sx={{ mt: 2 }} />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate('/quizzes')}
          sx={{ mb: 2 }}
        >
          Back to Quizzes
        </Button>
        <Alert severity="error">
          <AlertTitle>Error</AlertTitle>
          {error}
        </Alert>
      </Box>
    );
  }

  if (!analytics) {
    return null;
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
        <Box>
          <Button
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate('/quizzes')}
            sx={{ mb: 1 }}
          >
            Back to Quizzes
          </Button>
          <Typography variant="h3" component="h1">
            {analytics.quiz_title} - Analytics
          </Typography>
          <Typography color="text.secondary" sx={{ mt: 1 }}>
            Room Code: {analytics.room_code} • Status: {analytics.status}
          </Typography>
          {analytics.started_at && (
            <Typography variant="body2" color="text.secondary">
              Started: {new Date(analytics.started_at).toLocaleString()}
              {analytics.ended_at && ` • Ended: ${new Date(analytics.ended_at).toLocaleString()}`}
            </Typography>
          )}
        </Box>
        <Button
          variant="contained"
          startIcon={<DownloadIcon />}
          onClick={handleExportCSV}
        >
          Export CSV
        </Button>
      </Box>

      {/* Summary Cards */}
      <SessionSummaryCards analytics={analytics} />

      {/* Additional Stats */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Score Distribution</Typography>
              <Grid container spacing={2}>
                <Grid item xs={4}>
                  <Typography variant="body2" color="text.secondary">Highest</Typography>
                  <Typography variant="h5">{analytics.highest_score}</Typography>
                </Grid>
                <Grid item xs={4}>
                  <Typography variant="body2" color="text.secondary">Median</Typography>
                  <Typography variant="h5">{analytics.median_score.toFixed(1)}</Typography>
                </Grid>
                <Grid item xs={4}>
                  <Typography variant="body2" color="text.secondary">Lowest</Typography>
                  <Typography variant="h5">{analytics.lowest_score}</Typography>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Overall Performance</Typography>
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">Average Accuracy</Typography>
                  <Typography variant="h5">{(analytics.average_accuracy_rate * 100).toFixed(1)}%</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">Active Participants</Typography>
                  <Typography variant="h5">{analytics.active_participants}/{analytics.total_participants}</Typography>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Question Breakdown */}
      {analytics.question_analytics && analytics.question_analytics.length > 0 && (
        <QuestionBreakdown questions={analytics.question_analytics} />
      )}

      {/* Participant Results */}
      {participants.length > 0 && (
        <ParticipantTable
          participants={participants}
          onViewDetails={handleViewParticipantDetails}
        />
      )}

      {/* Participant Detail Modal */}
      <ParticipantDetailModal
        open={detailModalOpen}
        onClose={handleCloseDetailModal}
        participantId={selectedParticipantId}
        sessionId={sessionId}
      />
    </Box>
  );
};

export default QuizAnalytics;
