# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""Synthetic TOF projection data for demos and tests."""
from __future__ import annotations

import numpy as np

from .array_source import ArraySource


def make_demo_source(num_segments: int = 5, num_views: int = 48, num_tangential: int = 61,
                     axial_base: int = 24, tof_bins: int = 9, seed: int = 0) -> ArraySource:
    """Synthetic TOF data: a few hot spots seen as sinusoidal ridges.

    Each spot contributes, for a view angle theta, a ridge at tangential position
    ``s = x cos(theta) + y sin(theta)`` and sits along the LOR at
    ``u = -x sin(theta) + y cos(theta)``, which a Gaussian TOF kernel maps onto the TOF bins.
    Summing over TOF bins therefore gives the usual (non-TOF) sinogram.
    """
    if num_segments % 2 == 0:
        raise ValueError("num_segments must be odd (segments -k..k)")
    rng = np.random.default_rng(seed)
    half = num_segments // 2
    theta = np.pi * np.arange(num_views) / num_views                       # (V,)
    tang = np.arange(num_tangential) - num_tangential // 2                 # (T,)
    tof_centres = (np.arange(tof_bins) - (tof_bins - 1) / 2) * 5.0         # in tangential-pixel units
    # (x, y, z_fraction, amplitude)
    spots = [(-12.0, 4.0, 0.35, 100.0), (8.0, -10.0, 0.60, 70.0), (14.0, 12.0, 0.45, 40.0)]
    sigma_tang, sigma_tof, sigma_z = 1.6, 3.5, 3.0

    segments: dict[int, np.ndarray] = {}
    for seg in range(-half, half + 1):
        n_ax = max(axial_base - 4 * abs(seg), 4)
        z = np.arange(n_ax)
        arr = np.zeros((tof_bins, num_views, n_ax, num_tangential), dtype=np.float32)
        for x, y, zf, amp in spots:
            s = x * np.cos(theta) + y * np.sin(theta)                     # (V,)
            u = -x * np.sin(theta) + y * np.cos(theta)                    # (V,)
            ridge = np.exp(-0.5 * ((tang[None, :] - s[:, None]) / sigma_tang) ** 2)          # (V,T)
            tofw = np.exp(-0.5 * ((tof_centres[:, None] - u[None, :]) / sigma_tof) ** 2)     # (K,V)
            axw = np.exp(-0.5 * ((z - zf * (n_ax - 1)) / sigma_z) ** 2)                      # (A,)
            arr += (amp * tofw[:, :, None, None] * axw[None, None, :, None]
                    * ridge[None, :, None, :]).astype(np.float32)
        arr += rng.poisson(0.05, size=arr.shape).astype(np.float32)   # background counts
        segments[seg] = arr
    return ArraySource(segments, name="demo phantom (synthetic)",
                       extra={"format": "synthetic", "note": "3 hot spots, Gaussian TOF kernel"})
