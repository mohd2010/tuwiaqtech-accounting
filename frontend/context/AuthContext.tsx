"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useRouter } from "@/i18n/navigation";
import Cookies from "js-cookie";
import api from "@/lib/api";

interface User {
  id: string;
  username: string;
  role: string;
  permissions: string[];
}

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const loadUser = useCallback(async () => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setLoading(false);
      return;
    }
    try {
      const res = await api.get<User>("/api/v1/users/me");
      setUser({
        ...res.data,
        permissions: res.data.permissions ?? [],
      });
    } catch {
      localStorage.removeItem("access_token");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const login = useCallback(
    async (username: string, password: string) => {
      const params = new URLSearchParams();
      params.append("username", username);
      params.append("password", password);

      const res = await api.post<{ access_token: string }>(
        "/api/v1/auth/login/access-token",
        params,
        { headers: { "Content-Type": "application/x-www-form-urlencoded" } },
      );

      const token = res.data.access_token;
      localStorage.setItem("access_token", token);
      Cookies.set("access_token", token, { expires: 7 });
      await loadUser();
      router.push("/dashboard");
    },
    [loadUser, router],
  );

  const logout = useCallback(() => {
    localStorage.removeItem("access_token");
    Cookies.remove("access_token");
    setUser(null);
    router.push("/login");
  }, [router]);

  const value = useMemo(
    () => ({ user, loading, login, logout }),
    [user, loading, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
