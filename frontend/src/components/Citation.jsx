import React from 'react';

export default function Citation({ citation }) {
  const { index, ticker, title, source, url, published_at, sentiment } = citation;
  const sentClass = sentiment === 'positive' ? 'positive' : sentiment === 'negative' ? 'negative' : 'neutral';
  const date = published_at ? new Date(published_at).toLocaleDateString('en-IN') : null;

  return (
    <div className="citation-card">
      <span className="citation-num">[{index}]</span>
      <div className="citation-body">
        <div className="citation-title">
          {url ? (
            <a href={url} target="_blank" rel="noopener noreferrer">{title}</a>
          ) : title}
        </div>
        <div className="citation-source">
          {source}{date ? ` • ${date}` : ''}
          {sentiment && <span className={`sentiment-badge ${sentClass}`} style={{ marginLeft: 6, fontSize: 10 }}>
            {sentiment}
          </span>}
        </div>
      </div>
      <span className="citation-ticker">{ticker}</span>
    </div>
  );
}
