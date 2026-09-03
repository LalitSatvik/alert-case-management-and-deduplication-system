import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AlertsTable } from "./AlertsTable";
import type { AlertOut } from "../../api/types";

const alerts: AlertOut[] = [
  {
    id: "a1",
    external_alert_id: "T1",
    source_system: "acme-fraud",
    amount: "500.00",
    currency: "USD",
    direction: "inbound",
    customer_ref: "cust-1",
    merchant_name: "Quick Cash",
    risk_score: 88,
    typologies: ["structuring"],
    raw_payload: { note: "hello" },
    grouping: {
      method: "deterministic",
      matched_rule_ids: ["same-customer-72h"],
      similarity_score: null,
      feature_contributions: {},
      engine_version: "1.0.0",
      config_hash: "h",
    },
  },
  {
    id: "a2",
    external_alert_id: "T2",
    amount: "900.00",
    currency: "USD",
    risk_score: 40,
    raw_payload: {},
    grouping: null,
  },
];

it("expands a row to reveal the payload", async () => {
  render(<AlertsTable alerts={alerts} />);
  expect(screen.getByText("T1")).toBeInTheDocument();
  expect(screen.queryByText(/"note"/)).not.toBeInTheDocument();

  await userEvent.click(screen.getByText("T1"));
  await waitFor(() => expect(screen.getByText(/"note"/)).toBeInTheDocument());
});

it("opens the compare dialog", async () => {
  render(<AlertsTable alerts={alerts} />);
  await userEvent.click(screen.getAllByRole("button", { name: "Compare" })[0]);
  await waitFor(() => expect(screen.getByText("Compare alerts")).toBeInTheDocument());
});

it("shows a no-group tag when grouping is null", () => {
  render(<AlertsTable alerts={alerts} />);
  expect(screen.getByText("No group")).toBeInTheDocument();
});
