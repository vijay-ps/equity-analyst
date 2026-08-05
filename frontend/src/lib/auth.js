export function getToken() {
  return localStorage.getItem('equity_token');
}

export function setToken(token) {
  localStorage.setItem('equity_token', token);
}

export function clearToken() {
  localStorage.removeItem('equity_token');
}

export function isAuthenticated() {
  return Boolean(getToken());
}

// Parse JWT payload (no verification — server handles that)
export function parseJwt(token) {
  try {
    const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(window.atob(base64));
  } catch {
    return null;
  }
}

export function isTokenExpired(token) {
  const payload = parseJwt(token);
  if (!payload?.exp) return true;
  return Date.now() / 1000 > payload.exp;
}
