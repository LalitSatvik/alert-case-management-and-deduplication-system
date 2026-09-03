import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function AppShell({ children }: { children: ReactNode }) {
  const { principal, logout } = useAuth();
  return (
    <div className="min-h-screen bg-bg text-ink">
      <a
        href="#main"
        className="sr-only focus-visible:not-sr-only focus-visible:fixed focus-visible:left-4 focus-visible:top-4 focus-visible:z-50 focus-visible:rounded-md focus-visible:bg-surface focus-visible:px-3 focus-visible:py-2 focus-visible:text-sm focus-visible:font-medium focus-visible:text-ink focus-visible:shadow-lg"
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-30 border-b border-border bg-bg-header backdrop-blur-header supports-[backdrop-filter]:bg-bg-header">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-3">
          <Link
            to="/cases"
            className="group flex items-baseline gap-2 rounded-sm text-sm"
            aria-label="ACMS — go to cases"
          >
            <span className="font-mono text-[0.9375rem] font-semibold tracking-[0.14em] text-ink">
              ACMS
            </span>
            <span className="hidden text-xs text-ink-tertiary transition-colors group-hover:text-ink-secondary sm:inline">
              Investigator Console
            </span>
          </Link>
          <div className="flex items-center gap-3 text-sm">
            {principal && (
              <span className="hidden max-w-[16rem] truncate rounded-full bg-surface-sunken px-2.5 py-1 font-mono text-xs text-ink-secondary sm:inline">
                {principal.email}
              </span>
            )}
            <button
              type="button"
              onClick={logout}
              className="inline-flex min-h-control items-center rounded-md border border-border bg-surface px-3 text-xs font-medium text-ink-secondary shadow-xs hover:border-border-strong hover:text-ink"
            >
              Log out
            </button>
          </div>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="mx-auto max-w-6xl px-6 py-8 outline-none">
        {children}
      </main>
    </div>
  );
}
