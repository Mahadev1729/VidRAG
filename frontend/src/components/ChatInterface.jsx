import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { Send, Trash2, Bot, User, Loader2, Play } from 'lucide-react';
import { api } from '../services/api';

export default function ChatInterface({ videoId, onSeek, isProcessing }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
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

    let accumulatedContent = '';
    let accumulatedCitations = [];

    try {
      // Add initial streaming placeholder
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: '',
          citations: [],
          question: query,
          isStreaming: true,
        },
      ]);

      await api.askQuestionStream(
        videoId,
        query,
        (token) => {
          accumulatedContent += token;
          setMessages(prev => {
            const next = [...prev];
            const lastIdx = next.length - 1;
            if (lastIdx >= 0 && next[lastIdx].role === 'assistant') {
              next[lastIdx] = {
                ...next[lastIdx],
                content: accumulatedContent,
                isStreaming: true,
              };
            }
            return next;
          });
        },
        (citations) => {
          accumulatedCitations = citations;
          setMessages(prev => {
            const next = [...prev];
            const lastIdx = next.length - 1;
            if (lastIdx >= 0 && next[lastIdx].role === 'assistant') {
              next[lastIdx] = {
                ...next[lastIdx],
                citations: accumulatedCitations,
              };
            }
            return next;
          });
        }
      );

      // Finalize streaming
      setMessages(prev => {
        const next = [...prev];
        const lastIdx = next.length - 1;
        if (lastIdx >= 0 && next[lastIdx].role === 'assistant') {
          next[lastIdx] = {
            ...next[lastIdx],
            content: accumulatedContent || 'I couldn\'t find information about that in the video transcript.',
            citations: accumulatedCitations,
            isStreaming: false,
          };
        }
        return next;
      });
    } catch (err) {
      console.warn("Streaming error, falling back to batch request:", err);
      try {
        const response = await api.askQuestion(videoId, query);
        setMessages(prev => {
          const next = [...prev];
          const lastIdx = next.length - 1;
          if (lastIdx >= 0 && next[lastIdx].role === 'assistant') {
            next[lastIdx] = {
              role: 'assistant',
              content: response.answer,
              citations: response.citations || [],
              question: query,
              isStreaming: false,
            };
            return next;
          }
          return [...prev, {
            role: 'assistant',
            content: response.answer,
            citations: response.citations || [],
            question: query,
          }];
        });
      } catch (fallbackErr) {
        setMessages(prev => [
          ...prev.filter(m => m.content !== '' || !m.isStreaming),
          {
            role: 'assistant',
            content: `⚠️ Error: ${fallbackErr.message || 'Failed to generate answer. Please make sure the video is indexed.'}`,
            citations: [],
          },
        ]);
      }
    } finally {
      setLoading(false);
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
    <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', height: '620px', overflow: 'hidden' }}>
      
      {/* Header */}
      <div style={{
        padding: '0.85rem 1.15rem',
        borderBottom: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'rgba(12, 12, 14, 0.8)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Bot size={18} color="#ffffff" />
          <h3 style={{ fontSize: '0.92rem', fontWeight: '600', color: '#ffffff' }}>AI Chat</h3>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {messages.length > 0 && (
            <button
              onClick={handleClearHistory}
              title="Clear Conversation"
              style={{
                background: 'transparent',
                border: 'none',
                color: '#71717a',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                transition: 'color 0.2s',
              }}
              onMouseEnter={(e) => e.target.style.color = '#ef4444'}
              onMouseLeave={(e) => e.target.style.color = '#71717a'}
            >
              <Trash2 size={15} />
            </button>
          )}
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {messages.length === 0 ? (
          <div style={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#71717a',
            textAlign: 'center',
            gap: '0.85rem'
          }}>
            <Bot size={36} color="#3f3f46" />
            <div>
              <h4 style={{ color: '#e4e4e7', marginBottom: '0.2rem', fontSize: '0.95rem' }}>Ask anything</h4>
              <p style={{ fontSize: '0.8rem', color: '#71717a' }}>Query transcript timestamps or get key insights.</p>
            </div>

            {/* Quick Suggestions */}
            {videoId && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', width: '100%', maxWidth: '340px', marginTop: '0.5rem' }}>
                {quickQuestions.map((q, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSend(null, q)}
                    style={{
                      background: 'rgba(255, 255, 255, 0.03)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: '7px',
                      padding: '7px 11px',
                      color: '#d4d4d8',
                      fontSize: '0.78rem',
                      textAlign: 'left',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                    onMouseEnter={(e) => {
                      e.target.style.borderColor = 'rgba(255, 255, 255, 0.3)';
                      e.target.style.background = 'rgba(255, 255, 255, 0.08)';
                    }}
                    onMouseLeave={(e) => {
                      e.target.style.borderColor = 'var(--border-subtle)';
                      e.target.style.background = 'rgba(255, 255, 255, 0.03)';
                    }}
                  >
                    {q}
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
                gap: '0.65rem',
                alignItems: 'flex-start',
                flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
              }}
            >
              {/* Avatar */}
              <div style={{
                background: msg.role === 'user' ? '#ffffff' : 'rgba(24, 24, 27, 0.9)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '50%',
                width: '28px',
                height: '28px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}>
                {msg.role === 'user' ? <User size={14} color="#000000" /> : <Bot size={14} color="#ffffff" />}
              </div>

              {/* Message Body */}
              <div style={{
                maxWidth: '85%',
                background: msg.role === 'user' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(18, 18, 20, 0.9)',
                border: '1px solid',
                borderColor: msg.role === 'user' ? 'rgba(255, 255, 255, 0.2)' : 'var(--border-subtle)',
                borderRadius: '10px',
                padding: '0.75rem 1rem',
                fontSize: '0.88rem',
                lineHeight: '1.5',
                color: '#f4f4f5',
              }}>
                <ReactMarkdown>{msg.content}</ReactMarkdown>

                {/* Timestamp Citations */}
                {msg.citations && msg.citations.length > 0 && (
                  <div style={{ marginTop: '0.65rem', borderTop: '1px solid var(--border-subtle)', paddingTop: '0.45rem' }}>
                    <div style={{ fontSize: '0.72rem', color: '#71717a', marginBottom: '0.3rem', fontWeight: '600' }}>
                      Citations:
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
                      {msg.citations.map((cite, cIdx) => (
                        <button
                          key={cIdx}
                          onClick={() => onSeek(cite.start)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.25rem',
                            background: 'rgba(255, 255, 255, 0.08)',
                            border: '1px solid rgba(255, 255, 255, 0.2)',
                            color: '#ffffff',
                            borderRadius: '5px',
                            padding: '2px 7px',
                            fontSize: '0.72rem',
                            cursor: 'pointer',
                            transition: 'all 0.15s',
                          }}
                          onMouseEnter={(e) => e.target.style.background = 'rgba(255, 255, 255, 0.2)'}
                          onMouseLeave={(e) => e.target.style.background = 'rgba(255, 255, 255, 0.08)'}
                        >
                          <Play size={9} fill="#ffffff" />
                          <span>{cite.timestamp}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))
        )}

        {loading && (
          <div style={{ display: 'flex', gap: '0.65rem', alignItems: 'center' }}>
            <div style={{
              background: 'rgba(24, 24, 27, 0.9)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '50%',
              width: '28px',
              height: '28px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <Bot size={14} color="#ffffff" />
            </div>
            <div style={{
              background: 'rgba(18, 18, 20, 0.9)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '10px',
              padding: '0.65rem 0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.45rem',
              fontSize: '0.8rem',
              color: '#a1a1aa',
            }}>
              <Loader2 size={14} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
              <span>Thinking...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Box */}
      <form onSubmit={handleSend} style={{
        padding: '0.75rem',
        borderTop: '1px solid var(--border-subtle)',
        background: 'rgba(12, 12, 14, 0.9)',
        display: 'flex',
        gap: '0.5rem',
        alignItems: 'center',
      }}>
        <input
          type="text"
          placeholder={videoId ? "Ask about this video..." : "Index a video first..."}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={!videoId || loading || isProcessing}
          style={{
            flex: 1,
            background: 'rgba(24, 24, 27, 0.7)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '8px',
            color: '#f4f4f5',
            padding: '9px 12px',
            fontSize: '0.88rem',
            outline: 'none',
          }}
        />

        <button
          type="submit"
          disabled={!videoId || !input.trim() || loading || isProcessing}
          className="gradient-btn"
          style={{
            padding: '9px 15px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '8px',
          }}
        >
          <Send size={15} />
        </button>
      </form>

    </div>
  );
}
