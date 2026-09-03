import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "./AuthContext";

function Probe() {
  const { principal, booting, hasRole } = useAuth();
  return (
    <div>
      <span>{booting ? "booting" : "ready"}</span>
      <span>{principal ? `roles:${principal.roles.join(",")}` : "anon"}</span>
      <span>{hasRole("analyst") ? "is-analyst" : "not-analyst"}</span>
    </div>
  );
}

beforeEach(() => {
  localStorage.clear();
});

it("rehydrates the session from a stored refresh token on mount", async () => {
  localStorage.setItem("acms.refresh_token", "stored-rt");
  const jwt =
    "h." + btoa(JSON.stringify({ sub: "42", roles: ["analyst"] })) + ".s";
  global.fetch = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ access_token: jwt }), { status: 200 }),
  );

  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );

  // Starts blocked on the rehydration attempt.
  expect(screen.getByText("booting")).toBeInTheDocument();

  await waitFor(() => expect(screen.getByText("ready")).toBeInTheDocument());
  expect(screen.getByText("roles:analyst")).toBeInTheDocument();
  expect(screen.getByText("is-analyst")).toBeInTheDocument();

  const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls;
  expect(String(calls[0][0])).toContain("/auth/refresh");
  // Rehydration must not go through login().
  expect(calls.every(([u]) => !String(u).includes("/auth/token"))).toBe(true);
});

it("does not block the first render when there is no stored token", () => {
  global.fetch = vi.fn();
  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
  expect(screen.getByText("ready")).toBeInTheDocument();
  expect(screen.getByText("anon")).toBeInTheDocument();
  expect(global.fetch).not.toHaveBeenCalled();
});
