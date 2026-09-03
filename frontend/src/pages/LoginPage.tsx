import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";

const field =
  "mt-1.5 min-h-control w-full rounded-md border border-border bg-surface px-3 text-sm text-ink shadow-xs transition-colors placeholder:text-ink-muted hover:border-border-strong focus-visible:border-accent";

export function LoginPage() {
  const { login, principal } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (principal) navigate("/cases", { replace: true });
  }, [principal, navigate]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      navigate("/cases", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? (err.detail ?? "Login failed") : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="evidence-grid relative flex min-h-screen items-center justify-center px-4 text-ink">
      <form
        onSubmit={onSubmit}
        className="u-enter-soft w-full max-w-sm space-y-5 rounded-xl border border-border bg-surface p-7 shadow-lg"
      >
        <div className="space-y-1.5">
          <h1 className="font-mono text-lg font-semibold tracking-[0.14em] text-ink">ACMS</h1>
          <p className="text-sm text-ink-tertiary">Sign in to the investigator console</p>
        </div>

        <label className="block text-sm">
          <span className="text-2xs font-semibold uppercase tracking-wider text-ink-tertiary">
            Email
          </span>
          <input
            type="email"
            name="email"
            autoComplete="username"
            spellCheck={false}
            autoCapitalize="none"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className={`${field} font-mono`}
          />
        </label>

        <label className="block text-sm">
          <span className="text-2xs font-semibold uppercase tracking-wider text-ink-tertiary">
            Password
          </span>
          <input
            type="password"
            name="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className={field}
          />
        </label>

        {error && (
          <p
            role="alert"
            className="rounded-md border border-danger-border bg-danger-subtle px-3 py-2 text-sm text-danger-subtle-fg"
          >
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="inline-flex min-h-control w-full items-center justify-center rounded-md bg-accent px-3 text-sm font-medium text-accent-fg shadow-xs transition-colors hover:bg-accent-hover disabled:opacity-40"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
