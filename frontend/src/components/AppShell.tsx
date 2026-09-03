import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { SettingsMenu } from "./SettingsMenu";
import { Menu, MenuContent, MenuItem, MenuLabel, MenuSeparator, MenuTrigger } from "./ui/Menu";
import { TooltipProvider } from "./ui/Tooltip";
import { Toaster } from "./ui/Toaster";
import { cn } from "./ui/cn";

const railBtn =
  "flex h-9 w-9 items-center justify-center rounded-full text-ink-tertiary transition-colors hover:bg-surface-hover hover:text-ink focus-visible:outline-none";

function CasesIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-[18px] w-[18px]" fill="none" stroke="currentColor" strokeWidth="1.6">
      <rect x="3" y="4" width="14" height="12" rx="2.5" />
      <path d="M3 8.5h14" strokeLinecap="round" />
    </svg>
  );
}

function GearIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-[18px] w-[18px]" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="10" cy="10" r="2.6" />
      <path
        d="M10 2.5v2M10 15.5v2M17.5 10h-2M4.5 10h-2M15.3 4.7l-1.4 1.4M6.1 13.9l-1.4 1.4M15.3 15.3l-1.4-1.4M6.1 6.1 4.7 4.7"
        strokeLinecap="round"
      />
    </svg>
  );
}

function BellIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-[18px] w-[18px]" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d="M6 8a4 4 0 1 1 8 0c0 3 1.2 4.2 1.8 4.8.3.3.1.9-.3.9H4.5c-.4 0-.6-.6-.3-.9C4.8 12.2 6 11 6 8Z" />
      <path d="M8.5 16a1.6 1.6 0 0 0 3 0" strokeLinecap="round" />
    </svg>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { principal, logout } = useAuth();
  const initials = (principal?.email || "?").slice(0, 2).toUpperCase();
  const role = principal?.roles?.includes("admin")
    ? "Admin"
    : principal?.roles?.includes("readonly")
      ? "Auditor"
      : "Analyst";

  return (
    <TooltipProvider>
      <div className="flex h-screen overflow-hidden bg-bg p-3 text-ink">
        <a
          href="#main"
          className="sr-only focus-visible:not-sr-only focus-visible:fixed focus-visible:left-20 focus-visible:top-4 focus-visible:z-50 focus-visible:rounded-lg focus-visible:bg-surface focus-visible:px-3 focus-visible:py-2 focus-visible:text-sm focus-visible:font-medium focus-visible:text-ink focus-visible:shadow-lg"
        >
          Skip to content
        </a>

        <nav
          aria-label="Primary"
          className="mr-3 flex w-16 shrink-0 flex-col items-center gap-1.5 rounded-2xl border border-border bg-surface py-3 shadow-xs"
        >
          <NavLink
            to="/cases"
            aria-label="ACMS — Investigator Console"
            className="mb-1 flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-sm font-bold text-primary-fg"
          >
            A
          </NavLink>

          <NavLink
            to="/cases"
            aria-label="Cases"
            className={({ isActive }) =>
              cn(
                railBtn,
                isActive && "bg-primary text-primary-fg hover:bg-primary hover:text-primary-fg",
              )
            }
          >
            <CasesIcon />
          </NavLink>

          <div className="flex-1" />

          <SettingsMenu
            trigger={
              <button type="button" aria-label="Display settings" className={railBtn}>
                <GearIcon />
              </button>
            }
          />

          <Menu>
            <MenuTrigger asChild>
              <button
                type="button"
                aria-label="Account"
                title={principal?.email ?? undefined}
                className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-full bg-surface-sunken text-2xs font-bold text-ink-secondary transition-colors hover:text-ink focus-visible:outline-none"
              >
                {initials}
              </button>
            </MenuTrigger>
            <MenuContent side="right" align="end">
              {principal?.email && <MenuLabel>{principal.email}</MenuLabel>}
              <MenuSeparator />
              <MenuItem danger onSelect={() => logout()}>
                Log out
              </MenuItem>
            </MenuContent>
          </Menu>
        </nav>

        <div className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-sm">
          <div className="flex items-center justify-end gap-3 border-b border-border px-6 py-2.5">
            <button
              type="button"
              aria-label="Notifications"
              className="flex h-9 w-9 items-center justify-center rounded-full border border-border text-ink-tertiary transition-colors hover:text-ink"
            >
              <BellIcon />
            </button>
            <Menu>
              <MenuTrigger asChild>
                <button
                  type="button"
                  className="flex items-center gap-2.5 rounded-full py-1 pl-1 pr-2 transition-colors hover:bg-surface-hover"
                >
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-sunken text-2xs font-bold text-ink-secondary">
                    {initials}
                  </span>
                  <span className="hidden text-left leading-tight sm:block">
                    <span className="block text-sm font-medium text-ink">
                      {principal?.email?.split("@")[0] ?? "User"}
                    </span>
                    <span className="block text-2xs text-ink-tertiary">{role}</span>
                  </span>
                </button>
              </MenuTrigger>
              <MenuContent align="end">
                {principal?.email && <MenuLabel>{principal.email}</MenuLabel>}
                <MenuSeparator />
                <MenuItem danger onSelect={() => logout()}>
                  Log out
                </MenuItem>
              </MenuContent>
            </Menu>
          </div>

          <main id="main" tabIndex={-1} className="flex min-h-0 flex-1 flex-col overflow-hidden outline-none">
            {children}
          </main>
        </div>

        <Toaster />
      </div>
    </TooltipProvider>
  );
}
