import { createContext, useContext, useState, useEffect } from 'react';
import { setHasSession } from '../session';
import { apiUrl } from '../config';

const noop = () => {};
export const AuthContext = createContext({
  user: null,
  loading: false,
  authError: null,
  login: noop,
  logout: noop,
});

// Backend/database may still be booting when the tab opens right after start.
// A network error or 5xx must not be mistaken for "logged out": retry quietly.
const AUTH_RETRY_DELAYS_MS = [1000, 2000, 4000, 8000];

async function parseJsonResponse(res) {
  const contentType = res.headers.get('content-type');
  if (!contentType?.includes('application/json')) {
    throw new Error(`Server returned non-JSON response (${res.status})`);
  }
  return res.json();
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    let timer = null;

    const attempt = async (index) => {
      let loggedOut = false;
      try {
        const res = await fetch(apiUrl('/auth/me'), { credentials: 'include' });
        if (cancelled) return;
        if (res.ok) {
          const profile = await parseJsonResponse(res);
          if (cancelled) return;
          setHasSession(true);
          setAuthError(null);
          setUser(profile);
          setLoading(false);
          return;
        }
        if (res.status === 403) {
          // Wrong Stepik account: keep the backend detail so the user is not
          // silently returned to the login button in an endless loop.
          let detail = 'Этот аккаунт Stepik не является владельцем панели';
          try {
            const body = await res.json();
            if (body?.detail) detail = body.detail;
          } catch {
            // non-JSON body — keep generic message
          }
          if (cancelled) return;
          setHasSession(false);
          setAuthError(detail);
          loggedOut = true;
        } else if (res.status === 401) {
          setHasSession(false);
          setAuthError(null);
          loggedOut = true;
        }
      } catch {
        // network error — backend not ready yet
      }

      if (cancelled) return;
      if (loggedOut || index >= AUTH_RETRY_DELAYS_MS.length) {
        setUser(null);
        setLoading(false);
        return;
      }
      timer = setTimeout(() => attempt(index + 1), AUTH_RETRY_DELAYS_MS[index]);
    };

    attempt(0);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, []);

  const login = () => {
    window.location.href = apiUrl('/auth/login');
  };

  const logout = async () => {
    // Сначала выходим в интерфейсе: сеть/бэкенд могут тормозить.
    setUser(null);
    setHasSession(false);
    setAuthError(null);
    try {
      await fetch(apiUrl('/auth/logout'), { method: 'POST', credentials: 'include' });
    } catch {
      // ignore
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, authError, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
