import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from odei_api.schemas import RoleAssignmentCreate, RoleAssignmentRevoke
from odei_api.security import Principal, authorize_facility_access


class FakeCollection:
    def __init__(self, result):
        self.result = result
        self.query = None

    async def find_one(self, query):
        self.query = query
        return self.result


class FakeDatabase:
    def __init__(self, assignment, facility):
        self.role_assignments = FakeCollection(assignment)
        self.facilities = FakeCollection(facility)


def request_for(assignment, facility):
    return SimpleNamespace(app=SimpleNamespace(
        state=SimpleNamespace(mongo_database=FakeDatabase(assignment, facility))
    ))


def test_facility_authorization_scopes_by_tenant_facility_issuer_and_effective_period():
    db_request = request_for({"role": "clinician"}, {"status": "active"})
    principal = Principal(subject="sub-1", issuer="https://id.example", claims={})

    role = asyncio.run(authorize_facility_access(
        db_request, principal, "tenant-a", "facility-a", ["clinician"]
    ))

    assert role == "clinician"
    assert db_request.app.state.mongo_database.facilities.query == {
        "tenant_id": "tenant-a", "facility_id": "facility-a", "status": "active",
    }
    query = db_request.app.state.mongo_database.role_assignments.query
    assert query["tenant_id"] == "tenant-a"
    assert query["facility_id"] == "facility-a"
    assert query["user_issuer"] == "https://id.example"
    assert query["user_id"] == "sub-1"
    assert query["status"] == "active"
    assert query["role"] == {"$in": ["clinician"]}
    assert len(query["$and"]) == 2


def test_facility_authorization_denies_inactive_facility():
    request = request_for({"role": "clinician"}, None)
    principal = Principal(subject="sub-1", issuer="https://id.example", claims={})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(authorize_facility_access(
            request, principal, "tenant-a", "facility-a", ["clinician"]
        ))
    assert exc.value.status_code == 403


def test_facility_authorization_denies_missing_assignment():
    request = request_for(None, {"status": "active"})
    principal = Principal(subject="sub-1", issuer="https://id.example", claims={})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(authorize_facility_access(
            request, principal, "tenant-a", "facility-a", ["clinician"]
        ))
    assert exc.value.status_code == 403


def test_role_assignment_requires_issuer_qualified_subject():
    with pytest.raises(Exception):
        RoleAssignmentCreate(
            tenant_id="tenant-a", facility_id="facility-a", user_id="sub-1",
            role="clinician",
        )


def test_role_assignment_rejects_naive_effective_dates():
    with pytest.raises(ValueError):
        RoleAssignmentCreate(
            tenant_id="tenant-a", facility_id="facility-a", user_id="sub-1",
            user_issuer="https://id.example", role="clinician",
            effective_from=datetime.now(),
        )


def test_role_assignment_rejects_inverted_effective_period():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError):
        RoleAssignmentCreate(
            tenant_id="tenant-a", facility_id="facility-a", user_id="sub-1",
            user_issuer="https://id.example", role="clinician",
            effective_from=now, effective_until=now - timedelta(minutes=1),
        )


def test_role_assignment_accepts_timezone_aware_effective_period():
    now = datetime.now(timezone.utc)
    payload = RoleAssignmentCreate(
        tenant_id="tenant-a", facility_id="facility-a", user_id="sub-1",
        user_issuer="https://id.example", role="clinician",
        effective_from=now, effective_until=now + timedelta(days=90),
    )
    assert payload.effective_until > payload.effective_from


def test_role_revocation_requires_a_reason():
    with pytest.raises(ValueError):
        RoleAssignmentRevoke(
            tenant_id="tenant-a", facility_id="facility-a", user_id="sub-1",
            user_issuer="https://id.example", role="clinician", reason="no",
        )
