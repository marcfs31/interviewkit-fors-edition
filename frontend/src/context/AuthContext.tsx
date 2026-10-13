"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
  ReactNode,
} from "react";
import { getMyStats } from "@/services/sessionService";
import { getMyProfile } from "@/services/authService";
import { logoutUser } from "@/services/authService";
import { setOnUnauthorized } from "@/services/httpClient";
import type { StatsResponse } from "@/services/sessionService";

export type StatsStatus = "loading" | "ok" | "error";

interface AuthContextValue {
  user: string | null;
  // null means "unknown": still loading or the last fetch failed (see statsStatus)
  stats: StatsResponse | null;
  statsStatus: StatsStatus;
  initialized: boolean;
  login: (logUser: string, token?: string) => void;
  loginFromOAuth: () => Promise<void>;
  logout: () => Promise<void>;
  refreshStats: () => Promise<void>;
  updateUser: (newName: string) => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<string | null>(null);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [statsStatus, setStatsStatus] = useState<StatsStatus>("loading");
  const [initialized, setInitialized] = useState(false);
  const refreshingRef = useRef(false);
  // Marcamos un login en curso para que un 401 transitorio (p. ej. el
  // refreshStats inicial con token stale) no limpie el token nuevo que
  // loginFromOAuth acaba de escribir en localStorage.
  const loggingInRef = useRef(false);

  useEffect(() => {
    setOnUnauthorized(() => {
      if (loggingInRef.current) return;
      localStorage.removeItem("user");
      localStorage.removeItem("access_token");
      setUser(null);
      setStats(null);
      setStatsStatus("loading");
    });
  }, []);

  const refreshStats = useCallback(async () => {
    if (refreshingRef.current) return;
    refreshingRef.current = true;
    // Keep showing the last good value while re-fetching; only a first load
    // or a retry after an error goes back to "loading".
    setStatsStatus((prev) => (prev === "ok" ? prev : "loading"));
    try {
      setStats(await getMyStats());
      setStatsStatus("ok");
    } catch {
      setStats(null);
      setStatsStatus("error");
    } finally {
      refreshingRef.current = false;
    }
  }, []);

  useEffect(() => {
    const savedUser = localStorage.getItem("user");
    const savedToken = localStorage.getItem("access_token");

    const restore = async () => {
      if (savedUser && savedToken) {
        setUser(savedUser);
        refreshStats();
        setInitialized(true);
      } else if (savedUser && !savedToken) {
        // Login OAuth previo: no hay access_token en localStorage (vive en
        // la cookie httpOnly), asi que confirmamos la sesion via el perfil.
        loggingInRef.current = true;
        try {
          const profile = await getMyProfile();
          const name = profile.name || profile.email || "User";
          localStorage.setItem("user", name);
          setUser(name);
          refreshStats();
        } catch {
          localStorage.removeItem("user");
        } finally {
          loggingInRef.current = false;
          setInitialized(true);
        }
      } else {
        setInitialized(true);
      }
    };

    restore();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function login(logUser: string, token?: string) {
    const name = logUser || "User";
    if (token) localStorage.setItem("access_token", token);
    localStorage.setItem("user", name);
    setUser(name);
    refreshStats();
  }

  async function loginFromOAuth() {
    // El JWT llega en una cookie httpOnly (set_access_cookies en el backend);
    // aqui solo confirmamos la identidad via el perfil, sin token en localStorage.
    loggingInRef.current = true;
    try {
      const profile = await getMyProfile();
      const name = profile.name || profile.email || "User";
      localStorage.setItem("user", name);
      setUser(name);
      await refreshStats();
    } finally {
      loggingInRef.current = false;
    }
  }

  function updateUser(newName: string) {
    localStorage.setItem("user", newName);
    setUser(newName);
  }

  async function logout() {
    try {
      await logoutUser();
    } catch {}
    localStorage.removeItem("user");
    localStorage.removeItem("access_token");
    setUser(null);
    setStats(null);
    setStatsStatus("loading");
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        stats,
        statsStatus,
        initialized,
        login,
        loginFromOAuth,
        logout,
        refreshStats,
        updateUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (context === undefined) {
    throw new Error("useAuth should be used inside AuthProvider");
  }

  return context;
}
