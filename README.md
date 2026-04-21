# AI Video Frame Interpolation (React + FastAPI)

React Frontend -> FastAPI Backend -> Interpolator (Optical Flow or RIFE) -> OpenCV + FFmpeg -> Smooth Video

## Current status

- Single-frame session workflow: upload frames one-by-one, store in DB, generate after minimum 2 frames
- DB-backed frame sessions and frame uploads
- Public frame-session APIs + existing auth/job APIs
- Pluggable interpolation backend:
  - `optical_flow` (default fallback)
  - `rife` (real deep model, if repo + weights are available)

## Backend setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Health endpoint now returns backend:

- `GET http://127.0.0.1:8000/health`
- Example: `{ "status": "ok", "backend": "rife" }`

## Frontend setup

```powershell
cd frontend
npm install
npm run dev
```

Open: `http://127.0.0.1:5173`

## One-by-one frame upload flow

1. `POST /api/public/frame-sessions` -> create session
2. `POST /api/public/frame-sessions/{session_id}/frame` -> upload one frame
3. `GET /api/public/frame-sessions/{session_id}` -> check count (`can_generate` true when >= 2)
4. `POST /api/public/frame-sessions/{session_id}/generate` -> generate final smooth video
5. `GET /api/download/{video_id}` -> download result

## Enable real RIFE backend

By default, backend uses `optical_flow` so app runs without extra model files.

To enable RIFE:

1. Clone RIFE repository under project root:
```powershell
cd "C:\Users\kkavy\Documents\New project"
mkdir third_party -Force
cd third_party
git clone https://github.com/hzwer/ECCV2022-RIFE.git
```

2. Place pretrained RIFE model files in:
- `C:\Users\kkavy\Documents\New project\weights\rife`

3. Configure backend env (or set system env vars):
- `MODEL_BACKEND=rife`
- `RIFE_REPO_DIR=C:\Users\kkavy\Documents\New project\third_party\ECCV2022-RIFE`
- `RIFE_MODEL_DIR=C:\Users\kkavy\Documents\New project\weights\rife`
- `RIFE_STRICT=true` (optional: fail startup if RIFE unavailable)

4. Restart backend and verify:
- `GET /health` should show `"backend": "rife"`

If RIFE fails to load and `RIFE_STRICT=false`, backend automatically falls back to `optical_flow` and prints warning logs.

## Notes

- FFmpeg must be available in PATH.
- SQLite is used locally (`backend/app.db`).
- For production: PostgreSQL + Redis worker queue recommended.
