# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""Pure functions turning model objects into the text the view shows."""
from __future__ import annotations

import math

from ..model import ProjDataInfo, Selection, SliceImage, SliceMode, SliceStats, TofMode


def describe_dataset(info: ProjDataInfo) -> str:
    lines = [f"Source:      {info.name}"]
    lines += [f"{k}: {v}" for k, v in info.extra.items()]
    lines += [
        f"Segments:    {info.num_segments}  ({info.min_segment} .. {info.max_segment})",
        f"Views:       {info.num_views}  ({info.min_view} .. {info.max_view})",
        f"Tangential:  {info.num_tangential}  ({info.min_tangential} .. {info.max_tangential})",
        "Axial:       " + ", ".join(f"seg {s}: {info.num_axial(s)}" for s in info.segments),
        f"TOF bins:    {info.num_tof_bins}" + (f"  ({info.min_tof} .. {info.max_tof})" if info.is_tof else "  (non-TOF)"),
        f"Total bins:  {info.total_bins:,}  (~{info.total_bins * 4 / 1e6:.1f} MB as float32)",
    ]
    return "\n".join(lines)


def describe_slice(image: SliceImage, stats: SliceStats) -> str:
    rows, cols = image.shape
    return "\n".join([
        f"Current slice  ({image.title})",
        f"shape:       {rows} x {cols}  ({image.row_axis} x {image.col_axis})",
        f"min / max:   {stats.minimum:.6g} / {stats.maximum:.6g}",
        f"mean / std:  {stats.mean:.6g} / {stats.std:.6g}",
        f"sum:         {stats.total:.6g}",
        f"non-zero:    {100 * stats.nonzero_fraction:.1f} %",
    ])


def format_pixel(image: SliceImage, row: int, col: int, value: float) -> str:
    idx = image.indices_at(row, col)
    return f"{image.row_axis} {idx[image.row_axis]}, {image.col_axis} {idx[image.col_axis]}:  {value:.6g}"


def format_profile_title(segment: int, view: int, axial: int, tangential: int, total: float) -> str:
    return f"segment {segment}, view {view}, axial {axial}, tangential {tangential}   (sum {total:.6g})"


def _short(value: float) -> str:
    return "n/a" if value != value else f"{value:.4g}"


def format_metrics(stats: SliceStats) -> tuple[tuple[str, str], ...]:
    """(label, value) pairs for the metric tiles under the image."""
    return (("Min", _short(stats.minimum)), ("Max", _short(stats.maximum)), ("Mean", _short(stats.mean)),
            ("Std", _short(stats.std)), ("Sum", _short(stats.total)),
            ("Non-zero", f"{100 * stats.nonzero_fraction:.1f} %"))


_MODE_CHIP = {SliceMode.SINOGRAM: "Sinogram", SliceMode.VIEWGRAM: "Viewgram", SliceMode.TANGENTIAL: "Tangential"}


def context_chips(info: ProjDataInfo, sel: Selection) -> tuple[str, ...]:
    """Short labels naming what is on screen: mode, segment, fixed position, TOF state."""
    chips = [_MODE_CHIP[sel.slice_mode], f"segment {sel.segment}",
             f"{sel.active_dimension} {sel.get(sel.active_dimension)}"]
    if info.is_tof:
        chips.append(f"TOF bin {sel.tof}" if sel.tof_mode is TofMode.BIN else f"TOF {sel.tof_mode.name.lower()}")
    return tuple(chips)


def format_number(value: float) -> str:
    """Compact text for an editable number: 6 significant digits, scientific notation when needed."""
    return f"{float(value):.6g}"


def parse_number(text: str) -> float | None:
    """The finite float in ``text`` (``1e-8``, ``-3``, `` 2.5 ``), or None if it is not one."""
    try:
        value = float(text.strip().replace(",", "."))
    except (ValueError, AttributeError):
        return None
    return value if math.isfinite(value) else None
