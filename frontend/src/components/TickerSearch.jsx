import React, { useState } from 'react';
import { api } from '../lib/api';

export default function TickerSearch({ onFollow }) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleFollow = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const result = await api.followStock(query.trim().toUpperCase());
      setSuccess(`✓ Now following ${result.stock.ticker} — ingesting data in background...`);
      setQuery('');
      if (onFollow) onFollow(result.stock);
      setTimeout(() => setSuccess(''), 5000);
    } catch (err) {
      setError(err.message || 'Failed to follow ticker');
      setTimeout(() => setError(''), 4000);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <form onSubmit={handleFollow} className="ticker-search">
        <div className="input-wrapper" style={{ flex: 1 }}>
          <input
            className="input"
            placeholder="Enter NSE/BSE ticker (e.g. RELIANCE, TCS, HDFCBANK)"
            value={query}
            onChange={e => setQuery(e.target.value.toUpperCase())}
            disabled={loading}
            style={{ fontFamily: 'JetBrains Mono, monospace', letterSpacing: 1 }}
          />
        </div>
        <button className="btn btn-primary" type="submit" disabled={loading || !query.trim()}>
          {loading ? <span className="spinner" /> : '+ Follow'}
        </button>
      </form>
      {success && <div className="toast success" style={{ position: 'relative', bottom: 'auto', right: 'auto', margin: '0 32px' }}>{success}</div>}
      {error   && <div className="toast error"   style={{ position: 'relative', bottom: 'auto', right: 'auto', margin: '0 32px' }}>{error}</div>}
    </div>
  );
}
