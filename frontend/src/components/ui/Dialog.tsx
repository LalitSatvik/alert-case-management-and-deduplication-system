import type { ComponentPropsWithoutRef, ReactNode } from "react";
import * as RadixDialog from "@radix-ui/react-dialog";
import { cn } from "./cn";

export const Dialog = RadixDialog.Root;
export const DialogTrigger = RadixDialog.Trigger;
export const DialogClose = RadixDialog.Close;

export function DialogContent({
  className,
  title,
  description,
  children,
  width = "lg",
  ...rest
}: ComponentPropsWithoutRef<typeof RadixDialog.Content> & {
  title: string;
  description?: string;
  width?: "md" | "lg" | "xl";
}) {
  const w = { md: "max-w-md", lg: "max-w-2xl", xl: "max-w-4xl" }[width];
  return (
    <RadixDialog.Portal>
      <RadixDialog.Overlay className="dialog-overlay fixed inset-0 z-50 bg-[var(--overlay)]" />
      <RadixDialog.Content
        className={cn(
          "dialog-panel fixed left-1/2 top-1/2 z-50 flex max-h-[85vh] w-[92vw] -translate-x-1/2 -translate-y-1/2 flex-col",
          "rounded-lg border border-border bg-surface shadow-lg focus-visible:outline-none",
          w,
          className,
        )}
        {...rest}
      >
        <div className="flex items-start justify-between gap-4 border-b border-border px-4 py-3">
          <div className="min-w-0">
            <RadixDialog.Title className="text-md font-semibold text-ink">{title}</RadixDialog.Title>
            {description && (
              <RadixDialog.Description className="mt-0.5 text-xs text-ink-tertiary">
                {description}
              </RadixDialog.Description>
            )}
          </div>
          <RadixDialog.Close
            aria-label="Close"
            className="-mr-1 -mt-1 rounded-sm p-1 text-ink-tertiary hover:bg-surface-hover hover:text-ink"
          >
            <svg viewBox="0 0 14 14" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.75">
              <path d="M3 3l8 8M11 3l-8 8" strokeLinecap="round" />
            </svg>
          </RadixDialog.Close>
        </div>
        <div className="min-h-0 flex-1 overflow-auto">{children}</div>
      </RadixDialog.Content>
    </RadixDialog.Portal>
  );
}

export function DialogFooter({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center justify-end gap-2 border-t border-border px-4 py-3">
      {children}
    </div>
  );
}
