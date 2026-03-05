import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
STORAGE_DIR = BASE_DIR / "storage"
UPLOAD_DIR = STORAGE_DIR / "uploads"
OUTPUT_DIR = STORAGE_DIR / "outputs"
MODEL_DEVICE = os.getenv("MODEL_DEVICE", "cpu")
FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "250"))
