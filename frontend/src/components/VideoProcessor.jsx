import React, { useState } from 'react';
import { Search, Loader2, CheckCircle2, AlertCircle, Cpu, Globe } from 'lucide-react';
import { api } from '../services/api';

export default function VideoProcessor({ onVideoProcessed, currentVideoId, isProcessing, setIsProcessing }) {
  const [url, setUrl] = useState('');
  const [forceWhisper, setForceWhisper] = useState(false);
  const [language, setLanguage] = useState('en');
  const [statusMessage, setStatusMessage] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!url.trim()) return;

    setIsProcessing(true);
    setStatusMessage('Fetching transcript & generating TiDB Cloud vector embeddings...');
    setErrorMessage(null);

    try {
      const data = await api.processVideo(url, forceWhisper, language);
      setStatusMessage(data.message || 'Video successfully processed!');
      onVideoProcessed(data.video_id, url);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to process video.');
      setStatusMessage(null);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '1.25rem', marginBottom: '1.5rem' }}>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        
        {/* Main URL Bar */}
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <div style={{ 
            position: 'relative', 
            flex: 1, 
            display: 'flex', 
            alignItems: 'center',
            background: 'rgba(15, 23, 42, 0.6)',
            borderRadius: '10px',
            border: '1px solid var(--border-subtle)',
            padding: '0 12px'
          }}>
            <Search size={18} color="#64748b" />
            <input
              type="text"
              placeholder="Paste YouTube Video URL (e.g. https://www.youtube.com/watch?v=...)"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={isProcessing}
              style={{
                width: '100%',
                background: 'transparent',
                border: 'none',
                color: '#f8fafc',
                padding: '12px 10px',
                fontSize: '0.95rem',
                outline: 'none',
              }}
            />
          </div>

          <button
            type="submit"
            disabled={isProcessing || !url.trim()}
            className="gradient-btn"
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '0.5rem',
              whiteSpace: 'nowrap',
              padding: '12px 24px'
            }}
          >
            {isProcessing ? (
              <>
                <Loader2 size={18} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
                <span>Indexing...</span>
              </>
            ) : (
              <span>Index Video</span>
            )}
          </button>
        </div>

        {/* Options Row */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem', fontSize: '0.85rem', color: '#94a3b8' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={forceWhisper}
                onChange={(e) => setForceWhisper(e.target.checked)}
                disabled={isProcessing}
                style={{ cursor: 'pointer', accentColor: 'var(--accent-primary)' }}
              />
              <Cpu size={14} />
              <span>Force Whisper Audio Transcription</span>
            </label>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Globe size={14} />
              <span>Language:</span>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                disabled={isProcessing}
                style={{
                  background: 'rgba(15, 23, 42, 0.8)',
                  border: '1px solid var(--border-subtle)',
                  color: '#e2e8f0',
                  borderRadius: '6px',
                  padding: '2px 6px',
                  fontSize: '0.8rem',
                  outline: 'none',
                }}
              >
                <option value="en">English (en)</option>
                <option value="hi">Hindi (hi)</option>
                <option value="es">Spanish (es)</option>
                <option value="fr">French (fr)</option>
                <option value="de">German (de)</option>
              </select>
            </div>
          </div>

          {currentVideoId && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#34d399' }}>
              <CheckCircle2 size={14} />
              <span>Active Video ID: <strong>{currentVideoId}</strong></span>
            </div>
          )}
        </div>

        {/* Status Messages */}
        {statusMessage && (
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '0.5rem', 
            color: '#818cf8', 
            background: 'rgba(99, 102, 241, 0.1)',
            padding: '8px 12px',
            borderRadius: '8px',
            fontSize: '0.85rem'
          }}>
            <CheckCircle2 size={16} />
            <span>{statusMessage}</span>
          </div>
        )}

        {errorMessage && (
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '0.5rem', 
            color: '#f87171', 
            background: 'rgba(239, 68, 68, 0.1)',
            padding: '8px 12px',
            borderRadius: '8px',
            fontSize: '0.85rem'
          }}>
            <AlertCircle size={16} />
            <span>{errorMessage}</span>
          </div>
        )}

      </form>
    </div>
  );
}
