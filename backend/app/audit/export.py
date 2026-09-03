"""Per-case audit-trail export: a JSON bundle and a self-contained HTML render.

:func:`build_case_audit_bundle` assembles everything a reviewer needs to audit one
case offline -- the case header, its linked alerts with grouping rationale, every
note (retracted included), and the full ``case:{id}`` hash-chained event stream --
plus a ``chain_verified`` flag that re-runs :func:`app.audit.service.verify_stream`
*and* anchors the events against the ``audit_streams`` tip row (so a wholesale
truncate-and-rebuild is caught, not just in-list tampering). It never writes.

:func:`render_html` turns that bundle into one ``<!DOCTYPE html>`` document with
inline CSS and **no external references at all** -- no ``<link>``, no
``<script src>``, no URLs, no web fonts -- so it can be archived or emailed as a
single file. Every value that originates in the database (note bodies, reasons,
merchant names, ``before`` / ``after`` JSON, actor ids, ``human_ref`` ...) is run
through :func:`html.escape` before interpolation: a note body of
``<script>alert(1)</script>`` renders as inert text.
"""

from __future__ import annotations

import html
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import verify_stream
from app.cases.service import CaseNotFound
from app.models.alert import Alert
from app.models.audit import AuditEvent, AuditStream
from app.models.case import Case, CaseAlertLink, Note
from app.models.grouping import GroupingDecision

__all__ = ["build_case_audit_bundle", "render_html"]

_CASE_FIELDS = (
    "id",
    "human_ref",
    "status",
    "disposition",
    "assignee_id",
    "risk_score",
    "alert_count",
    "closed_at",
    "canonical_from_case_id",
    "version",
    "created_at",
    "updated_at",
)

_ALERT_FIELDS = (
    "id",
    "external_alert_id",
    "source_system",
    "event_time",
    "received_at",
    "amount",
    "currency",
    "direction",
    "customer_ref",
    "account_ref",
    "counterparty_ref",
    "merchant_name",
    "merchant_name_normalised",
    "mcc",
    "device_id",
    "session_id",
    "ip_address",
    "risk_score",
    "rule_codes",
    "typologies",
    "case_id",
)

_GROUPING_FIELDS = (
    "method",
    "matched_rule_ids",
    "similarity_score",
    "feature_contributions",
    "engine_version",
    "config_hash",
)

_NOTE_FIELDS = (
    "id",
    "author_id",
    "body",
    "retracted",
    "retraction_reason",
    "created_at",
)

_EVENT_FIELDS = (
    "id",
    "stream",
    "seq",
    "prev_hash",
    "hash",
    "actor_id",
    "actor_role",
    "action",
    "target_type",
    "target_id",
    "reason",
    "before",
    "after",
    "correlation_id",
    "created_at",
)


def _jsonable(value: object) -> Any:
    """Recursively coerce ORM/column values to JSON-native types.

    ``datetime`` -> ISO 8601 string, ``UUID`` / ``Decimal`` -> string, containers
    are walked; everything else (``str`` / ``int`` / ``float`` / ``bool`` /
    ``None``) passes through untouched.
    """
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _row(obj: object, fields: tuple[str, ...]) -> dict[str, Any]:
    return {name: _jsonable(getattr(obj, name)) for name in fields}


async def build_case_audit_bundle(session: AsyncSession, case_id: UUID) -> dict[str, Any]:
    """Assemble the full, JSON-safe audit bundle for one case. Never writes.

    Raises :class:`~app.cases.service.CaseNotFound` when ``case_id`` matches no
    row (the route maps that to 404).
    """
    case = await session.get(Case, case_id)
    if case is None:
        raise CaseNotFound(str(case_id))
    # Server-side defaults (``created_at`` / ``updated_at``) can be unpopulated on
    # a Case the ORM has already touched -- refresh before serialising.
    await session.refresh(case)

    stream = f"case:{case_id}"

    alert_rows = (
        await session.execute(
            select(Alert, GroupingDecision)
            .join(CaseAlertLink, CaseAlertLink.alert_id == Alert.id)
            .outerjoin(
                GroupingDecision,
                GroupingDecision.id == CaseAlertLink.grouping_decision_id,
            )
            .where(CaseAlertLink.case_id == case_id)
            .order_by(Alert.event_time, Alert.id)
        )
    ).all()
    alerts: list[dict[str, Any]] = []
    for alert, decision in alert_rows:
        entry = _row(alert, _ALERT_FIELDS)
        entry["grouping"] = None if decision is None else _row(decision, _GROUPING_FIELDS)
        alerts.append(entry)

    notes = list(
        (
            await session.execute(
                select(Note).where(Note.case_id == case_id).order_by(Note.created_at, Note.id)
            )
        )
        .scalars()
        .all()
    )

    events = list(
        (
            await session.execute(
                select(AuditEvent).where(AuditEvent.stream == stream).order_by(AuditEvent.seq)
            )
        )
        .scalars()
        .all()
    )

    chain_verified = not verify_stream(events)
    if events:
        stream_row = await session.get(AuditStream, stream)
        if stream_row is not None:
            chain_verified = chain_verified and (
                events[-1].hash == stream_row.last_hash and len(events) == stream_row.last_seq
            )

    return {
        "case": _row(case, _CASE_FIELDS),
        "alerts": alerts,
        "notes": [_row(note, _NOTE_FIELDS) for note in notes],
        "audit_events": [_row(event, _EVENT_FIELDS) for event in events],
        "chain_verified": chain_verified,
        "generated_at": datetime.now(UTC).isoformat(),
    }


# --- HTML render ----------------------------------------------------------------

_CSS = """
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial,
       sans-serif; margin: 0; padding: 2rem; color: #1a1a1a; background: #fafafa; }
h1, h2, h3 { margin: 0.6rem 0; }
header { border-bottom: 2px solid #dddddd; padding-bottom: 1rem; margin-bottom: 1.5rem; }
.badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 0.3rem; font-weight: 700;
         font-size: 0.85rem; letter-spacing: 0.02em; }
.badge.ok { background: #0a7b34; color: #ffffff; }
.badge.bad { background: #b21f2d; color: #ffffff; }
dl { display: grid; grid-template-columns: max-content 1fr; gap: 0.2rem 1rem; margin: 0.6rem 0; }
dt { font-weight: 600; }
dd { margin: 0; }
table { border-collapse: collapse; width: 100%; font-size: 0.85rem; }
th, td { border: 1px solid #cccccc; padding: 0.4rem 0.5rem; text-align: left; vertical-align: top; }
th { background: #eeeeee; }
pre { white-space: pre-wrap; word-break: break-word; margin: 0; font-family: ui-monospace,
      SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.8rem; }
section.alert, section.note { border: 1px solid #dddddd; border-radius: 0.4rem;
      padding: 0.8rem 1rem; margin: 0.8rem 0; background: #ffffff; }
section.note.retracted { opacity: 0.6; }
section.note.retracted .body { text-decoration: line-through; }
.role, .meta { color: #666666; font-size: 0.78rem; }
""".strip()


def _esc(value: object) -> str:
    """HTML-escape any value (``None`` -> empty string), quotes included."""
    return html.escape("" if value is None else str(value), quote=True)


def _json_block(value: object) -> str:
    """Compact, escaped JSON for a ``<pre>`` cell."""
    return _esc(json.dumps(value, indent=2, sort_keys=True, default=str))


def render_html(bundle: dict[str, Any]) -> str:
    """Render ``bundle`` as one self-contained HTML document (inline CSS, no URLs)."""
    case: dict[str, Any] = bundle["case"]
    verified = bool(bundle["chain_verified"])
    badge_class = "ok" if verified else "bad"
    badge_text = "chain verified" if verified else "CHAIN BROKEN"

    p: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>Audit trail {_esc(case.get('human_ref'))}</title>",
        f"<style>{_CSS}</style>",
        "</head>",
        "<body>",
        "<header>",
        f"<h1>Case {_esc(case.get('human_ref'))}</h1>",
        f'<span class="badge {badge_class}">{_esc(badge_text)}</span>',
        "<dl>",
        f"<dt>Status</dt><dd>{_esc(case.get('status'))}</dd>",
        f"<dt>Disposition</dt><dd>{_esc(case.get('disposition'))}</dd>",
        f"<dt>Risk score</dt><dd>{_esc(case.get('risk_score'))}</dd>",
        f"<dt>Alert count</dt><dd>{_esc(case.get('alert_count'))}</dd>",
        f"<dt>Generated</dt><dd>{_esc(bundle.get('generated_at'))}</dd>",
        "</dl>",
        "</header>",
    ]

    p.append("<h2>Audit events</h2>")
    p.append("<table>")
    p.append(
        "<thead><tr><th>Seq</th><th>Time</th><th>Actor</th><th>Action</th>"
        "<th>Reason</th><th>Before &rarr; After</th></tr></thead>"
    )
    p.append("<tbody>")
    for e in bundle["audit_events"]:
        p.append(
            "<tr>"
            f"<td>{_esc(e['seq'])}</td>"
            f"<td>{_esc(e['created_at'])}</td>"
            f"<td>{_esc(e['actor_id'])}<br><span class=\"role\">{_esc(e['actor_role'])}</span></td>"
            f"<td>{_esc(e['action'])}</td>"
            f"<td>{_esc(e['reason'])}</td>"
            f"<td><pre>{_json_block(e['before'])}\n&rarr;\n{_json_block(e['after'])}</pre></td>"
            "</tr>"
        )
    p.append("</tbody></table>")

    p.append("<h2>Alerts</h2>")
    if not bundle["alerts"]:
        p.append("<p>No alerts linked.</p>")
    for a in bundle["alerts"]:
        p.append('<section class="alert">')
        p.append(
            f"<h3>{_esc(a.get('external_alert_id'))} &mdash; {_esc(a.get('source_system'))}</h3>"
        )
        p.append("<dl>")
        for label, key in (
            ("Amount", "amount"),
            ("Currency", "currency"),
            ("Direction", "direction"),
            ("Event time", "event_time"),
            ("Merchant", "merchant_name"),
            ("Customer ref", "customer_ref"),
            ("Risk score", "risk_score"),
        ):
            p.append(f"<dt>{_esc(label)}</dt><dd>{_esc(a.get(key))}</dd>")
        p.append("</dl>")
        grouping = a.get("grouping")
        if grouping is None:
            p.append('<p class="meta">No grouping decision recorded.</p>')
        else:
            p.append('<p class="meta">Grouping rationale</p>')
            p.append(f"<pre>{_json_block(grouping)}</pre>")
        p.append("</section>")

    p.append("<h2>Notes</h2>")
    if not bundle["notes"]:
        p.append("<p>No notes.</p>")
    for n in bundle["notes"]:
        retracted = bool(n["retracted"])
        cls = "note retracted" if retracted else "note"
        p.append(f'<section class="{cls}">')
        suffix = " (retracted)" if retracted else ""
        p.append(
            f"<p class=\"meta\">{_esc(n['created_at'])} &mdash; {_esc(n['author_id'])}{suffix}</p>"
        )
        p.append(f"<p class=\"body\">{_esc(n['body'])}</p>")
        if retracted:
            p.append(f"<p class=\"meta\">Retraction reason: {_esc(n['retraction_reason'])}</p>")
        p.append("</section>")

    p.append("</body></html>")
    return "\n".join(p)
