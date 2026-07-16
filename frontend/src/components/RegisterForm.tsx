"use client";

import { useState, type FormEvent } from "react";

type RegisterFormProps = {
  error: string | null;
  isSubmitting: boolean;
  onSubmit: (username: string, password: string) => Promise<void>;
  onSwitchToLogin: () => void;
};

export const RegisterForm = ({
  error,
  isSubmitting,
  onSubmit,
  onSwitchToLogin,
}: RegisterFormProps) => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onSubmit(username, password);
  };

  return (
    <main className="relative grid min-h-screen place-items-center overflow-hidden px-6 py-12">
      <div className="pointer-events-none absolute left-0 top-0 h-[520px] w-[520px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.28)_0%,_rgba(32,157,215,0.06)_55%,_transparent_72%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[560px] w-[560px] translate-x-1/3 translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.2)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

      <section className="relative w-full max-w-md overflow-hidden rounded-[32px] border border-[var(--stroke)] bg-white p-8 shadow-[var(--shadow)] sm:p-10">
        <div className="absolute inset-x-0 top-0 h-2 bg-[var(--accent-yellow)]" />
        <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--primary-blue)]">
          Project workspace
        </p>
        <h1 className="mt-4 font-display text-4xl font-semibold text-[var(--navy-dark)]">
          Create your account
        </h1>
        <p className="mt-3 text-sm leading-6 text-[var(--gray-text)]">
          Get your own board with five ready-made columns.
        </p>

        <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
          <label className="block text-sm font-semibold text-[var(--navy-dark)]">
            Username
            <input
              autoComplete="username"
              className="mt-2 w-full rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-4 py-3 font-normal outline-none transition focus:border-[var(--primary-blue)] focus:bg-white"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              minLength={3}
              maxLength={32}
              pattern="[a-zA-Z0-9_\-]+"
              title="3-32 characters: letters, numbers, underscores, or dashes"
              required
            />
          </label>
          <p className="-mt-3 text-xs font-normal text-[var(--gray-text)]">
            3-32 characters: letters, numbers, underscores, or dashes.
          </p>
          <label className="block text-sm font-semibold text-[var(--navy-dark)]">
            Password
            <input
              autoComplete="new-password"
              className="mt-2 w-full rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-4 py-3 font-normal outline-none transition focus:border-[var(--primary-blue)] focus:bg-white"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={8}
              required
            />
          </label>
          <p className="-mt-3 text-xs font-normal text-[var(--gray-text)]">
            At least 8 characters.
          </p>

          {error ? (
            <p className="rounded-2xl bg-red-50 px-4 py-3 text-sm font-medium text-red-700" role="alert">
              {error}
            </p>
          ) : null}

          <button
            className="w-full rounded-full bg-[var(--secondary-purple)] px-5 py-3 text-sm font-semibold uppercase tracking-[0.18em] text-white transition hover:brightness-110 disabled:cursor-wait disabled:opacity-60"
            disabled={isSubmitting}
            type="submit"
          >
            {isSubmitting ? "Creating account..." : "Create account"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-[var(--gray-text)]">
          Already have an account?{" "}
          <button
            className="font-semibold text-[var(--primary-blue)] hover:underline"
            onClick={onSwitchToLogin}
            type="button"
          >
            Sign in
          </button>
        </p>
      </section>
    </main>
  );
};
