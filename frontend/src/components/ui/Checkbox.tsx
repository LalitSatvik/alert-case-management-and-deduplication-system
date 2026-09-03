import * as RadixCheckbox from "@radix-ui/react-checkbox";
import { cn } from "./cn";

export function Checkbox({
  checked,
  onCheckedChange,
  "aria-label": ariaLabel,
  className,
}: {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  "aria-label": string;
  className?: string;
}) {
  return (
    <RadixCheckbox.Root
      checked={checked}
      onCheckedChange={(v) => onCheckedChange(v === true)}
      aria-label={ariaLabel}
      className={cn(
        "flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-[3px] border border-border-strong bg-surface transition-colors",
        "data-[state=checked]:border-accent data-[state=checked]:bg-accent data-[state=checked]:text-accent-fg",
        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-focus",
        className,
      )}
    >
      <RadixCheckbox.Indicator>
        <svg viewBox="0 0 12 12" className="h-2.5 w-2.5" fill="none" stroke="currentColor" strokeWidth="2.5">
          <path d="M2.5 6.5 5 9l4.5-5.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </RadixCheckbox.Indicator>
    </RadixCheckbox.Root>
  );
}
