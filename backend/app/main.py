from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import FFMPEG_BIN, MODEL_DEVICE, OUTPUT_DIR, UPLOAD_DIR
from app.schemas import InterpolateResponse
from app.services.frame_pipeline import generate_interpolated_sequence
from app.services.model import FrameInterpolator, read_image_to_rgb_array
from app.services.video_utils import encode_video_with_ffmpeg, extract_frames_from_video, save_frames_as_images
from app.utils.fs import ensure_dir, new_id

app = FastAPI(title="AI Video Frame Interpolation API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ensure_dir(UPLOAD_DIR)
ensure_dir(OUTPUT_DIR)
interpolator = FrameInterpolator(device=MODEL_DEVICE)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/interpolate/images", response_model=InterpolateResponse)
async def interpolate_from_images(
    first_image: UploadFile = File(...),
    second_image: UploadFile = File(...),
    intermediate_count: int = Form(5),
    fps: int = Form(24),
) -> InterpolateResponse:
    if intermediate_count < 1 or intermediate_count > 60:
        raise HTTPException(status_code=400, detail="intermediate_count must be between 1 and 60")
    if fps < 1 or fps > 120:
        raise HTTPException(status_code=400, detail="fps must be between 1 and 120")

    job_id = new_id("img")
    job_upload_dir = ensure_dir(UPLOAD_DIR / job_id)
    job_frames_dir = ensure_dir(OUTPUT_DIR / job_id / "frames")
    output_video = OUTPUT_DIR / job_id / "smooth.mp4"

    first_path = job_upload_dir / first_image.filename
    second_path = job_upload_dir / second_image.filename

    first_path.write_bytes(await first_image.read())
    second_path.write_bytes(await second_image.read())

    try:
        first = read_image_to_rgb_array(str(first_path))
        second = read_image_to_rgb_array(str(second_path))
        frames = generate_interpolated_sequence([first, second], interpolator, intermediate_count)
        save_frames_as_images(frames, job_frames_dir)
        encode_video_with_ffmpeg(job_frames_dir, output_video, fps=fps, ffmpeg_bin=FFMPEG_BIN)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return InterpolateResponse(
        video_id=job_id,
        download_url=f"/api/download/{job_id}",
        total_frames=len(frames),
        fps=fps,
    )


@app.post("/api/interpolate/video", response_model=InterpolateResponse)
async def interpolate_from_video(
    video_file: UploadFile = File(...),
    intermediate_count: int = Form(1),
) -> InterpolateResponse:
    if intermediate_count < 1 or intermediate_count > 10:
        raise HTTPException(status_code=400, detail="intermediate_count must be between 1 and 10")

    job_id = new_id("vid")
    job_upload_dir = ensure_dir(UPLOAD_DIR / job_id)
    job_frames_dir = ensure_dir(OUTPUT_DIR / job_id / "frames")
    output_video = OUTPUT_DIR / job_id / "smooth.mp4"

    video_path = job_upload_dir / (video_file.filename or "input.mp4")
    video_path.write_bytes(await video_file.read())

    try:
        source_frames, src_fps = extract_frames_from_video(video_path)
        frames = generate_interpolated_sequence(source_frames, interpolator, intermediate_count)
        # Increase fps to keep duration near original while adding frames.
        out_fps = src_fps * (intermediate_count + 1)
        save_frames_as_images(frames, job_frames_dir)
        encode_video_with_ffmpeg(job_frames_dir, output_video, fps=out_fps, ffmpeg_bin=FFMPEG_BIN)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return InterpolateResponse(
        video_id=job_id,
        download_url=f"/api/download/{job_id}",
        total_frames=len(frames),
        fps=out_fps,
    )


@app.get("/api/download/{video_id}")
def download_video(video_id: str) -> FileResponse:
    video_path = OUTPUT_DIR / video_id / "smooth.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(path=video_path, media_type="video/mp4", filename=f"{video_id}.mp4")
