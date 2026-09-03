import { cn } from "./cn";

/** Black track, lime thumb when on — the switch style from the references. */
export function Toggle({
  checked,
  onChange,
  "aria-label": ariaLabel,
  disabled,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  "aria-label": string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors disabled:opacity-40",
        checked ? "bg-primary" : "bg-neutral-border",
      )}
    >
      <span
        className={cn(
          "inline-block h-4 w-4 rounded-full shadow-sm transition-transform",
          checked ? "translate-x-6 bg-accent" : "translate-x-1 bg-surface",
        )}
      />
    </button>
  );
}
