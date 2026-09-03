import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useInfiniteQuery } from "@tanstack/react-query";
import { listCases, type CaseQuery } from "../api/cases";
import type { CaseListItem } from "../api/types";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { CaseFilters } from "../components/CaseFilters";
import { DataTable, type Column } from "../components/DataTable";
import { StatusBadge } from "../components/StatusBadge";
import { RiskScore } from "../components/ui/RiskScore";
import { Page, PageBody, PageHeader } from "../components/ui/Page";
import { relativeTime } from "../lib/format";

const DEFAULT_SORT = "-risk_score";

export function CaseListPage() {
  const { token, principal } = useAuth();
  const [sp, setSp] = useSearchParams();

  const statuses = sp.getAll("status");
  const assignee = sp.get("assignee") ?? "all";
  const riskMinRaw = sp.get("risk_min");
  const riskMin = riskMinRaw != null && riskMinRaw !== "" ? Number(riskMinRaw) : null;
  const sort = sp.get("sort") ?? DEFAULT_SORT;
  const urlQ = sp.get("q") ?? "";

  const [qInput, setQInput] = useState(urlQ);

  // Debounce the free-text search into the URL (~300ms).
  useEffect(() => {
    if (qInput === urlQ) return;
    const t = setTimeout(() => {
      setSp(
        (prev) => {
          const n = new URLSearchParams(prev);
          if (qInput) n.set("q", qInput);
          else n.delete("q");
          return n;
        },
        { replace: true },
      );
    }, 300);
    return () => clearTimeout(t);
  }, [qInput, urlQ, setSp]);

  function mutateParams(fn: (n: URLSearchParams) => void) {
    setSp((prev) => {
      const n = new URLSearchParams(prev);
      fn(n);
      return n;
    });
  }

  const toggleStatus = (s: string) =>
    mutateParams((n) => {
      const current = n.getAll("status");
      const nextValues = current.includes(s)
        ? current.filter((x) => x !== s)
        : [...current, s];
      n.delete("status");
      nextValues.forEach((x) => n.append("status", x));
    });

  const setAssignee = (v: string) =>
    mutateParams((n) => (v === "all" ? n.delete("assignee") : n.set("assignee", v)));

  const setRiskMin = (v: number | null) =>
    mutateParams((n) => (v == null ? n.delete("risk_min") : n.set("risk_min", String(v))));

  const setSort = (v: string) =>
    mutateParams((n) => (v === DEFAULT_SORT ? n.delete("sort") : n.set("sort", v)));

  const assigneeId =
    assignee === "unassigned"
      ? "unassigned"
      : assignee === "me"
        ? principal?.id
        : undefined;

  const filters: CaseQuery = {
    status: statuses.length ? statuses : undefined,
    assignee_id: assigneeId ?? undefined,
    risk_min: riskMin ?? undefined,
    q: urlQ || undefined,
    sort,
    limit: 50,
  };

  const query = useInfiniteQuery({
    queryKey: ["cases", { statuses: statuses.join(","), assignee, riskMin, q: urlQ, sort }],
    queryFn: ({ pageParam }) =>
      listCases({ ...filters, cursor: pageParam as string | undefined }, token),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    retry: false,
  });

  const rows = query.data?.pages.flatMap((p) => p.items) ?? [];

  const columns: Column<CaseListItem>[] = [
    {
      key: "ref",
      header: "Case",
      render: (r) => (
        // The `after:` overlay spans the (position: relative) <tr>, so the whole
        // row is the link's hit area while cells keep their table semantics —
        // no role="button" on the row.
        <Link
          to={`/cases/${r.id}`}
          className="font-mono font-medium text-ink after:absolute after:inset-0 after:content-[''] hover:underline focus-visible:underline"
        >
          {r.human_ref}
        </Link>
      ),
    },
    { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
    {
      key: "assignee",
      header: "Assignee",
      render: (r) =>
        r.assignee_email ?? <span className="text-ink-tertiary">unassigned</span>,
    },
    {
      key: "risk",
      header: "Risk",
      render: (r) => <RiskScore score={r.risk_score} size="sm" />,
    },
    {
      key: "alerts",
      header: "Alerts",
      render: (r) => <span className="font-mono tabular-nums">{r.alert_count}</span>,
    },
    {
      key: "age",
      header: "Age",
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
        {query.isFetching && (
          <span className="text-xs text-ink-tertiary" aria-live="polite">
            Loading…
          </span>
        )}
      </PageHeader>
      <PageBody className="space-y-4">
        <CaseFilters
        statuses={statuses}
        onToggleStatus={toggleStatus}
        assignee={assignee}
        onAssignee={setAssignee}
        riskMin={riskMin}
        onRiskMin={setRiskMin}
        q={qInput}
        onQ={setQInput}
        sort={sort}
        onSort={setSort}
      />

      {query.isError && (
        <p
          role="alert"
          className="rounded-md border border-danger-border bg-danger-subtle px-3 py-2 text-sm text-danger-subtle-fg"
        >
          {query.error instanceof ApiError
            ? (query.error.detail ?? query.error.message)
            : "Could not load cases"}
        </p>
      )}

      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(r) => r.id}
        interactive
        empty={query.isLoading ? "Loading…" : "No cases match these filters."}
      />

        {query.hasNextPage && (
          <div className="flex justify-center">
            <button
              type="button"
              onClick={() => query.fetchNextPage()}
              disabled={query.isFetchingNextPage}
              className="inline-flex min-h-control items-center rounded-md border border-border bg-surface px-4 text-sm font-medium text-ink-secondary shadow-xs transition-colors hover:border-border-strong hover:text-ink disabled:opacity-40"
            >
              {query.isFetchingNextPage ? "Loading…" : "Load more"}
            </button>
          </div>
        )}
      </PageBody>
    </Page>
  );
}
