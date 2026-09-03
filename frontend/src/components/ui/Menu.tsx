import type { ComponentPropsWithoutRef, ReactNode } from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { cn } from "./cn";

export const Menu = DropdownMenu.Root;
export const MenuTrigger = DropdownMenu.Trigger;

const CONTENT =
  "pop-surface z-50 min-w-[10rem] overflow-hidden rounded-md border border-border bg-surface-raised p-1 shadow-md";

export function MenuContent({
  className,
  sideOffset = 6,
  align = "start",
  children,
  ...rest
}: ComponentPropsWithoutRef<typeof DropdownMenu.Content>) {
  return (
    <DropdownMenu.Portal>
      <DropdownMenu.Content
        sideOffset={sideOffset}
        align={align}
        className={cn(CONTENT, className)}
        {...rest}
      >
        {children}
      </DropdownMenu.Content>
    </DropdownMenu.Portal>
  );
}

const ITEM =
  "flex cursor-pointer select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm text-ink-secondary outline-none " +
  "data-[highlighted]:bg-surface-hover data-[highlighted]:text-ink data-[disabled]:pointer-events-none data-[disabled]:opacity-40";

export function MenuItem({
  className,
  danger = false,
  ...rest
}: ComponentPropsWithoutRef<typeof DropdownMenu.Item> & { danger?: boolean }) {
  return (
    <DropdownMenu.Item
      className={cn(ITEM, danger && "text-ink-danger data-[highlighted]:text-ink-danger", className)}
      {...rest}
    />
  );
}

export function MenuLabel({ children }: { children: ReactNode }) {
  return (
    <DropdownMenu.Label className="px-2 py-1 text-2xs font-semibold uppercase tracking-wider text-ink-tertiary">
      {children}
    </DropdownMenu.Label>
  );
}

export function MenuSeparator() {
  return <DropdownMenu.Separator className="my-1 h-px bg-border" />;
}
