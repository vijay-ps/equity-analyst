const API_BASE = import.meta.env.VITE_API_URL || '';

function getToken() {
  return localStorage.getItem('equity_token');
}

async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    localStorage.removeItem('equity_token');
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }

  return res.json();
}

export const api = {
  // Auth
  getMe: () => apiFetch('/api/stocks/me'),
  logout: () => {
    localStorage.removeItem('equity_token');
    window.location.href = '/login';
  },

  // Stocks
  getFollowed: () => apiFetch('/api/stocks/followed'),
  followStock: (ticker) => apiFetch('/api/stocks/follow', {
    method: 'POST',
    body: JSON.stringify({ ticker }),
  }),
  unfollowStock: (ticker) => apiFetch(`/api/stocks/unfollow/${ticker}`, {
    method: 'DELETE',
  }),
  searchStocks: (query) => apiFetch(`/api/stocks/search/${encodeURIComponent(query)}`),
  getSentimentHistory: (ticker, days = 30) =>
    apiFetch(`/api/stocks/${ticker}/sentiment-history?days=${days}`),
  refreshStock: (ticker) => apiFetch(`/api/stocks/${ticker}/refresh`, { method: 'POST' }),

  // Chat
  sendMessage: (message, threadId) => apiFetch('/api/chat/send', {
    method: 'POST',
    body: JSON.stringify({ message, thread_id: threadId }),
  }),
  newThread: () => apiFetch('/api/chat/new', { method: 'POST' }),
  getHistory: (threadId) => apiFetch(`/api/chat/history/${threadId}`),
  listThreads: () => apiFetch('/api/chat/threads'),

  // Health
  health: () => apiFetch('/api/health'),
};
