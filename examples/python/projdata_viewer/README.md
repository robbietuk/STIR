# stir-projdata-viewer

Interactive viewer for STIR projection data: sinograms, viewgrams and tangential slices, with
a time-of-flight (TOF) dimension you can step through, play back, or collapse.
PySide6 + pyqtgraph (no matplotlib), Python >= 3.11. A development tool: run it as a script,
no compiled executable.

This is a rewrite of `examples/python/projdata_visualisation` (PyQt5 + matplotlib), which is
left untouched on this branch. See [PLAN.md](PLAN.md) for design decisions and the roadmap.

## Install

STIR's Python module is a compiled extension and is **not** a pip dependency; the viewer finds it
at run time. Pick one:

```sh
# A) conda (recommended): STIR, Qt and the viewer in one environment
conda env create -f environment.yml && conda activate stir-viewer
pip install -e .                      # run from this directory

# B) existing STIR source build + a venv. The venv must use the SAME Python minor version (and a numpy
#    ABI compatible with) the one STIR was built against, or `import stir` will fail.
python -m venv .venv && . .venv/bin/activate
pip install -e .                      # numpy, PySide6, pyqtgraph
export LD_LIBRARY_PATH=<STIR install>/lib:$LD_LIBRARY_PATH   # DYLD_LIBRARY_PATH on macOS; on Windows --stir-path also registers <prefix>/bin and <prefix>/lib
stir-projdata-viewer file.hs --stir-path <STIR install>/python

# C) no STIR at all: numpy files and the synthetic demo still work
pip install -e . && stir-projdata-viewer --demo
```

## Loading data

The viewer accepts three kinds of input:

| Input | Needs `stir`? | Notes |
|---|---|---|
| STIR projection data: an Interfile header (`.hs`) or any other file `stir.ProjData.read_from_file` can open | yes | Read lazily, one segment (and TOF bin) at a time. |
| A numpy file (`.npy` / `.npz`) | no | See [numpy layout](#numpy-layout) below. |
| The built-in demo (`--demo`) | no | A synthetic TOF phantom, handy to check the install. |

### 1. From the command line

Run these from an environment where the viewer is installed (see [Install](#install)):

```sh
stir-projdata-viewer my_sinogram.hs                    # STIR projection data
stir-projdata-viewer -f my_sinogram.hs                 # same, old-tool spelling
python -m stir_projdata_viewer my_sinogram.hs          # same, without the console script
stir-projdata-viewer data.npz                          # numpy arrays
stir-projdata-viewer --demo                            # synthetic TOF demo
stir-projdata-viewer                                   # empty window: load from the GUI
stir-projdata-viewer my_sinogram.hs --theme light      # light colour scheme
```

If `stir` is a source build that is not on the Python path, tell the viewer where it is installed:

```sh
stir-projdata-viewer my_sinogram.hs --stir-path <STIR install prefix>/python
# or, once per shell:
export STIR_PYTHON_PATH=<STIR install prefix>/python
export DYLD_LIBRARY_PATH=<STIR install prefix>/lib:$DYLD_LIBRARY_PATH   # macOS (LD_LIBRARY_PATH on Linux)
```

The `.hs` header must sit next to its data file (`.s`) as STIR expects; relative paths in the header are
resolved by STIR, not by the viewer.

### 2. From the window

* Type or paste a path in the *Data* box and press **Load** (or Enter), or
* press **Browse...** (File > Open) and choose a `.hs`, `.npy` or `.npz` file, or
* use File > **Demo data** for the synthetic phantom.

If loading fails, the reason is shown in a banner at the top of the window and the previously loaded data
stays on screen. The most common message, *Could not import the 'stir' module*, means the viewer cannot see
STIR's Python bindings: use the conda environment, or `--stir-path` / `STIR_PYTHON_PATH` as above.

### 3. From Python

`launch` blocks until the window is closed. It takes a filename, a `stir.ProjData` object you already have
(for example one you just forward projected into), or nothing:

```python
from stir_projdata_viewer.app import launch    # `launch_GUI` is kept as an alias of the old name

launch("my_sinogram.hs")                         # a filename (.hs, .npy, .npz)

import stir
proj_data = stir.ProjData.read_from_file("my_sinogram.hs")
launch(proj_data)                                # an in-memory stir.ProjData

launch(demo=True)                                # the synthetic demo
launch("my_sinogram.hs", stir_path="/opt/stir/python", theme="light")
```

### numpy layout

* `.npz`: one array per segment, named `segment_<n>` (`n` may be negative, e.g. `segment_-1`). Each array is
  `(views, axial, tangential)` for non-TOF data or `(tof, views, axial, tangential)` for TOF data. Segment
  numbers must be contiguous (e.g. -1, 0, 1). All segments must have the same number of views, tangential
  positions and TOF bins; the axial size may differ.
* `.npy`: a single array with the same shape rules, shown as segment 0.

```python
import numpy as np
np.savez("data.npz", segment_0=seg0, **{"segment_-1": seg_m1, "segment_1": seg_p1})
```

## Using the window

In the window: the *Slice* box chooses sinogram / viewgram / tangential slice; *Time of flight*
chooses a single bin (with Play) or Sum / Mean / Max over all bins. Hovering shows the value, the
bin indices, and (for TOF data) the counts-versus-TOF-bin profile of the LOR under the cursor.
Keys: Space play/pause, Left/Right step the active index, PgUp/PgDn change segment.

## Architecture (MVVM)

```
stir module ─▶ stir_interface ─▶ model ◀─ viewmodel ◀─ view (PySide6 + pyqtgraph)
               gateway+adapter   pure     no Qt         thin binding
               (only layer       domain   observable
               that sees stir)   logic    props+commands
```

| Package | Knows about | Role |
|---|---|---|
| `model/` | numpy only | `ProjDataInfo`, immutable `Selection`, `ProjDataset` (slices, TOF reduction, caches, stats) |
| `sources/` | model | numpy `.npy/.npz` source, synthetic TOF demo, `make_source` |
| `stir_interface/` | model, `stir` | `StirGateway`/`StirProjDataHandle` protocols, `SwigStirGateway` (the only file importing `stir`), `StirProjDataSource` adapter |
| `viewmodel/` | model | `ViewerViewModel`: observable properties + command methods, formatting; shared `ChoiceOptions` and `BindingRegistry`; no Qt |
| `view/` | viewmodel, Qt | `ViewerWindow` binds reusable `components` to the view model; `theme` (colour scheme) is Qt-free; knows nothing about sources or STIR |
| `app.py` | everything | composition root: wires loader, demo data, view model and window |

`tests/test_architecture.py` enforces these import rules, and checks in a clean interpreter that the
Qt-free layers never load PySide6, pyqtgraph, matplotlib or `stir`.

## Look and feel

The UI uses one colour scheme (`view/theme.py`): a dark default and a light variant, chosen with
`--theme dark|light` or View > Light theme. Every colour comes from a `Palette` (text/background pairs are
tested for WCAG AA contrast, and a test fails if a widget file hard-codes a colour); `build_stylesheet`
turns the palette into the application stylesheet and the plots read the same palette.

Shared component logic lives in two places: Qt-free `viewmodel/options.py` (`ChoiceOptions`: one definition of
the labels/order of slice modes, TOF modes, level modes and colour maps) and `viewmodel/bindings.py`
(`BindingRegistry`: declarative property -> widget bindings, each run once per command), and Qt
`view/components.py` (`SegmentedControl` and `ChoiceCombo` share one `ChoiceControl` contract; `Card`,
`LabeledRow`, `ChipRow`, `MetricGrid`, `Banner`, `EmptyState`, `DimensionControl`). Errors appear in an inline,
dismissable banner instead of a modal dialog, and an empty state is shown until data is loaded.

## Tests

```sh
pip install -e .[test] && pytest
```

| Directory | What it covers | Needs |
|---|---|---|
| `tests/model` | selection clamping, slicing, TOF reductions, caches, stats, geometry | numpy |
| `tests/sources` | array/demo sources, file loading, loader dispatch | numpy |
| `tests/stir_interface` | SWIG gateway against a fake `stir`, adapter, one contract run on every handle implementation | numpy |
| `tests/viewmodel` | every command, notification batching, levels, hover/profile, failure paths, seeded random-command invariants | numpy |
| `tests/view` | window binding with stubbed Qt (always runs) and with real PySide6 offscreen (if installed) | Qt optional |
| `tests/stir_interface/test_real_stir_integration.py` | real bindings: contract, axis order vs STIR's own accessors, full stack on a real file | `stir` + a `.hs` (`STIR_TEST_PROJDATA`) |

## Differences from the old PyQt5/matplotlib tool

Kept: sinogram and viewgram modes (same axes and orientation), segment/axial/view/TOF controls, file
browse + typed path + Load, `launch(...)` with a path, a `stir.ProjData` or no argument (`launch_GUI` alias),
`-f FILE` on the command line, max-level control (now numeric Min/Max level boxes plus a draggable histogram).

Changed on purpose: no matplotlib toolbar; the slice is always shown as a fixed image with axis ticks (no zoom/pan), File > Save image;
vmin is no longer fixed at 0 (auto per slice, or fixed global range); the initial slice is the central one;
the data summary is shown in the Information panel instead of the console.

Dropped: the Qt style/palette selector; installation by STIR's CMake into the `stir` package
(this is a standalone project, so `python -m stir.projdata_visualisation` is unchanged and still the old tool).

## Known limitations

* Everything runs on the UI thread. Collapsing TOF bins, *Fixed (global range)* levels and the first hover on TOF
  data read every bin of one segment (all segments for the global range); on large TOF data this can take a while
  and use several GB (the cache holds all TOF bins of one segment). Not measured on real data yet.
* Left/Right arrow shortcuts apply to the whole window and take precedence over a focused slider.
* Written against PySide6 >= 6.6 and pyqtgraph >= 0.13.7 but not yet run against them: see PLAN.md section 4.
