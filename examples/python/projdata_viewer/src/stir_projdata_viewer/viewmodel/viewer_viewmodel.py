# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""VIEWMODEL layer: everything the window shows or does, with no widget code.

The view binds to the observable properties below and calls the command methods. The view model
talks to the model (``ProjDataset``/``Selection``) and receives its data source through an
injected ``source_factory``, so it never imports Qt, pyqtgraph or STIR.
"""
from __future__ import annotations

import functools
import os
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from ..model import ProjDataset, ProjDataSource, Selection, SliceImage, SliceMode, TofMode, finite_range
from ..model.selection import DIMENSIONS
from . import formatting
from .observable import Observed, ObservableObject
from .options import COLORMAPS, LevelMode

DIM_LABELS = {
    "segment": "Segment",
    "axial": "Axial position",
    "view": "View",
    "tangential": "Tangential position",
    "tof": "TOF bin",
}
MIN_FPS, MAX_FPS = 1, 30
DEFAULT_STATUS = "Open a file, or use File > Demo data"

SourceFactory = Callable[[Any], ProjDataSource]


@dataclass(frozen=True)
class DimensionState:
    """What one slider/spin-box pair should show."""
    name: str
    label: str
    lo: int
    hi: int
    value: int
    enabled: bool


@dataclass(frozen=True)
class DisplayImage:
    """A ready-to-draw image: values (log-transformed if requested) and its rectangle in axis
    coordinates, where integer positions are pixel centres."""
    data: np.ndarray
    x0: float
    y0: float
    width: float
    height: float
    row_label: str
    col_label: str
    title: str


@dataclass(frozen=True)
class TofProfile:
    x: tuple[int, ...]
    y: tuple[float, ...]
    title: str


@dataclass(frozen=True)
class _Rendered:
    image: SliceImage
    display: np.ndarray
    levels: tuple[float, float]
    stats: Any


def clean_path(text: str) -> str:
    """Normalise a typed or pasted path: strip whitespace and one pair of surrounding quotes, expand ``~``."""
    text = (text or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    return os.path.expanduser(text) if text else ""


def _command(fn):
    """Run a view-model method as one transaction: subscribers are notified once at the end."""
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        with self.transaction():
            return fn(self, *args, **kwargs)
    return wrapper


class ViewerViewModel(ObservableObject):
    # ---- observable state (read-only for the view) --------------------------------
    loaded = Observed(False)
    window_title = Observed("STIR projection data viewer")
    source_label = Observed("")            # name of the loaded data set (file name for files)
    source_path = Observed("")             # path of the loaded file, "" for in-memory or demo data
    status = Observed(DEFAULT_STATUS)
    error = Observed(None)                 # last error message; re-notified on every failure
    dimensions = Observed(())              # tuple[DimensionState, ...]
    slice_mode = Observed(SliceMode.SINOGRAM)
    tof_mode = Observed(TofMode.BIN)
    tof_available = Observed(False)
    can_play = Observed(False)
    playing = Observed(False)
    fps = Observed(4)
    tof_marker = Observed(None)            # TOF bin to mark in the profile plot, or None
    colormap = Observed(COLORMAPS[0])
    level_mode = Observed(LevelMode.AUTO)
    log_display = Observed(False)
    image = Observed(None)                 # DisplayImage | None
    levels = Observed(None)                # (lo, hi) | None
    info_text = Observed("")
    pixel_text = Observed("")
    tof_profile = Observed(None)           # TofProfile | None
    metrics = Observed(())                 # tuple[(label, value), ...] for the current slice
    context = Observed(())                 # tuple[str, ...] chips describing the current selection

    def __init__(self, source_factory: SourceFactory, demo_factory: Callable[[], ProjDataSource] | None = None):
        super().__init__()
        self._factory = source_factory
        self._demo_factory = demo_factory
        self._dataset: ProjDataset | None = None
        self._selection: Selection | None = None
        self._slice: SliceImage | None = None
        self._manual_levels: tuple[float, float] | None = None
        self._last_pixel: tuple[int, int] | None = None
        self._cursor: tuple[float, float] | None = None     # last hover position in axis coordinates

    # ---- read access for tests and views --------------------------------------------
    @property
    def selection(self) -> Selection | None:
        return self._selection

    @property
    def dataset(self) -> ProjDataset | None:
        return self._dataset

    def dimension(self, name: str) -> DimensionState:
        return next(d for d in self.dimensions if d.name == name)

    # ---- commands --------------------------------------------------------------------
    @_command
    def load(self, obj: Any) -> bool:
        """Load a path, ``stir.ProjData`` or ``ProjDataSource`` through the injected factory.
        On failure the previous data stays, ``error`` is set and False is returned."""
        level_mode = LevelMode.AUTO if self.level_mode is LevelMode.MANUAL else self.level_mode
        try:
            dataset = ProjDataset(self._factory(obj))
            selection = Selection.initial(dataset.info)
            rendered = self._render(dataset, selection, level_mode, None)   # first slice must be readable
        except Exception as exc:  # noqa: BLE001 - any loader failure is reported, not raised
            self._report_error(f"Could not load projection data: {exc}")
            return False
        self._manual_levels = None
        self.level_mode = level_mode
        self.playing = False
        self.error = None
        self.loaded = True
        self.window_title = f"STIR projection data viewer - {dataset.info.name}"
        self.source_label = dataset.info.name
        self.source_path = os.fspath(obj) if isinstance(obj, (str, os.PathLike)) else ""
        self.status = f"Loaded {dataset.info.name}"
        self.tof_available = dataset.info.is_tof
        self.tof_profile = None
        self.pixel_text = ""
        self._cursor = None
        self._commit(dataset, selection, rendered)
        return True

    @_command
    def load_path(self, text: str) -> bool:
        """Load a path typed or pasted by the user: surrounding whitespace and quotes (e.g. from Windows
        "Copy as path") are removed and ``~`` is expanded. Blank input does nothing."""
        path = clean_path(text)
        if not path:
            return False
        return self.load(path)

    @_command
    def load_demo(self) -> bool:
        """Load the injected demo data set (the view must not know where demo data comes from)."""
        if self._demo_factory is None:
            self._report_error("No demo data is available in this configuration")
            return False
        return self.load(self._demo_factory())

    @_command
    def clear_error(self) -> None:
        """The user dismissed the error banner."""
        self.error = None

    @_command
    def report_error(self, message: str) -> None:
        """Let the view report a failure it caused itself (e.g. a failed image export) through the same
        channel as every other error, so the banner state lives in one place."""
        self._report_error(message)

    @_command
    def set_value(self, dim: str, value: int) -> None:
        if self._ready():
            self._show(self._selection.with_value(self._dataset.info, dim, value))

    @_command
    def step(self, dim: str, delta: int) -> None:
        if self._ready():
            self.set_value(dim, self._selection.get(dim) + delta)

    @_command
    def step_active(self, delta: int) -> None:
        if self._ready():
            self.step(self._selection.active_dimension, delta)

    @_command
    def set_slice_mode(self, mode: SliceMode) -> None:
        if self._ready():
            self._show(self._selection.with_slice_mode(mode))

    @_command
    def set_tof_mode(self, mode: TofMode) -> None:
        if self._ready():
            self._show(self._selection.with_tof_mode(mode))

    @_command
    def set_playing(self, playing: bool) -> None:
        self.playing = bool(playing) and self.can_play

    @_command
    def toggle_play(self) -> None:
        self.set_playing(not self.playing)

    @_command
    def set_fps(self, fps: int) -> None:
        self.fps = int(min(max(fps, MIN_FPS), MAX_FPS))

    @_command
    def tick(self) -> None:
        """One playback step; the view calls this from its timer. Ignored unless ``playing``,
        so a stale timer event after pause/error/collapse does nothing."""
        if not self._ready() or not self.playing:
            return
        if not self.can_play:
            self.playing = False
            return
        self._show(self._selection.step_tof(self._dataset.info, 1))

    @_command
    def set_colormap(self, name: str) -> None:
        if name not in COLORMAPS:
            raise ValueError(f"unknown colour map {name!r}; choose from {COLORMAPS}")
        self.colormap = name

    @_command
    def set_level_mode(self, mode: LevelMode) -> None:
        old = self.level_mode
        self.level_mode = mode
        if self._ready() and not self._show(self._selection):
            self.level_mode = old

    @_command
    def set_log_display(self, enabled: bool) -> None:
        self.log_display = bool(enabled)
        self._manual_levels = None     # levels chosen in the other scale are meaningless
        if self.level_mode is LevelMode.MANUAL:
            self.level_mode = LevelMode.AUTO
        if self._ready():
            self._show(self._selection)

    @_command
    def set_manual_levels(self, lo: float, hi: float) -> None:
        """Called by the view when the user drags the histogram region. An empty, inverted or non-finite
        range is rejected; ``levels`` is then re-announced so the view puts its widgets back."""
        if not (np.isfinite(lo) and np.isfinite(hi)) or hi <= lo:
            self.status = f"Ignored level range {lo:g} .. {hi:g}: the minimum must be below the maximum"
            self._mark_changed("levels")
            return
        self._manual_levels = (float(lo), float(hi))
        self.level_mode = LevelMode.MANUAL
        self.levels = self._manual_levels

    @_command
    def set_level_bounds(self, low: float | None = None, high: float | None = None) -> None:
        """Type in one or both colour-scale limits (switches to manual levels). Ignored if it would
        make the range empty or inverted."""
        cur_lo, cur_hi = self.levels if self.levels is not None else (0.0, 1.0)
        lo = cur_lo if low is None else float(low)
        hi = cur_hi if high is None else float(high)
        self.set_manual_levels(lo, hi)

    @_command
    def hover_at(self, x: float, y: float) -> None:
        """Cursor at axis coordinates (x = column axis, y = row axis) of the displayed image."""
        if self._slice is None or self._dataset is None:
            return
        self._cursor = (x, y)
        self._hover(x, y)

    @_command
    def hover_leave(self) -> None:
        self._cursor = None
        self.pixel_text = ""

    def _hover(self, x: float, y: float) -> None:
        row, col = self._slice.pixel_from_axes(x, y)
        value = self._slice.value_at(row, col)
        if value is None:
            self.pixel_text = ""
            return
        self.pixel_text = formatting.format_pixel(self._slice, row, col, value)
        if self._dataset.info.is_tof and (row, col) != self._last_pixel:
            self._last_pixel = (row, col)
            self._update_tof_profile(self._slice.indices_at(row, col))

    # ---- internals ---------------------------------------------------------------------
    def _ready(self) -> bool:
        return self._dataset is not None and self._selection is not None

    def _report_error(self, message: str) -> None:
        self.error = message
        self._mark_changed("error")      # notify even if the text repeats
        self.status = message

    def _show(self, selection: Selection) -> bool:
        """Display ``selection`` of the current data set. All or nothing: if the slice cannot be read the
        previous selection, picture and controls stay (the view is told to repaint the controls)."""
        try:
            rendered = self._render(self._dataset, selection, self.level_mode, self._manual_levels)
        except Exception as exc:  # noqa: BLE001 - keep the previous picture, tell the user why
            self.playing = False         # never keep playing into a stream of identical errors
            self._report_error(f"Could not read the slice: {exc}")
            self._mark_changed("dimensions", "slice_mode", "tof_mode", "level_mode")  # snap widgets back
            return False
        self._commit(self._dataset, selection, rendered)
        return True

    def _commit(self, dataset: ProjDataset, sel: Selection, rendered: "_Rendered") -> None:
        """Make ``dataset``/``sel`` current and publish everything derived from them (cannot fail)."""
        self._dataset, self._selection = dataset, sel
        info = dataset.info
        self.slice_mode = sel.slice_mode
        self.tof_mode = sel.tof_mode
        self.can_play = info.is_tof and sel.tof_mode is TofMode.BIN
        if not self.can_play:
            self.playing = False
        self.tof_marker = sel.tof if self.can_play else None
        self._refresh_dimensions()
        image = rendered.image
        self._slice = image
        rows, cols = image.shape
        self.image = DisplayImage(rendered.display, image.col_origin - 0.5, image.row_origin - 0.5,
                                  float(cols), float(rows), image.row_axis, image.col_axis, image.title)
        self.levels = rendered.levels
        self.metrics = formatting.format_metrics(rendered.stats)
        self.context = formatting.context_chips(info, sel)
        self.info_text = (formatting.describe_dataset(info) + "\n\n"
                          + formatting.describe_slice(image, rendered.stats))
        # the LOR under a resting cursor changes with the selection: recompute readout and profile
        self._last_pixel = None
        if self._cursor is not None:
            self._hover(*self._cursor)
        else:
            self.tof_profile = None

    def _refresh_dimensions(self) -> None:
        sel, info = self._selection, self._dataset.info
        active = sel.active_dimension
        states = []
        for dim in DIMENSIONS:
            lo, hi = sel.range(info, dim)
            wanted = dim in ("segment", active) or (dim == "tof" and info.is_tof and sel.tof_mode is TofMode.BIN)
            states.append(DimensionState(dim, DIM_LABELS[dim], lo, hi, sel.get(dim), wanted and hi > lo))
        self.dimensions = tuple(states)

    def _display_values(self, data: np.ndarray) -> np.ndarray:
        if self.log_display:
            return np.log1p(np.clip(data, 0, None)).astype(np.float32)
        return np.ascontiguousarray(data, dtype=np.float32)

    def _render(self, dataset: ProjDataset, sel: Selection, level_mode: LevelMode,
                manual: tuple[float, float] | None) -> "_Rendered":
        """Everything needed to show ``sel``, computed without touching any observable state (may raise)."""
        image = dataset.slice(sel)
        disp = self._display_values(image.data)
        if level_mode is LevelMode.FIXED:
            lo, hi = dataset.global_range(sel)
            if self.log_display:
                lo, hi = float(np.log1p(max(lo, 0.0))), float(np.log1p(max(hi, 0.0)))
        elif level_mode is LevelMode.MANUAL and manual is not None:
            lo, hi = manual
        else:
            lo, hi = finite_range(disp) or (0.0, 1.0)
        if hi <= lo:
            hi = lo + max(abs(lo) * 1e-6, np.finfo(np.float32).tiny)
        return _Rendered(image, disp, (lo, hi), dataset.stats(image))

    def _update_tof_profile(self, indices: dict[str, int]) -> None:
        sel = self._selection
        lor = {d: sel.get(d) for d in ("view", "axial", "tangential")}
        lor.update(indices)
        try:
            prof = self._dataset.tof_profile(sel.segment, lor["view"], lor["axial"], lor["tangential"])
        except Exception as exc:  # noqa: BLE001
            self._report_error(f"TOF profile unavailable: {exc}")
            return
        self.tof_profile = TofProfile(
            tuple(self._dataset.info.tof_bins), tuple(float(v) for v in prof),
            formatting.format_profile_title(sel.segment, lor["view"], lor["axial"], lor["tangential"],
                                            float(prof.sum())))
