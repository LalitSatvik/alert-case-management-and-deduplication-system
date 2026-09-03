import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Timeline } from "./Timeline";
import type { TimelineEntry } from "../api/types";

const entries: TimelineEntry[] = [
  {
    seq: 3,
    action: "case.transitioned",
    actor_id: "u1",
    actor_role: "analyst",
    created_at: "2026-08-30T10:00:05Z",
    before: { status: "Open" },
    after: { status: "In Progress" },
  },
  {
    seq: 2,
    action: "case.alert_linked",
    actor_role: "system",
    created_at: "2026-08-30T10:00:00.100Z",
    before: {},
    after: { method: "deterministic", alert_id: "alert-abc" },
  },
  {
    seq: 1,
    action: "case.alert_linked",
    actor_role: "system",
    created_at: "2026-08-30T10:00:00.200Z",
    before: {},
    after: { method: "deterministic", alert_id: "alert-def" },
  },
];

it("clusters same-second alert links into one node", () => {
  render(<Timeline entries={entries} />);
  expect(screen.getByText(/2 × case\.alert_linked/)).toBeInTheDocument();
  expect(screen.getByText("case.transitioned")).toBeInTheDocument();
});

it("highlights events for an entity picked from the panel", async () => {
  render(<Timeline entries={entries} />);
  const panel = screen.getByText("Entities").closest("aside")!;
  const methodBtn = within(panel).getByRole("button", { name: /Method deterministic/i });
  await userEvent.click(methodBtn);
  expect(screen.getByRole("button", { name: /clear highlight/i })).toBeInTheDocument();
});

it("renders an empty state", () => {
  render(<Timeline entries={[]} />);
  expect(screen.getByText(/no activity recorded/i)).toBeInTheDocument();
});
