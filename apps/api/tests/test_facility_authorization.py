from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from odei_api.schemas import RoleAssignmentCreate
from odei_api.security import Principal, authorize_facility_access


class FakeAssignments:
    def __init__(self, result):
        self.result = result
        self.query = None

    async def find_one(self, query):
        self.query = query
        return self.result


@pytest.mark.asyncio
async def test_facility_authorization_scopes_by_tenant_facility_and_issuer():
    assignments = FakeAssignments({"role": "clinician"})
    request = SimpleNamespace(app=SimpleNamespace(
        state=SimpleNamespace(mongo_database=SimpleNamespace(role_assignments=assignments))
    ))
    principal = Principal(subject="sub-1", issuer="https://id.example", claims={})

    role = await authorize_facility_access(
        request, principal, "tenant-a", "facility-a", ["clinician"]
    )

    assert role == "clinician"
    assert assignments.query == {
        "tenant_id": "tenant-a",
        "facility_id": "facility-a",
        "user_issuer": "https://id.example",
        "user_id": "sub-1",
        "status": "active",
        "role": {"$in": ["clinician"]},
    }


@pytest.mark.asyncio
async def test_facility_authorization_denies_missing_assignment():
    assignments = FakeAssignments(None)
    request = SimpleNamespace(app=SimpleNamespace(
        state=SimpleNamespace(mongo_database=SimpleNamespace(role_assignments=assignments))
    ))
    principal = Principal(subject="sub-1", issuer="https://id.example", claims={})

    with pytest.raises(HTTPException) as exc:
        await authorize_facility_access(
            request, principal, "tenant-a", "facility-a", ["clinician"]
        )
    assert exc.value.status_code == 403


def test_role_assignment_requires_issuer_qualified_subject():
    with pytest.raises(Exception):
        RoleAssignmentCreate(
            tenant_id="tenant-a", facility_id="facility-a", user_id="sub-1",
            role="clinician",
        )
