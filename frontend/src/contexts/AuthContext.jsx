/* eslint-disable react-refresh/only-export-components */
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const AuthContext = createContext(null);

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
};

const STORAGE_KEYS = {
  access: "access_token",
  refresh: "refresh_token",
  user: "auth_user",
};

const readStored = () => {
  try {
    const access = localStorage.getItem(STORAGE_KEYS.access);
    const refresh = localStorage.getItem(STORAGE_KEYS.refresh);
    const userRaw = localStorage.getItem(STORAGE_KEYS.user);
    const user = userRaw ? JSON.parse(userRaw) : null;
    return { access, refresh, user };
  } catch {
    return { access: null, refresh: null, user: null };
  }
};

const persist = ({ access, refresh, user }) => {
  if (access) localStorage.setItem(STORAGE_KEYS.access, access);
  if (refresh) localStorage.setItem(STORAGE_KEYS.refresh, refresh);
  if (user) localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(user));
};

const clearStorage = () => {
  localStorage.removeItem(STORAGE_KEYS.access);
  localStorage.removeItem(STORAGE_KEYS.refresh);
  localStorage.removeItem(STORAGE_KEYS.user);
};

export const AuthProvider = ({ children }) => {
  const [{ access, refresh, user }, setAuthState] = useState(readStored);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const setSession = useCallback((next) => {
    setAuthState((prev) => {
      const updated = {
        access: next.access ?? prev.access ?? null,
        refresh: next.refresh ?? prev.refresh ?? null,
        user: next.user ?? prev.user ?? null,
      };
      persist(updated);
      return updated;
    });
  }, []);

  const logout = useCallback(() => {
    clearStorage();
    setAuthState({ access: null, refresh: null, user: null });
  }, []);

  const login = useCallback(
    async (email, password) => {
      setLoading(true);
      setError(null);
      try {
        const resp = await fetch(`${API_BASE_URL}/api/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        if (!resp.ok) {
          const err = await resp.json().catch(() => null);
          throw new Error(err?.detail || "Login failed");
        }
        const data = await resp.json();
        setSession({
          access: data.access_token,
          refresh: data.refresh_token,
          user: data.user || { email },
        });
        return data;
      } catch (e) {
        setError(e.message || "Login failed");
        throw e;
      } finally {
        setLoading(false);
      }
    },
    [setSession],
  );

  const register = useCallback(
    async (email, password) => {
      setLoading(true);
      setError(null);
      try {
        const resp = await fetch(`${API_BASE_URL}/api/auth/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        if (!resp.ok) {
          const err = await resp.json().catch(() => null);
          throw new Error(err?.detail || "Registration failed");
        }
        // Optionally auto-login after register
        await login(email, password);
        return true;
      } catch (e) {
        setError(e.message || "Registration failed");
        throw e;
      } finally {
        setLoading(false);
      }
    },
    [login],
  );

  const refreshTokens = useCallback(async () => {
    if (!refresh) return null;
    try {
      const resp = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (!resp.ok) return null;
      const data = await resp.json();
      if (data.access_token) {
        setSession({
          access: data.access_token,
          refresh: data.refresh_token || refresh,
        });
        return data.access_token;
      }
    } catch {
      /* ignore */
    }
    return null;
  }, [refresh, setSession]);

  const authFetch = useCallback(
    async (url, options = {}) => {
      const opts = { ...options, headers: { ...(options.headers || {}) } };
      if (access) {
        opts.headers.Authorization = `Bearer ${access}`;
      }
      let resp = await fetch(url, opts);
      if (resp.status === 401) {
        const newAccess = await refreshTokens();
        if (newAccess) {
          opts.headers.Authorization = `Bearer ${newAccess}`;
          resp = await fetch(url, opts);
        } else {
          logout();
        }
      }
      return resp;
    },
    [access, logout, refreshTokens],
  );

  useEffect(() => {
    // keep state in sync with localStorage on mount
    setAuthState(readStored());
  }, []);

  const value = useMemo(
    () => ({
      user,
      accessToken: access,
      refreshToken: refresh,
      loading,
      error,
      login,
      register,
      logout,
      authFetch,
      setUser: (nextUser) => setSession({ user: nextUser }),
    }),
    [
      user,
      access,
      refresh,
      loading,
      error,
      login,
      register,
      logout,
      authFetch,
      setSession,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
