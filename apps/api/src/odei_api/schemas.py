"""Validated control-plane request and response models."""
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


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
