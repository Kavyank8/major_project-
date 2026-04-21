from __future__ import annotations

from datetime import datetime
import hashlib
from pathlib import Path
from typing import Dict

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import text
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from .auth import create_access_token, get_current_user, hash_password, verify_password
from .config import (
    FFMPEG_BIN,
    MODEL_BACKEND,
    MODEL_DEVICE,
    OUTPUT_DIR,
    RIFE_MODEL_DIR,
    RIFE_REPO_DIR,
    RIFE_STRICT,
    UPLOAD_DIR,
)
from .database import Base, engine, get_db
from .models import FrameSession, FrameUpload, Job, JobStatus, JobType, User
from .schemas import (
    FrameSessionCreateResponse,
    FrameSessionStatusResponse,
    FrameUploadResponse,
    InterpolateResponse,
    JobResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from .services.frame_pipeline import generate_interpolated_sequence
from .services.model import FrameInterpolator, read_image_to_rgb_array
from .services.video_utils import encode_video_with_ffmpeg, extract_frames_from_video, save_frames_as_images
from .utils.fs import ensure_dir, new_id

app = FastAPI(title="AI Video Frame Interpolation API", version="0.5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ensure_dir(UPLOAD_DIR)
ensure_dir(OUTPUT_DIR)
interpolator = FrameInterpolator(
    device=MODEL_DEVICE,
    backend=MODEL_BACKEND,
    rife_repo_dir=RIFE_REPO_DIR,
    rife_model_dir=RIFE_MODEL_DIR,
    strict=RIFE_STRICT,
)
if interpolator.warning:
    print(interpolator.warning)
print(f"Interpolation backend: {interpolator.backend}")

# In-memory interpolation cache: maps cache_key -> output_video_id
# cache_key = sha256(sorted frame content hashes + intermediate_count + fps)
_interpolation_cache: Dict[str, str] = {}


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        frame_session_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(frame_sessions)")).fetchall()
        }
        if "user_id" not in frame_session_columns:
            connection.execute(text("ALTER TABLE frame_sessions ADD COLUMN user_id INTEGER"))
        frame_upload_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(frame_uploads)")).fetchall()
        }
        if "content_hash" not in frame_upload_columns:
            connection.execute(text("ALTER TABLE frame_uploads ADD COLUMN content_hash VARCHAR(64)"))
        user_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(users)")).fetchall()
        }
        if "name" not in user_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN name VARCHAR(255)"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "backend": interpolator.backend}


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="http://127.0.0.1:5173", status_code=307)


@app.post("/api/auth/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    exists = db.query(User).filter(User.email == payload.email).first()
    if exists:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(email=payload.email, name=payload.name, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    return TokenResponse(access_token=create_access_token(user.id))


@app.post("/api/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return TokenResponse(access_token=create_access_token(user.id))


@app.get("/api/auth/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


def _job_to_response(job: Job) -> JobResponse:
    download_url = f"/api/download/{job.id}" if job.status == JobStatus.COMPLETED else None
    return JobResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        intermediate_count=job.intermediate_count,
        fps=job.fps,
        total_frames=job.total_frames,
        download_url=download_url,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def _process_image_job(job: Job) -> None:
    first = read_image_to_rgb_array(job.input_path_a)
    second = read_image_to_rgb_array(job.input_path_b)
    frames = generate_interpolated_sequence([first, second], interpolator, job.intermediate_count)

    job_frames_dir = ensure_dir(OUTPUT_DIR / job.id / "frames")
    output_video = OUTPUT_DIR / job.id / "smooth.mp4"
    save_frames_as_images(frames, job_frames_dir)
    encode_video_with_ffmpeg(job_frames_dir, output_video, fps=job.fps, ffmpeg_bin=FFMPEG_BIN)

    job.output_path = str(output_video)
    job.total_frames = len(frames)


def _process_video_job(job: Job) -> None:
    source_frames, src_fps = extract_frames_from_video(Path(job.input_path_a))
    frames = generate_interpolated_sequence(source_frames, interpolator, job.intermediate_count)

    out_fps = src_fps * (job.intermediate_count + 1)
    job.fps = out_fps

    job_frames_dir = ensure_dir(OUTPUT_DIR / job.id / "frames")
    output_video = OUTPUT_DIR / job.id / "smooth.mp4"
    save_frames_as_images(frames, job_frames_dir)
    encode_video_with_ffmpeg(job_frames_dir, output_video, fps=out_fps, ffmpeg_bin=FFMPEG_BIN)

    job.output_path = str(output_video)
    job.total_frames = len(frames)


def _run_job(job: Job, db: Session) -> None:
    job.status = JobStatus.PROCESSING
    job.started_at = datetime.utcnow()
    job.error_message = None
    db.commit()

    try:
        if job.job_type == JobType.IMAGES:
            _process_image_job(job)
        else:
            _process_video_job(job)
        job.status = JobStatus.COMPLETED
        job.finished_at = datetime.utcnow()
        db.commit()
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error_message = str(exc)
        job.finished_at = datetime.utcnow()
        db.commit()
        raise


@app.post("/api/public/frame-sessions", response_model=FrameSessionCreateResponse)
def create_frame_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FrameSessionCreateResponse:
    session_id = new_id("session")
    session = FrameSession(id=session_id, user_id=current_user.id)
    db.add(session)
    db.commit()
    return FrameSessionCreateResponse(session_id=session_id)


@app.post("/api/public/frame-sessions/{session_id}/frame", response_model=FrameUploadResponse)
async def upload_frame_to_session(
    session_id: str,
    frame: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FrameUploadResponse:
    session = db.get(FrameSession, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Frame session not found")

    session_dir = ensure_dir(UPLOAD_DIR / session_id)
    existing_count = db.query(FrameUpload).filter(FrameUpload.session_id == session_id).count()
    original_name = frame.filename or "frame.png"
    filename = f"{existing_count:04d}_{original_name}"
    payload = await frame.read()
    content_hash = hashlib.sha256(payload).hexdigest()

    existing_upload = (
        db.query(FrameUpload)
        .join(FrameSession, FrameUpload.session_id == FrameSession.id)
        .filter(
            FrameSession.user_id == current_user.id,
            FrameUpload.content_hash == content_hash,
        )
        .order_by(FrameUpload.created_at.desc())
        .first()
    )

    reused_existing = existing_upload is not None and Path(existing_upload.file_path).exists()
    if reused_existing:
        save_path = Path(existing_upload.file_path)
    else:
        save_path = session_dir / filename
        save_path.write_bytes(payload)

    frame_row = FrameUpload(
        session_id=session_id,
        sequence_index=existing_count,
        filename=filename,
        file_path=str(save_path),
        content_hash=content_hash,
    )
    db.add(frame_row)
    db.commit()
    db.refresh(frame_row)

    total_frames = db.query(FrameUpload).filter(FrameUpload.session_id == session_id).count()
    return FrameUploadResponse(
        session_id=session_id,
        frame_id=frame_row.id,
        total_frames=total_frames,
        reused_existing=reused_existing,
    )


@app.get("/api/public/frame-sessions/{session_id}", response_model=FrameSessionStatusResponse)
def frame_session_status(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FrameSessionStatusResponse:
    session = db.get(FrameSession, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Frame session not found")

    frames = (
        db.query(FrameUpload)
        .filter(FrameUpload.session_id == session_id)
        .order_by(FrameUpload.sequence_index.asc())
        .all()
    )

    uploaded_frames_dir = str(UPLOAD_DIR / session_id)
    generated_frames_dir = None
    generated_frame_count = None
    if session.output_video_id:
        candidate_dir = OUTPUT_DIR / session.output_video_id / "frames"
        if candidate_dir.exists():
            generated_frames_dir = str(candidate_dir)
            generated_frame_count = len(list(candidate_dir.glob("frame_*.png")))

    return FrameSessionStatusResponse(
        session_id=session_id,
        total_frames=len(frames),
        can_generate=len(frames) >= 2,
        frame_names=[f.filename for f in frames],
        generated_video_id=session.output_video_id,
        uploaded_frames_dir=uploaded_frames_dir,
        generated_frames_dir=generated_frames_dir,
        generated_frame_count=generated_frame_count,
    )


@app.post("/api/public/frame-sessions/{session_id}/generate", response_model=InterpolateResponse)
def generate_from_frame_session(
    session_id: str,
    intermediate_count: int = Form(7),
    fps: int = Form(12),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterpolateResponse:
    if intermediate_count < 1 or intermediate_count > 60:
        raise HTTPException(status_code=400, detail="intermediate_count must be between 1 and 60")
    if fps < 1 or fps > 120:
        raise HTTPException(status_code=400, detail="fps must be between 1 and 120")

    session = db.get(FrameSession, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Frame session not found")

    frames = (
        db.query(FrameUpload)
        .filter(FrameUpload.session_id == session_id)
        .order_by(FrameUpload.sequence_index.asc())
        .all()
    )
    if len(frames) < 2:
        raise HTTPException(status_code=400, detail="Upload at least 2 frames before generating video")

    # Build cache key from frame content hashes + params
    frame_hashes = [f.content_hash or "" for f in frames]
    cache_raw = "|".join(frame_hashes) + f"|ic={intermediate_count}|fps={fps}"
    cache_key = hashlib.sha256(cache_raw.encode()).hexdigest()

    # Check cache: if same frames+params were processed before, reuse the output
    cached_video_id = _interpolation_cache.get(cache_key)
    if cached_video_id:
        cached_video = OUTPUT_DIR / cached_video_id / "smooth.mp4"
        cached_frames_dir = OUTPUT_DIR / cached_video_id / "frames"
        if cached_video.exists():
            cached_frame_count = len(list(cached_frames_dir.glob("frame_*.png"))) if cached_frames_dir.exists() else 0
            session.output_video_id = cached_video_id
            db.commit()
            return InterpolateResponse(
                video_id=cached_video_id,
                job_status=JobStatus.COMPLETED,
                download_url=f"/api/download/{cached_video_id}",
                total_frames=cached_frame_count,
                fps=fps,
                original_frame_count=len(frames),
                generated_frame_count=cached_frame_count,
                uploaded_frames_dir=str(UPLOAD_DIR / session_id),
                generated_frames_dir=str(cached_frames_dir),
            )

    output_video_id = new_id("frames")
    output_frames_dir = ensure_dir(OUTPUT_DIR / output_video_id / "frames")
    output_video = OUTPUT_DIR / output_video_id / "smooth.mp4"

    try:
        source_frames = [read_image_to_rgb_array(f.file_path) for f in frames]
        output_frames = generate_interpolated_sequence(source_frames, interpolator, intermediate_count)
        save_frames_as_images(output_frames, output_frames_dir)
        encode_video_with_ffmpeg(output_frames_dir, output_video, fps=fps, ffmpeg_bin=FFMPEG_BIN)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Store in cache
    _interpolation_cache[cache_key] = output_video_id

    session.output_video_id = output_video_id
    db.commit()

    return InterpolateResponse(
        video_id=output_video_id,
        job_status=JobStatus.COMPLETED,
        download_url=f"/api/download/{output_video_id}",
        total_frames=len(output_frames),
        fps=fps,
        original_frame_count=len(frames),
        generated_frame_count=len(output_frames),
        uploaded_frames_dir=str(UPLOAD_DIR / session_id),
        generated_frames_dir=str(output_frames_dir),
    )


@app.post("/api/interpolate/images", response_model=InterpolateResponse)
async def interpolate_from_images(
    first_image: UploadFile = File(...),
    second_image: UploadFile = File(...),
    intermediate_count: int = Form(30),
    fps: int = Form(12),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterpolateResponse:
    if intermediate_count < 1 or intermediate_count > 120:
        raise HTTPException(status_code=400, detail="intermediate_count must be between 1 and 120")
    if fps < 1 or fps > 120:
        raise HTTPException(status_code=400, detail="fps must be between 1 and 120")

    job_id = new_id("img")
    job_upload_dir = ensure_dir(UPLOAD_DIR / job_id)

    first_name = first_image.filename or "first.png"
    second_name = second_image.filename or "second.png"

    first_path = job_upload_dir / first_name
    second_path = job_upload_dir / second_name

    first_path.write_bytes(await first_image.read())
    second_path.write_bytes(await second_image.read())

    job = Job(
        id=job_id,
        user_id=current_user.id,
        job_type=JobType.IMAGES,
        status=JobStatus.QUEUED,
        input_path_a=str(first_path),
        input_path_b=str(second_path),
        intermediate_count=intermediate_count,
        fps=fps,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        _run_job(job, db)
    except Exception:
        pass

    return InterpolateResponse(
        video_id=job.id,
        job_status=job.status,
        download_url=f"/api/download/{job.id}" if job.status == JobStatus.COMPLETED else None,
        total_frames=job.total_frames,
        fps=job.fps,
        original_frame_count=2,
        generated_frame_count=job.total_frames,
        uploaded_frames_dir=str(job_upload_dir),
        generated_frames_dir=str(OUTPUT_DIR / job.id / "frames") if job.total_frames else None,
    )


@app.post("/api/interpolate/video", response_model=InterpolateResponse)
async def interpolate_from_video(
    video_file: UploadFile = File(...),
    intermediate_count: int = Form(1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterpolateResponse:
    if intermediate_count < 1 or intermediate_count > 10:
        raise HTTPException(status_code=400, detail="intermediate_count must be between 1 and 10")

    job_id = new_id("vid")
    job_upload_dir = ensure_dir(UPLOAD_DIR / job_id)

    input_name = video_file.filename or "input.mp4"
    video_path = job_upload_dir / input_name
    video_path.write_bytes(await video_file.read())

    job = Job(
        id=job_id,
        user_id=current_user.id,
        job_type=JobType.VIDEO,
        status=JobStatus.QUEUED,
        input_path_a=str(video_path),
        intermediate_count=intermediate_count,
        fps=24,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        _run_job(job, db)
    except Exception:
        pass

    return InterpolateResponse(
        video_id=job.id,
        job_status=job.status,
        download_url=f"/api/download/{job.id}" if job.status == JobStatus.COMPLETED else None,
        total_frames=job.total_frames,
        fps=job.fps,
        generated_frame_count=job.total_frames,
        uploaded_frames_dir=str(job_upload_dir),
        generated_frames_dir=str(OUTPUT_DIR / job.id / "frames") if job.total_frames else None,
    )


@app.get("/api/jobs", response_model=list[JobResponse])
def list_jobs(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[JobResponse]:
    jobs = (
        db.query(Job)
        .filter(Job.user_id == current_user.id)
        .order_by(desc(Job.created_at))
        .limit(100)
        .all()
    )
    return [_job_to_response(job) for job in jobs]


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> JobResponse:
    job = db.get(Job, job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_response(job)


@app.post("/api/jobs/{job_id}/retry", response_model=JobResponse)
def retry_job(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> JobResponse:
    job = db.get(Job, job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.input_path_a or (job.job_type == JobType.IMAGES and not job.input_path_b):
        raise HTTPException(status_code=400, detail="Input files not available for retry")

    job.status = JobStatus.QUEUED
    job.output_path = None
    job.total_frames = None
    job.error_message = None
    job.started_at = None
    job.finished_at = None
    db.commit()

    try:
        _run_job(job, db)
    except Exception:
        pass

    return _job_to_response(job)


@app.get("/api/analytics")
def analytics(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, int]:
    rows = (
        db.query(Job.status, func.count(Job.id))
        .filter(Job.user_id == current_user.id)
        .group_by(Job.status)
        .all()
    )
    by_status = {status.value: count for status, count in rows}
    total_frames = (
        db.query(func.coalesce(func.sum(Job.total_frames), 0))
        .filter(Job.user_id == current_user.id, Job.status == JobStatus.COMPLETED)
        .scalar()
    )
    return {
        "total_jobs": int(sum(by_status.values())),
        "queued_jobs": int(by_status.get(JobStatus.QUEUED.value, 0)),
        "processing_jobs": int(by_status.get(JobStatus.PROCESSING.value, 0)),
        "completed_jobs": int(by_status.get(JobStatus.COMPLETED.value, 0)),
        "failed_jobs": int(by_status.get(JobStatus.FAILED.value, 0)),
        "total_generated_frames": int(total_frames or 0),
    }


@app.get("/api/billing")
def billing(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, float]:
    # Simple usage-based estimate. Replace with Stripe or your billing provider later.
    total_frames = (
        db.query(func.coalesce(func.sum(Job.total_frames), 0))
        .filter(Job.user_id == current_user.id, Job.status == JobStatus.COMPLETED)
        .scalar()
    )
    frame_count = int(total_frames or 0)
    rate_per_1000_frames = 0.25
    estimated_usd = round((frame_count / 1000.0) * rate_per_1000_frames, 4)
    return {
        "total_generated_frames": frame_count,
        "rate_per_1000_frames_usd": rate_per_1000_frames,
        "estimated_cost_usd": estimated_usd,
    }


@app.get("/api/download/{video_id}")
def download_video(video_id: str) -> FileResponse:
    video_path = OUTPUT_DIR / video_id / "smooth.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(path=video_path, media_type="video/mp4", filename=f"{video_id}.mp4")
