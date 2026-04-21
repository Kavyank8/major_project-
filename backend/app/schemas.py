from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

from .models import JobStatus, JobType


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    name: str | None = None

    class Config:
        from_attributes = True


class InterpolateResponse(BaseModel):
    video_id: str = Field(..., description="Generated video id")
    job_status: JobStatus
    download_url: str | None = Field(None, description="Path to download generated video")
    total_frames: int | None = Field(None, description="Total output frames")
    fps: int | None = Field(None, description="Output frame rate")
    original_frame_count: int | None = Field(None, description="Uploaded source frame count")
    generated_frame_count: int | None = Field(None, description="Stored output frame count")
    uploaded_frames_dir: str | None = Field(None, description="Directory containing uploaded source frames")
    generated_frames_dir: str | None = Field(None, description="Directory containing generated output frames")


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


class FrameSessionCreateResponse(BaseModel):
    session_id: str


class FrameUploadResponse(BaseModel):
    session_id: str
    frame_id: int
    total_frames: int
    reused_existing: bool = False


class FrameSessionStatusResponse(BaseModel):
    session_id: str
    total_frames: int
    can_generate: bool
    frame_names: list[str]
    generated_video_id: str | None
    uploaded_frames_dir: str | None
    generated_frames_dir: str | None
    generated_frame_count: int | None
