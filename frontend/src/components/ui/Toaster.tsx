import { Toaster as SonnerToaster } from "sonner";

/**
 * Mounted once in AppShell. Styling is bound to the console tokens so toasts
 * match every other surface in both themes.
 */
export function Toaster() {
  return (
    <SonnerToaster
      position="bottom-right"
      gap={8}
      toastOptions={{
        classNames: {
          toast:
            "!rounded-md !border !border-border !bg-surface-raised !text-ink !shadow-md !font-sans",
          description: "!text-ink-tertiary",
          actionButton: "!bg-accent !text-accent-fg",
          cancelButton: "!bg-surface-hover !text-ink-secondary",
          error: "!border-danger-border",
          success: "!border-success-border",
        },
      }}
    />
  );
}

export { toast } from "sonner";
