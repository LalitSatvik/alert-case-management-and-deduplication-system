import { apiFetch } from "./client";
import type { UserOut } from "./types";

/** Active users, ordered by email — for the assignee picker. */
export function listUsers(token: string | null): Promise<UserOut[]> {
  return apiFetch<UserOut[]>("/users", { token });
}
