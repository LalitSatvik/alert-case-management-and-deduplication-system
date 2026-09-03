import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { CaseListPage } from "./CaseListPage";
import { vi } from "vitest";
import * as auth from "../auth/AuthContext";

function wrap(ui: React.ReactNode) {
  return <QueryClientProvider client={new QueryClient()}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>;
}

function Loc() {
  return <span data-testid="loc">{useLocation().pathname}</span>;
}

beforeEach(() => {
  vi.spyOn(auth, "useAuth").mockReturnValue({ token: "t", principal: { email: "a@b.c", roles: ["analyst"] }, hasRole: () => true } as any);
});

it("renders cases from the API and filters by status", async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ id: "1", human_ref: "CASE-1", status: "Open", assignee_email: null, risk_score: 80, alert_count: 3, created_at: "2026-08-30T00:00:00Z", oldest_alert_event_time: "2026-08-29T00:00:00Z" }], next_cursor: null }), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ items: [], next_cursor: null }), { status: 200 }));
  global.fetch = fetchMock;
  render(wrap(<CaseListPage />));
  await waitFor(() => expect(screen.getByText("CASE-1")).toBeInTheDocument());
  await userEvent.click(screen.getByRole("button", { name: /in progress/i }));
  await waitFor(() => expect(screen.queryByText("CASE-1")).not.toBeInTheDocument());
  const lastUrl = fetchMock.mock.calls.at(-1)![0] as string;
  expect(lastUrl).toContain("status=In+Progress");
});

it("navigates to the case detail route via the case-ref link", async () => {
  global.fetch = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ items: [{ id: "abc", human_ref: "CASE-9", status: "Open", assignee_email: null, risk_score: 10, alert_count: 1, created_at: "2026-08-30T00:00:00Z", oldest_alert_event_time: null }], next_cursor: null }), { status: 200 }),
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<><CaseListPage /><Loc /></>} />
          <Route path="/cases/:id" element={<Loc />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  await waitFor(() => expect(screen.getByText("CASE-9")).toBeInTheDocument());
  // The ref is a real <a>, not a role="button" row.
  const link = screen.getByRole("link", { name: "CASE-9" });
  await userEvent.click(link);
  await waitFor(() => expect(screen.getByTestId("loc")).toHaveTextContent("/cases/abc"));
});
