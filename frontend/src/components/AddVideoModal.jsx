import React, { useState, useEffect } from 'react';
import { X, Youtube, Sparkles, Loader2, AlertCircle, CheckCircle2, Play } from 'lucide-react';
import { api } from '../services/api';

export default function AddVideoModal({ isOpen, onClose, onVideoAdded }) {
  const [url, setUrl] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [previewId, setPreviewId] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  // Extract YouTube ID for instant thumbnail preview
  useEffect(() => {
    if (!url.trim()) {
      setPreviewId('');
      return;
    }
    const match = url.match(/(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=|shorts\/))([\w-]{11})/);
    if (match && match[1]) {
      setPreviewId(match[1]);
    } else {
      setPreviewId('');
    }
  }, [url]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!url.trim() || isProcessing) return;

    setIsProcessing(true);
    setStatusMessage('Indexing video with TiDB Vector...');
    setErrorMessage('');

    try {
      const data = await api.processVideo(url, false, 'en');
      setStatusMessage(data.message || 'Video indexed successfully!');
      onVideoAdded(data.video_id, url);
      setTimeout(() => {
        setIsProcessing(false);
        setUrl('');
        setStatusMessage('');
        onClose();
      }, 700);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to process video.');
      setStatusMessage('');
      setIsProcessing(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'rgba(0, 0, 0, 0.75)',
      backdropFilter: 'blur(8px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: '1rem',
      animation: 'fadeIn 0.2s ease-out',
    }}>
      <div className="glass-panel" style={{
        width: '100%',
        maxWidth: '520px',
        borderRadius: '16px',
        border: '1px solid rgba(255, 255, 255, 0.15)',
        background: 'rgba(18, 18, 22, 0.95)',
        boxShadow: '0 20px 40px rgba(0, 0, 0, 0.6)',
        overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{
          padding: '1rem 1.25rem',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <div style={{
              background: '#ef4444',
              padding: '6px',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <Youtube size={16} color="#ffffff" />
            </div>
            <h3 style={{ fontSize: '1rem', fontWeight: '700', color: '#ffffff', margin: 0 }}>
              Add New YouTube Video
            </h3>
          </div>
          <button
            onClick={onClose}
            disabled={isProcessing}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#a1a1aa',
              cursor: isProcessing ? 'not-allowed' : 'pointer',
              padding: '4px',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: '600', color: '#cbd5e1', marginBottom: '0.4rem' }}>
              YouTube URL
            </label>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              background: 'rgba(0, 0, 0, 0.4)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '10px',
              padding: '0 12px',
            }}>
              <Youtube size={16} color="#ef4444" style={{ marginRight: '8px', flexShrink: 0 }} />
              <input
                type="text"
                placeholder="https://www.youtube.com/watch?v=..."
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                disabled={isProcessing}
                autoFocus
                style={{
                  width: '100%',
                  background: 'transparent',
                  border: 'none',
                  color: '#ffffff',
                  padding: '10px 0',
                  fontSize: '0.9rem',
                  outline: 'none',
                }}
              />
            </div>
          </div>

          {/* Real-time Video Thumbnail Preview */}
          {previewId && (
            <div style={{
              borderRadius: '10px',
              overflow: 'hidden',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              position: 'relative',
              background: '#000000',
              height: '160px',
            }}>
              <img
                src={`https://img.youtube.com/vi/${previewId}/hqdefault.jpg`}
                alt="Video Thumbnail Preview"
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'cover',
                  opacity: 0.85,
                }}
              />
              <div style={{
                position: 'absolute',
                inset: 0,
                background: 'linear-gradient(to top, rgba(0,0,0,0.8) 0%, transparent 60%)',
                display: 'flex',
                alignItems: 'flex-end',
                padding: '10px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#ffffff', fontSize: '0.8rem', fontWeight: '600' }}>
                  <Play size={14} fill="#ffffff" />
                  <span>Ready to Index: {previewId}</span>
                </div>
              </div>
            </div>
          )}

          {/* Status / Error Alerts */}
          {statusMessage && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '8px 12px',
              borderRadius: '8px',
              background: 'rgba(99, 102, 241, 0.15)',
              border: '1px solid rgba(99, 102, 241, 0.3)',
              color: '#a5b4fc',
              fontSize: '0.82rem',
            }}>
              <CheckCircle2 size={15} />
              <span>{statusMessage}</span>
            </div>
          )}

          {errorMessage && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '8px 12px',
              borderRadius: '8px',
              background: 'rgba(239, 68, 68, 0.15)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              color: '#fca5a5',
              fontSize: '0.82rem',
            }}>
              <AlertCircle size={15} />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Actions */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.6rem', marginTop: '0.5rem' }}>
            <button
              type="button"
              onClick={onClose}
              disabled={isProcessing}
              style={{
                background: 'transparent',
                border: '1px solid var(--border-subtle)',
                color: '#a1a1aa',
                padding: '8px 16px',
                borderRadius: '8px',
                fontSize: '0.85rem',
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isProcessing || !previewId}
              className="gradient-btn"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.45rem',
                padding: '8px 20px',
                fontSize: '0.85rem',
                cursor: isProcessing || !previewId ? 'not-allowed' : 'pointer',
                opacity: !previewId && !isProcessing ? 0.6 : 1,
              }}
            >
              {isProcessing ? (
                <>
                  <Loader2 size={15} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
                  <span>Processing...</span>
                </>
              ) : (
                <>
                  <Sparkles size={14} />
                  <span>Add to Workspace</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
