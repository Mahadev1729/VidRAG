import React from 'react';
import { Sparkles, Database, Youtube, User, LogOut, Plus } from 'lucide-react';

export default function Navbar({ user, onLogout, onOpenAddVideo, currentVideoId }) {
  return (
    <header className="glass-panel" style={{ borderRadius: '0 0 14px 14px', borderTop: 'none', padding: '0.85rem 1.5rem', marginBottom: '1.25rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        
        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <div style={{ 
            background: '#ffffff', 
            padding: '7px', 
            borderRadius: '10px', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            boxShadow: '0 0 15px rgba(255, 255, 255, 0.25)'
          }}>
            <Youtube size={20} color="#000000" />
          </div>
          <div>
            <h1 style={{ fontSize: '1.25rem', fontWeight: '800', letterSpacing: '-0.5px', color: '#ffffff' }}>
              Vid<span style={{ color: '#a1a1aa' }}>RAG</span>
            </h1>
          </div>
        </div>

        {/* Tech Badges */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '0.35rem', 
            background: 'rgba(255, 255, 255, 0.05)', 
            border: '1px solid rgba(255, 255, 255, 0.12)',
            borderRadius: '20px',
            padding: '4px 10px',
            fontSize: '0.75rem',
            color: '#e4e4e7'
          }}>
            <Database size={13} color="#a1a1aa" />
            <span>TiDB Vector</span>
          </div>

          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '0.35rem', 
            background: 'rgba(255, 255, 255, 0.05)', 
            border: '1px solid rgba(255, 255, 255, 0.12)',
            borderRadius: '20px',
            padding: '4px 10px',
            fontSize: '0.75rem',
            color: '#e4e4e7'
          }}>
            <Sparkles size={13} color="#a1a1aa" />
            <span>Groq LLaMA</span>
          </div>
        </div>

        {/* User / Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          {onOpenAddVideo && (
            <button
              onClick={onOpenAddVideo}
              className="gradient-btn"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                padding: '6px 14px',
                borderRadius: '8px',
                fontSize: '0.8rem',
                fontWeight: '600',
                cursor: 'pointer',
              }}
            >
              <Plus size={14} />
              <span>Add Video</span>
            </button>
          )}



          {user && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '0.5rem',
                background: 'rgba(255, 255, 255, 0.07)',
                padding: '4px 10px',
                borderRadius: '10px',
                border: '1px solid var(--border-subtle)',
                fontSize: '0.82rem'
              }}>
                {user.avatar ? (
                  <img
                    src={user.avatar}
                    alt={user.username}
                    style={{ width: '20px', height: '20px', borderRadius: '50%', objectFit: 'cover' }}
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <User size={14} color="#a1a1aa" />
                )}
                <span style={{ fontWeight: '600', color: '#ffffff' }}>{user.username}</span>
              </div>
              <button
                onClick={onLogout}
                title="Sign Out"
                style={{
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  color: '#a1a1aa',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  padding: '6px 8px',
                  fontSize: '0.75rem',
                  fontWeight: '500',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={(e) => {
                  e.target.style.borderColor = 'rgba(239, 68, 68, 0.4)';
                  e.target.style.color = '#f87171';
                }}
                onMouseLeave={(e) => {
                  e.target.style.borderColor = 'rgba(255, 255, 255, 0.12)';
                  e.target.style.color = '#a1a1aa';
                }}
              >
                <LogOut size={13} />
              </button>
            </div>
          )}
        </div>

      </div>
    </header>
  );
}
