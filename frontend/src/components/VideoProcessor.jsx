import React, { useState } from 'react';
import { Search, Loader2, CheckCircle2, AlertCircle, Sparkles, Youtube } from 'lucide-react';
import { api } from '../services/api';

export default function VideoProcessor({ onVideoProcessed, currentVideoId, isProcessing, setIsProcessing }) {
  const [url, setUrl] = useState('');
  const [statusMessage, setStatusMessage] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!url.trim()) return;

    setIsProcessing(true);
    setStatusMessage('Processing video content...');
    setErrorMessage(null);

    try {
      const data = await api.processVideo(url, false, 'en');
      setStatusMessage(data.message || 'Video ready for analysis!');
      onVideoProcessed(data.video_id, url);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to process video.');
      setStatusMessage(null);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '1rem 1.25rem', marginBottom: '1.25rem' }}>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>

        {/* Responsive Search & Ingest Bar */}
        <div style={{
          display: 'flex',
          gap: '0.6rem',
          alignItems: 'center',
          flexWrap: 'wrap'
        }}>
          <div style={{
            position: 'relative',
            flex: '1 1 260px',
            display: 'flex',
            alignItems: 'center',
            background: 'rgba(15, 23, 42, 0.7)',
            borderRadius: '10px',
            border: '1px solid var(--border-subtle)',
            padding: '0 12px',
            transition: 'border-color 0.2s, box-shadow 0.2s'
          }}>
            <Youtube size={18} color="#ef4444" style={{ flexShrink: 0, marginRight: '6px' }} />
            <input
              type="text"
              placeholder="Paste YouTube link (e.g. https://youtu.be/...)"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={isProcessing}
              style={{
                width: '100%',
                background: 'transparent',
                border: 'none',
                color: '#f8fafc',
                padding: '11px 4px',
                fontSize: '0.92rem',
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
              justifyContent: 'center',
              gap: '0.45rem',
              whiteSpace: 'nowrap',
              padding: '11px 20px',
              flex: '0 0 auto',
              minWidth: '120px',
              fontSize: '0.9rem',
              cursor: isProcessing || !url.trim() ? 'not-allowed' : 'pointer'
            }}
          >
            {isProcessing ? (
              <>
                <Loader2 size={16} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
                <span>Processing...</span>
              </>
            ) : (
              <>
                <Sparkles size={15} />
                <span>Process Video</span>
              </>
            )}
          </button>
        </div>

        {/* Live Status Indicators */}
        {(statusMessage || errorMessage || currentVideoId) && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem', fontSize: '0.8rem' }}>
            {statusMessage && !errorMessage && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#818cf8' }}>
                <CheckCircle2 size={14} />
                <span>{statusMessage}</span>
              </div>
            )}

            {errorMessage && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#f87171' }}>
                <AlertCircle size={14} />
                <span>{errorMessage}</span>
              </div>
            )}

            {currentVideoId && !statusMessage && !errorMessage && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#34d399', marginLeft: 'auto' }}>
                <CheckCircle2 size={14} />
                <span>Active: <strong>{currentVideoId}</strong></span>
              </div>
            )}
          </div>
        )}

      </form>
    </div>
  );
}
