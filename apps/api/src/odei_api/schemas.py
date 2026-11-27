"""Validated control-plane request and response models."""
from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OrganizationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    organization_id: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=2, max_length=200)
    legal_name: str | None = Field(default=None, max_length=240)
    country_code: str = Field(min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")


class FacilityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    organization_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=2, max_length=200)
    facility_type: Literal["clinic", "health_centre", "polyclinic", "hospital", "other"]
    country_code: str = Field(min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")


class RegistryRecord(BaseModel):
    id: str
    status: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TenantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=2, max_length=200)
    deployment_model: Literal["multi_tenant_saas", "dedicated", "self_hosted", "hybrid"]
    country_code: str = Field(min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")


class RoleAssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    user_id: str = Field(min_length=1, max_length=200)
    user_issuer: str = Field(min_length=1, max_length=500)
    role: Literal[
        "facility_admin", "clinician", "nurse", "pharmacist", "lab_scientist",
        "vaccinator", "receptionist", "finance_officer", "procurement_officer",
        "claims_officer", "auditor", "read_only",
    ]
    effective_from: datetime | None = None
    effective_until: datetime | None = None

    @model_validator(mode="after")
    def validate_effective_period(self):
        for value in (self.effective_from, self.effective_until):
            if value is not None and value.utcoffset() is None:
                raise ValueError("Role assignment effective dates must include a timezone")
        if self.effective_from and self.effective_until and self.effective_until <= self.effective_from:
            raise ValueError("effective_until must be later than effective_from")
        return self


class RoleAssignmentRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    user_id: str = Field(min_length=1, max_length=200)
    user_issuer: str = Field(min_length=1, max_length=500)
    role: Literal[
        "facility_admin", "clinician", "nurse", "pharmacist", "lab_scientist",
        "vaccinator", "receptionist", "finance_officer", "procurement_officer",
        "claims_officer", "auditor", "read_only",
    ]
    reason: str = Field(min_length=5, max_length=1000)


class PatientRegistrationCreate(BaseModel):
    """Minimal registration data; clinical notes and diagnoses belong to later workflows."""
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    medical_record_number: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9/_-]+$")
    legal_name: str = Field(min_length=2, max_length=200)
    preferred_name: str | None = Field(default=None, max_length=100)
    date_of_birth: date | None = None
    sex_at_birth: Literal["female", "male", "intersex", "unknown", "not_recorded"] = "not_recorded"
    phone_number: str | None = Field(default=None, min_length=5, max_length=30)
    preferred_language: str | None = Field(default=None, max_length=50)
