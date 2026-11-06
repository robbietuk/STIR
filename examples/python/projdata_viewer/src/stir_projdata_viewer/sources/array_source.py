# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""Source backed by numpy arrays and ``.npy``/``.npz`` files (no STIR needed)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping

import numpy as np

from ..model.info import ProjDataInfo


class ArraySource:
    """Projection data held in numpy arrays.

    ``segments`` maps segment number -> array of shape ``(views, axial, tangential)``
    (non-TOF) or ``(tof, views, axial, tangential)``. All segments must agree on
    views, tangential positions and number of TOF bins.
    """

    def __init__(self, segments: Mapping[int, np.ndarray], name: str = "array data",
                 extra: dict[str, str] | None = None):
        if not segments:
            raise ValueError("need at least one segment")
        self._data: dict[int, np.ndarray] = {}
        for seg, arr in segments.items():
            arr = np.asarray(arr, dtype=np.float32)
            if arr.ndim == 3:
                arr = arr[np.newaxis]
            if arr.ndim != 4:
                raise ValueError(f"segment {seg}: expected 3D or 4D array, got {arr.ndim}D")
            self._data[int(seg)] = arr

        keys = sorted(self._data)
        ref = self._data[keys[0]]
        for seg in keys:
            a = self._data[seg]
            if a.shape[0] != ref.shape[0] or a.shape[1] != ref.shape[1] or a.shape[3] != ref.shape[3]:
                raise ValueError(
                    f"segment {seg} has shape {a.shape}, inconsistent with segment {keys[0]} {ref.shape} "
                    "(TOF bins, views and tangential positions must match)")
        n_tof, n_view, _, n_tang = ref.shape
        self.info = ProjDataInfo(
            name=name,
            min_segment=keys[0], max_segment=keys[-1],
            min_view=0, max_view=n_view - 1,
            # STIR convention: tangential positions are centred on zero
            min_tangential=-(n_tang // 2), max_tangential=-(n_tang // 2) + n_tang - 1,
            axial_ranges={s: (0, self._data[s].shape[2] - 1) for s in keys},
            min_tof=0, max_tof=n_tof - 1,
            extra=dict(extra or {}),
        )
        if keys != list(range(keys[0], keys[-1] + 1)):
            raise ValueError(f"segment numbers must be contiguous, got {keys}")

    def get_segment(self, segment: int, tof_bin: int) -> np.ndarray:
        arr = self._data[segment]
        return arr[tof_bin - self.info.min_tof]

    # ---- file loading -------------------------------------------------
    @classmethod
    def from_file(cls, path: str | Path) -> "ArraySource":
        """Load ``.npy`` (one segment, 3D or 4D) or ``.npz`` (keys ``segment_<n>``)."""
        path = Path(path)
        suffix = path.suffix.lower()
        if suffix == ".npy":
            return cls({0: np.load(path)}, name=path.name,
                       extra={"format": "numpy .npy (treated as segment 0)"})
        if suffix == ".npz":
            with np.load(path) as z:
                segs = {}
                for key in z.files:
                    m = re.fullmatch(r"segment_(-?\d+)", key)
                    if not m:
                        raise ValueError(f"unexpected key {key!r} in {path.name}; use 'segment_<n>'")
                    segs[int(m.group(1))] = z[key]
            return cls(segs, name=path.name, extra={"format": "numpy .npz"})
        raise ValueError(f"unsupported array file type: {path.suffix}")
