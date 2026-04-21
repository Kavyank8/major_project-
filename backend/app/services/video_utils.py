from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List

import cv2
import numpy as np


def extract_frames_from_video(video_path: Path) -> tuple[list[np.ndarray], int]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError("Could not open uploaded video.")

    fps = int(cap.get(cv2.CAP_PROP_FPS)) or 24
    frames: List[np.ndarray] = []

    while True:
        ok, frame_bgr = cap.read()
        if not ok:
            break
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        frames.append(frame_rgb)

    cap.release()

    if len(frames) < 2:
        raise ValueError("Video must contain at least 2 frames.")

    return frames, fps


def save_frames_as_images(frames: list[np.ndarray], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for idx, frame_rgb in enumerate(frames):
        if frame_rgb.size == 0:
            raise ValueError("Generated frame is empty and cannot be encoded.")
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        ok = cv2.imwrite(str(output_dir / f"frame_{idx:06d}.png"), frame_bgr)
        if not ok:
            raise RuntimeError(f"Failed to write generated frame {idx}.")


def encode_video_with_ffmpeg(frames_dir: Path, output_path: Path, fps: int, ffmpeg_bin: str = "ffmpeg") -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin,
        "-y",
        "-framerate",
        str(fps),
        "-start_number",
        "0",
        "-i",
        str(frames_dir / "frame_%06d.png"),
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-preset",
        "fast",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr[-1000:]}")
