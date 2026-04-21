from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image


class OpticalFlowInterpolator:
    """Fallback interpolation using optical flow + blending."""

    def interpolate(self, frame_a: np.ndarray, frame_b: np.ndarray, t: float) -> np.ndarray:
        if frame_a.shape != frame_b.shape:
            raise ValueError("Input frames must have the same shape")

        a_bgr = cv2.cvtColor(frame_a, cv2.COLOR_RGB2BGR)
        b_bgr = cv2.cvtColor(frame_b, cv2.COLOR_RGB2BGR)

        a_gray = cv2.cvtColor(a_bgr, cv2.COLOR_BGR2GRAY)
        b_gray = cv2.cvtColor(b_bgr, cv2.COLOR_BGR2GRAY)

        flow_ab = cv2.calcOpticalFlowFarneback(a_gray, b_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        flow_ba = cv2.calcOpticalFlowFarneback(b_gray, a_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)

        h, w = a_gray.shape
        grid_x, grid_y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))

        map_ax = grid_x + flow_ab[..., 0] * t
        map_ay = grid_y + flow_ab[..., 1] * t
        map_bx = grid_x + flow_ba[..., 0] * (1.0 - t)
        map_by = grid_y + flow_ba[..., 1] * (1.0 - t)

        warp_a = cv2.remap(a_bgr, map_ax, map_ay, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        warp_b = cv2.remap(b_bgr, map_bx, map_by, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

        out = cv2.addWeighted(warp_a, 1.0 - t, warp_b, t, 0)
        return cv2.cvtColor(out, cv2.COLOR_BGR2RGB)


class RifeInterpolator:
    """RIFE model adapter. Expects ECCV2022-RIFE repo + pretrained weights locally."""

    def __init__(self, device: str, repo_dir: Path, model_dir: Path) -> None:
        self.device = torch.device(device if device != "cuda" or torch.cuda.is_available() else "cpu")

        if not repo_dir.exists():
            raise RuntimeError(f"RIFE repo not found: {repo_dir}")
        if not model_dir.exists():
            raise RuntimeError(f"RIFE model directory not found: {model_dir}")

        sys.path.insert(0, str(repo_dir))
        try:
            from model.RIFE import Model as RIFEModel
        except Exception as exc:
            raise RuntimeError("Failed to import RIFE model code from repo") from exc

        self.model = RIFEModel()
        self.model.load_model(str(model_dir), -1)
        self.model.eval()
        if hasattr(self.model, "device"):
            self.model.device()

    def _to_tensor(self, frame: np.ndarray) -> torch.Tensor:
        tensor = torch.from_numpy(frame).permute(2, 0, 1).float().unsqueeze(0) / 255.0
        return tensor.to(self.device)

    def interpolate(self, frame_a: np.ndarray, frame_b: np.ndarray, t: float) -> np.ndarray:
        ta = self._to_tensor(frame_a)
        tb = self._to_tensor(frame_b)

        with torch.no_grad():
            try:
                out = self.model.inference(ta, tb, timestep=float(t))
            except TypeError:
                out = self.model.inference(ta, tb, float(t))

        out = out.squeeze(0).clamp(0, 1).mul(255.0).byte().permute(1, 2, 0)
        return out.cpu().numpy()


class FrameInterpolator:
    """Pluggable interpolator with optional RIFE backend and fallback."""

    def __init__(
        self,
        device: str = "cpu",
        backend: str = "optical_flow",
        rife_repo_dir: Path | None = None,
        rife_model_dir: Path | None = None,
        strict: bool = False,
    ) -> None:
        self.backend = "optical_flow"
        self.warning: str | None = None

        if backend == "rife":
            try:
                if not rife_repo_dir or not rife_model_dir:
                    raise RuntimeError("RIFE paths are required when backend='rife'")
                self.impl = RifeInterpolator(device=device, repo_dir=rife_repo_dir, model_dir=rife_model_dir)
                self.backend = "rife"
                return
            except Exception as exc:
                if strict:
                    raise
                self.warning = f"RIFE unavailable, using optical_flow fallback: {exc}"

        self.impl = OpticalFlowInterpolator()

    def interpolate(self, frame_a: np.ndarray, frame_b: np.ndarray, t: float) -> np.ndarray:
        return self.impl.interpolate(frame_a, frame_b, t)


def read_image_to_rgb_array(file_path: str) -> np.ndarray:
    image = Image.open(file_path).convert("RGB")
    return np.array(image)
