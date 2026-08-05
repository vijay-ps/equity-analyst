import React from 'react';

function fmt(val, prefix = 'Rs. ') {
  if (val == null) return 'N/A';
  if (val >= 1e12) return `${prefix}${(val / 1e12).toFixed(2)}T`;
  if (val >= 1e7) return `${prefix}${(val / 1e7).toFixed(2)} Cr`;
  if (val >= 1e5) return `${prefix}${(val / 1e5).toFixed(2)}L`;
  return `${prefix}${val.toFixed(2)}`;
}

function fmtPct(val) {
  if (val == null) return 'N/A';
  return `${(val * 100).toFixed(2)}%`;
}

function fmtX(val) {
  if (val == null) return 'N/A';
  return `${val.toFixed(2)}x`;
}

function SentimentBadge({ score }) {
  if (score == null) return null;
  const cls = score > 0.1 ? 'positive' : score < -0.1 ? 'negative' : 'neutral';
  const label = score > 0.1 ? '▲ Positive' : score < -0.1 ? '▼ Negative' : '◆ Neutral';
  return <span className={`sentiment-badge ${cls}`}>{label}</span>;
}

export default function StockCard({ stock, onUnfollow }) {
  return (
    <div className="stock-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div className="stock-ticker">{stock.ticker}</div>
          <div className="stock-name">{stock.name || '—'}</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <SentimentBadge score={stock.sentiment_score} />
          {onUnfollow && (
            <button
              className="btn btn-ghost btn-sm btn-icon"
              onClick={() => onUnfollow(stock.ticker)}
              title="Unfollow"
              style={{ fontSize: 12 }}
            >
              ✕
            </button>
          )}
        </div>
      </div>

      <div className="stock-price">
        {stock.last_price ? `Rs. ${stock.last_price.toFixed(2)}` : 'N/A'}
      </div>

      <div className="stock-meta">
        <div className="metric-pill">
          <span className="metric-label">P/E</span>
          <span className="metric-value">{fmtX(stock.pe_ratio)}</span>
        </div>
        <div className="metric-pill">
          <span className="metric-label">P/B</span>
          <span className="metric-value">{fmtX(stock.pb_ratio)}</span>
        </div>
        <div className="metric-pill">
          <span className="metric-label">Div Yield</span>
          <span className="metric-value">{fmtPct(stock.dividend_yield)}</span>
        </div>
        <div className="metric-pill">
          <span className="metric-label">D/E</span>
          <span className="metric-value">{fmtX(stock.debt_to_equity)}</span>
        </div>
        <div className="metric-pill">
          <span className="metric-label">ROE</span>
          <span className="metric-value">{fmtPct(stock.roe)}</span>
        </div>
      </div>

      <div style={{ marginTop: 10 }}>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          {stock.sector || ''} • {stock.exchange}
        </span>
        {stock.last_ingested && (
          <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>
            • Updated {new Date(stock.last_ingested).toLocaleDateString('en-IN')}
          </span>
        )}
      </div>
    </div>
  );
}
