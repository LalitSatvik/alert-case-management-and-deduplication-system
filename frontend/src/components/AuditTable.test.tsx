import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import * as auth from "../auth/AuthContext";
import { AuditTable } from "./AuditTable";

vi.spyOn(auth, "useAuth").mockReturnValue({
  token: "t",
  principal: { email: "a@b.c", roles: ["analyst"] },
  booting: false,
  hasRole: () => true,
} as unknown as auth.AuthValue);

const ENTRIES = [
  { seq: 1, action: "case.created", actor_id: "u1", actor_role: "system", created_at: "2026-08-30T00:00:00Z" },
];

it("shows a neutral chain pill until a JSON export reports chain_verified", async () => {
  global.fetch = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ chain_verified: true, events: [] }), { status: 200 }),
  );
  render(<AuditTable caseId="1" entries={ENTRIES} />);

  expect(screen.getByText("Chain not checked")).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: /export json/i }));

  await waitFor(() => expect(screen.getByText("Chain verified")).toBeInTheDocument());
});

it("downloads the HTML export instead of opening it same-origin", async () => {
  global.fetch = vi.fn().mockResolvedValue(
    new Response("<!doctype html><body>audit</body>", {
      status: 200,
      headers: { "Content-Type": "text/html" },
    }),
  );
  const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
  URL.createObjectURL = vi.fn(() => "blob:mock");
  URL.revokeObjectURL = vi.fn();

  const clickSpy = vi.fn();
  const realCreate = document.createElement.bind(document);
  const createSpy = vi
    .spyOn(document, "createElement")
    .mockImplementation((tag: string) => {
      const el = realCreate(tag) as HTMLElement;
      if (tag === "a") el.click = clickSpy;
      return el;
    });

  render(<AuditTable caseId="7" entries={ENTRIES} />);
  await userEvent.click(screen.getByRole("button", { name: /export html/i }));

  await waitFor(() => expect(clickSpy).toHaveBeenCalled());
  expect(openSpy).not.toHaveBeenCalled();

  createSpy.mockRestore();
  openSpy.mockRestore();
});
