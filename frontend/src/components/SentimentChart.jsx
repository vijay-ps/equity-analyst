import React, { useState, useEffect } from 'react';
import {
  ComposedChart,
  Area,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
} from 'recharts';
import { api } from '../lib/api';

// ── Custom Tooltip ────────────────────────────────────────────────────────────
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;

  const d = payload[0]?.payload || {};
  const score = d.sentiment_score ?? 0;
  const color = score > 0.1 ? 'var(--green)' : score < -0.1 ? 'var(--red)' : 'var(--text-secondary)';

  return (
    <div style={{
      background: 'rgba(13,18,48,0.95)',
      border: '1px solid var(--border)',
      borderRadius: 8,
      padding: '10px 14px',
      fontSize: 12,
      backdropFilter: 'blur(12px)',
      minWidth: 180,
    }}>
      <div style={{ fontWeight: 700, marginBottom: 6, color: 'var(--text-primary)' }}>{label}</div>
      <div style={{ color, fontWeight: 700, fontSize: 14, marginBottom: 4 }}>
        Score: {score.toFixed(3)}
        <span style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 6 }}>
          {score > 0.1 ? '▲ Positive' : score < -0.1 ? '▼ Negative' : '◆ Neutral'}
        </span>
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 4 }}>
        <span style={{ color: 'var(--green)' }}>+{d.positive_count}</span>
        <span style={{ color: 'var(--red)' }}>-{d.negative_count}</span>
        <span style={{ color: 'var(--text-muted)' }}>◆{d.neutral_count}</span>
      </div>
      {d.close_price && (
        <div style={{ color: 'var(--text-secondary)', marginTop: 6 }}>
          Close: Rs. {d.close_price.toFixed(2)}
        </div>
      )}
      <div style={{ color: 'var(--text-muted)', marginTop: 2 }}>
        {d.article_count} article{d.article_count !== 1 ? 's' : ''}
      </div>
    </div>
  );
}

// ── Seed mock data for tickers with no real history yet ───────────────────────
function generateMockData(days = 30) {
  const data = [];
  let score = (Math.random() - 0.5) * 0.4;

  for (let i = days - 1; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const dateStr = d.toISOString().slice(0, 10);

    // Random walk
    score = Math.max(-1, Math.min(1, score + (Math.random() - 0.5) * 0.2));
    const articles = Math.floor(Math.random() * 8) + 1;
    const pos = Math.floor(articles * Math.max(0, score + 0.5) * 0.8);
    const neg = Math.floor(articles * Math.max(0, -score + 0.5) * 0.8);

    data.push({
      date: dateStr,
      sentiment_score: parseFloat(score.toFixed(3)),
      positive_count: pos,
      negative_count: neg,
      neutral_count: Math.max(0, articles - pos - neg),
      article_count: articles,
      close_price: null,
    });
  }
  return data;
}

// ── Main Chart Component ──────────────────────────────────────────────────────
export default function SentimentChart({ ticker, days = 30 }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isMock, setIsMock] = useState(false);

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    setError('');

    api.getSentimentHistory(ticker, days)
      .then(res => {
        if (res.data && res.data.length > 0) {
          setData(res.data);
          setIsMock(false);
        } else {
          // No real history yet — show mock data with disclaimer
          setData(generateMockData(days));
          setIsMock(true);
        }
      })
      .catch(() => {
        setData(generateMockData(days));
        setIsMock(true);
      })
      .finally(() => setLoading(false));
  }, [ticker, days]);

  // Color the area based on latest score
  const latestScore = data[data.length - 1]?.sentiment_score ?? 0;
  const areaColor = latestScore > 0.1 ? '#4ade80' : latestScore < -0.1 ? '#f87171' : '#94a3b8';
  const areaFill = latestScore > 0.1
    ? 'url(#sentimentGradientPos)'
    : latestScore < -0.1
    ? 'url(#sentimentGradientNeg)'
    : 'url(#sentimentGradientNeu)';

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 220 }}>
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
          Sentiment Trend
          <span style={{
            marginLeft: 8,
            padding: '2px 8px',
            borderRadius: 100,
            fontSize: 11,
            background: latestScore > 0.1 ? 'rgba(74,222,128,0.1)' : latestScore < -0.1 ? 'rgba(248,113,113,0.1)' : 'rgba(148,163,184,0.1)',
            color: latestScore > 0.1 ? 'var(--green)' : latestScore < -0.1 ? 'var(--red)' : 'var(--text-secondary)',
            border: `1px solid ${latestScore > 0.1 ? 'rgba(74,222,128,0.2)' : latestScore < -0.1 ? 'rgba(248,113,113,0.2)' : 'rgba(148,163,184,0.2)'}`,
          }}>
            {latestScore > 0.1 ? '▲ Positive' : latestScore < -0.1 ? '▼ Negative' : '◆ Neutral'}
          </span>
        </div>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          {days}d · {data.length} data points
          {isMock && <span style={{ color: 'var(--gold)', marginLeft: 6 }}>· Preview (populates after ingestion)</span>}
        </span>
      </div>

      <ResponsiveContainer width="100%" height={200}>
        <ComposedChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="sentimentGradientPos" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#4ade80" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#4ade80" stopOpacity={0.02} />
            </linearGradient>
            <linearGradient id="sentimentGradientNeg" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#f87171" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#f87171" stopOpacity={0.02} />
            </linearGradient>
            <linearGradient id="sentimentGradientNeu" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#94a3b8" stopOpacity={0.2} />
              <stop offset="95%" stopColor="#94a3b8" stopOpacity={0.02} />
            </linearGradient>
          </defs>

          <CartesianGrid
            strokeDasharray="3 3"
            stroke="rgba(255,255,255,0.04)"
            vertical={false}
          />

          <XAxis
            dataKey="date"
            tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
            tickFormatter={d => {
              const parts = d.split('-');
              return `${parts[2]}/${parts[1]}`;
            }}
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
          />

          <YAxis
            domain={[-1, 1]}
            tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
            tickLine={false}
            axisLine={false}
            tickFormatter={v => v.toFixed(1)}
          />

          <Tooltip content={<CustomTooltip />} />

          {/* Zero reference line */}
          <ReferenceLine y={0} stroke="rgba(255,255,255,0.1)" strokeDasharray="4 4" />

          {/* Article volume as faint bars */}
          <Bar
            dataKey="article_count"
            fill="rgba(255,255,255,0.04)"
            yAxisId={0}
            // Scale bars to fit -1/+1 domain
            maxBarSize={12}
            radius={[2, 2, 0, 0]}
          />

          {/* Sentiment area */}
          <Area
            type="monotone"
            dataKey="sentiment_score"
            stroke={areaColor}
            strokeWidth={2}
            fill={areaFill}
            dot={false}
            activeDot={{ r: 4, fill: areaColor, strokeWidth: 0 }}
          />
        </ComposedChart>
      </ResponsiveContainer>

      {/* Article breakdown legend */}
      <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 11, justifyContent: 'flex-end' }}>
        <span style={{ color: 'var(--green)', display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--green)', display: 'inline-block' }} />
          Positive
        </span>
        <span style={{ color: 'var(--red)', display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--red)', display: 'inline-block' }} />
          Negative
        </span>
        <span style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--text-muted)', display: 'inline-block' }} />
          Neutral
        </span>
      </div>
    </div>
  );
}
