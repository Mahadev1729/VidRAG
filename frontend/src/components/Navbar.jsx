import React from 'react';
import { Sparkles, Database, Youtube, User, LogOut, LogIn } from 'lucide-react';

export default function Navbar({ user, onOpenAuth, onLogout, onOpenSummary, currentVideoId }) {
  return (
    <header className="glass-panel" style={{ borderRadius: '0 0 16px 16px', borderTop: 'none', padding: '1rem 2rem', marginBottom: '1.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        
        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{ 
            background: 'var(--accent-gradient)', 
            padding: '8px', 
            borderRadius: '12px', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            boxShadow: 'var(--accent-glow)'
          }}>
            <Youtube size={24} color="#ffffff" />
          </div>
          <div>
            <h1 style={{ fontSize: '1.4rem', fontWeight: '800', letterSpacing: '-0.5px' }}>
              Vid<span className="gradient-text">RAG</span>
            </h1>
            <p style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
              YouTube AI Chatbot &bull; TiDB Vector Cloud
            </p>
          </div>
        </div>

        {/* Tech Badges */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '0.4rem', 
            background: 'rgba(99, 102, 241, 0.1)', 
            border: '1px solid rgba(99, 102, 241, 0.3)',
            borderRadius: '20px',
            padding: '4px 12px',
            fontSize: '0.8rem',
            color: '#a5b4fc'
          }}>
            <Database size={14} />
            <span>TiDB Serverless Vector</span>
          </div>

          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '0.4rem', 
            background: 'rgba(236, 72, 153, 0.1)', 
            border: '1px solid rgba(236, 72, 153, 0.3)',
            borderRadius: '20px',
            padding: '4px 12px',
            fontSize: '0.8rem',
            color: '#f472b6'
          }}>
            <Sparkles size={14} />
            <span>Groq LLaMA 3.3</span>
          </div>
        </div>

        {/* User / Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {currentVideoId && (
            <button
              onClick={onOpenSummary}
              style={{
                background: 'rgba(255, 255, 255, 0.06)',
                border: '1px solid var(--border-subtle)',
                color: '#e2e8f0',
                padding: '6px 14px',
                borderRadius: '8px',
                cursor: 'pointer',
                fontSize: '0.85rem',
                fontWeight: '500',
                transition: 'all 0.2s',
              }}
              onMouseEnter={(e) => e.target.style.borderColor = 'var(--accent-primary)'}
              onMouseLeave={(e) => e.target.style.borderColor = 'var(--border-subtle)'}
            >
              📝 Video Summary
            </button>
          )}

          {user ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '0.5rem',
                background: 'rgba(255, 255, 255, 0.05)',
                padding: '6px 12px',
                borderRadius: '8px',
                border: '1px solid var(--border-subtle)',
                fontSize: '0.85rem'
              }}>
                <User size={15} color="#818cf8" />
                <span style={{ fontWeight: '600', color: '#f8fafc' }}>{user.username}</span>
              </div>
              <button
                onClick={onLogout}
                title="Logout"
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#94a3b8',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  padding: '6px',
                }}
              >
                <LogOut size={18} />
              </button>
            </div>
          ) : (
            <button
              onClick={onOpenAuth}
              className="gradient-btn"
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '7px 16px', fontSize: '0.85rem' }}
            >
              <LogIn size={15} />
              <span>Sign In</span>
            </button>
          )}
        </div>

      </div>
    </header>
  );
}
