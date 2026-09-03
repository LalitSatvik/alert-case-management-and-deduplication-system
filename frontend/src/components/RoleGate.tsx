import type { ReactNode } from "react";
import { useAuth } from "../auth/AuthContext";
import type { Role } from "../api/types";

export function RoleGate({ allow, children }: { allow: Role[]; children: ReactNode }) {
  const { hasRole } = useAuth();
  return hasRole(...allow) ? <>{children}</> : null;
}
