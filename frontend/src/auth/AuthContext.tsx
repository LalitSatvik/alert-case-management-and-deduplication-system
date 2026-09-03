import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { apiFetch, setRefreshHandler } from "../api/client";
import { queryClient } from "../api/queryClient";
import type { Role } from "../api/types";

export interface Principal {
  email: string;
  roles: Role[];
  id?: string;
}

export interface AuthValue {
  principal: Principal | null;
  token: string | null;
  /** True until the one-shot session rehydration on mount has settled. */
  booting: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  hasRole: (...r: Role[]) => boolean;
}

const REFRESH_KEY = "acms.refresh_token";
const AuthContext = createContext<AuthValue | null>(null);

function readRefresh(): string | null {
  try {
    return localStorage.getItem(REFRESH_KEY);
  } catch {
    return null;
  }
}

function writeRefresh(value: string | null): void {
  try {
    if (value == null) localStorage.removeItem(REFRESH_KEY);
    else localStorage.setItem(REFRESH_KEY, value);
  } catch {
    // Private-window / storage disabled — tolerate silently.
  }
}

/** Tolerant decode of a JWT payload — handles non-padded / URL-safe base64. */
export function decodeToken(token: string): { roles: Role[]; sub?: string } {
  try {
    let part = token.split(".")[1] ?? "";
    part = part.replace(/-/g, "+").replace(/_/g, "/");
    while (part.length % 4 !== 0) part += "=";
    const payload = JSON.parse(atob(part)) as { roles?: unknown; sub?: unknown };
    return {
      roles: Array.isArray(payload.roles) ? (payload.roles as Role[]) : [],
      sub: typeof payload.sub === "string" ? payload.sub : undefined,
    };
  } catch {
    return { roles: [] };
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [principal, setPrincipal] = useState<Principal | null>(null);
  // No stored refresh token => nothing to rehydrate, so don't block the first render.
  const [booting, setBooting] = useState<boolean>(() => readRefresh() != null);
  const emailRef = useRef<string | null>(null);

  const doRefresh = useCallback(async (): Promise<string | null> => {
    const rt = readRefresh();
    if (!rt) {
      setToken(null);
      setPrincipal(null);
      return null;
    }
    try {
      const res = await apiFetch<{ access_token: string }>("/auth/refresh", {
        body: { refresh_token: rt },
        skipRefresh: true,
      });
      const { roles, sub } = decodeToken(res.access_token);
      setToken(res.access_token);
      // After a cold reload there is no `/me` endpoint and the login email is
      // deliberately not persisted, so `email` may be "" — roles/id come from
      // the JWT and that is what gates the UI.
      setPrincipal((p) => ({ email: p?.email ?? emailRef.current ?? "", roles, id: sub }));
      return res.access_token;
    } catch {
      setToken(null);
      setPrincipal(null);
      writeRefresh(null);
      return null;
    }
  }, []);

  useEffect(() => {
    setRefreshHandler(doRefresh);
    return () => setRefreshHandler(null);
  }, [doRefresh]);

  useEffect(() => {
    let cancelled = false;
    if (readRefresh() == null) return;
    doRefresh().finally(() => {
      if (!cancelled) setBooting(false);
    });
    return () => {
      cancelled = true;
    };
  }, [doRefresh]);

  const value = useMemo<AuthValue>(
    () => ({
      principal,
      token,
      booting,
      async login(email, password) {
        const res = await apiFetch<{ access_token: string; refresh_token: string }>("/auth/token", {
          body: { email, password },
          // A 401 here means bad credentials — it must not fall through to
          // /auth/refresh (there is no session yet to refresh).
          skipRefresh: true,
        });
        const { roles, sub } = decodeToken(res.access_token);
        emailRef.current = email;
        writeRefresh(res.refresh_token);
        setToken(res.access_token);
        setPrincipal({ email, roles, id: sub });
      },
      logout() {
        emailRef.current = null;
        setToken(null);
        setPrincipal(null);
        writeRefresh(null);
        // Drop every cached query so the next user (or the login screen) never
        // sees the previous session's cases / audit data.
        queryClient.clear();
      },
      hasRole(...r) {
        return principal !== null && r.some((role) => principal.roles.includes(role));
      },
    }),
    [principal, token, booting],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
