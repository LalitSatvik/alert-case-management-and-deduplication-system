import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { listCases } from "../api/cases";
import { listUsers } from "../api/users";
import type { CaseListItem } from "../api/types";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { CaseFilters } from "../components/CaseFilters";
import { CasesSummary } from "../components/cases/CasesSummary";
import { BulkActionBar } from "../components/cases/BulkActionBar";
import { DataTable, type Column } from "../components/ui/DataTable";
import { StatusBadge } from "../components/StatusBadge";
import { RiskScore } from "../components/ui/RiskScore";
import { Button } from "../components/ui/Button";
import { Page, PageBody, PageHeader } from "../components/ui/Page";
import { readFilterState, toCaseQuery } from "../lib/caseFilters";
import { riskBand, RISK_BAR_BG } from "../lib/risk";
import { relativeTime } from "../lib/format";

export function CaseListPage() {
  const { token, principal } = useAuth();
  const [sp, setSp] = useSearchParams();
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const state = readFilterState(sp);
  const query = useMemo(() => toCaseQuery(state, principal?.id), [state, principal?.id]);

  const usersQuery = useQuery({
    queryKey: ["users"],
    queryFn: () => listUsers(token),
    staleTime: 5 * 60_000,
    retry: false,
  });
  const users = usersQuery.data ?? [];

  const casesQuery = useInfiniteQuery({
    queryKey: ["cases", query],
    queryFn: ({ pageParam }) => listCases({ ...query, limit: 100, cursor: pageParam }, token),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    retry: false,
  });

  const rows = casesQuery.data?.pages.flatMap((p) => p.items) ?? [];
  const selectedCases = rows.filter((r) => selected.has(r.id));

  const setSort = (sortKey: string) =>
    setSp(
      (prev) => {
        const n = new URLSearchParams(prev);
        if (sortKey === "-risk_score") n.delete("sort");
        else n.set("sort", sortKey);
        return n;
      },
      { replace: true },
    );

  const toggleRow = (key: string) =>
    setSelected((prev) => {
      const n = new Set(prev);
      if (n.has(key)) n.delete(key);
      else n.add(key);
      return n;
    });

  const toggleAll = () =>
    setSelected((prev) =>
      prev.size === rows.length ? new Set() : new Set(rows.map((r) => r.id)),
    );

  const columns: Column<CaseListItem>[] = [
    {
      key: "risk",
      header: "Risk",
      sortKey: "-risk_score",
      align: "right",
      width: "5.5rem",
      render: (r) => <RiskScore score={r.risk_score} size="sm" />,
    },
    {
      key: "ref",
      header: "Case",
      render: (r) => <span className="font-mono font-medium text-ink">{r.human_ref}</span>,
    },
    { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
    {
      key: "assignee",
      header: "Assignee",
      render: (r) =>
        r.assignee_email ? (
          <span className="font-mono text-xs">{r.assignee_email}</span>
        ) : (
          <span className="text-ink-tertiary">—</span>
        ),
    },
    {
      key: "alerts",
      header: "Alerts",
      align: "right",
      width: "4.5rem",
      render: (r) => <span className="font-mono">{r.alert_count}</span>,
    },
    {
      key: "age",
      header: "Age",
      sortKey: "oldest_alert",
      align: "right",
      width: "7rem",
      render: (r) => (
        <span className="text-ink-tertiary">
          {relativeTime(r.oldest_alert_event_time ?? r.created_at)}
        </span>
      ),
    },
  ];

  return (
    <Page>
      <PageHeader title="Cases">
        <span className="font-mono text-xs tabular-nums text-ink-tertiary">
          {rows.length}
          {casesQuery.hasNextPage ? "+" : ""}
        </span>
        {casesQuery.isFetching && (
          <span className="text-2xs uppercase tracking-wider text-ink-tertiary" aria-live="polite">
            Loading
          </span>
        )}
      </PageHeader>

      <PageBody className="flex flex-col gap-2">
        <CasesSummary query={query} />
        <CaseFilters users={users} />

        {selectedCases.length > 0 && (
          <BulkActionBar
            selected={selectedCases}
            users={users}
            onDone={() => setSelected(new Set())}
          />
        )}

        {casesQuery.isError && (
          <p
            role="alert"
            className="rounded-md border border-danger-border bg-danger-subtle px-3 py-2 text-sm text-danger-subtle-fg"
          >
            {casesQuery.error instanceof ApiError
              ? (casesQuery.error.detail ?? casesQuery.error.message)
              : "Could not load cases"}
          </p>
        )}

        <div className="min-h-0 flex-1">
          <DataTable
            columns={columns}
            rows={rows}
            rowKey={(r) => r.id}
            rowHref={(r) => `/cases/${r.id}`}
            rowAccent={(r) => RISK_BAR_BG[riskBand(r.risk_score)]}
            selectable
            selected={selected}
            onToggleRow={toggleRow}
            onToggleAll={toggleAll}
            sort={state.sort}
            onSort={setSort}
            empty={casesQuery.isLoading ? "Loading…" : "No cases match these filters."}
          />
        </div>

        {casesQuery.hasNextPage && (
          <div className="flex justify-center py-1">
            <Button
              size="sm"
              onClick={() => casesQuery.fetchNextPage()}
              disabled={casesQuery.isFetchingNextPage}
            >
              {casesQuery.isFetchingNextPage ? "Loading…" : "Load more"}
            </Button>
          </div>
        )}
      </PageBody>
    </Page>
  );
}
