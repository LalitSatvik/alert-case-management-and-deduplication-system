# Screenshots

Captured from the running stack against the `seed` demo data (three demo logins,
~780 alerts grouped into ~350 cases, five worked to *In Progress*). 1440×900,
2× density. Each screen is shown in both light and dark themes — the app follows
the viewer's `prefers-color-scheme`.

| File | Screen |
|---|---|
| `01-login` | Sign-in |
| `02-case-list` | Case list — filter bar, keyset-paginated table, risk / alert-count / age columns |
| `03-case-list-filtered` | Case list filtered to *In Progress* (filter state is in the URL) |
| `04-case-detail-alerts` | Case detail, **Alerts** tab — one card per linked alert with its grouping rationale (matched deterministic rule ids, or a similarity score with per-feature bars) and a raw-payload disclosure |
| `05-case-detail-timeline` | **Timeline** tab — the case's audit stream, newest first, with before→after diffs |
| `06-case-detail-notes` | **Notes** tab — append-only notes with retract |
| `07-case-detail-audit` | **Audit** tab — the hash-chained event log, chain-verification badge, JSON / HTML export |
| `08-case-detail-readonly` | The same case seen by a `readonly` user — every mutating control is hidden (the server is still the enforcement point) |

Regenerate: run the stack (`docker compose up -d && docker compose run --rm seed`,
or the local equivalent), then drive a browser through the screens above.
