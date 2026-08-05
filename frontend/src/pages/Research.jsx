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
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);

  // Initialize single persistent chat stream on mount
  useEffect(() => {
    const initSingleChat = async () => {
      setLoading(true);
      try {
        const savedTid = localStorage.getItem('equity_active_thread_id');
        const existingThreads = await api.listThreads();
        
        let tidToUse = savedTid;

        // If saved thread ID is valid in existing threads, use it
        if (savedTid && existingThreads.some(t => t.thread_id === savedTid)) {
          tidToUse = savedTid;
        } else if (existingThreads.length > 0) {
          // Otherwise pick the user's existing chat thread
          tidToUse = existingThreads[0].thread_id;
        } else {
          // Create a new single chat thread
          const newRes = await api.newThread();
          tidToUse = newRes.thread_id;
        }

        setThreadId(tidToUse);
        localStorage.setItem('equity_active_thread_id', tidToUse);

        // Fetch complete message history for refresh persistence
        const history = await api.getHistory(tidToUse);
        setMessages(history.messages || []);
      } catch (e) {
        console.error("Failed to load chat history:", e);
      } finally {
        setLoading(false);
      }
    };

    initSingleChat();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const clearChatStream = async () => {
    if (loading) return;
    setLoading(true);
    try {
      const res = await api.newThread();
      setThreadId(res.thread_id);
      localStorage.setItem('equity_active_thread_id', res.thread_id);
      setMessages([]);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
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
        localStorage.setItem('equity_active_thread_id', response.thread_id);
      }
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
      <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 120px)' }}>
        {/* Main Chat Container */}
        <div className="chat-container" style={{ flex: 1, width: '100%', maxWidth: 1000, margin: '0 auto' }}>
          {/* Header */}
          <div className="page-header" style={{ paddingBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <h1 className="page-title">AI Chat</h1>
              <p className="page-subtitle">
                Ask about fundamentals, sentiment, or say "Recommend stocks for my profile".
                All answers cited &amp; in INR.
              </p>
              {user?.persona_text && (
                <div style={{ marginTop: 8, fontSize: 13, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span>🧠</span>
                  <span>Investor Profile: {user.persona_text.slice(0, 120)}{user.persona_text.length > 120 ? '…' : ''}</span>
                </div>
              )}
            </div>

            {messages.length > 0 && (
              <button
                className="btn btn-ghost btn-sm"
                onClick={clearChatStream}
                title="Clear Chat Stream"
                style={{ marginTop: 4, fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}
              >
                <span>🗑️</span> Clear Chat
              </button>
            )}
          </div>

          {/* Messages */}
          <div className="chat-messages">
            {messages.length === 0 && (
              <div className="empty-state" style={{ padding: '40px 0' }}>
                <div className="icon">💬</div>
                <h3>Start your AI Chat session</h3>
                <p>Ask anything about your followed stocks, or tell me about your investment style.</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center', marginTop: 24 }}>
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

