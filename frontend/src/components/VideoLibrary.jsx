import React from 'react';
import { PlaySquare, CheckCircle, MessageSquare } from 'lucide-react';

export default function VideoLibrary({ videos, currentVideoId, onSelectVideo }) {
  if (!videos || videos.length === 0) {
    return null;
  }

  return (
    <div className="glass-panel" style={{
      padding: '0.75rem 1rem',
      borderRadius: '12px',
      marginBottom: '1.25rem',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '0.65rem',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
          <PlaySquare size={15} color="#ffffff" />
          <span style={{ fontSize: '0.82rem', fontWeight: '700', color: '#ffffff', letterSpacing: '0.2px' }}>
            My Videos ({videos.length})
          </span>
        </div>
        <span style={{ fontSize: '0.72rem', color: '#71717a' }}>
          Click to switch video & chat
        </span>
      </div>

      {/* Horizontal Scrollable Private Video Cards */}
      <div style={{
        display: 'flex',
        gap: '0.65rem',
        overflowX: 'auto',
        paddingBottom: '0.35rem',
        scrollbarWidth: 'thin',
      }}>
        {videos.map((vidObj, idx) => {
          const vidId = typeof vidObj === 'string' ? vidObj : vidObj.video_id;
          const isActive = vidId === currentVideoId;
          const msgCount = typeof vidObj === 'object' ? vidObj.message_count : 0;

          return (
            <div
              key={idx}
              onClick={() => onSelectVideo(vidId)}
              style={{
                flex: '0 0 145px',
                background: isActive ? 'rgba(255, 255, 255, 0.12)' : 'rgba(255, 255, 255, 0.03)',
                border: isActive ? '1.5px solid #ffffff' : '1px solid var(--border-subtle)',
                borderRadius: '8px',
                overflow: 'hidden',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                position: 'relative',
                boxShadow: isActive ? '0 0 12px rgba(255, 255, 255, 0.2)' : 'none',
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.35)';
                  e.currentTarget.style.transform = 'translateY(-2px)';
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.borderColor = 'var(--border-subtle)';
                  e.currentTarget.style.transform = 'translateY(0)';
                }
              }}
            >
              {/* Thumbnail */}
              <div style={{ height: '78px', width: '100%', position: 'relative', background: '#000000' }}>
                <img
                  src={`https://img.youtube.com/vi/${vidId}/mqdefault.jpg`}
                  alt={vidId}
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
                {isActive && (
                  <div style={{
                    position: 'absolute',
                    top: '5px',
                    left: '5px',
                    background: 'rgba(16, 185, 129, 0.92)',
                    backdropFilter: 'blur(4px)',
                    color: '#ffffff',
                    fontSize: '0.62rem',
                    fontWeight: '700',
                    padding: '2px 5px',
                    borderRadius: '4px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '3px',
                  }}>
                    <CheckCircle size={9} />
                    <span>ACTIVE</span>
                  </div>
                )}
              </div>

              {/* Card Meta */}
              <div style={{ padding: '5px 7px' }}>
                <div style={{
                  fontSize: '0.72rem',
                  fontWeight: '600',
                  color: isActive ? '#ffffff' : '#d4d4d8',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}>
                  {vidId}
                </div>
                {msgCount > 0 && (
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '3px',
                    fontSize: '0.65rem',
                    color: '#a1a1aa',
                    marginTop: '2px',
                  }}>
                    <MessageSquare size={9} />
                    <span>{msgCount} msgs</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

