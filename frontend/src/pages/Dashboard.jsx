import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import Layout from '../components/Layout';
import StockCard from '../components/StockCard';
import TickerSearch from '../components/TickerSearch';
import { api } from '../lib/api';
import { useAuth } from '../lib/AuthContext';


export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getFollowed()
      .then(setStocks)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleFollow = (newStock) => {
    setStocks(prev => {
      if (prev.find(s => s.ticker === newStock.ticker)) return prev;
      return [newStock, ...prev];
    });
  };

  const handleUnfollow = async (ticker) => {
    try {
      await api.unfollowStock(ticker);
      setStocks(prev => prev.filter(s => s.ticker !== ticker));
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <Layout>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 className="page-title">Your Watchlist</h1>
          <p className="page-subtitle">
            Follow NSE/BSE tickers to ingest their fundamentals &amp; news into your research brain.
            {stocks.length > 0 && (
              <span style={{ color: 'var(--teal)', marginLeft: 8 }}>
                {stocks.length} stock{stocks.length !== 1 ? 's' : ''} tracked
              </span>
            )}
          </p>
        </div>
        {stocks.length > 0 && (
          <Link to="/analytics" className="btn btn-ghost btn-sm" style={{ marginTop: 4, fontSize: 12 }}>
            📈 View Sentiment Charts →
          </Link>
        )}
      </div>


      <TickerSearch onFollow={handleFollow} />

      {user?.persona_text && (
        <div className="persona-banner">
          <span className="icon">🧠</span>
          <span><strong>Your Profile:</strong> {user.persona_text}</span>
          <button
            className="btn btn-ghost btn-sm"
            style={{ marginLeft: 'auto' }}
            onClick={() => navigate('/research')}
          >
            Get Recommendations →
          </button>
        </div>
      )}

      {loading ? (
        <div className="empty-state">
          <div className="spinner" style={{ width: 40, height: 40 }} />
          <p style={{ marginTop: 16 }}>Loading your watchlist<span className="loading-dots" /></p>
        </div>
      ) : stocks.length === 0 ? (
        <div className="empty-state">
          <div className="icon">📭</div>
          <h3>No stocks followed yet</h3>
          <p>Search for an NSE or BSE ticker above and click <strong>Follow</strong> to start ingesting data.</p>
          <div style={{ marginTop: 24, display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
            {['RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'WIPRO'].map(t => (
              <button
                key={t}
                className="btn btn-ghost btn-sm"
                onClick={() => api.followStock(t).then(r => handleFollow(r.stock))}
              >
                + {t}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="stocks-grid">
          {stocks.map(stock => (
            <StockCard
              key={stock.id}
              stock={stock}
              onUnfollow={handleUnfollow}
            />
          ))}
        </div>
      )}
    </Layout>
  );
}
