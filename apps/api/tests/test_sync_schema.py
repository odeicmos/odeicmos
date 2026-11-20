import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from odei_api.routers.sync import (
    DeviceEnrollmentCreate, DeviceRevocationCreate, OfflineChange, SyncBatchCreate, _signed_bytes,
)


def _public_pem(private_key):
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


def test_device_enrollment_accepts_ed25519_and_rejects_other_key_types():
    key = Ed25519PrivateKey.generate()
    payload = DeviceEnrollmentCreate(
        tenant_id="tenant-a", facility_id="facility-a", device_id="device-0001",
        public_key_pem=_public_pem(key), label="Reception tablet",
    )
    assert payload.device_id == "device-0001"
    with pytest.raises(ValidationError):
        DeviceEnrollmentCreate(
            tenant_id="tenant-a", facility_id="facility-a", device_id="device-0002",
            public_key_pem="not-a-pem-public-key-" * 8, label="Invalid device",
        )


def test_offline_change_requires_timezone_and_unique_batch_ids():
    change = OfflineChange(
        change_id="change-0001", aggregate_type="patient_registration",
        aggregate_id="patient-local-1", base_version=0,
        client_recorded_at="2026-11-20T10:00:00+03:00",
        change_type="create", payload={"given_name": "Synthetic"},
    )
    assert change.change_id == "change-0001"
    with pytest.raises(ValidationError):
        OfflineChange(
            change_id="change-0002", aggregate_type="patient_registration",
            aggregate_id="patient-local-2", base_version=0,
            client_recorded_at="2026-11-20T10:00:00",
            change_type="create", payload={},
        )


def test_batch_signature_covers_scope_ids_and_full_change_payload():
    key = Ed25519PrivateKey.generate()
    change = OfflineChange(
        change_id="change-0001", aggregate_type="patient_registration",
        aggregate_id="patient-local-1", base_version=0,
        client_recorded_at="2026-11-20T10:00:00+03:00",
        change_type="create", payload={"given_name": "Synthetic"},
    )
    unsigned = {
        "tenant_id": "tenant-a", "facility_id": "facility-a",
        "device_id": "device-0001", "batch_id": "batch-0001",
        "changes": [change],
    }
    from odei_api.routers.sync import _canonical_batch
    canonical = _canonical_batch(unsigned)
    signature = base64.b64encode(key.sign(canonical)).decode()
    batch = SyncBatchCreate(**unsigned, signature=signature)
    key.public_key().verify(base64.b64decode(batch.signature), _signed_bytes(batch))
    changed = batch.model_copy(update={"facility_id": "facility-b"})
    with pytest.raises(Exception):
        key.public_key().verify(base64.b64decode(changed.signature), _signed_bytes(changed))


def test_device_revocation_requires_a_reason():
    payload = DeviceRevocationCreate(
        tenant_id="tenant-a", facility_id="facility-a",
        reason="Device reported lost; revoke its signing key immediately.",
    )
    assert "lost" in payload.reason
    with pytest.raises(ValidationError):
        DeviceRevocationCreate(
            tenant_id="tenant-a", facility_id="facility-a", reason="lost",
        )
