import pytest
from pydantic import ValidationError

from odei_api.routers.privacy import ConsentEventCreate


def test_consent_event_requires_timezone_and_explicit_purpose():
    event = ConsentEventCreate(
        tenant_id="tenant-a", facility_id="facility-a", patient_id="patient-a",
        purpose_code="care_sharing", data_categories=["demographics", "clinical"],
        action="granted", lawful_basis="consent", notice_version="UG-privacy-1.0",
        recorded_at="2026-11-20T10:00:00+03:00",
        evidence_reference="private-object://consent/evidence-1",
    )
    assert event.action == "granted"
    assert event.data_categories == ["demographics", "clinical"]
    with pytest.raises(ValidationError):
        ConsentEventCreate(
            tenant_id="tenant-a", facility_id="facility-a", patient_id="patient-a",
            purpose_code="care_sharing", data_categories=["clinical"],
            action="granted", lawful_basis="consent", notice_version="v1",
            recorded_at="2026-11-20T10:00:00",
        )


def test_consent_event_rejects_duplicate_categories_and_unknown_fields():
    values = dict(
        tenant_id="tenant-a", facility_id="facility-a", patient_id="patient-a",
        purpose_code="care_sharing", data_categories=["clinical", "clinical"],
        action="granted", lawful_basis="consent", notice_version="v1",
        recorded_at="2026-11-20T10:00:00+03:00",
    )
    with pytest.raises(ValidationError):
        ConsentEventCreate(**values)
    values["data_categories"] = ["clinical"]
    values["unexpected"] = True
    with pytest.raises(ValidationError):
        ConsentEventCreate(**values)


def test_withdrawal_is_not_a_new_nonconsent_basis():
    with pytest.raises(ValidationError):
        ConsentEventCreate(
            tenant_id="tenant-a", facility_id="facility-a", patient_id="patient-a",
            purpose_code="care_sharing", data_categories=["clinical"],
            action="withdrawn", lawful_basis="healthcare_delivery", notice_version="v1",
            recorded_at="2026-11-20T10:00:00+03:00",
        )


def test_other_lawful_basis_is_recorded_without_claiming_consent():
    event = ConsentEventCreate(
        tenant_id="tenant-a", facility_id="facility-a", patient_id="patient-a",
        purpose_code="care_delivery", data_categories=["clinical"],
        action="basis_recorded", lawful_basis="healthcare_delivery", notice_version="v1",
        recorded_at="2026-11-20T10:00:00+03:00",
    )
    assert event.action == "basis_recorded"
    with pytest.raises(ValidationError):
        ConsentEventCreate(
            tenant_id="tenant-a", facility_id="facility-a", patient_id="patient-a",
            purpose_code="care_delivery", data_categories=["clinical"],
            action="granted", lawful_basis="healthcare_delivery", notice_version="v1",
            recorded_at="2026-11-20T10:00:00+03:00",
        )
