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

// Safe JSON parser to prevent "Unexpected end of JSON input" errors
async function handleResponse(res, fallbackErrMsg = 'Request failed') {
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch (e) {
    data = { detail: text || fallbackErrMsg };
  }

  if (!res.ok) {
    const errorMsg = data.detail || (typeof data === 'string' ? data : fallbackErrMsg);
    throw new Error(errorMsg);
  }
  return data;
}

export const api = {
  // Health
  checkHealth: async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/health`);
      return await handleResponse(res, 'Health check failed');
    } catch (err) {
      throw new Error('Backend server is not reachable at http://127.0.0.1:8000. Please ensure uvicorn is running.');
    }
  },

  // Auth
  register: async (username, email, password) => {
    const res = await fetch(`${API_BASE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, email, password }),
    });
    return await handleResponse(res, 'Registration failed');
  },

  login: async (identifier, password) => {
    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier, password }),
    });
    const data = await handleResponse(res, 'Invalid credentials');
    if (data.access_token) {
      setAuthToken(data.access_token);
      setStoredUser(data.user);
    }
    return data;
  },

  googleLogin: async (credential) => {
    const res = await fetch(`${API_BASE_URL}/auth/google`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential }),
    });
    const data = await handleResponse(res, 'Google authentication failed');
    if (data.access_token) {
      setAuthToken(data.access_token);
      setStoredUser(data.user);
    }
    return data;
  },

  getMe: async () => {
    const res = await fetch(`${API_BASE_URL}/auth/me`, {
      headers: authHeaders(),
    });
    return await handleResponse(res, 'Session expired');
  },

  // Ingestion
  processVideo: async (url, forceWhisper = false, language = 'en') => {
    try {
      const res = await fetch(`${API_BASE_URL}/video/process`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          url,
          force_whisper: forceWhisper,
          preferred_language: language,
        }),
      });
      return await handleResponse(res, 'Failed to process video');
    } catch (err) {
      if (err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
        throw new Error('Could not reach backend server. Please verify FastAPI backend (uvicorn) is running.');
      }
      throw err;
    }
  },

  // Chat / RAG
  askQuestion: async (videoId, question) => {
    try {
      const res = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          video_id: videoId,
          question,
        }),
      });
      return await handleResponse(res, 'Error getting answer');
    } catch (err) {
      if (err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
        throw new Error('Backend connection lost. Please verify FastAPI server is running.');
      }
      throw err;
    }
  },

  askQuestionStream: async (videoId, question, onToken, onCitations) => {
    try {
      const res = await fetch(`${API_BASE_URL}/chat/stream`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          video_id: videoId,
          question,
        }),
      });

      if (!res.ok) {
        return await handleResponse(res, 'Error streaming answer');
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('data: ')) {
            try {
              const data = JSON.parse(trimmed.slice(6));
              if (data.type === 'token' && onToken) {
                onToken(data.token);
              } else if (data.type === 'citations' && onCitations) {
                onCitations(data.citations);
              }
            } catch (err) {
              console.warn('SSE parse error:', err);
            }
          }
        }
      }
    } catch (err) {
      if (err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
        throw new Error('Backend connection lost. Please verify FastAPI server is running.');
      }
      throw err;
    }
  },


  // Summary
  getSummary: async (url) => {
    const res = await fetch(`${API_BASE_URL}/summary`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ url }),
    });
    return await handleResponse(res, 'Failed to generate summary');
  },

  // Chat History
  getHistory: async (videoId) => {
    try {
      const res = await fetch(`${API_BASE_URL}/history/${videoId}`, {
        headers: authHeaders(),
      });
      if (!res.ok) return { history: [] };
      return await handleResponse(res, 'Failed to load history');
    } catch (err) {
      console.warn('Could not fetch history:', err.message);
      return { history: [] };
    }
  },

  clearHistory: async (videoId) => {
    const res = await fetch(`${API_BASE_URL}/history/${videoId}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    return await handleResponse(res, 'Failed to clear history');
  },

  getUserVideos: async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/user/videos`, {
        headers: authHeaders(),
      });
      if (!res.ok) return { videos: [] };
      return await handleResponse(res, 'Failed to get videos');
    } catch (err) {
      console.warn('Could not fetch user videos:', err.message);
      return { videos: [] };
    }
  },
};
