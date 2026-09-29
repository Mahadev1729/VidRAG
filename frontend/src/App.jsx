import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import VideoProcessor from './components/VideoProcessor';
import YouTubePlayer from './components/YouTubePlayer';
import ChatInterface from './components/ChatInterface';
import SummaryModal from './components/SummaryModal';
import AuthModal from './components/AuthModal';
import { getStoredUser, removeAuthToken, removeStoredUser, api } from './services/api';
import { History, PlaySquare, Sparkles } from 'lucide-react';

export default function App() {
  const [user, setUser] = useState(null);
  const [currentVideoId, setCurrentVideoId] = useState('');
  const [currentVideoUrl, setCurrentVideoUrl] = useState('');
  const [currentTimestamp, setCurrentTimestamp] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isAuthOpen, setIsAuthOpen] = useState(false);
  const [isSummaryOpen, setIsSummaryOpen] = useState(false);
  const [userVideos, setUserVideos] = useState([]);

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
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Navbar
        user={user}
        onOpenAuth={() => setIsAuthOpen(true)}
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
            {user && userVideos.length > 0 && (
              <div className="glass-panel" style={{ padding: '1rem 1.25rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', fontSize: '0.9rem', color: '#cbd5e1' }}>
                  <History size={16} color="#818cf8" />
                  <span style={{ fontWeight: '600' }}>Your Recent Indexed Videos</span>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
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
                        gap: '0.4rem',
                        background: vid === currentVideoId ? 'rgba(99, 102, 241, 0.3)' : 'rgba(255, 255, 255, 0.05)',
                        border: '1px solid',
                        borderColor: vid === currentVideoId ? 'var(--accent-primary)' : 'var(--border-subtle)',
                        borderRadius: '8px',
                        padding: '6px 12px',
                        color: '#e2e8f0',
                        fontSize: '0.8rem',
                        cursor: 'pointer',
                      }}
                    >
                      <PlaySquare size={14} color="#818cf8" />
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

      {/* Modals */}
      <SummaryModal
        isOpen={isSummaryOpen}
        onClose={() => setIsSummaryOpen(false)}
        videoUrl={currentVideoUrl}
        videoId={currentVideoId}
      />

      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        onAuthSuccess={(userData) => setUser(userData)}
      />
    </div>
  );
}
