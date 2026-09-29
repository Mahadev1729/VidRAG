/**
 * API Service for YouTube RAG Backend.
 * Handles Authentication, Video Ingestion, RAG Chat, Summarization, History, Feedback.
 */

const API_BASE_URL = '/api';

export const getAuthToken = () => localStorage.getItem('vidrag_token');
export const setAuthToken = (token) => localStorage.setItem('vidrag_token', token);
export const removeAuthToken = () => localStorage.removeItem('vidrag_token');

export const getStoredUser = () => {
  const user = localStorage.getItem('vidrag_user');
  return user ? JSON.parse(user) : null;
};
export const setStoredUser = (user) => localStorage.setItem('vidrag_user', JSON.stringify(user));
export const removeStoredUser = () => localStorage.removeItem('vidrag_user');

const authHeaders = () => {
  const token = getAuthToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
};

export const api = {
  // Health
  checkHealth: async () => {
    const res = await fetch(`${API_BASE_URL}/health`);
    return res.json();
  },

  // Auth
  register: async (username, email, password) => {
    const res = await fetch(`${API_BASE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, email, password }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Registration failed');
    }
    return res.json();
  },

  login: async (identifier, password) => {
    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier, password }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Invalid credentials');
    }
    const data = await res.json();
    setAuthToken(data.access_token);
    setStoredUser(data.user);
    return data;
  },

  getMe: async () => {
    const res = await fetch(`${API_BASE_URL}/auth/me`, {
      headers: authHeaders(),
    });
    if (!res.ok) throw new Error('Session expired');
    return res.json();
  },

  // Ingestion
  processVideo: async (url, forceWhisper = false, language = 'en') => {
    const res = await fetch(`${API_BASE_URL}/video/process`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({
        url,
        force_whisper: forceWhisper,
        preferred_language: language,
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to process video');
    }
    return res.json();
  },

  // Chat / RAG
  askQuestion: async (videoId, question) => {
    const res = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({
        video_id: videoId,
        question,
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Error getting answer');
    }
    return res.json();
  },

  // Summary
  getSummary: async (url) => {
    const res = await fetch(`${API_BASE_URL}/summary`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ url }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to generate summary');
    }
    return res.json();
  },

  // Chat History
  getHistory: async (videoId) => {
    const res = await fetch(`${API_BASE_URL}/history/${videoId}`, {
      headers: authHeaders(),
    });
    if (!res.ok) return { history: [] };
    return res.json();
  },

  clearHistory: async (videoId) => {
    const res = await fetch(`${API_BASE_URL}/history/${videoId}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    return res.json();
  },

  getUserVideos: async () => {
    const res = await fetch(`${API_BASE_URL}/user/videos`, {
      headers: authHeaders(),
    });
    if (!res.ok) return { videos: [] };
    return res.json();
  },

  // Feedback
  sendFeedback: async (videoId, question, answer, rating, comment = null) => {
    const res = await fetch(`${API_BASE_URL}/feedback`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({
        video_id: videoId,
        question,
        answer,
        rating,
        comment,
      }),
    });
    return res.json();
  },

  getFeedbackStats: async (videoId) => {
    const res = await fetch(`${API_BASE_URL}/feedback/stats/${videoId}`);
    if (!res.ok) return { stats: { upvotes: 0, downvotes: 0 } };
    return res.json();
  },
};
