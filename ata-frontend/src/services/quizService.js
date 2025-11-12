// /src/services/quizService.js

import apiClient from './api';

const quizService = {
  // ==================== QUIZ CRUD OPERATIONS ====================

  /**
   * Get all quizzes for the current user
   */
  getAllQuizzes: async () => {
    try {
      const response = await apiClient.get('/api/quizzes');
      return response.data || [];
    } catch (error) {
      console.error("Error fetching quizzes:", error);
      const errorMessage = error.response?.data?.detail || "Could not load quizzes.";
      throw new Error(errorMessage);
    }
  },

  /**
   * Get a single quiz by ID
   */
  getQuizById: async (quizId) => {
    try {
      const response = await apiClient.get(`/api/quizzes/${quizId}`);
      return response.data;
    } catch (error) {
      console.error(`Error fetching quiz ${quizId}:`, error);
      const errorMessage = error.response?.data?.detail || "Could not load quiz details.";
      throw new Error(errorMessage);
    }
  },

  /**
   * Create a new quiz
   */
  createQuiz: async (quizData) => {
    try {
      const response = await apiClient.post('/api/quizzes', quizData);
      return response.data;
    } catch (error) {
      console.error("Error creating quiz:", error);
      const errorMessage = error.response?.data?.detail || "Failed to create quiz.";
      throw new Error(errorMessage);
    }
  },

  /**
   * Update an existing quiz
   */
  updateQuiz: async (quizId, quizData) => {
    try {
      const response = await apiClient.put(`/api/quizzes/${quizId}`, quizData);
      return response.data;
    } catch (error) {
      console.error(`Error updating quiz ${quizId}:`, error);
      const errorMessage = error.response?.data?.detail || "Failed to update quiz.";
      throw new Error(errorMessage);
    }
  },

  /**
   * Delete a quiz (soft delete)
   */
  deleteQuiz: async (quizId) => {
    try {
      await apiClient.delete(`/api/quizzes/${quizId}`);
    } catch (error) {
      console.error(`Error deleting quiz ${quizId}:`, error);
      const errorMessage = error.response?.data?.detail || "Failed to delete quiz.";
      throw new Error(errorMessage);
    }
  },

  /**
   * Duplicate a quiz
   */
  duplicateQuiz: async (quizId, newTitle) => {
    try {
      const response = await apiClient.post(`/api/quizzes/${quizId}/duplicate`, { new_title: newTitle });
      return response.data;
    } catch (error) {
      console.error(`Error duplicating quiz ${quizId}:`, error);
      const errorMessage = error.response?.data?.detail || "Failed to duplicate quiz.";
      throw new Error(errorMessage);
    }
  },

  /**
   * Publish a quiz (make it available for sessions)
   */
  publishQuiz: async (quizId) => {
    try {
      const response = await apiClient.post(`/api/quizzes/${quizId}/publish`);
      return response.data;
    } catch (error) {
      console.error(`Error publishing quiz ${quizId}:`, error);
      const errorMessage = error.response?.data?.detail || "Failed to publish quiz.";
      throw new Error(errorMessage);
    }
  },

  // ==================== QUESTION OPERATIONS ====================

  /**
   * Add a question to a quiz
   */
  addQuestion: async (quizId, questionData) => {
    try {
      const response = await apiClient.post(`/api/quizzes/${quizId}/questions`, questionData);
      return response.data;
    } catch (error) {
      console.error(`Error adding question to quiz ${quizId}:`, error);
      const errorMessage = error.response?.data?.detail || "Failed to add question.";
      throw new Error(errorMessage);
    }
  },

  /**
   * Update a question
   */
  updateQuestion: async (quizId, questionId, questionData) => {
    try {
      const response = await apiClient.put(`/api/quizzes/${quizId}/questions/${questionId}`, questionData);
      return response.data;
    } catch (error) {
      console.error(`Error updating question ${questionId}:`, error);
      const errorMessage = error.response?.data?.detail || "Failed to update question.";
      throw new Error(errorMessage);
    }
  },

  /**
   * Delete a question
   */
  deleteQuestion: async (quizId, questionId) => {
    try {
      await apiClient.delete(`/api/quizzes/${quizId}/questions/${questionId}`);
    } catch (error) {
      console.error(`Error deleting question ${questionId}:`, error);
      const errorMessage = error.response?.data?.detail || "Failed to delete question.";
      throw new Error(errorMessage);
    }
  },

  /**
   * Reorder questions in a quiz
   */
  reorderQuestions: async (quizId, questionOrder) => {
    try {
      const response = await apiClient.put(`/api/quizzes/${quizId}/questions/reorder`, { question_order: questionOrder });
      return response.data;
    } catch (error) {
      console.error(`Error reordering questions for quiz ${quizId}:`, error);
      const errorMessage = error.response?.data?.detail || "Failed to reorder questions.";
      throw new Error(errorMessage);
    }
  },

  // ==================== SESSION OPERATIONS (HOST) ====================

  /**
   * Create a new quiz session
   */
  createSession: async (quizId) => {
    try {
      const response = await apiClient.post('/api/quiz-sessions', { quiz_id: quizId });
      return response.data;
    } catch (error) {
      console.error(`Error creating session for quiz ${quizId}:`, error);
      const errorMessage = error.response?.data?.detail || "Failed to create quiz session.";
      throw new Error(errorMessage);
    }
  },

  /**
   * Get session by ID (host access)
   */
  getSession: async (sessionId) => {
    try {
      const response = await apiClient.get(`/api/quiz-sessions/${sessionId}`);
      return response.data;
    } catch (error) {
      console.error(`Error fetching session ${sessionId}:`, error);
      const errorMessage = error.response?.data?.detail || "Could not load session details.";
      throw new Error(errorMessage);
    }
  },

  /**
   * Start a session (begin quiz)
   */
  startSession: async (sessionId) => {
    try {
      const response = await apiClient.post(`/api/quiz-sessions/${sessionId}/start`);
      return response.data;
    } catch (error) {
      console.error(`Error starting session ${sessionId}:`, error);
      const errorMessage = error.response?.data?.detail || "Failed to start session.";
      throw new Error(errorMessage);
    }
  },

  /**
   * End a session
   */
  endSession: async (sessionId) => {
    try {
      const response = await apiClient.post(`/api/quiz-sessions/${sessionId}/end`);
      return response.data;
    } catch (error) {
      console.error(`Error ending session ${sessionId}:`, error);
      const errorMessage = error.response?.data?.detail || "Failed to end session.";
      throw new Error(errorMessage);
    }
  },

  /**
   * Cancel a session
   */
  cancelSession: async (sessionId) => {
    try {
      const response = await apiClient.post(`/api/quiz-sessions/${sessionId}/cancel`);
      return response.data;
    } catch (error) {
      console.error(`Error cancelling session ${sessionId}:`, error);
      const errorMessage = error.response?.data?.detail || "Failed to cancel session.";
      throw new Error(errorMessage);
    }
  },

  /**
   * Advance to next question (host controls)
   */
  nextQuestion: async (sessionId) => {
    try {
      const response = await apiClient.post(`/api/quiz-sessions/${sessionId}/next-question`);
      return response.data;
    } catch (error) {
      console.error(`Error advancing to next question in session ${sessionId}:`, error);
      const errorMessage = error.response?.data?.detail || "Failed to advance to next question.";
      throw new Error(errorMessage);
    }
  },

  /**
   * Get all sessions for the current user
   */
  getAllSessions: async () => {
    try {
      const response = await apiClient.get('/api/quiz-sessions');
      return response.data || [];
    } catch (error) {
      console.error("Error fetching sessions:", error);
      const errorMessage = error.response?.data?.detail || "Could not load sessions.";
      throw new Error(errorMessage);
    }
  },

  // ==================== PARTICIPANT OPERATIONS (PUBLIC) ====================

  /**
   * Join a session as a guest (no auth required)
   */
  joinSession: async (roomCode, guestName) => {
    try {
      const response = await apiClient.post('/api/quiz-sessions/join', {
        room_code: roomCode,
        guest_name: guestName
      });
      return response.data; // Returns { participant, session, guest_token }
    } catch (error) {
      console.error(`Error joining session with room code ${roomCode}:`, error);
      const errorMessage = error.response?.data?.detail || "Failed to join quiz session.";
      throw new Error(errorMessage);
    }
  },

  /**
   * Submit an answer (participant)
   */
  submitAnswer: async (sessionId, answerData, guestToken) => {
    try {
      const response = await apiClient.post(
        `/api/quiz-sessions/${sessionId}/submit-answer`,
        answerData,
        {
          headers: {
            'X-Guest-Token': guestToken
          }
        }
      );
      return response.data;
    } catch (error) {
      console.error(`Error submitting answer for session ${sessionId}:`, error);
      const errorMessage = error.response?.data?.detail || "Failed to submit answer.";
      throw new Error(errorMessage);
    }
  },

  /**
   * Get leaderboard for a session
   */
  getLeaderboard: async (sessionId, guestToken = null) => {
    try {
      const headers = guestToken ? { 'X-Guest-Token': guestToken } : {};
      const response = await apiClient.get(`/api/quiz-sessions/${sessionId}/leaderboard`, { headers });
      return response.data;
    } catch (error) {
      console.error(`Error fetching leaderboard for session ${sessionId}:`, error);
      const errorMessage = error.response?.data?.detail || "Could not load leaderboard.";
      throw new Error(errorMessage);
    }
  },

  // ==================== ANALYTICS OPERATIONS ====================

  /**
   * Get session analytics
   */
  getSessionAnalytics: async (sessionId) => {
    try {
      const response = await apiClient.get(`/api/quiz-analytics/sessions/${sessionId}`);
      return response.data;
    } catch (error) {
      console.error(`Error fetching analytics for session ${sessionId}:`, error);
      const errorMessage = error.response?.data?.detail || "Could not load analytics.";
      throw new Error(errorMessage);
    }
  },

  /**
   * Get question analytics
   */
  getQuestionAnalytics: async (questionId) => {
    try {
      const response = await apiClient.get(`/api/quiz-analytics/questions/${questionId}`);
      return response.data;
    } catch (error) {
      console.error(`Error fetching analytics for question ${questionId}:`, error);
      const errorMessage = error.response?.data?.detail || "Could not load question analytics.";
      throw new Error(errorMessage);
    }
  },

  /**
   * Get comparative analytics for a quiz
   */
  getComparativeAnalytics: async (quizId) => {
    try {
      const response = await apiClient.get(`/api/quiz-analytics/quizzes/${quizId}/comparative`);
      return response.data;
    } catch (error) {
      console.error(`Error fetching comparative analytics for quiz ${quizId}:`, error);
      const errorMessage = error.response?.data?.detail || "Could not load comparative analytics.";
      throw new Error(errorMessage);
    }
  },

  /**
   * Export session results as CSV
   */
  exportSessionCSV: async (sessionId) => {
    try {
      const response = await apiClient.get(`/api/quiz-analytics/sessions/${sessionId}/export-csv`, {
        responseType: 'blob'
      });

      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const contentDisposition = response.headers['content-disposition'];
      let fileName = `quiz_results_${sessionId}.csv`;

      if (contentDisposition) {
        const fileNameMatch = contentDisposition.match(/filename="(.+)"/);
        if (fileNameMatch && fileNameMatch.length === 2) {
          fileName = fileNameMatch[1];
        }
      }

      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', fileName);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error(`Error exporting CSV for session ${sessionId}:`, error);
      throw new Error("Failed to export quiz results. Please try again.");
    }
  },

  /**
   * Export detailed session results as CSV
   */
  exportSessionDetailedCSV: async (sessionId) => {
    try {
      const response = await apiClient.get(`/api/quiz-analytics/sessions/${sessionId}/export-detailed-csv`, {
        responseType: 'blob'
      });

      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const contentDisposition = response.headers['content-disposition'];
      let fileName = `quiz_detailed_${sessionId}.csv`;

      if (contentDisposition) {
        const fileNameMatch = contentDisposition.match(/filename="(.+)"/);
        if (fileNameMatch && fileNameMatch.length === 2) {
          fileName = fileNameMatch[1];
        }
      }

      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', fileName);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error(`Error exporting detailed CSV for session ${sessionId}:`, error);
      throw new Error("Failed to export detailed quiz results. Please try again.");
    }
  },

  // ==================== WEBSOCKET CONNECTION ====================

  /**
   * Create WebSocket connection for real-time updates
   *
   * @param {string} sessionId - Session ID
   * @param {string} token - JWT token for host OR guest token for participant
   * @param {boolean} isHost - Whether this is a host connection
   * @returns {WebSocket} WebSocket connection
   */
  connectWebSocket: (sessionId, token, isHost = false) => {
    const wsBaseUrl = import.meta.env.VITE_API_BASE_URL.replace('http', 'ws');
    const queryParam = isHost ? `token=${token}` : `guest_token=${token}`;
    const wsUrl = `${wsBaseUrl}/api/ws/quiz-sessions/${sessionId}?${queryParam}`;

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected to quiz session:', sessionId);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected from quiz session:', sessionId);
    };

    return ws;
  }
};

export default quizService;
