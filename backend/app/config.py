import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
STORAGE_DIR = BASE_DIR / "storage"
UPLOAD_DIR = STORAGE_DIR / "uploads"
OUTPUT_DIR = STORAGE_DIR / "outputs"
MODEL_DEVICE = os.getenv("MODEL_DEVICE", "cpu")
MODEL_BACKEND = os.getenv("MODEL_BACKEND", "optical_flow").strip().lower()
RIFE_REPO_DIR = Path(os.getenv("RIFE_REPO_DIR", str(BASE_DIR / "third_party" / "ECCV2022-RIFE")))
RIFE_MODEL_DIR = Path(os.getenv("RIFE_MODEL_DIR", str(BASE_DIR / "weights" / "rife")))
RIFE_STRICT = os.getenv("RIFE_STRICT", "false").strip().lower() in {"1", "true", "yes"}
FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "250"))

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'app.db').as_posix()}")
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
