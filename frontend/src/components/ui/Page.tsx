import type { ReactNode } from "react";
import { cn } from "./cn";

/** Full-height page frame: a sticky header strip over an independently scrolling body. */
export function Page({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("flex h-full min-h-0 flex-col", className)}>{children}</div>;
}

export function PageHeader({
  title,
  children,
  className,
}: {
  title: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <header
      className={cn(
        "sticky top-0 z-20 flex items-center gap-3 border-b border-border bg-bg-header px-4 py-2.5 backdrop-blur-header supports-[backdrop-filter]:bg-bg-header",
        className,
      )}
    >
      <h1 className="text-md font-semibold text-ink">{title}</h1>
      {children}
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
    <div className={cn("min-h-0 flex-1 overflow-y-auto", pad && "px-4 py-4", className)}>
      {children}
    </div>
  );
}
