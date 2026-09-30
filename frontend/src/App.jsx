import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import VideoProcessor from './components/VideoProcessor';
import YouTubePlayer from './components/YouTubePlayer';
import ChatInterface from './components/ChatInterface';
import AddVideoModal from './components/AddVideoModal';
import VideoLibrary from './components/VideoLibrary';
import AuthPage from './components/AuthPage';
import { getStoredUser, removeAuthToken, removeStoredUser, api } from './services/api';

export default function App() {
  const [user, setUser] = useState(null);
  const [currentVideoId, setCurrentVideoId] = useState('');
  const [currentVideoUrl, setCurrentVideoUrl] = useState('');
  const [currentTimestamp, setCurrentTimestamp] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [userVideos, setUserVideos] = useState([]);

  // Auto-login from stored session
  useEffect(() => {
    const savedUser = getStoredUser();
    if (savedUser) setUser(savedUser);
  }, []);

  useEffect(() => {
    if (user) {
      loadUserVideos();
    }
  }, [user, currentVideoId]);

  const loadUserVideos = async () => {
    try {
      const data = await api.getUserVideos();
      if (data && data.videos) {
        setUserVideos(data.videos);
        // If no video is currently selected, select the first recent video
        if (!currentVideoId && data.videos.length > 0) {
          const firstVid = typeof data.videos[0] === 'string' ? data.videos[0] : data.videos[0].video_id;
          if (firstVid) {
            setCurrentVideoId(firstVid);
            setCurrentVideoUrl(`https://www.youtube.com/watch?v=${firstVid}`);
          }
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleVideoProcessed = (videoId, url) => {
    setCurrentVideoId(videoId);
    setCurrentVideoUrl(url || `https://www.youtube.com/watch?v=${videoId}`);
    loadUserVideos();
  };

  const handleSelectVideo = (videoId) => {
    setCurrentVideoId(videoId);
    setCurrentVideoUrl(`https://www.youtube.com/watch?v=${videoId}`);
  };

  const handleSeek = (seconds) => {
    setCurrentTimestamp(seconds);
  };

  const handleLogout = () => {
    removeAuthToken();
    removeStoredUser();
    setUser(null);
    setCurrentVideoId('');
    setCurrentVideoUrl('');
  };

  // ── 1. Unauthenticated State: Show Clean Auth Page ─────────────────────────
  if (!user) {
    return <AuthPage onAuthSuccess={(userData) => setUser(userData)} />;
  }

  // ── 2. Authenticated State: Show Main Dashboard ────────────────────────────
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Navbar
        user={user}
        onLogout={handleLogout}
        onOpenAddVideo={() => setIsAddModalOpen(true)}
        currentVideoId={currentVideoId}
      />

      <main className="container-app" style={{ flex: 1, paddingBottom: '2rem' }}>
        {/* Top Video URL Search & Ingestion Bar */}
        <VideoProcessor
          onVideoProcessed={handleVideoProcessed}
          currentVideoId={currentVideoId}
          isProcessing={isProcessing}
          setIsProcessing={setIsProcessing}
        />

        {/* Video Library / Switcher Strip */}
        <VideoLibrary
          videos={userVideos}
          currentVideoId={currentVideoId}
          onSelectVideo={handleSelectVideo}
          onOpenAddModal={() => setIsAddModalOpen(true)}
        />

        {/* Main 2-Column Responsive Layout */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))',
          gap: '1.5rem',
          alignItems: 'start',
        }}>
          {/* Left Column: YouTube Player */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <YouTubePlayer
              videoId={currentVideoId}
              currentTimestamp={currentTimestamp}
            />
          </div>

          {/* Right Column: Interactive AI Chat */}
          <div>
            <ChatInterface
              videoId={currentVideoId}
              onSeek={handleSeek}
              isProcessing={isProcessing}
            />
          </div>
        </div>
      </main>

      {/* Add New Video Modal */}
      <AddVideoModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onVideoAdded={handleVideoProcessed}
      />
    </div>
  );
}


