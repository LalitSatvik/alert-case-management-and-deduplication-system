import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { CaseListPage } from "./CaseListPage";
import { vi } from "vitest";
import * as auth from "../auth/AuthContext";

function wrap(ui: React.ReactNode) {
  return (
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

function Loc() {
  return <span data-testid="loc">{useLocation().pathname}</span>;
}

const STATS = {
  total: 1,
  by_status: { Open: 1 },
  unassigned: 1,
  high_risk: 0,
  high_risk_threshold: 90,
  avg_risk: 80,
};

function routedFetch(caseItems: (url: string) => unknown[]) {
  return vi.fn((url: string) => {
    const u = String(url);
    let body: unknown;
    if (u.includes("/cases/stats")) body = STATS;
    else if (u.includes("/users")) body = [];
    else if (u.includes("/cases")) body = { items: caseItems(u), next_cursor: null };
    else body = {};
    return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
  });
}

const CASE_1 = {
  id: "1",
  human_ref: "CASE-1",
  status: "Open",
  assignee_email: null,
  risk_score: 80,
  alert_count: 3,
  created_at: "2026-08-30T00:00:00Z",
  oldest_alert_event_time: "2026-08-29T00:00:00Z",
};

beforeEach(() => {
  vi.spyOn(auth, "useAuth").mockReturnValue({
    token: "t",
    principal: { email: "a@b.c", roles: ["analyst"] },
    hasRole: () => true,
  } as never);
});

it("renders cases from the API and filters by status", async () => {
  const fetchMock = routedFetch((u) => (u.includes("status=In+Progress") ? [] : [CASE_1]));
  global.fetch = fetchMock as never;

  render(wrap(<CaseListPage />));
  await waitFor(() => expect(screen.getByText("CASE-1")).toBeInTheDocument());

  await userEvent.click(screen.getByRole("button", { name: /in progress/i }));
  await waitFor(() => expect(screen.queryByText("CASE-1")).not.toBeInTheDocument());

  const caseListCalls = fetchMock.mock.calls
    .map((c) => String(c[0]))
    .filter((u) => u.includes("/cases") && !u.includes("/cases/stats"));
  expect(caseListCalls.at(-1)).toContain("status=In+Progress");
});

it("navigates to the case detail route when a row is activated", async () => {
  global.fetch = routedFetch(() => [{ ...CASE_1, id: "abc", human_ref: "CASE-9" }]) as never;

  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <Routes>
          <Route
            path="/"
            element={
              <>
                <CaseListPage />
                <Loc />
              </>
            }
          />
          <Route path="/cases/:id" element={<Loc />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  await waitFor(() => expect(screen.getByText("CASE-9")).toBeInTheDocument());
  await userEvent.click(screen.getByText("CASE-9"));
  await waitFor(() => expect(screen.getByTestId("loc")).toHaveTextContent("/cases/abc"));
});
