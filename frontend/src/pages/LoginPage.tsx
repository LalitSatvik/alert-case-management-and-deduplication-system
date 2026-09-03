import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";
import { Button } from "../components/ui/Button";
import { TextInput, FieldLabel } from "../components/ui/Field";

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
        className="u-enter-soft w-full max-w-sm space-y-5 rounded-lg border border-border border-t-2 border-t-accent bg-surface p-6 shadow-md"
      >
        <div className="space-y-1">
          <h1 className="font-mono text-sm font-bold uppercase tracking-[0.22em] text-ink">ACMS</h1>
          <p className="text-xs text-ink-tertiary">Investigator console — sign in</p>
        </div>

        <label className="block">
          <FieldLabel>Email</FieldLabel>
          <TextInput
            type="email"
            name="email"
            autoComplete="username"
            spellCheck={false}
            autoCapitalize="none"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="mt-1 font-mono"
          />
        </label>

        <label className="block">
          <FieldLabel>Password</FieldLabel>
          <TextInput
            type="password"
            name="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="mt-1"
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

        <Button type="submit" variant="primary" disabled={busy} className="w-full">
          {busy ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </div>
  );
}
