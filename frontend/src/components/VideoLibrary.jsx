import React from 'react';
import { PlaySquare, Plus, CheckCircle, MessageSquare } from 'lucide-react';

export default function VideoLibrary({ videos, currentVideoId, onSelectVideo, onOpenAddModal }) {
  if (!videos || videos.length === 0) {
    return null;
  }

  return (
    <div className="glass-panel" style={{
      padding: '0.85rem 1rem',
      borderRadius: '12px',
      marginBottom: '1rem',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '0.75rem',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <PlaySquare size={16} color="#ffffff" />
          <span style={{ fontSize: '0.85rem', fontWeight: '700', color: '#ffffff' }}>
            Video Library ({videos.length})
          </span>
        </div>

        <button
          onClick={onOpenAddModal}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.35rem',
            background: 'rgba(255, 255, 255, 0.1)',
            border: '1px solid rgba(255, 255, 255, 0.25)',
            color: '#ffffff',
            borderRadius: '6px',
            padding: '4px 10px',
            fontSize: '0.75rem',
            fontWeight: '600',
            cursor: 'pointer',
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) => {
            e.target.style.background = '#ffffff';
            e.target.style.color = '#000000';
          }}
          onMouseLeave={(e) => {
            e.target.style.background = 'rgba(255, 255, 255, 0.1)';
            e.target.style.color = '#ffffff';
          }}
        >
          <Plus size={13} />
          <span>Add New Video</span>
        </button>
      </div>

      {/* Horizontal Scrollable Video Cards */}
      <div style={{
        display: 'flex',
        gap: '0.75rem',
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
                flex: '0 0 160px',
                background: isActive ? 'rgba(255, 255, 255, 0.12)' : 'rgba(255, 255, 255, 0.04)',
                border: isActive ? '1.5px solid rgba(255, 255, 255, 0.6)' : '1px solid var(--border-subtle)',
                borderRadius: '10px',
                overflow: 'hidden',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                position: 'relative',
                boxShadow: isActive ? '0 0 15px rgba(255, 255, 255, 0.15)' : 'none',
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.3)';
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
              <div style={{ height: '90px', width: '100%', position: 'relative', background: '#000000' }}>
                <img
                  src={`https://img.youtube.com/vi/${vidId}/mqdefault.jpg`}
                  alt={vidId}
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
                {isActive && (
                  <div style={{
                    position: 'absolute',
                    top: '6px',
                    left: '6px',
                    background: 'rgba(16, 185, 129, 0.9)',
                    backdropFilter: 'blur(4px)',
                    color: '#ffffff',
                    fontSize: '0.65rem',
                    fontWeight: '700',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '3px',
                  }}>
                    <CheckCircle size={10} />
                    <span>ACTIVE</span>
                  </div>
                )}
              </div>

              {/* Card Meta */}
              <div style={{ padding: '6px 8px' }}>
                <div style={{
                  fontSize: '0.75rem',
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
                    gap: '4px',
                    fontSize: '0.68rem',
                    color: '#a1a1aa',
                    marginTop: '2px',
                  }}>
                    <MessageSquare size={10} />
                    <span>{msgCount} messages</span>
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
