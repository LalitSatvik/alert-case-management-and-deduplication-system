# Screenshots

Captured from the running stack against the `seed` demo data (three demo logins,
~780 alerts grouped into ~350 cases, five worked to *In Progress*). 1440×900,
2× density. Each screen is shown in both light and dark themes — the app defaults
to the viewer's `prefers-color-scheme` and the theme can be pinned in Settings.

| File | Screen |
|---|---|
| `01-login` | Sign-in |
| `02-case-list` | Cases dashboard — KPI summary strip, filter bar, risk-band row accents, sortable dense table |
| `03-case-list-filtered` | Dashboard filtered to *In Progress* (filter state is in the URL; the KPI strip and the *Clear* control follow it) |
| `04-case-detail-alerts` | Case detail — control rail (risk gauge, action toolbar, status history) beside the **Alerts** tab: an aligned table with a risk bar, typology and linking badges, and a per-row payload accordion / compare dialog |
| `05-case-detail-timeline` | **Timeline** tab — a spine of expandable event nodes with entity chips (alert / note / user / method / status) and an entity sidebar; clicking an entity highlights every event that touches it |
| `06-case-detail-notes` | **Notes** tab — append-only notes with retract |
| `07-case-detail-audit` | **Audit** tab — the hash-chained event log, chain-verification badge, JSON / HTML export |
| `08-case-detail-readonly` | The same case seen by a `readonly` user — the action toolbar and every mutating control are gone (the server is still the enforcement point) |

Regenerate: run the stack (`docker compose up -d && docker compose run --rm seed`,
or the local equivalent), then drive a browser through the screens above.
