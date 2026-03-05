import { useMemo, useState } from "react";
import { uploadImages, uploadVideo } from "./api";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

function ResultCard({ result }) {
  if (!result) return null;
  const videoUrl = `${API_BASE}${result.download_url}`;

  return (
    <section className="result">
      <h3>Generated Smooth Video</h3>
      <p>
        Frames: <strong>{result.total_frames}</strong> | FPS: <strong>{result.fps}</strong>
      </p>
      <video controls src={videoUrl} className="player" />
      <a href={videoUrl} className="btn" download>
        Download Video
      </a>
    </section>
  );
}

function ImagesMode({ setError, setLoading, loading, result, setResult }) {
  const [firstImage, setFirstImage] = useState(null);
  const [secondImage, setSecondImage] = useState(null);
  const [intermediateCount, setIntermediateCount] = useState(5);
  const [fps, setFps] = useState(24);

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setResult(null);

    if (!firstImage || !secondImage) {
      setError("Please upload both images.");
      return;
    }

    try {
      setLoading(true);
      const data = await uploadImages({ firstImage, secondImage, intermediateCount, fps, apiBase: API_BASE });
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="card">
      <label>
        First frame image
        <input type="file" accept="image/*" onChange={(e) => setFirstImage(e.target.files?.[0] || null)} />
      </label>
      <label>
        Second frame image
        <input type="file" accept="image/*" onChange={(e) => setSecondImage(e.target.files?.[0] || null)} />
      </label>
      <label>
        Intermediate frames
        <input
          type="number"
          min={1}
          max={60}
          value={intermediateCount}
          onChange={(e) => setIntermediateCount(Number(e.target.value))}
        />
      </label>
      <label>
        Output FPS
        <input type="number" min={1} max={120} value={fps} onChange={(e) => setFps(Number(e.target.value))} />
      </label>
      <button disabled={loading} type="submit" className="btn">
        {loading ? "Processing..." : "Generate Smooth Video"}
      </button>
      <ResultCard result={result} />
    </form>
  );
}

function VideoMode({ setError, setLoading, loading, result, setResult }) {
  const [videoFile, setVideoFile] = useState(null);
  const [intermediateCount, setIntermediateCount] = useState(1);

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setResult(null);

    if (!videoFile) {
      setError("Please upload a video file.");
      return;
    }

    try {
      setLoading(true);
      const data = await uploadVideo({ videoFile, intermediateCount, apiBase: API_BASE });
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="card">
      <label>
        Input video
        <input type="file" accept="video/*" onChange={(e) => setVideoFile(e.target.files?.[0] || null)} />
      </label>
      <label>
        Intermediate frames per gap
        <input
          type="number"
          min={1}
          max={10}
          value={intermediateCount}
          onChange={(e) => setIntermediateCount(Number(e.target.value))}
        />
      </label>
      <button disabled={loading} type="submit" className="btn">
        {loading ? "Processing..." : "Generate Smooth Video"}
      </button>
      <ResultCard result={result} />
    </form>
  );
}

export default function App() {
  const [mode, setMode] = useState("images");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const title = useMemo(() => (mode === "images" ? "Two Images -> Smooth Video" : "Video -> Smoother Video"), [mode]);

  return (
    <main className="page">
      <header>
        <h1>AI Video Frame Interpolation</h1>
        <p>{title}</p>
      </header>

      <div className="tabs">
        <button className={mode === "images" ? "tab active" : "tab"} onClick={() => setMode("images")}>
          Images
        </button>
        <button className={mode === "video" ? "tab active" : "tab"} onClick={() => setMode("video")}>
          Video
        </button>
      </div>

      {mode === "images" ? (
        <ImagesMode
          setError={setError}
          setLoading={setLoading}
          loading={loading}
          result={result}
          setResult={setResult}
        />
      ) : (
        <VideoMode
          setError={setError}
          setLoading={setLoading}
          loading={loading}
          result={result}
          setResult={setResult}
        />
      )}

      {error ? <p className="error">{error}</p> : null}
    </main>
  );
}
