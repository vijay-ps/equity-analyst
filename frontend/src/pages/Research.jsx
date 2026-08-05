import React, { useState, useEffect, useRef } from 'react';
import Layout from '../components/Layout';
import Citation from '../components/Citation';
import { api } from '../lib/api';
import { useAuth } from '../lib/AuthContext';

const SUGGESTIONS = [
  "What's the sentiment on TCS this week?",
  "Compare RELIANCE and HDFCBANK fundamentals",
  "I'm a conservative, dividend-focused investor who avoids high debt",
  "Recommend stocks for my investor profile",
  "What is INFY's P/E ratio and recent earnings news?",
  "Which of my followed stocks have the best ROE?",
];

function MessageBubble({ msg }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`message ${isUser ? 'user' : 'assistant'}`}>
      <div className="message-avatar">
        {isUser ? '👤' : '🤖'}
      </div>
      <div>
        <div className="message-bubble">
          {/* Render markdown-like bold formatting */}
          {msg.content.split('\n').map((line, i) => (
            <React.Fragment key={i}>
              {line.split(/(\*\*[^*]+\*\*)/).map((part, j) =>
                part.startsWith('**') && part.endsWith('**')
                  ? <strong key={j}>{part.slice(2, -2)}</strong>
                  : part
              )}
              {i < msg.content.split('\n').length - 1 && <br />}
            </React.Fragment>
          ))}
        </div>
        {msg.citations && msg.citations.length > 0 && (
          <div className="citations-list">
            {msg.citations.map(c => (
              <Citation key={c.index} citation={c} />
            ))}
          </div>
        )}
        {msg.created_at && (
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4, marginLeft: 4 }}>
            {new Date(msg.created_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
          </div>
        )}
      </div>
    </div>
  );
}

export default function Research() {
  const { user } = useAuth();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [threadId, setThreadId] = useState(null);
  const [threads, setThreads] = useState([]);
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);

  // Load threads and active conversation on mount
  const loadThreads = async () => {
    try {
      const data = await api.listThreads();
      setThreads(data || []);
      return data || [];
    } catch (e) {
      console.error(e);
      return [];
    }
  };

  useEffect(() => {
    const initChat = async () => {
      const existingThreads = await loadThreads();
      const savedTid = localStorage.getItem('equity_active_thread_id');

      if (savedTid && existingThreads.some(t => t.thread_id === savedTid)) {
        selectThread(savedTid);
      } else if (existingThreads.length > 0) {
        selectThread(existingThreads[0].thread_id);
      } else {
        startNewChat();
      }
    };
    initChat();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const selectThread = async (tid) => {
    if (loading) return;
    setThreadId(tid);
    localStorage.setItem('equity_active_thread_id', tid);
    setLoading(true);
    try {
      const history = await api.getHistory(tid);
      setMessages(history.messages || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const startNewChat = async () => {
    if (loading) return;
    try {
      const res = await api.newThread();
      setThreadId(res.thread_id);
      localStorage.setItem('equity_active_thread_id', res.thread_id);
      setMessages([]);
    } catch (e) {
      console.error(e);
    }
  };


  const sendMessage = async (text) => {
    const msgText = text || input.trim();
    if (!msgText || loading) return;

    const userMsg = {
      role: 'user',
      content: msgText,
      created_at: new Date().toISOString(),
      id: `u-${Date.now()}`,
    };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    // Add typing indicator
    const typingId = `typing-${Date.now()}`;
    setMessages(prev => [...prev, { id: typingId, role: 'assistant', content: '...', isTyping: true }]);

    try {
      const response = await api.sendMessage(msgText, threadId);
      setMessages(prev => [
        ...prev.filter(m => m.id !== typingId),
        {
          id: response.id,
          role: 'assistant',
          content: response.content,
          citations: response.citations,
          created_at: response.created_at,
          thread_id: response.thread_id,
        },
      ]);
      if (response.thread_id && !threadId) {
        setThreadId(response.thread_id);
      }
      loadThreads();
    } catch (err) {
      setMessages(prev => [
        ...prev.filter(m => m.id !== typingId),
        { id: `err-${Date.now()}`, role: 'assistant', content: `⚠️ Error: ${err.message}`, created_at: new Date().toISOString() },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleTextareaInput = (e) => {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 140) + 'px';
  };

  return (
    <Layout>
      <div style={{ display: 'flex', gap: 20, height: 'calc(100vh - 120px)' }}>
        {/* Sidebar: Past Threads */}
        <div style={{
          width: 260,
          flexShrink: 0,
          background: 'rgba(255, 255, 255, 0.03)',
          border: '1px solid var(--border-color)',
          borderRadius: 16,
          padding: 16,
          display: 'flex',
          flexDirection: 'column',
          backdropFilter: 'blur(10px)',
        }}>
          <button
            className="btn btn-primary"
            onClick={startNewChat}
            style={{ width: '100%', marginBottom: 16, justifyContent: 'center', gap: 8 }}
          >
            <span>+</span> New Research Session
          </button>

          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 10, tracking: '0.05em' }}>
            Past Conversations ({threads.length})
          </div>

          <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
            {threads.length === 0 ? (
              <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', marginTop: 20 }}>
                No past sessions yet
              </div>
            ) : (
              threads.map(t => {
                const isActive = t.thread_id === threadId;
                return (
                  <button
                    key={t.thread_id}
                    onClick={() => selectThread(t.thread_id)}
                    style={{
                      textAlign: 'left',
                      padding: '10px 12px',
                      borderRadius: 8,
                      border: '1px solid',
                      borderColor: isActive ? 'var(--teal)' : 'transparent',
                      background: isActive ? 'rgba(45, 212, 191, 0.1)' : 'rgba(255, 255, 255, 0.02)',
                      color: isActive ? 'var(--teal)' : 'var(--text-color)',
                      fontSize: 12,
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    💬 {t.preview}
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Main Chat Container */}
        <div className="chat-container" style={{ flex: 1 }}>
          {/* Header */}
          <div className="page-header" style={{ paddingBottom: 16 }}>
            <h1 className="page-title">AI Research Chat</h1>
            <p className="page-subtitle">
              Ask about fundamentals, sentiment, or say "Recommend stocks for my profile".
              All answers cited &amp; in INR.
            </p>
            {user?.persona_text && (
              <div style={{ marginTop: 10, fontSize: 13, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span>🧠</span>
                <span>Profile: {user.persona_text.slice(0, 120)}{user.persona_text.length > 120 ? '…' : ''}</span>
              </div>
            )}
          </div>

          {/* Messages */}
          <div className="chat-messages">
            {messages.length === 0 && (
              <div className="empty-state" style={{ padding: '32px 0' }}>
                <div className="icon">💬</div>
                <h3>Start your research session</h3>
                <p>Ask anything about your followed stocks, or tell me about your investment style.</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center', marginTop: 20 }}>
                  {SUGGESTIONS.map(s => (
                    <button
                      key={s}
                      className="btn btn-ghost btn-sm"
                      style={{ fontSize: 12 }}
                      onClick={() => sendMessage(s)}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map(msg => (
              msg.isTyping ? (
                <div key={msg.id} className="message assistant">
                  <div className="message-avatar">🤖</div>
                  <div className="message-bubble" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div className="spinner" style={{ width: 16, height: 16 }} />
                    <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>Analysing data<span className="loading-dots" /></span>
                  </div>
                </div>
              ) : (
                <MessageBubble key={msg.id} msg={msg} />
              )
            ))}
            <div ref={bottomRef} />
          </div>

          {/* Input Bar */}
          <div className="chat-input-bar">
            <div className="chat-input-form">
              <textarea
                ref={textareaRef}
                className="chat-textarea"
                placeholder="Ask about a stock, request recommendations, or update your investor profile…"
                value={input}
                onChange={handleTextareaInput}
                onKeyDown={handleKeyDown}
                rows={1}
                disabled={loading}
              />
              <button
                className="send-btn"
                onClick={() => sendMessage()}
                disabled={loading || !input.trim()}
                id="send-message-btn"
              >
                {loading ? <span className="spinner" style={{ width: 18, height: 18 }} /> : '↑'}
              </button>
            </div>
            <div style={{ textAlign: 'center', marginTop: 8, fontSize: 11, color: 'var(--text-muted)' }}>
              Enter to send • Shift+Enter for new line • All figures in INR (Rs.)
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}

