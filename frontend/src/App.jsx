import React, { useState, useEffect, useCallback } from 'react';
import Navbar from './components/Navbar';
import VideoProcessor from './components/VideoProcessor';
import YouTubePlayer from './components/YouTubePlayer';
import ChatInterface from './components/ChatInterface';
import VideoLibrary from './components/VideoLibrary';
import AuthPage from './components/AuthPage';
import { api, getStoredUser, removeAuthToken, removeStoredUser } from './services/api';

export default function App() {
  const [user, setUser] = useState(null);
  const [currentVideoId, setCurrentVideoId] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [userVideos, setUserVideos] = useState([]);

  // Auto-login from stored session
  useEffect(() => {
    const savedUser = getStoredUser();
    if (savedUser) setUser(savedUser);
  }, []);

  // Fetch private user videos whenever user state changes
  const fetchUserVideos = useCallback(async () => {
    if (!user) return;
    try {
      const data = await api.getUserVideos();
      if (data && Array.isArray(data.videos)) {
        setUserVideos(data.videos);
        // If currentVideoId is not set, set it to the most recent video
        if (!currentVideoId && data.videos.length > 0) {
          setCurrentVideoId(data.videos[0].video_id);
        }
      }
    } catch (err) {
      console.warn('Could not fetch user videos:', err);
    }
  }, [user, currentVideoId]);

  useEffect(() => {
    fetchUserVideos();
  }, [fetchUserVideos]);

  const handleVideoProcessed = (videoId) => {
    setCurrentVideoId(videoId);
    fetchUserVideos();
  };

  const handleLogout = () => {
    removeAuthToken();
    removeStoredUser();
    setUser(null);
    setCurrentVideoId('');
    setUserVideos([]);
  };

  // ── 1. Unauthenticated State: Show Clean Auth Page ─────────────────────────
  if (!user) {
    return <AuthPage onAuthSuccess={(userData) => setUser(userData)} />;
  }

  // ── 2. Authenticated State: Show Clean Dashboard ───────────────────────────
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Navbar
        user={user}
        onLogout={handleLogout}
        currentVideoId={currentVideoId}
      />

      <main className="container-app" style={{ flex: 1, paddingBottom: '2rem' }}>
        {/* Top Video URL Ingestion Bar */}
        <VideoProcessor
          onVideoProcessed={handleVideoProcessed}
          currentVideoId={currentVideoId}
          isProcessing={isProcessing}
          setIsProcessing={setIsProcessing}
        />

        {/* Private User Video Library (Only visible for the logged-in user's own videos) */}
        {userVideos.length > 0 && (
          <VideoLibrary
            videos={userVideos}
            currentVideoId={currentVideoId}
            onSelectVideo={(vidId) => setCurrentVideoId(vidId)}
          />
        )}

        {/* Main 2-Column Responsive Layout: Compact Player + Spacious Chat */}
        <div className="workspace-grid">
          {/* Left Column: YouTube Player (Compact, perfect 16:9 ratio) */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <YouTubePlayer
              videoId={currentVideoId}
            />
          </div>

          {/* Right Column: AI Chat Interface (Generous expanded space) */}
          <div style={{ minWidth: 0 }}>
            <ChatInterface
              videoId={currentVideoId}
              isProcessing={isProcessing}
            />
          </div>
        </div>
      </main>
    </div>
  );
}





