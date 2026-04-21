# Task: Run Frontend and Backend Servers

## Plan Steps:
1. [ ] Backend setup: cd backend && python -m venv .venv && .\.venv\Scripts\Activate.ps1 && pip install -r requirements.txt
2. [ ] Start backend: cd backend && .\.venv\Scripts\Activate.ps1 && uvicorn app.main:app --reload --port 8000
3. [ ] Frontend deps: cd frontend && npm install
4. [ ] Start frontend: cd frontend && npm run dev

Verify:
- Backend: curl http://127.0.0.1:8000/health or browser
- Frontend: http://127.0.0.1:5173

