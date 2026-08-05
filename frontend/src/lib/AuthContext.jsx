import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../lib/api';
import { getToken, setToken, clearToken, isTokenExpired } from '../lib/auth';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getToken();
    if (token && !isTokenExpired(token)) {
      api.getMe()
        .then(setUser)
        .catch(() => clearToken())
        .finally(() => setLoading(false));
    } else {
      clearToken();
      setLoading(false);
    }
  }, []);

  const login = (token) => {
    setToken(token);
    return api.getMe().then(setUser);
  };

  const logout = () => {
    clearToken();
    setUser(null);
    window.location.href = '/login';
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
