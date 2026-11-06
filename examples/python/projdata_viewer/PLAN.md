# Plan and design decisions

## 1. Getting STIR (decision)

**The viewer does not declare `stir` as a dependency; it uses whichever `stir` it can import.**

Why: `stir` is a SWIG-generated C++ extension tied to the exact build (ITK, HDF5, ROOT,
parallelproj options, shared libraries). It is not on PyPI, so a pip dependency cannot be
satisfied, and vendoring or re-building it from this package would be wrong. What the viewer
needs from it is tiny (index ranges, `get_segment_by_view`, `as_array`), so the coupling is
confined to one gateway (`stir_interface/swig_gateway.py`) behind a `ProjDataSource` protocol.

Lookup order in `import_stir()`:

1. `--stir-path DIR` or `$STIR_PYTHON_PATH`: the `<CMAKE_INSTALL_PREFIX>/python` of a source build
   (shared libraries must also be findable: `LD_LIBRARY_PATH` / `DYLD_LIBRARY_PATH` / `PATH`).
2. Whatever `import stir` finds: the conda-forge `stir` package, which ships the Python bindings
   (builds cover Python 3.10 - 3.14, so a `>=3.11` floor is fine).
3. No STIR: `.npy`/`.npz` files and `--demo` still work, which also keeps the core testable in CI
   without a C++ build.

Qt stack: in a conda env take `pyside6`/`pyqtgraph` from conda-forge too (one Qt copy); in a
plain venv the PySide6 wheel is fine. `environment.yml` and the README cover both.

Rejected: depending on a PyPI `stir` (doesn't exist); a subprocess bridge exporting data with
STIR utilities (loses live access, more moving parts; could be a later fallback for odd formats).

## 2. Architecture (MVVM, strict layering)

```
stir module -> SwigStirGateway -> StirProjDataSource -> model.ProjDataset -> ViewerViewModel -> ViewerWindow
 (compiled)     stir_interface      stir_interface         model              viewmodel            view
```

* **Model** (`model/`): pure domain logic, numpy only. `Selection` is an immutable value with all
  clamping rules; `ProjDataset` turns a `ProjDataSource` + `Selection` into slices, TOF reductions,
  stats and per-LOR profiles. It holds no UI state, so one dataset can serve any selection.
* **STIR interface** (`stir_interface/`): an anti-corruption layer. `gateway.py` states what we need from
  STIR without STIR types; `swig_gateway.py` is the only file that imports `stir` (lazily) and does the
  axis-order self-check; `source.py` adapts any handle to the model's `ProjDataSource`. Tests swap in
  fakes; the same contract test runs against every handle implementation, including real STIR.
* **ViewModel** (`viewmodel/`): everything the window shows or does, without widgets. Observable
  properties (`Observed` descriptors) plus command methods; every command is one transaction, so the view
  is notified once per command with the set of changed property names. Data sources are injected
  (`source_factory`), so the view model never imports STIR.
* **View** (`view/`): `ViewerWindow` forwards user input to commands and redraws from properties. Loop
  guards (`blockSignals`, `_applying_levels`) stop programmatic updates echoing back. It does not import
  `sources` or `stir_interface`.
* **Composition root** (`app.py`, top level): the only module that wires loader, demo data, view model and window.

Dependency rules are enforced by `tests/test_architecture.py` (static import analysis plus a clean-interpreter
check that the Qt-free layers load no Qt/STIR/matplotlib).

Display: pyqtgraph `ImageItem` + `HistogramLUTItem` replace matplotlib `imshow` + colorbar. A slider
change swaps the array and levels with no figure rebuild. Axes show real bin numbers.

Extra information versus the old tool: dataset summary (scanner, TOF resolution/mashing when STIR
exposes them), per-segment axial sizes, memory estimate, per-slice min/max/mean/std/sum/non-zero
fraction, value + indices under the cursor, histogram with draggable levels, log display,
fixed-global or per-slice levels, tangential slices.

## 3. Time of flight

Implemented (v0.1):

* STIR's TOF bin numbers are used as-is (may be negative); non-TOF data is one bin and the TOF box is disabled.
* **Iterate:** a TOF-bin slider/spin box plus *Play* (1-30 fps, wrap-around), Space toggles.
* **Collapse:** Sum / Mean / Max over all TOF bins. Computed bin by bin into one accumulator (one extra
  segment in memory), cached per (segment, mode). Sum equals the non-TOF projection data.
* **Per-LOR TOF profile:** hovering a pixel plots counts versus TOF bin for that LOR, with the current
  bin marked; the title shows the profile's sum.
* Caches: raw bins for one segment (enough for playback and profiles) plus reduced segments.

Next steps, roughly in order:

1. Collapse over a *range* of bins (e.g. central +/- k), and a TOF-bin axis in ps/mm using the scanner timing resolution and mashing factor.
2. Check whether STIR exposes a cheaper TOF-summed accessor than reading every bin; if so use it for Sum.
3. Show the fitted TOF centroid / width of the profile, and optionally the expected Gaussian kernel for the scanner.
4. Export: PNG of the current view, and an animated GIF/MP4 of the TOF sweep.
5. Compare mode: two data sets side by side or difference/ratio (e.g. measured vs. forward projection).

## 4. Status and what is not verified

* Verified here: all Qt-free layers, the SWIG gateway against a *fake* `stir` module, and the
  window's binding logic against stubbed Qt/pyqtgraph; the suite was mutation-checked (deliberately injected
  bugs are caught).
* **Not verified:** running under real PySide6/pyqtgraph (PyPI is unreachable from the authoring
  sandbox) and against the real `stir` bindings. First things to check on a real machine:
  `pytest` (including `tests/view/test_window_real_qt.py`), `stir-projdata-viewer --demo`, then a real `.hs`.
* Assumption to confirm with real STIR: `SegmentByView.as_array()` is ordered (view, axial,
  tangential). The adapter checks the shape and compares against `get_sinogram()` once, and
  fails with an explicit message instead of showing a wrong picture.
* Best-effort metadata calls (`get_proj_data_info().get_scanner()...`, timing resolution, TOF mashing)
  are wrapped so a missing method just omits that line.

## 5. Open points

* Where this finally lives (here as a standalone project vs. `src/swig/python`) and whether to remove the old PyQt5 viewer.
* Should CI install the conda environment and run `pytest` + the offscreen GUI smoke test?

## 6. Independent review (what it found and what was done)

A separate reviewer read the old and new code without trusting these documents. Fixed since: a probable
startup crash (`HistogramLUTItem` signal name; now guarded by a test that emits the real signal under Qt),
stale TOF profile after a selection change, playback continuing through read errors (and stacking error
dialogs, now deferred out of the wait-cursor scope), NaN/inf poisoning levels and statistics, a NaN-unsafe
axis-order check, manual levels surviving a reload, view -> sources dependency (demo data is now injected),
missing parity features (typed path + Load, numeric level boxes, save image, `-f`, `launch_GUI`),
Windows DLL search paths for `--stir-path`, and stale documentation.

Still open: memory/latency on large TOF data (see README, Known limitations), no style selector, shortcuts vs
focused slider, and everything that needs real PySide6/pyqtgraph/STIR to confirm.

## 7. UI modernisation

Added after the review: a colour scheme (`view/theme.py`, dark default + light, contrast-tested), an
application stylesheet and Fusion-based `QPalette` (`view/styling.py`), reusable components with shared logic
(`view/components.py`, `viewmodel/options.py`, `viewmodel/bindings.py`), a card-based window with an empty
state, context chips, metric tiles and an inline error banner. The view model gained `metrics`, `context`
and `clear_error`. The window declares its property -> widget bindings through `BindingRegistry`, and a test
fails if any observable property is left unbound.

Unverified here (no PySide6/pyqtgraph in the sandbox): how the stylesheet actually renders, pyqtgraph
theming calls, and `tests/view/test_components_real_qt.py` / the updated `test_window_real_qt.py`. The
first thing to do on a machine with Qt is run `pytest`, then `stir-projdata-viewer --demo` in both themes.

## 8. Planned: several data sets in one window, synced when they have the same shape

Not implemented. Today one `ViewerViewModel` owns one `ProjDataset`; the model, view model and STIR adapter
hold no global state, so the work is mostly above them and in the window.

**Compatible = same geometry.** Two data sets can be synced if their `ProjDataInfo` agree on segment
range, per-segment axial ranges, view range, tangential range and TOF bin range (names and header extras are
ignored). A model-level `ProjDataInfo.same_geometry_as(other)` decides this, so the rule is unit-tested without
Qt. Data sets that differ are still shown side by side but cannot be linked, and the UI says why.

**Structure (new code only above the existing layers):**
* `WorkspaceViewModel` (Qt-free): ordered list of per-data-set `ViewerViewModel`s, the active one, a
  `link` setting (off / selection / selection + levels), and commands `add`, `close`, `set_active`,
  `set_link`. Observable properties follow the existing `Observed` + transaction rules.
* Linking lives only in the workspace: when a linked view model's selection changes, the workspace applies the same
  `Selection` values to the other compatible view models inside one transaction. View models do not know about
  each other, which also avoids feedback loops (changes from the workspace are marked as coming from linking).
* Shared display levels (optional): the workspace computes one range across the linked slices, so the
  same colour means the same value in every pane.
* View: split `ViewerWindow` into a `ViewerPane` (image, chips, metrics, TOF plot, bound to one view model) and the
  sidebar, which acts on the active pane. Panes sit in a tile / tab layout; a pane header shows the data set name,
  a link toggle and a close button.
* Compare helpers once panes are linked: difference and ratio panes computed in the model from two compatible
  `ProjDataset`s (new pure functions, tested with numpy only).
* Memory: one shared cache budget across data sets, evicting the least recently used data first; today each
  dataset caches independently.

**Tests to add:** `same_geometry_as` (equal, differing in each dimension, TOF only); workspace linking
(applies to compatible only, no feedback loops, one notification per command, closing the active pane);
random-walk invariants across several view models; architecture rules for the new workspace module;
stubbed and real-Qt tests for the pane and layout.

**Order:** (1) `same_geometry_as` and tests; (2) `ViewerPane` split with the app behaving as today;
(3) `WorkspaceViewModel` with link off; (4) linking; (5) shared levels and difference panes; (6) cache budget.

### 8a. Details checked against STIR's own headers (added after reading `ProjData.h`, `ProjDataInfo.h`, the SWIG files)

* TOF access is `ProjData::get_segment_by_view(SegmentIndices(segment, timing_pos))`; `timing_pos` is the
  *mashed* TOF bin number (`get_min/max_tof_pos_num`, `get_tof_mash_factor`), not the scanner's unmashed bin.
  `ProjData` forwards these range getters (via `DataWithProjDataInfo`), so the adapter's calls exist. The old tool
  already had a single-TOF-bin slider; what the rewrite adds is collapsing, playback and the per-LOR profile.
* STIR's `is_tof_data()` is "mash factor > 0", so a TOF file with a single bin counts as TOF in STIR but as non-TOF
  here (`num_tof_bins > 1`). Harmless for display, but the information panel would say "non-TOF". Fix: carry
  `tof_mash_factor` in `ProjDataLayout` and show it. Non-TOF data is always one bin numbered 0.
* TOF bin numbers are not symmetric for an even count (e.g. -2..1). Everything here uses `min_tof..max_tof`, never `+-n/2`.
* `ProjData.to_array()/as_array()` return the whole 4D data (TOF, sinograms, views, tangential). It is simple but loads
  everything, so the viewer keeps reading one segment per TOF bin and caching.
* Multi-data-set sync should treat TOF separately: `same_geometry_as` can have a mode that ignores the TOF range, so a
  TOF and a non-TOF data set (or two with different TOF bin counts) can still link segment/axial/view/tangential.
  Linking the TOF *bin* only makes sense when the bin count and mash factor match (the same time per bin).
* TOF + multi display: overlay the per-LOR TOF profiles of all linked data sets on one plot (same LOR, different curves)
  and share the TOF reduction mode (bin / sum / mean / max) across linked panes.
* Memory: each data set caches all TOF bins of a segment, so N data sets cost N times that. The shared cache budget
  in section 8 matters most for TOF data.
