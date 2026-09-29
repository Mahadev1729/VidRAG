import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { X, Loader2, Sparkles } from 'lucide-react';
import { api } from '../services/api';

export default function SummaryModal({ isOpen, onClose, videoUrl, videoId }) {
  const [summary, setSummary] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (isOpen && videoUrl && !summary) {
      fetchSummary();
    }
  }, [isOpen, videoUrl]);

  const fetchSummary = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getSummary(videoUrl);
      setSummary(data.summary);
    } catch (err) {
      setError(err.message || 'Failed to generate summary.');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.85)',
      backdropFilter: 'blur(10px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: '1.5rem',
    }}>
      <div className="glass-panel" style={{
        width: '100%',
        maxWidth: '700px',
        maxHeight: '85vh',
        display: 'flex',
        flexDirection: 'column',
        background: 'rgba(18, 18, 20, 0.95)',
        border: '1px solid rgba(255, 255, 255, 0.12)',
        boxShadow: '0 25px 60px rgba(0, 0, 0, 0.8)',
      }}>
        {/* Header */}
        <div style={{
          padding: '1rem 1.25rem',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Sparkles size={18} color="#ffffff" />
            <h3 style={{ fontSize: '1rem', fontWeight: '700', color: '#ffffff' }}>Video Summary</h3>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#71717a',
              cursor: 'pointer',
              padding: '4px',
              transition: 'color 0.15s',
            }}
            onMouseEnter={(e) => e.target.style.color = '#ffffff'}
            onMouseLeave={(e) => e.target.style.color = '#71717a'}
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: '1.25rem', overflowY: 'auto', flex: 1, fontSize: '0.9rem', lineHeight: '1.6', color: '#f4f4f5' }}>
          {loading ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '3rem 0', gap: '0.85rem', color: '#a1a1aa' }}>
              <Loader2 size={28} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
              <p style={{ fontSize: '0.85rem' }}>Generating summary...</p>
            </div>
          ) : error ? (
            <div style={{ color: '#f87171', padding: '0.85rem', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '8px', fontSize: '0.85rem' }}>
              {error}
            </div>
          ) : (
            <ReactMarkdown>{summary}</ReactMarkdown>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '0.85rem 1.25rem',
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex',
          justifyContent: 'flex-end',
        }}>
          <button onClick={onClose} className="gradient-btn" style={{ padding: '7px 18px', fontSize: '0.85rem' }}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
