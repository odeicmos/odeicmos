"""Append-only audit event writer. Database credentials must deny update/delete on this collection."""
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any
from pymongo.errors import PyMongoError


async def append_audit_event(
    db: Any, *, actor_id: str, action: str, resource_type: str,
    resource_id: str, tenant_id: str | None, outcome: str,
    correlation_id: str | None = None, metadata: dict[str, Any] | None = None,
) -> str:
    event_id = str(uuid4())
    event = {
        "event_id": event_id, "actor_id": actor_id, "action": action,
        "resource_type": resource_type, "resource_id": resource_id,
        "tenant_id": tenant_id, "outcome": outcome,
        "correlation_id": correlation_id,
        "metadata": metadata or {}, "occurred_at": datetime.now(timezone.utc),
    }
    try:
        await db.audit_events.insert_one(event)
    except PyMongoError:
        # Never allow a sensitive control-plane write to succeed without its audit event.
        raise
    return event_id
