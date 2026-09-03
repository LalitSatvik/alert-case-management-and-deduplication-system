import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { SettingsMenu } from "./SettingsMenu";
import { Menu, MenuContent, MenuItem, MenuLabel, MenuSeparator, MenuTrigger } from "./ui/Menu";
import { Tooltip, TooltipProvider } from "./ui/Tooltip";
import { Toaster } from "./ui/Toaster";
import { cn } from "./ui/cn";

const railBtn =
  "flex h-9 w-9 items-center justify-center rounded-md text-ink-tertiary transition-colors hover:bg-surface-hover hover:text-ink focus-visible:outline-none";

function CasesIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-[18px] w-[18px]" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d="M3 5.5h14M3 10h14M3 14.5h14" strokeLinecap="round" />
    </svg>
  );
}

function GearIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-[18px] w-[18px]" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="10" cy="10" r="2.6" />
      <path d="M10 2.5v2M10 15.5v2M17.5 10h-2M4.5 10h-2M15.3 4.7l-1.4 1.4M6.1 13.9l-1.4 1.4M15.3 15.3l-1.4-1.4M6.1 6.1 4.7 4.7" strokeLinecap="round" />
    </svg>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { principal, logout } = useAuth();
  const initials = (principal?.email ?? "?").slice(0, 2).toUpperCase();

  return (
    <TooltipProvider>
      <div className="flex h-screen overflow-hidden bg-bg text-ink">
        <a
          href="#main"
          className="sr-only focus-visible:not-sr-only focus-visible:fixed focus-visible:left-16 focus-visible:top-3 focus-visible:z-50 focus-visible:rounded-md focus-visible:bg-surface focus-visible:px-3 focus-visible:py-2 focus-visible:text-sm focus-visible:font-medium focus-visible:text-ink focus-visible:shadow-lg"
        >
          Skip to content
        </a>

        <nav
          aria-label="Primary"
          className="flex w-[52px] shrink-0 flex-col items-center gap-1 border-r border-border bg-surface-sunken py-3"
        >
          <NavLink
            to="/cases"
            aria-label="ACMS — Investigator Console"
            className="mb-2 flex h-9 w-9 items-center justify-center rounded-md font-mono text-xs font-bold tracking-tight text-ink"
          >
            AC
          </NavLink>

          <Tooltip content="Cases" side="right">
            <NavLink
              to="/cases"
              className={({ isActive }) =>
                cn(
                  railBtn,
                  isActive && "bg-surface-hover text-accent [box-shadow:inset_2px_0_0_var(--accent)]",
                )
              }
            >
              <CasesIcon />
            </NavLink>
          </Tooltip>

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
                className="flex h-9 w-9 items-center justify-center rounded-md bg-surface-hover font-mono text-2xs font-semibold text-ink-secondary transition-colors hover:text-ink focus-visible:outline-none"
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

        <main id="main" tabIndex={-1} className="flex min-w-0 flex-1 flex-col overflow-hidden outline-none">
          {children}
        </main>

        <Toaster />
      </div>
    </TooltipProvider>
  );
}
