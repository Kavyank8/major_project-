# AI Video Frame Interpolation (React + FastAPI)

This project implements the architecture you requested:

React Frontend
-> FastAPI Backend
-> PyTorch Frame Interpolation Model
-> OpenCV + FFmpeg
-> Generated Smooth Video

## Workflows

### 1) Two Images to Smooth Video
1. User uploads two frames.
2. Backend loads the two images.
3. PyTorch interpolation model generates intermediate frames.
4. OpenCV writes frame sequence.
5. FFmpeg encodes frames into MP4.
6. User downloads smooth video.

### 2) Video to Smoother Video
1. User uploads a video.
2. Backend extracts frames using OpenCV.
3. Model generates intermediate frames between every adjacent pair.
4. OpenCV writes output frame sequence.
5. FFmpeg encodes smooth MP4.
6. User downloads smooth video.

## Project Structure

```text
backend/
  app/
    main.py
    config.py
    schemas.py
    services/
      model.py
      frame_pipeline.py
      video_utils.py
    utils/
      fs.py
  requirements.txt
  .env.example
frontend/
  src/
    App.jsx
    api.js
    main.jsx
    styles.css
  package.json
  vite.config.js
README.md
```

## Backend Setup (FastAPI)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Health check:

- `GET http://127.0.0.1:8000/health`

## Frontend Setup (React + Vite)

```powershell
cd frontend
npm install
npm run dev
```

Open:

- `http://127.0.0.1:5173`

If backend is on another host/port, set:

- `VITE_API_BASE=http://127.0.0.1:8000`

## API Endpoints

### POST `/api/interpolate/images`
Form fields:
- `first_image`: file
- `second_image`: file
- `intermediate_count`: int (1-60)
- `fps`: int (1-120)

Returns:
- `video_id`
- `download_url`
- `total_frames`
- `fps`

### POST `/api/interpolate/video`
Form fields:
- `video_file`: file
- `intermediate_count`: int (1-10)

Returns same shape as above.

### GET `/api/download/{video_id}`
Downloads the generated MP4.

## Replacing Placeholder Model

Current `backend/app/services/model.py` uses linear blend as a placeholder so the system runs end-to-end. Replace `FrameInterpolator.interpolate(...)` with your trained model inference (for example RIFE/FILM) while keeping the same method signature.

## Notes

- FFmpeg must be installed and accessible in PATH.
- Output videos are stored under `backend/storage/outputs/`.
- Uploaded files are stored under `backend/storage/uploads/`.
