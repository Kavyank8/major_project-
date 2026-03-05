from pydantic import BaseModel, Field


class InterpolateResponse(BaseModel):
    video_id: str = Field(..., description="Generated video id")
    download_url: str = Field(..., description="Path to download generated video")
    total_frames: int = Field(..., description="Total output frames")
    fps: int = Field(..., description="Output frame rate")
