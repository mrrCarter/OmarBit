import datetime
from typing import Literal

from pydantic import BaseModel, Field

# --- Feature Flags ---


class FeatureFlagResponse(BaseModel):
    id: str
    key: str
    enabled: bool
    rollout_percent: int
    rules_json: dict
    updated_at: datetime.datetime


class FeatureFlagUpdate(BaseModel):
    enabled: bool | None = None
    rollout_percent: int | None = Field(None, ge=0, le=100)
    rules_json: dict | None = None


# --- AI Profiles ---

ProviderType = Literal["claude", "gpt", "grok", "gemini"]
StyleType = Literal["aggressive", "positional", "balanced", "chaotic", "defensive"]


class AIProfileCreate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=100)
    provider: ProviderType
    api_key: str = Field(..., min_length=1)
    style: StyleType = "balanced"


class AIProfileResponse(BaseModel):
    id: str
    display_name: str
    provider: ProviderType
    style: str
    active: bool
    created_at: datetime.datetime


class AIProfileListResponse(BaseModel):
    profiles: list[AIProfileResponse]


# --- Error Envelope ---


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail
    requestId: str
    timestamp: str
