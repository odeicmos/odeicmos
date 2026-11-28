from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from odei_api.routers.privacy import (
    ConsentEventCreate, DataSubjectRequestCreate,
    IdentityVerificationCreate, DataSubjectRequestTransition,
    _consent_event_is_chronological,
)


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


def test_data_subject_request_requires_timezone_and_scoped_request():
    request = DataSubjectRequestCreate(
        tenant_id="tenant-a", facility_id="facility-a", patient_id="patient-a",
        request_type="access", requester_type="patient", requester_name="Patient One",
        requested_scope="Copy of the patient's longitudinal record.",
        received_at="2026-11-20T10:00:00+03:00",
    )
    assert request.request_type == "access"
    with pytest.raises(ValidationError):
        DataSubjectRequestCreate(
            tenant_id="tenant-a", facility_id="facility-a", patient_id="patient-a",
            request_type="access", requester_type="patient", requester_name="Patient One",
            requested_scope="Copy of the patient's longitudinal record.",
            received_at="2026-11-20T10:00:00",
        )


def test_identity_verification_and_request_transitions_require_evidence():
    verified = IdentityVerificationCreate(
        tenant_id="tenant-a", facility_id="facility-a", outcome="verified",
        method="in_person_document", evidence_reference="private-object://identity/check-1",
        rationale="Identity checked against the approved in-person document procedure.",
    )
    assert verified.outcome == "verified"
    transition = DataSubjectRequestTransition(
        tenant_id="tenant-a", facility_id="facility-a", status="fulfilled",
        rationale="The approved response package was delivered to the verified requester.",
        evidence_reference="private-object://dsr/delivery-1",
    )
    assert transition.status == "fulfilled"
    with pytest.raises(ValidationError):
        DataSubjectRequestTransition(
            tenant_id="tenant-a", facility_id="facility-a", status="fulfilled",
            rationale="short",
        )


def test_consent_event_timestamp_cannot_predate_latest_event():
    grant_time = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)
    grant = {"recorded_at": grant_time}
    assert _consent_event_is_chronological(grant, grant_time)
    assert _consent_event_is_chronological(
        grant, datetime(2026, 11, 20, 10, 1, tzinfo=timezone.utc)
    )
    assert not _consent_event_is_chronological(
        grant, datetime(2026, 11, 20, 9, 59, tzinfo=timezone.utc)
    )
    assert not _consent_event_is_chronological(None, grant_time)
