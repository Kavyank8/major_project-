from __future__ import annotations

from typing import List

import cv2
import numpy as np

from .model import FrameInterpolator


def ensure_even_dimensions(frame: np.ndarray) -> np.ndarray:
    """libx264/yuv420p requires even frame dimensions."""
    height, width = frame.shape[:2]
    even_height = height if height % 2 == 0 else height - 1
    even_width = width if width % 2 == 0 else width - 1

    if even_height < 2 or even_width < 2:
        raise ValueError("Frame dimensions must be at least 2x2 pixels.")

    if (even_height, even_width) == (height, width):
        return frame

    return frame[:even_height, :even_width]


def normalize_frame_sizes(source_frames: list[np.ndarray]) -> list[np.ndarray]:
    """Resize all frames to the first frame size for stable interpolation/encoding."""
    base_frame = ensure_even_dimensions(source_frames[0])
    base_h, base_w = base_frame.shape[:2]
    normalized: list[np.ndarray] = []

    for frame in source_frames:
        even_frame = ensure_even_dimensions(frame)
        if even_frame.shape[:2] == (base_h, base_w):
            normalized.append(even_frame)
        else:
            resized = cv2.resize(even_frame, (base_w, base_h), interpolation=cv2.INTER_CUBIC)
            normalized.append(ensure_even_dimensions(resized))

    return normalized


def generate_interpolated_sequence(
    source_frames: list[np.ndarray],
    interpolator: FrameInterpolator,
    intermediate_count: int,
) -> list[np.ndarray]:
    if intermediate_count < 0:
        raise ValueError("intermediate_count must be >= 0")
    if len(source_frames) < 2:
        raise ValueError("Need at least two source frames")

    source_frames = normalize_frame_sizes(source_frames)
    output: List[np.ndarray] = []

    for i in range(len(source_frames) - 1):
        first = source_frames[i]
        second = source_frames[i + 1]
        output.append(first)

        for step in range(1, intermediate_count + 1):
            t = step / (intermediate_count + 1)
            middle = ensure_even_dimensions(interpolator.interpolate(first, second, t))
            output.append(middle)

    output.append(ensure_even_dimensions(source_frames[-1]))
    return output
