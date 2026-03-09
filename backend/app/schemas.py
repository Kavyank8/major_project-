from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

from app.models import JobStatus, JobType


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class InterpolateResponse(BaseModel):
    video_id: str = Field(..., description="Generated video id")
    job_status: JobStatus
    download_url: str | None = Field(None, description="Path to download generated video")
    total_frames: int | None = Field(None, description="Total output frames")
    fps: int | None = Field(None, description="Output frame rate")


class JobResponse(BaseModel):
    id: str
    job_type: JobType
    status: JobStatus
    intermediate_count: int
    fps: int
    total_frames: int | None
    download_url: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    class Config:
        from_attributes = True
