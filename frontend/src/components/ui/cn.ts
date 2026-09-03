export type ClassValue = string | number | false | null | undefined;

/** Join truthy class fragments. No tailwind-merge — callers keep class sets disjoint. */
export function cn(...parts: ClassValue[]): string {
  return parts.filter(Boolean).join(" ");
}
