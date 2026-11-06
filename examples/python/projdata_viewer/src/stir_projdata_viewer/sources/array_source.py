# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""Source backed by numpy arrays and ``.npy``/``.npz`` files (no STIR needed)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping

import numpy as np

from ..model.info import ProjDataInfo


def standard_segment_sequence(num_segments: int) -> list[int]:
    """STIR's ``ProjData::standard_segment_sequence`` for a symmetric range: 0, 1, -1, 2, -2, ...
    (an even count ends on a positive segment, as STIR does when the range is -k..k+1)."""
    seq, n = [0], 1
    while len(seq) < num_segments:
        seq.append(n)
        if len(seq) < num_segments:
            seq.append(-n)
        n += 1
    return seq[:num_segments]


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

    def get_sinogram(self, segment: int, axial: int, tof_bin: int) -> np.ndarray:
        a_lo, _ = self.info.axial_range(segment)
        return self._data[segment][tof_bin - self.info.min_tof, :, axial - a_lo, :]

    # ---- STIR's own numpy export --------------------------------------------
    @classmethod
    def from_stir_as_array(cls, data: np.ndarray, axial_counts, segment_numbers=None,
                           name: str = "array data", extra: dict[str, str] | None = None) -> "ArraySource":
        """Split the array returned by STIR's ``ProjData.as_array()`` into segments.

        That array is ``(tof, sinograms, views, tangential)`` (3D without the TOF axis in old STIR
        versions), where the sinogram axis holds all segments one after another in STIR's
        ``standard_segment_sequence`` order (0, 1, -1, 2, -2, ...), each segment ``(axial, view, tang)``.
        ``axial_counts`` gives the number of axial positions of each segment in that same order;
        ``segment_numbers`` overrides the order (needed only for non-symmetric segment ranges).
        """
        data = np.asarray(data, dtype=np.float32)
        if data.ndim == 3:
            data = data[np.newaxis]
        if data.ndim != 4:
            raise ValueError(f"STIR as_array data must be 3D or 4D, got {data.ndim}D")
        counts = [int(c) for c in np.atleast_1d(axial_counts)]
        if any(c < 1 for c in counts):
            raise ValueError(f"axial counts must be positive, got {counts}")
        segs = (standard_segment_sequence(len(counts)) if segment_numbers is None
                else [int(s) for s in np.atleast_1d(segment_numbers)])
        if len(segs) != len(counts):
            raise ValueError(f"{len(segs)} segment numbers but {len(counts)} axial counts")
        if sum(counts) != data.shape[1]:
            raise ValueError(f"axial counts add up to {sum(counts)} sinograms, but the array has "
                             f"{data.shape[1]} (shape {data.shape}: expected (tof, sinograms, views, tangential))")
        segments, start = {}, 0
        for seg, n in zip(segs, counts):
            # (tof, axial, view, tang) -> (tof, view, axial, tang)
            segments[seg] = data[:, start:start + n].transpose(0, 2, 1, 3)
            start += n
        return cls(segments, name=name, extra=extra)

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
                if "as_array" in z.files:
                    if "axial_counts" not in z.files:
                        raise ValueError(f"{path.name} has 'as_array' but no 'axial_counts' "
                                         "(number of axial positions per segment, see the README)")
                    unknown = set(z.files) - {"as_array", "axial_counts", "segment_numbers"}
                    if unknown:
                        raise ValueError(f"unexpected keys {sorted(unknown)} in {path.name}")
                    return cls.from_stir_as_array(
                        z["as_array"], z["axial_counts"],
                        z["segment_numbers"] if "segment_numbers" in z.files else None,
                        name=path.name, extra={"format": "numpy .npz (STIR ProjData.as_array layout)"})
                segs = {}
                for key in z.files:
                    m = re.fullmatch(r"segment_(-?\d+)", key)
                    if not m:
                        raise ValueError(f"unexpected key {key!r} in {path.name}; use 'segment_<n>', "
                                         "or 'as_array' + 'axial_counts' for STIR's ProjData.as_array() layout")
                    segs[int(m.group(1))] = z[key]
            return cls(segs, name=path.name, extra={"format": "numpy .npz"})
        raise ValueError(f"unsupported array file type: {path.suffix}")
