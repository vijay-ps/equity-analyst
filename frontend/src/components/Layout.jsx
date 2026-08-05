import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../lib/AuthContext';

const NAV = [
  { to: '/dashboard', icon: '📊', label: 'Dashboard' },
  { to: '/chat',      icon: '💬', label: 'AI Chat' },
];


export default function Layout({ children }) {
  const { user, logout } = useAuth();

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="logo">
          <div className="logo-icon">📈</div>
          <div>
            <div className="logo-text">Equity AI</div>
            <div className="logo-sub">NSE · BSE AI Chat</div>
          </div>
        </div>

        <nav className="nav-section">
          <div className="nav-label">Navigation</div>
          {NAV.map(({ to, icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
            >
              <span className="icon">{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-bottom">
          {user && (
            <div className="user-chip">
              <div className="avatar">
                {user.picture
                  ? <img src={user.picture} alt={user.name} />
                  : user.name?.[0]?.toUpperCase()}
              </div>
              <div className="user-info">
                <div className="user-name">{user.name}</div>
                <div className="user-email">{user.email}</div>
              </div>
              <button
                className="btn btn-ghost btn-sm btn-icon"
                onClick={logout}
                title="Logout"
              >
                ↩
              </button>
            </div>
          )}
        </div>
      </aside>

      <main className="main-content">
        {children}
      </main>
    </div>
  );
}
