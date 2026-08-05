import React, { useState, useEffect, useRef } from 'react';
import { api } from '../lib/api';

// Curated list of popular Indian NSE stocks for instant autocomplete
const POPULAR_STOCKS = [
  { ticker: 'RELIANCE', name: 'Reliance Industries Ltd', exchange: 'NSE' },
  { ticker: 'TCS', name: 'Tata Consultancy Services Ltd', exchange: 'NSE' },
  { ticker: 'HDFCBANK', name: 'HDFC Bank Ltd', exchange: 'NSE' },
  { ticker: 'INFY', name: 'Infosys Ltd', exchange: 'NSE' },
  { ticker: 'ICICIBANK', name: 'ICICI Bank Ltd', exchange: 'NSE' },
  { ticker: 'TATAMOTORS', name: 'Tata Motors Ltd', exchange: 'NSE' },
  { ticker: 'ZOMATO', name: 'Zomato Ltd', exchange: 'NSE' },
  { ticker: 'PAYTM', name: 'One97 Communications Ltd (Paytm)', exchange: 'NSE' },
  { ticker: 'SWIGGY', name: 'Swiggy Ltd', exchange: 'NSE' },
  { ticker: 'BAJFINANCE', name: 'Bajaj Finance Ltd', exchange: 'NSE' },
  { ticker: 'HAL', name: 'Hindustan Aeronautics Ltd', exchange: 'NSE' },
  { ticker: 'TITAN', name: 'Titan Company Ltd', exchange: 'NSE' },
  { ticker: 'SUZLON', name: 'Suzlon Energy Ltd', exchange: 'NSE' },
  { ticker: 'IRFC', name: 'Indian Railway Finance Corp', exchange: 'NSE' },
  { ticker: 'HINDUNILVR', name: 'Hindustan Unilever Ltd (HUL)', exchange: 'NSE' },
  { ticker: 'ITC', name: 'ITC Ltd', exchange: 'NSE' },
  { ticker: 'AXISBANK', name: 'Axis Bank Ltd', exchange: 'NSE' },
  { ticker: 'KOTAKBANK', name: 'Kotak Mahindra Bank Ltd', exchange: 'NSE' },
  { ticker: 'LT', name: 'Larsen & Toubro Ltd', exchange: 'NSE' },
  { ticker: 'TATASTEEL', name: 'Tata Steel Ltd', exchange: 'NSE' },
  { ticker: 'MARUTI', name: 'Maruti Suzuki India Ltd', exchange: 'NSE' },
  { ticker: 'ADANIENT', name: 'Adani Enterprises Ltd', exchange: 'NSE' },
  { ticker: 'ADANIPORTS', name: 'Adani Ports & SEZ Ltd', exchange: 'NSE' },
  { ticker: 'BHARTIARTL', name: 'Bharti Airtel Ltd', exchange: 'NSE' },
  { ticker: 'M&M', name: 'Mahindra & Mahindra Ltd', exchange: 'NSE' },
  { ticker: 'SUNPHARMA', name: 'Sun Pharmaceutical Industries', exchange: 'NSE' },
];

export default function TickerSearch({ onFollow }) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const wrapperRef = useRef(null);

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Filter local & remote suggestions dynamically on query change
  useEffect(() => {
    const q = query.trim().toLowerCase();
    if (!q) {
      setSuggestions([]);
      setIsOpen(false);
      return;
    }

    // Filter instant local Nifty list
    const localMatches = POPULAR_STOCKS.filter(
      s => s.ticker.toLowerCase().includes(q) || s.name.toLowerCase().includes(q)
    );

    setSuggestions(localMatches.slice(0, 6));
    setIsOpen(true);
    setSelectedIndex(-1);

    // Debounced remote Yahoo Finance API search for long-tail stocks
    const timer = setTimeout(async () => {
      if (q.length >= 2) {
        try {
          const apiResults = await api.searchStocks(q);
          if (apiResults && apiResults.length > 0) {
            const formattedRemote = apiResults.map(r => ({
              ticker: r.ticker.replace('.NS', '').replace('.BO', ''),
              name: r.name || r.ticker,
              exchange: r.ticker.endsWith('.BO') ? 'BSE' : 'NSE',
            }));

            // Merge local + remote without duplicates
            const combined = [...localMatches];
            formattedRemote.forEach(rem => {
              if (!combined.some(c => c.ticker === rem.ticker)) {
                combined.push(rem);
              }
            });
            setSuggestions(combined.slice(0, 8));
          }
        } catch (err) {
          // ignore background search error
        }
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [query]);

  const handleSelectStock = async (tickerSymbol) => {
    if (!tickerSymbol) return;
    setLoading(true);
    setIsOpen(false);
    setError('');
    setSuccess('');
    try {
      const result = await api.followStock(tickerSymbol.toUpperCase());
      setSuccess(`✓ Now following ${result.stock.ticker} (${result.stock.name || 'NSE/BSE'}) — ingesting data in background...`);
      setQuery('');
      setSuggestions([]);
      if (onFollow) onFollow(result.stock);
      setTimeout(() => setSuccess(''), 5000);
    } catch (err) {
      setError(err.message || 'Failed to follow ticker');
      setTimeout(() => setError(''), 4000);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (!isOpen || suggestions.length === 0) {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleSelectStock(query);
      }
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => (prev < suggestions.length - 1 ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => (prev > 0 ? prev - 1 : suggestions.length - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (selectedIndex >= 0 && selectedIndex < suggestions.length) {
        handleSelectStock(suggestions[selectedIndex].ticker);
      } else {
        handleSelectStock(query);
      }
    } else if (e.key === 'Escape') {
      setIsOpen(false);
    }
  };

  return (
    <div style={{ padding: '16px 32px 8px' }}>
      <div ref={wrapperRef} style={{ position: 'relative', width: '100%', maxWidth: '700px' }}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (selectedIndex >= 0 && selectedIndex < suggestions.length) {
              handleSelectStock(suggestions[selectedIndex].ticker);
            } else {
              handleSelectStock(query);
            }
          }}
          style={{ display: 'flex', gap: '10px' }}
        >
          <div className="input-wrapper" style={{ flex: 1, position: 'relative' }}>
            <span style={{ position: 'absolute', left: '14px', color: 'var(--text-muted)', fontSize: '15px' }}>🔍</span>
            <input
              className="input"
              placeholder="Search stock by name or symbol (e.g. Reliance, TCS, HDFC, Zomato...)"
              value={query}
              onChange={e => setQuery(e.target.value)}
              onFocus={() => query.trim() && setIsOpen(true)}
              onKeyDown={handleKeyDown}
              disabled={loading}
              style={{
                paddingLeft: '38px',
                fontFamily: 'Inter, system-ui, sans-serif',
                fontSize: '14px',
              }}
            />
          </div>
          <button
            className="btn btn-primary"
            type="submit"
            disabled={loading || !query.trim()}
          >
            {loading ? <span className="spinner" /> : '+ Follow'}
          </button>
        </form>

        {/* Groww-style Dynamic Floating Dropdown */}
        {isOpen && suggestions.length > 0 && (
          <div
            style={{
              position: 'absolute',
              top: 'calc(100% + 6px)',
              left: 0,
              right: 0,
              background: '#0d1330',
              border: '1px solid rgba(0, 212, 170, 0.3)',
              borderRadius: '12px',
              boxShadow: '0 12px 36px rgba(0,0,0,0.6), 0 0 20px rgba(0,212,170,0.15)',
              zIndex: 100,
              overflow: 'hidden',
              backdropFilter: 'blur(16px)',
            }}
          >
            <div style={{ padding: '8px 12px 4px', fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', letterSpacing: '0.5px', textTransform: 'uppercase' }}>
              Suggestions ({suggestions.length})
            </div>
            {suggestions.map((item, idx) => {
              const isSelected = idx === selectedIndex;
              return (
                <div
                  key={item.ticker}
                  onClick={() => handleSelectStock(item.ticker)}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  style={{
                    padding: '10px 14px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    cursor: 'pointer',
                    background: isSelected ? 'rgba(0, 212, 170, 0.15)' : 'transparent',
                    borderLeft: isSelected ? '3px solid var(--teal)' : '3px solid transparent',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div
                      style={{
                        width: '32px',
                        height: '32px',
                        borderRadius: '8px',
                        background: 'linear-gradient(135deg, rgba(0,212,170,0.2), rgba(94,60,255,0.2))',
                        border: '1px solid rgba(255,255,255,0.1)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontWeight: 700,
                        fontSize: '12px',
                        color: 'var(--teal)',
                        fontFamily: 'JetBrains Mono, monospace',
                      }}
                    >
                      {item.ticker.slice(0, 2)}
                    </div>
                    <div>
                      <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'JetBrains Mono, monospace' }}>
                        {item.ticker}
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                        {item.name}
                      </div>
                    </div>
                  </div>
                  <span
                    style={{
                      fontSize: '10px',
                      fontWeight: 700,
                      padding: '2px 7px',
                      borderRadius: '4px',
                      background: 'rgba(255,255,255,0.06)',
                      color: 'var(--text-muted)',
                      border: '1px solid rgba(255,255,255,0.08)',
                    }}
                  >
                    {item.exchange || 'NSE'}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {success && <div className="toast success" style={{ position: 'relative', bottom: 'auto', right: 'auto', margin: '8px 0 0' }}>{success}</div>}
      {error   && <div className="toast error"   style={{ position: 'relative', bottom: 'auto', right: 'auto', margin: '8px 0 0' }}>{error}</div>}
    </div>
  );
}

