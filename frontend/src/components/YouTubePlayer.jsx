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
          height: '360px', 
          display: 'flex', 
          flexDirection: 'column', 
          alignItems: 'center', 
          justifyContent: 'center',
          color: '#52525b',
          gap: '0.75rem',
          textAlign: 'center',
          padding: '2rem'
        }}
      >
        <PlayCircle size={42} strokeWidth={1.5} color="#3f3f46" />
        <div>
          <h3 style={{ fontSize: '1rem', color: '#a1a1aa', marginBottom: '0.2rem' }}>No Video Loaded</h3>
          <p style={{ fontSize: '0.8rem', color: '#71717a' }}>Paste a YouTube link above to index.</p>
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
        padding: '0.65rem 0.85rem', 
        background: 'rgba(12, 12, 14, 0.8)', 
        borderTop: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontSize: '0.75rem',
        color: '#71717a'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <Clock size={13} color="#a1a1aa" />
          <span>Click citations in chat to jump video timestamp</span>
        </div>
      </div>
    </div>
  );
}
