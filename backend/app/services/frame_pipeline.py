from __future__ import annotations

from typing import List

import cv2
import numpy as np

from app.services.model import FrameInterpolator


def resize_match(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if a.shape[:2] == b.shape[:2]:
        return a, b

    h = min(a.shape[0], b.shape[0])
    w = min(a.shape[1], b.shape[1])
    return cv2.resize(a, (w, h)), cv2.resize(b, (w, h))


def generate_interpolated_sequence(
    source_frames: list[np.ndarray],
    interpolator: FrameInterpolator,
    intermediate_count: int,
) -> list[np.ndarray]:
    if intermediate_count < 0:
        raise ValueError("intermediate_count must be >= 0")
    if len(source_frames) < 2:
        raise ValueError("Need at least two source frames")

    output: List[np.ndarray] = []

    for i in range(len(source_frames) - 1):
        first, second = resize_match(source_frames[i], source_frames[i + 1])
        output.append(first)

        for step in range(1, intermediate_count + 1):
            t = step / (intermediate_count + 1)
            middle = interpolator.interpolate(first, second, t)
            output.append(middle)

    output.append(source_frames[-1])
    return output
