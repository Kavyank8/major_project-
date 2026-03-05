from __future__ import annotations

import torch
from PIL import Image
import numpy as np


class FrameInterpolator:
    """Simple placeholder model.

    Swap this class with a trained model (RIFE/FILM/DAIN/etc.) while keeping
    the same interpolate method signature.
    """

    def __init__(self, device: str = "cpu") -> None:
        self.device = torch.device(device)

    def _to_tensor(self, frame: np.ndarray) -> torch.Tensor:
        # HWC uint8 -> CHW float32 [0,1]
        tensor = torch.from_numpy(frame).permute(2, 0, 1).float() / 255.0
        return tensor.to(self.device)

    def _to_frame(self, tensor: torch.Tensor) -> np.ndarray:
        tensor = tensor.clamp(0, 1).mul(255.0).byte().permute(1, 2, 0)
        return tensor.cpu().numpy()

    def interpolate(self, frame_a: np.ndarray, frame_b: np.ndarray, t: float) -> np.ndarray:
        ta = self._to_tensor(frame_a)
        tb = self._to_tensor(frame_b)
        out = ta * (1.0 - t) + tb * t
        return self._to_frame(out)


def read_image_to_rgb_array(file_path: str) -> np.ndarray:
    image = Image.open(file_path).convert("RGB")
    return np.array(image)
