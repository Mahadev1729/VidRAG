import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { X, FileText, Loader2, Sparkles } from 'lucide-react';
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
      background: 'rgba(0, 0, 0, 0.75)',
      backdropFilter: 'blur(8px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: '1.5rem',
    }}>
      <div className="glass-panel" style={{
        width: '100%',
        maxWidth: '750px',
        maxHeight: '85vh',
        display: 'flex',
        flexDirection: 'column',
        background: 'rgba(15, 23, 42, 0.95)',
        boxShadow: '0 20px 50px rgba(0,0,0,0.6)',
      }}>
        {/* Header */}
        <div style={{
          padding: '1.25rem 1.5rem',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Sparkles size={20} color="#ec4899" />
            <h3 style={{ fontSize: '1.1rem', fontWeight: '700' }}>AI Video Summary</h3>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              padding: '4px',
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: '1.5rem', overflowY: 'auto', flex: 1, fontSize: '0.95rem', lineHeight: '1.6' }}>
          {loading ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '3rem 0', gap: '1rem', color: '#818cf8' }}>
              <Loader2 size={32} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
              <p>Extracting video sections & generating executive summary...</p>
            </div>
          ) : error ? (
            <div style={{ color: '#f87171', padding: '1rem', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '8px' }}>
              {error}
            </div>
          ) : (
            <ReactMarkdown>{summary}</ReactMarkdown>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '1rem 1.5rem',
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex',
          justifyContent: 'flex-end',
        }}>
          <button onClick={onClose} className="gradient-btn" style={{ padding: '8px 20px' }}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
