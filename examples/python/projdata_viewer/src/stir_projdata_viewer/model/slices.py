# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""2D slices extracted from projection data, and their statistics."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SliceImage:
    """A 2D image plus what is needed to label axes and map pixels to bin indices."""

    data: np.ndarray
    title: str
    row_axis: str
    col_axis: str
    row_origin: int   # bin index of data[0, :]
    col_origin: int   # bin index of data[:, 0]

    @property
    def shape(self) -> tuple[int, int]:
        return self.data.shape  # type: ignore[return-value]

    def value_at(self, row: int, col: int) -> float | None:
        if 0 <= row < self.data.shape[0] and 0 <= col < self.data.shape[1]:
            return float(self.data[row, col])
        return None

    def indices_at(self, row: int, col: int) -> dict[str, int]:
        return {self.row_axis: self.row_origin + row, self.col_axis: self.col_origin + col}

    def pixel_from_axes(self, x: float, y: float) -> tuple[int, int]:
        """Map axis coordinates (x = column axis, y = row axis, in bin-index units, where an
        integer is a pixel *centre*) to ``(row, col)``. The result may lie outside the image."""
        return math.floor(y - self.row_origin + 0.5), math.floor(x - self.col_origin + 0.5)


@dataclass(frozen=True)
class SliceStats:
    minimum: float
    maximum: float
    mean: float
    std: float
    total: float
    nonzero_fraction: float


def compute_stats(data: np.ndarray) -> SliceStats:
    """Statistics over the *finite* values (NaN/inf are ignored, not propagated)."""
    d = np.asarray(data, dtype=np.float64)
    if d.size == 0:
        raise ValueError("cannot compute statistics of an empty slice")
    finite = d[np.isfinite(d)]
    if finite.size == 0:
        nan = float("nan")
        return SliceStats(nan, nan, nan, nan, 0.0, 0.0)
    return SliceStats(float(finite.min()), float(finite.max()), float(finite.mean()), float(finite.std()),
                      float(finite.sum()), float(np.count_nonzero(finite)) / d.size)


def finite_range(data: np.ndarray) -> tuple[float, float] | None:
    """(min, max) over the finite values only, or None if there are none (NaN/inf are ignored)."""
    d = np.asarray(data)
    finite = d[np.isfinite(d)]
    if finite.size == 0:
        return None
    return float(finite.min()), float(finite.max())
