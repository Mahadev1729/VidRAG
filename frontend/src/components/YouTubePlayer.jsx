import React, { useRef } from 'react';
import { PlayCircle } from 'lucide-react';

export default function YouTubePlayer({ videoId }) {
  const iframeRef = useRef(null);

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
    </div>
  );
}

