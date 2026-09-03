import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { cn } from "./cn";

export interface Crumb {
  label: string;
  to?: string;
}

/** Full-height page frame; header strip stays sticky. */
export function Page({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("flex h-full min-h-0 flex-col bg-surface", className)}>{children}</div>;
}

export function Breadcrumbs({ items }: { items: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-xs text-ink-tertiary">
      {items.map((c, i) => (
        <span key={i} className="flex items-center gap-1.5">
          {i > 0 && <span aria-hidden="true">/</span>}
          {c.to ? (
            <Link to={c.to} className="hover:text-ink">
              {c.label}
            </Link>
          ) : (
            <span className={i === items.length - 1 ? "text-ink" : undefined}>{c.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}

export function PageHeader({
  title,
  description,
  breadcrumbs,
  children,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  breadcrumbs?: Crumb[];
  children?: ReactNode;
  className?: string;
}) {
  return (
    <header
      className={cn(
        "sticky top-0 z-20 flex flex-col gap-1 border-b border-border bg-bg-header px-6 py-3 backdrop-blur-header supports-[backdrop-filter]:bg-bg-header",
        className,
      )}
    >
      {breadcrumbs && <Breadcrumbs items={breadcrumbs} />}
      <div className="flex items-center gap-3">
        <div className="min-w-0">
          <h1 className="text-lg font-semibold text-ink">{title}</h1>
          {description && <p className="text-xs text-ink-tertiary">{description}</p>}
        </div>
        {children && <div className="ml-auto flex items-center gap-2">{children}</div>}
      </div>
    </header>
  );
}

export function PageBody({
  children,
  className,
  pad = true,
}: {
  children: ReactNode;
  className?: string;
  pad?: boolean;
}) {
  return (
    <div
      className={cn("min-h-0 flex-1 overflow-y-auto bg-surface-sunken", pad && "px-6 py-5", className)}
    >
      {children}
    </div>
  );
}
