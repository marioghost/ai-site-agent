import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { getMe, login as apiLogin, logout as apiLogout, setAuthToken } from "../api/client";
import type { AuthUser, UserRole } from "../types";
import { resetEngineeringModeOff } from "../lib/engineeringModeStorage";

const TOKEN_KEY = "ai-site-agent-auth-token";

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (...roles: UserRole[]) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function readToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function storeToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
  setAuthToken(token);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(() => readToken());
  const [loading, setLoading] = useState(true);

  const bootstrap = useCallback(async (existingToken: string | null) => {
    if (!existingToken) {
      setUser(null);
      setLoading(false);
      return;
    }
    setAuthToken(existingToken);
    try {
      const me = await getMe();
      setUser(me);
    } catch {
      storeToken(null);
      setToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void bootstrap(readToken());
  }, [bootstrap]);

  const login = useCallback(async (username: string, password: string) => {
    const res = await apiLogin(username, password);
    storeToken(res.access_token);
    setToken(res.access_token);
    setUser(res.user);
  }, []);

  const logout = useCallback(async () => {
    try {
      if (token) await apiLogout();
    } catch {
      /* ignore */
    }
    resetEngineeringModeOff();
    storeToken(null);
    setToken(null);
    setUser(null);
  }, [token]);

  const hasRole = useCallback(
    (...roles: UserRole[]) => (user ? roles.includes(user.role) : false),
    [user]
  );

  const value = useMemo(
    () => ({ user, token, loading, login, logout, hasRole }),
    [user, token, loading, login, logout, hasRole]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function getStoredToken() {
  return readToken();
}
