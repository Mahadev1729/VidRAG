import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import VideoProcessor from './components/VideoProcessor';
import YouTubePlayer from './components/YouTubePlayer';
import ChatInterface from './components/ChatInterface';
import SummaryModal from './components/SummaryModal';
import AuthPage from './components/AuthPage';
import { getStoredUser, removeAuthToken, removeStoredUser, api } from './services/api';
import { History, PlaySquare } from 'lucide-react';

export default function App() {
  const [user, setUser] = useState(null);
  const [currentVideoId, setCurrentVideoId] = useState('');
  const [currentVideoUrl, setCurrentVideoUrl] = useState('');
  const [currentTimestamp, setCurrentTimestamp] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSummaryOpen, setIsSummaryOpen] = useState(false);
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
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleVideoProcessed = (videoId, url) => {
    setCurrentVideoId(videoId);
    setCurrentVideoUrl(url);
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

  // ── 1. Unauthenticated State: Show Professional Clean Auth Page ────────────
  if (!user) {
    return <AuthPage onAuthSuccess={(userData) => setUser(userData)} />;
  }

  // ── 2. Authenticated State: Show Main Dashboard ────────────────────────────
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Navbar
        user={user}
        onLogout={handleLogout}
        onOpenSummary={() => setIsSummaryOpen(true)}
        currentVideoId={currentVideoId}
      />

      <main className="container-app" style={{ flex: 1 }}>
        {/* Top Video URL input & Ingestion */}
        <VideoProcessor
          onVideoProcessed={handleVideoProcessed}
          currentVideoId={currentVideoId}
          isProcessing={isProcessing}
          setIsProcessing={setIsProcessing}
        />

        {/* Main 2-Column Responsive Layout */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))',
          gap: '1.5rem',
          alignItems: 'start',
        }}>
          {/* Left Column: Player & History */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <YouTubePlayer
              videoId={currentVideoId}
              currentTimestamp={currentTimestamp}
            />

            {/* User Session History Videos */}
            {userVideos.length > 0 && (
              <div className="glass-panel" style={{ padding: '0.85rem 1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginBottom: '0.6rem', fontSize: '0.8rem', color: '#a1a1aa' }}>
                  <History size={14} color="#ffffff" />
                  <span style={{ fontWeight: '600' }}>Recent Videos</span>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                  {userVideos.map((vid, idx) => (
                    <button
                      key={idx}
                      onClick={() => {
                        setCurrentVideoId(vid);
                        setCurrentVideoUrl(`https://www.youtube.com/watch?v=${vid}`);
                      }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.35rem',
                        background: vid === currentVideoId ? 'rgba(255, 255, 255, 0.15)' : 'rgba(255, 255, 255, 0.04)',
                        border: '1px solid',
                        borderColor: vid === currentVideoId ? 'rgba(255, 255, 255, 0.4)' : 'var(--border-subtle)',
                        borderRadius: '6px',
                        padding: '4px 10px',
                        color: vid === currentVideoId ? '#ffffff' : '#a1a1aa',
                        fontSize: '0.75rem',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <PlaySquare size={12} color="#ffffff" />
                      <span>{vid}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right Column: Interactive Chat */}
          <div>
            <ChatInterface
              videoId={currentVideoId}
              onSeek={handleSeek}
              isProcessing={isProcessing}
            />
          </div>
        </div>
      </main>

      {/* Video Summary Modal */}
      <SummaryModal
        isOpen={isSummaryOpen}
        onClose={() => setIsSummaryOpen(false)}
        videoUrl={currentVideoUrl}
        videoId={currentVideoId}
      />
    </div>
  );
}
