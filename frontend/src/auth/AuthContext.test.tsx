import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthProvider, useAuth } from "./AuthContext";
import { vi } from "vitest";

function Probe() {
  const { principal, login, hasRole } = useAuth();
  return (
    <div>
      <button onClick={() => login("a@b.c", "pw")}>login</button>
      <span>{principal?.email ?? "anon"}</span>
      <span>{hasRole("admin") ? "is-admin" : "not-admin"}</span>
    </div>
  );
}

it("stores principal after login", async () => {
  global.fetch = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ access_token: "hdr." + btoa(JSON.stringify({ sub: "1", roles: ["analyst"] })) + ".sig", refresh_token: "r", token_type: "bearer" }), { status: 200 }),
  );
  render(<AuthProvider><Probe /></AuthProvider>);
  await userEvent.click(screen.getByText("login"));
  await waitFor(() => expect(screen.getByText("a@b.c")).toBeInTheDocument());
  expect(screen.getByText("not-admin")).toBeInTheDocument();
});
