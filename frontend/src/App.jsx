import { useEffect, useState } from "react";
import {
  clearStoredToken,
  createFrameSession,
  generateFromSession,
  getCurrentUser,
  getFrameSessionStatus,
  getStoredToken,
  login,
  register,
  uploadSingleFrame,
} from "./api";

const API_BASE = "";
const GUEST_EMAIL = "guest@framemind.app";
const GUEST_PASSWORD = "guest_pass_123";
const GUEST_NAME = "Guest";

function AppButton({ children, variant = "primary", onClick, disabled = false, type = "button" }) {
  return (
    <button type={type} className={`app-btn ${variant}`} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  );
}

function DashboardMetric({ label, value, tone = "default" }) {
  return (
    <div className={`metric-card ${tone}`}>
      <span className="metric-label">{label}</span>
      <strong className="metric-value">{value}</strong>
    </div>
  );
}

function StagePill({ label, state }) {
  return <div className={`stage-pill ${state}`}>{label}</div>;
}

function UploadedFramesList({ frames }) {
  if (!frames.length) {
    return <p className="empty-copy">No frames selected yet. Add at least two frames to start.</p>;
  }
  return (
    <div className="uploaded-list">
      {frames.map((file, index) => (
        <div key={`${file.name}-${index}`} className="uploaded-row">
          <span className="uploaded-index">{String(index + 1).padStart(2, "0")}</span>
          <div>
            <p className="uploaded-name">{file.name}</p>
            <p className="uploaded-meta">{Math.max(1, Math.round(file.size / 1024))} KB</p>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function App() {
  const [screen, setScreen] = useState("upload");
  const [sessionId, setSessionId] = useState("");
  const [selectedFrames, setSelectedFrames] = useState([]);
  const [frameCount, setFrameCount] = useState(0);
  const [frameNames, setFrameNames] = useState([]);
  const [intermediateCount, setIntermediateCount] = useState(3);
  const [fps, setFps] = useState(24);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [ready, setReady] = useState(false);
  const [statusText, setStatusText] = useState("Pick your source frames to begin.");

  // Auto-authenticate as guest on load
  useEffect(() => {
    async function autoAuth() {
      // If we already have a valid token, use it
      if (getStoredToken()) {
        try {
          await getCurrentUser({ apiBase: API_BASE });
          setReady(true);
          return;
        } catch {
          clearStoredToken();
        }
      }
      // Try login first, then register if not exists
      try {
        await login({ apiBase: API_BASE, email: GUEST_EMAIL, password: GUEST_PASSWORD });
      } catch {
        try {
          await register({ apiBase: API_BASE, email: GUEST_EMAIL, password: GUEST_PASSWORD, name: GUEST_NAME });
        } catch {
          // ignore — token may already be set
        }
      }
      setReady(true);
    }
    autoAuth();
  }, []);

  function mergeFrames(existingFrames, incomingFrames) {
    const merged = [...existingFrames];
    for (const frame of incomingFrames) {
      const alreadyAdded = merged.some(
        (f) => f.name === frame.name && f.size === frame.size && f.lastModified === frame.lastModified
      );
      if (!alreadyAdded) merged.push(frame);
    }
    return merged;
  }

  async function ensureSession() {
    if (sessionId) return sessionId;
    const created = await createFrameSession({ apiBase: API_BASE });
    setSessionId(created.session_id);
    return created.session_id;
  }

  async function uploadAndGenerate() {
    setError("");
    if (selectedFrames.length < 2) {
      setError("Please select at least 2 frames.");
      return;
    }
    try {
      setLoading(true);
      setScreen("processing");
      const sid = await ensureSession();
      setStatusText("Uploading frames...");
      for (const frame of selectedFrames) {
        await uploadSingleFrame({ apiBase: API_BASE, sessionId: sid, frame });
      }
      const status = await getFrameSessionStatus({ apiBase: API_BASE, sessionId: sid });
      setFrameCount(status.total_frames);
      setFrameNames(status.frame_names);
      setStatusText("Generating smooth video...");
      const data = await generateFromSession({ apiBase: API_BASE, sessionId: sid, intermediateCount, fps });
      setResult(data);
      setScreen("results");
    } catch (err) {
      setError(err.message);
      setScreen("upload");
    } finally {
      setLoading(false);
    }
  }

  function resetSession() {
    setScreen("upload");
    setSessionId("");
    setSelectedFrames([]);
    setFrameCount(0);
    setFrameNames([]);
    setResult(null);
    setError("");
    setStatusText("Pick your source frames to begin.");
  }

  useEffect(() => {
    if (!ready || screen !== "upload" || loading || selectedFrames.length < 2) return;
    uploadAndGenerate();
  }, [selectedFrames, ready]);

  if (!ready) return null;

  const videoUrl = result?.download_url ? `${API_BASE}${result.download_url}` : "";
  const generatedCount = result?.generated_frame_count ?? result?.total_frames ?? 0;
  const originalCount = result?.original_frame_count ?? frameCount;
  const motionGain = originalCount > 0 ? `${Math.max(1, Math.round(generatedCount / originalCount))}x` : "-";

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="logo">FrameMind AI</div>
      </header>

      <main className="dashboard">
        {screen === "upload" && (
          <section className="workspace-grid">
            <article className="panel upload-panel">
              <div className="panel-head">
                <h2>Upload Frames</h2>
                <div className="mini-status ready">Ready</div>
              </div>

              <div className="stage-row">
                <StagePill label="Frames Added" state={selectedFrames.length ? "done" : "idle"} />
                <StagePill label="Interpolation" state={selectedFrames.length >= 2 ? "active" : "idle"} />
                <StagePill label="Video Render" state="idle" />
              </div>

              <label className="upload-dropzone">
                <input
                  type="file"
                  accept="image/png,image/jpeg"
                  multiple
                  onChange={(e) => {
                    const incoming = Array.from(e.target.files || []);
                    setSelectedFrames((cur) => mergeFrames(cur, incoming));
                    e.target.value = "";
                  }}
                />
                <div className="drop-illustration">
                  <span className="drop-square first" />
                  <span className="drop-square second" />
                  <span className="drop-square third" />
                </div>
                <p className="drop-title">
                  {selectedFrames.length ? `${selectedFrames.length} frames queued` : "Drop frames or click to browse"}
                </p>
                <span className="drop-copy">PNG and JPG supported</span>
              </label>

              {error ? <p className="error-inline">{error}</p> : null}
            </article>

            <article className="panel right-stack">
              <section className="side-section">
                <h3>Settings</h3>
                <label>
                  Intermediate frames per gap
                  <input
                    type="number" min="1" max="60" value={intermediateCount}
                    onChange={(e) => setIntermediateCount(Number(e.target.value))}
                  />
                </label>
                <label>
                  Output FPS
                  <input
                    type="number" min="1" max="60" value={fps}
                    onChange={(e) => setFps(Number(e.target.value))}
                  />
                </label>
              </section>

              <section className="side-section">
                <h3>Selected Frames</h3>
                <UploadedFramesList frames={selectedFrames} />
              </section>

              <div className="hero-summary compact">
                <DashboardMetric label="Source Frames" value={selectedFrames.length} />
                <DashboardMetric label="In-Between" value={intermediateCount} tone="accent" />
                <DashboardMetric label="FPS" value={fps} />
              </div>
            </article>
          </section>
        )}

        {screen === "processing" && (
          <section className="workspace-grid processing-layout">
            <article className="panel processing-panel">
              <div className="loader-ring" />
              <h2>Generating Video</h2>
              <p className="hero-copy">{statusText}</p>
              <div className="stage-row">
                <StagePill label="Frames Uploaded" state="done" />
                <StagePill label="Interpolation" state="active" />
                <StagePill label="Encoding" state="active" />
              </div>
            </article>
          </section>
        )}

        {screen === "results" && (
          <section className="workspace-grid">
            <article className="panel results-panel">
              <div className="panel-head">
                <h2>Result</h2>
                <div className="mini-status complete">Done</div>
              </div>

              <div className="hero-summary compact">
                <DashboardMetric label="Source Frames" value={originalCount} />
                <DashboardMetric label="Generated Frames" value={generatedCount} tone="accent" />
                <DashboardMetric label="Motion Gain" value={motionGain} />
              </div>

              <div className="video-shell">
                {videoUrl ? <video key={videoUrl} className="media-preview" controls autoPlay src={videoUrl} /> : null}
              </div>
            </article>

            <article className="panel right-stack">
              <section className="side-section cta-panel">
                {videoUrl ? (
                  <a className="app-btn primary full-width" href={videoUrl} download>
                    Download Video
                  </a>
                ) : null}
                <AppButton variant="ghost" onClick={resetSession}>
                  New Render
                </AppButton>
              </section>

              <section className="side-section">
                <h3>Frames</h3>
                <div className="tag-cluster">
                  {frameNames.map((name, idx) => (
                    <span key={`${name}-${idx}`} className="tag-pill">
                      {idx + 1}. {name}
                    </span>
                  ))}
                </div>
              </section>
            </article>
          </section>
        )}
      </main>
    </div>
  );
}
