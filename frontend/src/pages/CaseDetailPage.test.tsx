import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { CaseDetailPage } from "./CaseDetailPage";
import { vi } from "vitest";
import * as auth from "../auth/AuthContext";

const CASE = {
  id: "1", human_ref: "CASE-1", status: "Open", disposition: null, assignee_email: null, risk_score: 80, alert_count: 2,
  created_at: "2026-08-30T00:00:00Z",
  alerts: [
    { id: "a1", external_alert_id: "T1", amount: "500", currency: "USD", raw_payload: {}, grouping: { method: "deterministic", matched_rule_ids: ["same-txn-dispute"], similarity_score: null, feature_contributions: {}, engine_version: "1.0.0", config_hash: "h" } },
    { id: "a2", external_alert_id: "T2", amount: "500", currency: "USD", raw_payload: {}, grouping: { method: "similarity", matched_rule_ids: [], similarity_score: 0.81, feature_contributions: { name: 0.95, amount: 0.9 }, engine_version: "1.0.0", config_hash: "h" } },
  ],
  notes: [], timeline: [{ seq: 1, action: "case.created", actor: "system", created_at: "2026-08-30T00:00:00Z" }],
};

function wrap() {
  return (
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/cases/1"]}>
        <Routes><Route path="/cases/:id" element={<CaseDetailPage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

it("shows grouping rationale and hides mutations for readonly", async () => {
  vi.spyOn(auth, "useAuth").mockReturnValue({ token: "t", principal: { email: "r@b.c", roles: ["readonly"] }, hasRole: (r: string) => r === "readonly" } as any);
  global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(CASE), { status: 200 }));
  render(wrap());
  await waitFor(() => expect(screen.getByText("CASE-1")).toBeInTheDocument());
  expect(screen.getByText(/same-txn-dispute/)).toBeInTheDocument();
  expect(screen.getByText(/0\.81/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /move to in progress/i })).not.toBeInTheDocument();
});

it("offers legal transitions for an analyst", async () => {
  vi.spyOn(auth, "useAuth").mockReturnValue({ token: "t", principal: { email: "a@b.c", roles: ["analyst"] }, hasRole: () => true } as any);
  global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(CASE), { status: 200 }));
  render(wrap());
  await waitFor(() => expect(screen.getByText("CASE-1")).toBeInTheDocument());
  expect(screen.getByRole("button", { name: /move to in progress/i })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /close/i })).not.toBeInTheDocument(); // Closed not legal from Open
});
