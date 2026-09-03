import {
  forwardRef,
  type InputHTMLAttributes,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
  type ReactNode,
} from "react";
import { cn } from "./cn";

const CONTROL =
  "min-h-control w-full rounded-lg border border-border bg-surface px-3 text-sm text-ink shadow-xs " +
  "transition-colors placeholder:text-ink-muted hover:border-border-strong " +
  "focus-visible:border-ink focus-visible:outline-none disabled:opacity-40";

export const TextInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function TextInput({ className, type = "text", ...rest }, ref) {
    return <input ref={ref} type={type} className={cn(CONTROL, className)} {...rest} />;
  },
);

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...rest }, ref) {
    return (
      <select ref={ref} className={cn(CONTROL, "cursor-pointer", className)} {...rest}>
        {children}
      </select>
    );
  },
);

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...rest }, ref) {
    return (
      <textarea
        ref={ref}
        className={cn(CONTROL, "min-h-[auto] py-2 leading-relaxed", className)}
        {...rest}
      />
    );
  },
);

/** Field / section label. */
export function FieldLabel({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span className={cn("text-xs font-medium text-ink-secondary", className)}>{children}</span>
  );
}
