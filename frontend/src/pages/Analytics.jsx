import React, { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import SentimentChart from '../components/SentimentChart';
import { api } from '../lib/api';
import {
  RadarChart, PolarGrid, PolarAngleAxis, Radar,
  ResponsiveContainer, Tooltip,
} from 'recharts';

const DAY_OPTIONS = [7, 14, 30, 60];

function SentimentMeter({ score }) {
  const pct = ((score + 1) / 2) * 100; // convert -1..1 to 0..100
  const color = score > 0.1 ? 'var(--green)' : score < -0.1 ? 'var(--red)' : 'var(--text-secondary)';
  const label = score > 0.1 ? 'Bullish' : score < -0.1 ? 'Bearish' : 'Neutral';

  return (
    <div style={{ textAlign: 'center', padding: '12px 0' }}>
      {/* Arc meter using conic-gradient */}
      <div style={{ position: 'relative', width: 80, height: 80, margin: '0 auto 8px' }}>
        <svg viewBox="0 0 80 80" width="80" height="80">
          {/* Track */}
          <circle cx="40" cy="40" r="30" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="8" />
          {/* Fill */}
          <circle
            cx="40" cy="40" r="30"
            fill="none"
            stroke={color}
            strokeWidth="8"
            strokeDasharray={`${(pct / 100) * 188.5} 188.5`}
            strokeLinecap="round"
            transform="rotate(-90 40 40)"
            style={{ transition: 'stroke-dasharray 0.6s ease, stroke 0.3s ease' }}
          />
        </svg>
        <div style={{
          position: 'absolute', top: '50%', left: '50%',
          transform: 'translate(-50%,-50%)',
          fontSize: 14, fontWeight: 800,
          color, fontFamily: 'JetBrains Mono, monospace',
        }}>
          {score >= 0 ? '+' : ''}{score.toFixed(2)}
        </div>
      </div>
      <div style={{ fontSize: 12, fontWeight: 600, color }}>{label}</div>
    </div>
  );
}

function SchedulerStatus() {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '10px 14px',
      background: 'rgba(0,212,170,0.06)',
      border: '1px solid rgba(0,212,170,0.2)',
      borderRadius: 8,
      fontSize: 12,
      color: 'var(--text-secondary)',
    }}>
      <span style={{
        width: 8, height: 8, borderRadius: '50%',
        background: 'var(--teal)',
        boxShadow: '0 0 6px var(--teal)',
        display: 'inline-block',
        animation: 'pulse 2s ease-in-out infinite',
      }} />
      <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }`}</style>
      <span>
        <strong style={{ color: 'var(--teal)' }}>Scheduler active</strong> — auto-refreshes every 6h · daily sentiment snapshot at 15:35 IST
      </span>
    </div>
  );
}

export default function Analytics() {
  const [stocks, setStocks] = useState([]);
  const [selected, setSelected] = useState(null);
  const [days, setDays] = useState(30);
  const [refreshing, setRefreshing] = useState('');
  const [toast, setToast] = useState('');
  const [latestScores, setLatestScores] = useState({});

  useEffect(() => {
    api.getFollowed().then(data => {
      setStocks(data);
      if (data.length > 0) setSelected(data[0].ticker);
    });
  }, []);

  // Build radar data from all stocks' current sentiment
  const radarData = stocks
    .filter(s => s.sentiment_score != null)
    .map(s => ({
      stock: s.ticker,
      score: parseFloat(((s.sentiment_score + 1) * 50).toFixed(1)), // 0–100
      fullMark: 100,
    }));

  const handleRefresh = async (ticker) => {
    setRefreshing(ticker);
    try {
      const res = await api.refreshStock(ticker);
      setToast(res.message);
      setTimeout(() => setToast(''), 4000);
    } catch (e) {
      setToast(`Failed to refresh ${ticker}`);
      setTimeout(() => setToast(''), 3000);
    } finally {
      setRefreshing('');
    }
  };

  const selectedStock = stocks.find(s => s.ticker === selected);

  return (
    <Layout>
      <div className="page-header">
        <h1 className="page-title">Sentiment Analytics</h1>
        <p className="page-subtitle">
          Daily news sentiment trends per ticker — updated automatically every 6 hours.
        </p>
        <div style={{ marginTop: 12 }}>
          <SchedulerStatus />
        </div>
      </div>

      <div style={{ padding: '20px 32px', display: 'flex', flexDirection: 'column', gap: 20 }}>

        {stocks.length === 0 ? (
          <div className="empty-state">
            <div className="icon">📊</div>
            <h3>No stocks followed yet</h3>
            <p>Go to Dashboard and follow some NSE/BSE tickers to see sentiment charts here.</p>
          </div>
        ) : (
          <>
            {/* ── Top: Radar + Stock Selector ──────────────────────────── */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

              {/* Radar overview */}
              <div className="card">
                <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 12, color: 'var(--text-primary)' }}>
                  Portfolio Sentiment Radar
                </div>
                {radarData.length >= 3 ? (
                  <ResponsiveContainer width="100%" height={220}>
                    <RadarChart data={radarData}>
                      <PolarGrid stroke="rgba(255,255,255,0.06)" />
                      <PolarAngleAxis
                        dataKey="stock"
                        tick={{ fontSize: 11, fill: 'var(--text-muted)', fontFamily: 'JetBrains Mono' }}
                      />
                      <Tooltip
                        formatter={(v) => [`${((v / 50) - 1).toFixed(2)}`, 'Sentiment']}
                        contentStyle={{
                          background: 'rgba(13,18,48,0.95)',
                          border: '1px solid var(--border)',
                          borderRadius: 8,
                          fontSize: 12,
                        }}
                      />
                      <Radar
                        dataKey="score"
                        stroke="var(--teal)"
                        fill="var(--teal)"
                        fillOpacity={0.12}
                        strokeWidth={2}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {stocks.map(s => (
                      <div key={s.ticker} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <span style={{ fontFamily: 'JetBrains Mono', fontSize: 12, fontWeight: 700, width: 100 }}>
                          {s.ticker}
                        </span>
                        <div style={{ flex: 1, height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{
                            height: '100%',
                            width: `${((s.sentiment_score || 0) + 1) / 2 * 100}%`,
                            background: (s.sentiment_score || 0) > 0.1 ? 'var(--green)' : (s.sentiment_score || 0) < -0.1 ? 'var(--red)' : 'var(--text-muted)',
                            borderRadius: 3,
                            transition: 'width 0.6s ease',
                          }} />
                        </div>
                        <span style={{ fontSize: 11, fontFamily: 'JetBrains Mono', color: 'var(--text-secondary)', width: 40, textAlign: 'right' }}>
                          {(s.sentiment_score || 0) >= 0 ? '+' : ''}{(s.sentiment_score || 0).toFixed(2)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Stock list with meters */}
              <div className="card">
                <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 12, color: 'var(--text-primary)' }}>
                  Current Sentiment
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))', gap: 12 }}>
                  {stocks.map(s => (
                    <button
                      key={s.ticker}
                      onClick={() => setSelected(s.ticker)}
                      style={{
                        background: selected === s.ticker ? 'var(--teal-glow)' : 'transparent',
                        border: `1px solid ${selected === s.ticker ? 'rgba(0,212,170,0.3)' : 'var(--border)'}`,
                        borderRadius: 10,
                        padding: 8,
                        cursor: 'pointer',
                        transition: 'all 0.18s',
                      }}
                    >
                      <div style={{ fontSize: 11, fontFamily: 'JetBrains Mono', fontWeight: 700, color: selected === s.ticker ? 'var(--teal)' : 'var(--text-primary)', marginBottom: 4 }}>
                        {s.ticker}
                      </div>
                      <SentimentMeter score={s.sentiment_score || 0} />
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* ── Bottom: Trend Chart ───────────────────────────────────── */}
            {selected && (
              <div className="card">
                {/* Chart header */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span style={{ fontFamily: 'JetBrains Mono', fontSize: 20, fontWeight: 800 }}>{selected}</span>
                    <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      {selectedStock?.name || ''}
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    {/* Day range toggle */}
                    <div style={{ display: 'flex', background: 'rgba(255,255,255,0.04)', borderRadius: 6, border: '1px solid var(--border)', overflow: 'hidden' }}>
                      {DAY_OPTIONS.map(d => (
                        <button
                          key={d}
                          onClick={() => setDays(d)}
                          style={{
                            padding: '5px 10px',
                            fontSize: 11,
                            fontWeight: 600,
                            border: 'none',
                            background: days === d ? 'var(--teal-glow)' : 'transparent',
                            color: days === d ? 'var(--teal)' : 'var(--text-muted)',
                            cursor: 'pointer',
                            transition: 'all 0.15s',
                          }}
                        >
                          {d}d
                        </button>
                      ))}
                    </div>

                    {/* Manual refresh */}
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => handleRefresh(selected)}
                      disabled={!!refreshing}
                      style={{ fontSize: 12, gap: 6 }}
                    >
                      {refreshing === selected ? <span className="spinner" style={{ width: 12, height: 12 }} /> : '↻'}
                      Refresh now
                    </button>
                  </div>
                </div>

                <SentimentChart ticker={selected} days={days} />

                {/* Stock ticker row */}
                <div style={{ display: 'flex', gap: 8, marginTop: 16, flexWrap: 'wrap' }}>
                  {stocks.map(s => (
                    <button
                      key={s.ticker}
                      className={`btn btn-ghost btn-sm ${selected === s.ticker ? 'active' : ''}`}
                      style={{
                        fontSize: 11,
                        fontFamily: 'JetBrains Mono',
                        background: selected === s.ticker ? 'var(--teal-glow)' : undefined,
                        color: selected === s.ticker ? 'var(--teal)' : undefined,
                        borderColor: selected === s.ticker ? 'rgba(0,212,170,0.3)' : undefined,
                      }}
                      onClick={() => setSelected(s.ticker)}
                    >
                      {s.ticker}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Toast */}
      {toast && <div className="toast success">{toast}</div>}
    </Layout>
  );
}
