import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { Send, ThumbsUp, ThumbsDown, Trash2, Bot, User, Loader2, Play } from 'lucide-react';
import { api } from '../services/api';

export default function ChatInterface({ videoId, onSeek, isProcessing }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [feedbackSent, setFeedbackSent] = useState({});
  const messagesEndRef = useRef(null);

  // Load chat history when videoId changes
  useEffect(() => {
    if (videoId) {
      loadHistory();
    } else {
      setMessages([]);
    }
  }, [videoId]);

  const loadHistory = async () => {
    try {
      const data = await api.getHistory(videoId);
      if (data && data.history) {
        setMessages(data.history.map(m => ({
          role: m.role,
          content: m.message,
          citations: [],
        })));
      }
    } catch (err) {
      console.error("Could not load history:", err);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSend = async (e, customText = null) => {
    if (e) e.preventDefault();
    const query = customText || input;
    if (!query.trim() || !videoId || loading) return;

    const userMessage = { role: 'user', content: query };
    setMessages(prev => [...prev, userMessage]);
    if (!customText) setInput('');
    setLoading(true);

    try {
      const response = await api.askQuestion(videoId, query);
      const assistantMessage = {
        role: 'assistant',
        content: response.answer,
        citations: response.citations || [],
        question: query,
      };
      setMessages(prev => [...prev, assistantMessage]);
    } catch (err) {
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: `⚠️ Error: ${err.message || 'Failed to generate answer. Please make sure the video is indexed.'}`,
          citations: [],
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (msgIndex, msg, rating) => {
    if (feedbackSent[msgIndex]) return;
    try {
      await api.sendFeedback(videoId, msg.question || "Video Q&A", msg.content, rating);
      setFeedbackSent(prev => ({ ...prev, [msgIndex]: rating > 0 ? 'up' : 'down' }));
    } catch (err) {
      console.error("Feedback failed:", err);
    }
  };

  const handleClearHistory = async () => {
    if (!videoId) return;
    if (window.confirm("Are you sure you want to clear the chat history for this video?")) {
      await api.clearHistory(videoId);
      setMessages([]);
    }
  };

  const quickQuestions = [
    "What is the main topic of this video?",
    "Summarize key insights in 3 bullet points",
    "What are the practical takeaways?",
  ];

  return (
    <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', height: '650px', overflow: 'hidden' }}>
      
      {/* Header */}
      <div style={{
        padding: '1rem 1.25rem',
        borderBottom: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'rgba(15, 23, 42, 0.4)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Bot size={20} color="#818cf8" />
          <h3 style={{ fontSize: '1rem', fontWeight: '600' }}>AI Video Assistant</h3>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {messages.length > 0 && (
            <button
              onClick={handleClearHistory}
              title="Clear Conversation"
              style={{
                background: 'transparent',
                border: 'none',
                color: '#64748b',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <Trash2 size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        {messages.length === 0 ? (
          <div style={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#64748b',
            textAlign: 'center',
            gap: '1rem'
          }}>
            <Bot size={40} color="#475569" />
            <div>
              <h4 style={{ color: '#cbd5e1', marginBottom: '0.25rem' }}>Ready to analyze video</h4>
              <p style={{ fontSize: '0.85rem' }}>Ask any question or pick a prompt below to get started.</p>
            </div>

            {/* Quick Suggestions */}
            {videoId && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', width: '100%', maxWidth: '360px', marginTop: '0.5rem' }}>
                {quickQuestions.map((q, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSend(null, q)}
                    style={{
                      background: 'rgba(255, 255, 255, 0.04)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: '8px',
                      padding: '8px 12px',
                      color: '#cbd5e1',
                      fontSize: '0.8rem',
                      textAlign: 'left',
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                    }}
                    onMouseEnter={(e) => {
                      e.target.style.borderColor = 'var(--accent-primary)';
                      e.target.style.background = 'rgba(99, 102, 241, 0.1)';
                    }}
                    onMouseLeave={(e) => {
                      e.target.style.borderColor = 'var(--border-subtle)';
                      e.target.style.background = 'rgba(255, 255, 255, 0.04)';
                    }}
                  >
                    ✨ {q}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          messages.map((msg, index) => (
            <div
              key={index}
              style={{
                display: 'flex',
                gap: '0.75rem',
                alignItems: 'flex-start',
                flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
              }}
            >
              {/* Avatar */}
              <div style={{
                background: msg.role === 'user' ? 'var(--accent-primary)' : 'rgba(30, 41, 59, 0.9)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '50%',
                width: '32px',
                height: '32px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}>
                {msg.role === 'user' ? <User size={16} color="#ffffff" /> : <Bot size={16} color="#818cf8" />}
              </div>

              {/* Message Body */}
              <div style={{
                maxWidth: '85%',
                background: msg.role === 'user' ? 'rgba(99, 102, 241, 0.2)' : 'rgba(18, 24, 38, 0.9)',
                border: '1px solid',
                borderColor: msg.role === 'user' ? 'rgba(99, 102, 241, 0.4)' : 'var(--border-subtle)',
                borderRadius: '12px',
                padding: '0.85rem 1.1rem',
                fontSize: '0.9rem',
                lineHeight: '1.5',
                color: '#f1f5f9',
              }}>
                <ReactMarkdown>{msg.content}</ReactMarkdown>

                {/* Timestamp Citations */}
                {msg.citations && msg.citations.length > 0 && (
                  <div style={{ marginTop: '0.75rem', borderTop: '1px solid var(--border-subtle)', paddingTop: '0.5rem' }}>
                    <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.35rem', fontWeight: '600' }}>
                      Timestamp Citations:
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                      {msg.citations.map((cite, cIdx) => (
                        <button
                          key={cIdx}
                          onClick={() => onSeek(cite.start)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.3rem',
                            background: 'rgba(99, 102, 241, 0.15)',
                            border: '1px solid rgba(99, 102, 241, 0.3)',
                            color: '#a5b4fc',
                            borderRadius: '6px',
                            padding: '3px 8px',
                            fontSize: '0.75rem',
                            cursor: 'pointer',
                            transition: 'all 0.2s',
                          }}
                          onMouseEnter={(e) => e.target.style.background = 'rgba(99, 102, 241, 0.3)'}
                          onMouseLeave={(e) => e.target.style.background = 'rgba(99, 102, 241, 0.15)'}
                        >
                          <Play size={10} fill="#a5b4fc" />
                          <span>{cite.timestamp}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Feedback buttons */}
                {msg.role === 'assistant' && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.6rem' }}>
                    <button
                      onClick={() => handleFeedback(index, msg, 1)}
                      title="Helpful Answer"
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: feedbackSent[index] === 'up' ? '#34d399' : '#64748b',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                      }}
                    >
                      <ThumbsUp size={14} />
                    </button>
                    <button
                      onClick={() => handleFeedback(index, msg, -1)}
                      title="Not Helpful"
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: feedbackSent[index] === 'down' ? '#f87171' : '#64748b',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                      }}
                    >
                      <ThumbsDown size={14} />
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))
        )}

        {loading && (
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <div style={{
              background: 'rgba(30, 41, 59, 0.9)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '50%',
              width: '32px',
              height: '32px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <Bot size={16} color="#818cf8" />
            </div>
            <div style={{
              background: 'rgba(18, 24, 38, 0.9)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '12px',
              padding: '0.75rem 1rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              fontSize: '0.85rem',
              color: '#94a3b8',
            }}>
              <Loader2 size={16} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
              <span>Analyzing transcript & querying TiDB Vector Store...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Box */}
      <form onSubmit={handleSend} style={{
        padding: '1rem',
        borderTop: '1px solid var(--border-subtle)',
        background: 'rgba(15, 23, 42, 0.6)',
        display: 'flex',
        gap: '0.75rem',
        alignItems: 'center',
      }}>
        <input
          type="text"
          placeholder={videoId ? "Ask anything about the video..." : "Please index a video first..."}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={!videoId || loading || isProcessing}
          style={{
            flex: 1,
            background: 'rgba(15, 23, 42, 0.8)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '10px',
            color: '#f8fafc',
            padding: '10px 14px',
            fontSize: '0.9rem',
            outline: 'none',
          }}
        />

        <button
          type="submit"
          disabled={!videoId || !input.trim() || loading || isProcessing}
          className="gradient-btn"
          style={{
            padding: '10px 18px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Send size={16} />
        </button>
      </form>

    </div>
  );
}
