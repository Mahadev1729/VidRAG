import React, { useRef, useEffect } from 'react';
import { PlayCircle, Clock } from 'lucide-react';

export default function YouTubePlayer({ videoId, currentTimestamp }) {
  const iframeRef = useRef(null);

  // Jump to timestamp when changed
  useEffect(() => {
    if (iframeRef.current && currentTimestamp !== null && currentTimestamp !== undefined) {
      const src = `https://www.youtube.com/embed/${videoId}?start=${Math.floor(currentTimestamp)}&autoplay=1&enablejsapi=1`;
      iframeRef.current.src = src;
    }
  }, [currentTimestamp, videoId]);

  if (!videoId) {
    return (
      <div 
        className="glass-panel" 
        style={{ 
          height: '380px', 
          display: 'flex', 
          flexDirection: 'column', 
          alignItems: 'center', 
          justifyContent: 'center',
          color: '#64748b',
          gap: '1rem',
          textAlign: 'center',
          padding: '2rem'
        }}
      >
        <PlayCircle size={48} strokeWidth={1.5} color="#475569" />
        <div>
          <h3 style={{ fontSize: '1.1rem', color: '#94a3b8', marginBottom: '0.25rem' }}>No Video Loaded</h3>
          <p style={{ fontSize: '0.85rem' }}>Enter a YouTube URL above to index and watch the video.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="glass-panel" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div style={{ 
        position: 'relative', 
        paddingBottom: '56.25%', /* 16:9 Aspect Ratio */ 
        height: 0, 
        overflow: 'hidden',
        background: '#000000'
      }}>
        <iframe
          ref={iframeRef}
          src={`https://www.youtube.com/embed/${videoId}?enablejsapi=1`}
          title="YouTube Video Player"
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            border: 'none',
          }}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
        />
      </div>

      <div style={{ 
        padding: '0.75rem 1rem', 
        background: 'rgba(15, 23, 42, 0.6)', 
        borderTop: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontSize: '0.8rem',
        color: '#94a3b8'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Clock size={14} color="#818cf8" />
          <span>Click any timestamp citation in the chat to jump the video directly!</span>
        </div>
      </div>
    </div>
  );
}
