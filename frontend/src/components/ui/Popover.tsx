import type { ComponentPropsWithoutRef } from "react";
import * as RadixPopover from "@radix-ui/react-popover";
import { cn } from "./cn";

export const Popover = RadixPopover.Root;
export const PopoverTrigger = RadixPopover.Trigger;
export const PopoverAnchor = RadixPopover.Anchor;

const CONTENT =
  "pop-surface z-50 rounded-md border border-border bg-surface-raised p-3 shadow-md " +
  "focus-visible:outline-none";

export function PopoverContent({
  className,
  sideOffset = 6,
  align = "start",
  children,
  ...rest
}: ComponentPropsWithoutRef<typeof RadixPopover.Content>) {
  return (
    <RadixPopover.Portal>
      <RadixPopover.Content
        sideOffset={sideOffset}
        align={align}
        className={cn(CONTENT, className)}
        {...rest}
      >
        {children}
      </RadixPopover.Content>
    </RadixPopover.Portal>
  );
}
