"use client";

import { useEffect, useState } from "react";
import { KanbanBoard } from "@/components/KanbanBoard";
import { LoginForm } from "@/components/LoginForm";
import {
  ApiError,
  getSession,
  login,
  logout,
  type User,
} from "@/lib/api";

export default function Home() {
  const [user, setUser] = useState<User | null>();
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    getSession()
      .then(setUser)
      .catch((sessionError: unknown) => {
        if (sessionError instanceof ApiError && sessionError.status === 401) {
          setUser(null);
          return;
        }
        setError("Unable to connect to the server.");
        setUser(null);
      });
  }, []);

  const handleLogin = async (username: string, password: string) => {
    setError(null);
    setIsSubmitting(true);
    try {
      setUser(await login(username, password));
    } catch (loginError) {
      setError(
        loginError instanceof ApiError
          ? loginError.message
          : "Unable to connect to the server."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    setUser(null);
  };

  if (user === undefined) {
    return (
      <main className="grid min-h-screen place-items-center" aria-busy="true">
        <p className="text-sm font-semibold uppercase tracking-[0.25em] text-[var(--primary-blue)]">
          Loading workspace...
        </p>
      </main>
    );
  }

  if (!user) {
    return (
      <LoginForm
        error={error}
        isSubmitting={isSubmitting}
        onSubmit={handleLogin}
      />
    );
  }

  return (
    <KanbanBoard username={user.username} onLogout={handleLogout} />
  );
}
