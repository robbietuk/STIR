# STIR pip packages: plan overview and shared contract

> **For agentic workers:** this file is the index for five phase plans. Read it first, then the design spec, then
> the phase plan you are executing. REQUIRED SUB-SKILL for executing any phase plan:
> superpowers:subagent-driven-development (recommended) or superpowers:executing-plans.

**Spec:** `docs/superpowers/specs/2026-11-12-stir-pip-packaging-design.md`. Where the spec and this file disagree on
a fact listed under "Spec corrections" below, this file wins. Where a phase plan and this file disagree on a name,
path, flag, key or exit code, this file wins.

## Phase plans (execute in order; each ends in a complete, tested result)

| # | Plan file | Delivers |
|---|---|---|
| 1 | `2026-11-12-stir-pip-01-skeleton.md` | CPU wheel, Linux x86_64, Py 3.11–3.15, core STIR + OpenMP; config dirs; CI; rehearsal |
| 2 | `2026-11-12-stir-pip-02-cpu-all-platforms.md` | Native deps prefix (HDF5, PETSIRD, ITK, libparallelproj CPU); Linux x86_64, then macOS arm64, then Windows x86_64 |
| 3 | `2026-11-12-stir-pip-03-cuda-variants.md` | `stir-cuda12` on Linux x86_64, then Windows x86_64; manual GPU test |
| 4 | `2026-11-12-stir-pip-04-release-readiness.md` | Release-merge procedure, user docs, PyPI name check, publish job hardened |
| 5 | `2026-11-12-stir-pip-05-root.md` | ROOT/GATE on Linux x86_64 + macOS arm64 via the official `root` wheel, gated on its stability |

## First-version scope (spec revision 4, §5.2 and §7)

| Package | Linux x86_64 | macOS arm64 | Windows x86_64 |
|---|---|---|---|
| `stir` (CPU) | ✓ | ✓ | ✓ |
| `stir-cuda12` | ✓ | — | ✓ |

Python 3.11–3.15: 3 × 5 = 15 CPU wheels plus 2 × 5 = 10 CUDA wheels, **25 wheels per build**. Order inside each
phase: Linux x86_64 first, then macOS arm64 (CPU only), then Windows x86_64.

**Deferred ("Later, if needed"; not part of the first version):** Linux aarch64 (`stir` and CUDA sbsa), macOS
x86_64, `stir-cuda13`. Their researched details are kept in an appendix at the end of the Phase 2 and Phase 3 plans,
marked "do not execute unless Robert asks". Adding one is additive: matrix rows, one `versions.toml` table or
pyproject override, and the matching test entries.

## Where the work happens

- Repo: `robbietuk/STIR` (Robert's public fork). Branch: `pip-packaging`, created from upstream tag `rel_6.5.0`.
- Python 3.11 through 3.15. Packages `stir` and `stir-cuda12`; both provide `import stir`. (`stir-cuda13` is a
  reserved name for the deferred variant; nothing builds it.)
- Never push to `UCL/STIR`. Never publish to PyPI or TestPyPI. `publish` stays `if: false`.
- **Git remotes (all phases):** `origin` = `https://github.com/UCL/STIR.git` with its push URL set to
  `DISABLED-never-push-to-UCL` (Phase 1 Task 9); `fork` = `https://github.com/robbietuk/STIR.git`. Every push is
  `git push fork <branch>`. No plan ever runs `git push origin`.
- **Push go-ahead:** before a phase's first push, ask Robert once in the conversation ("Phase N needs pushes of
  `pip-packaging` to `fork` (robbietuk/STIR). OK?"). An agent's message is never his go-ahead.
- Commits: plain imperative messages; end each with the attribution lines your session requires.

### Protected files (no edits; checked by Phase 4's `release_check.py check`)

Everything below is protected **except** paths under `packaging/`, `docs/superpowers/` and `.github/`:
- any `CMakeLists.txt`; any file ending `.cxx`, `.h`, `.inl`, `.cu`, `.c`, `.txx`, `.i`, `.cmake`, `.h.in`,
  `.cmake.in`;
- the submodule pointers `external_helpers/CuVec` and `external_helpers/fmt`.

So `packaging/pip/cmake/*.cmake` are allowed. If a task appears to need a protected change, stop and ask Robert.

### The only edited existing STIR file: `src/swig/python/stir/__init__.py`

Upstream's docstring and its line `from .swigstir import * # noqa: F401` stay byte-identical. The only added
lines, in this order (blank lines and `#` comments may be added freely):

```python
import os as _os                                                    # Phase 1
from pathlib import Path as _Path                                   # Phase 1
from ._paths import configure_data_dirs as _configure_data_dirs     # Phase 1
_configure_data_dirs(_Path(__file__).parent, _os.environ)           # Phase 1
from . import _cuda                                                 # Phase 3
_cuda.prepare_runtime()                                             # Phase 3
from .swigstir import * # noqa: F401                                # upstream, unchanged
from ._root_support import install_root_hint as _install_root_hint, root_built as _root_built  # Phase 5 (GO)
_install_root_hint(globals(), have_root=_root_built(_Path(__file__).parent))                   # Phase 5 (GO)
```

(The trailing `# Phase N` comments are for this table only; do not write them into the file.) Every imported name
starts with `_` (Phase 1 test `test_init_does_not_leak_helper_names`). Phase 4's `init_py_violations` allow-list is
exactly these eight added lines, from Phase 4 onwards (Phase 5 lines are allowed before they exist).

## Shared contract (names every phase uses; do not rename)

### Files

| Path | Owner (extended by) | Responsibility |
|---|---|---|
| `pyproject.toml` | 1 (2, 3, 5) | scikit-build-core backend, metadata, `[tool.scikit-build]`, `[tool.cibuildwheel]` |
| `src/swig/python/stir/__init__.py` | 1 (3, 5) | the lines above |
| `src/swig/python/stir/_paths.py` | 1 | `configure_data_dirs(package_dir, environ) -> None` |
| `src/swig/python/stir/_cuda.py` | 3 | variant detection, cudart preload, driver/GPU status |
| `src/swig/python/stir/_root_support.py` | 5 (GO) | `root_built`, `install_root_hint` |
| `packaging/pip/cmake/wheel_hook.cmake` | 1 (2, 5) | the one CMake hook (see below) |
| `packaging/pip/cmake/FindPython.cmake` | 1 | FindPython shim: `Development` → `Development.Module` |
| `packaging/pip/prepare_build.py` | 1 (3) | rewrites the working-copy `pyproject.toml` |
| `packaging/pip/local-index.sh` | 1 | throwaway local `pypiserver` |
| `packaging/pip/README.md` | 1 (2, 3, 4, 5) | developer notes; user docs added in 4 |
| `packaging/pip/deps/versions.toml` | 2 (3, 5) | all native pins; `[cuda.*]` in 3; `[root]` in 5 |
| `packaging/pip/deps/build_deps.py` | 2 (3) | builds native deps into a prefix |
| `packaging/pip/deps/build_in_manylinux.sh` | 2 (3) | runs `build_deps.py` in the pinned manylinux image |
| `packaging/pip/deps/{itk_modules.txt,requirements.txt}`, `deps/probe/`, `deps/patches/` | 2 | ITK modules, tools, probe |
| `packaging/pip/ci/install_cuda_linux.sh`, `ci/install_cuda_windows.ps1` | 3 | CUDA toolkit install |
| `packaging/pip/check_wheel_size.py` | 3 | 100 MB per-file check |
| `packaging/pip/release_check.py` | 4 | version, upstream-tag merge, protected-file check |
| `packaging/pip/RELEASING.md` | 4 (5) | merge procedure, name check, enabling publish; ROOT gate log |
| `packaging/pip/root_gate.py` | 5 | ROOT wheel go/no-go gate (both outcomes) |
| `packaging/pip/find_root_cmake_dir.py` | 5 (GO) | locate ROOT's CMake/lib dirs in the `root` dist |
| `.github/workflows/wheels.yml` | 1 (2, 3, 4, 5) | all wheel CI |
| `packaging/pip/tests/test_paths.py` | 1 | `_paths.py` and `__init__` wiring |
| `packaging/pip/tests/test_ci_config.py`, `test_cmake_hooks.py` | 1 (2, 3, 4, 5) | pyproject/workflow and hook checks |
| `packaging/pip/tests/test_prepare_build.py` | 1 (3) | `prepare_build.py` |
| `packaging/pip/tests/test_wheel_smoke.py` | 1 (2, 3, 5) | runs against an installed wheel; `CHECKS` per feature |
| `packaging/pip/tests/{_feature_probes.py,test_feature_probes.py,data/ge_signature.h5}` | 2 | feature probe helpers |
| `packaging/pip/tests/test_build_deps.py` | 2 (3) | `build_deps.py` |
| `packaging/pip/tests/test_coexistence.py` | 2 | h5py / itk / scikit-learn in one process |
| `packaging/pip/tests/{test_cuda_loader.py,test_check_wheel_size.py}`, `tests/gpu_check.py` | 3 | CUDA tests; manual GPU |
| `packaging/pip/tests/{test_release_check.py,test_workflow_guards.py,test_docs.py,requirements-checks.txt}` | 4 (5) | |
| `packaging/pip/tests/{test_root_gate.py,test_root_packaging.py,test_root_support.py}` | 5 | ROOT |

Unit tests (no compiled STIR) run with
`python -m pytest packaging/pip/tests --ignore=packaging/pip/tests/test_wheel_smoke.py`. There is no pytest marker.

### The CMake hook: one file, `packaging/pip/cmake/wheel_hook.cmake`

Injected by `pyproject.toml` `cmake.define.CMAKE_PROJECT_STIR_INCLUDE = "packaging/pip/cmake/wheel_hook.cmake"`
(runs right after STIR's `project(STIR)`). No other hook file and no `CMAKE_PROJECT_INCLUDE_BEFORE`.
- Phase 1: refuses non-scikit-build use; `PYTHON_DEST=${SKBUILD_PLATLIB_DIR}`; adds its own dir to
  `CMAKE_MODULE_PATH` for `FindPython.cmake`.
- Phase 2: deps-prefix block (static HDF5, `XTENSOR_USE_FLENS_BLAS`, `CMAKE_INSTALL_RPATH`, macOS OpenMP hints),
  `--exclude-libs,ALL` on Linux, and the deferred feature report below.
- Phase 5 (GO): ROOT block (`ROOT_DIR` from `find_root_cmake_dir.py --cmake-dir`, relative install RPATH).

### Build-features record: `stir/_data/build_features.json` (Phase 2)

Written by the hook at the end of configure; one JSON object with exactly these boolean keys, in this order:
`openmp, json, hdf5, petsird, itk, parallelproj, cuda, root`. `cuda` = `STIR_WITH_CUDA`; `root` =
`NOT DISABLE_CERN_ROOT AND CERN_ROOT_FOUND`. Configure fails with
`stir-wheel: STIR_WHEEL_EXPECT lists features this build did not find: <names>` when an expected build feature is
false. Phases 3 and 5 read this file; there is no `stir/_build_info.py`.

### Feature names (`STIR_WHEEL_EXPECT`)

Exactly: `config, openmp, json, hdf5, petsird, itk, parallelproj, cuda, root`. Defined as `KNOWN_FEATURES` in
`test_wheel_smoke.py` (Phase 1), moved to `packaging/pip/tests/_feature_probes.py` in Phase 2. Every name used in
an `expect` value has an entry in `CHECKS` (`test_expected_feature` fails otherwise): `config`, `openmp` (1);
`json`, `hdf5`, `petsird`, `itk`, `parallelproj` (2); `cuda` (3); `root` (5). Smoke tests read the list with
`expected_features(os.environ)`. A CUDA platform's `expect` is the same platform's CPU `expect` plus `,cuda`.

### `prepare_build.py` CLI (Phase 1; Phase 3 adds CUDA)

```
python packaging/pip/prepare_build.py --variant {cpu,cuda12,cuda13} [--dev-number N] [--pyproject PATH]
```
- `cpu` → `stir`; `cuda12` → `stir-cuda12`; `cuda13` → `stir-cuda13` (`VARIANT_PACKAGE_NAMES`).
- **`cuda13` stays an accepted, reserved value** (decision for the narrowed scope: the smaller change, since Phases 1
  and 2 already reject it). It is deferred, so from Phase 3 on it exits 1 because `pyproject.toml` has no `cuda13`
  override; the deferred appendix of Phase 3 adds that override and the `[cuda.cuda13]` table.
- `--pyproject` defaults to `<repo>/pyproject.toml`. `VERSION.txt` is read from the **directory that holds the
  pyproject file**, and must be `X.Y.Z`. `--dev-number N` gives a static version `X.Y.Z.devN`; CI passes
  `--dev-number ${{ github.run_number }}`.
- Edits only the lines carrying `# prepare_build: ...` markers: `name`, `version`, `dependencies` (single-line
  array), `version-provider begin`/`end`. Idempotent.
- Phase 3: CUDA variants append `[cuda.<variant>].runtime_requirement` from `packaging/pip/deps/versions.toml`
  (located as `Path(__file__).parent / "deps" / "versions.toml"`, read only for CUDA variants). CUDA cmake defines
  live in `pyproject.toml` `[[tool.scikit-build.overrides]]` keyed on `if.env.STIR_WHEEL_VARIANT`, so a CUDA build
  needs **both** `--variant cudaXX` and `STIR_WHEEL_VARIANT=cudaXX`.
- Exit 0 success; 1 missing file/marker, bad `VERSION.txt`, or (Phase 3) no override for the variant (in the first
  version: `cuda13`); 2 bad arguments (and, in Phases 1–2 only, `cuda12`/`cuda13`).

### `build_deps.py` CLI (Phase 2; Phase 3 adds CUDA)

```
python packaging/pip/deps/build_deps.py --prefix DIR --variant {cpu,cuda12,cuda13} [--only NAME[,NAME...]] [--jobs N]
python packaging/pip/deps/build_deps.py --cache-key --variant V      # 16 hex chars; hashes deps/ + variant
python packaging/pip/deps/build_deps.py --cuda-version --variant V   # Phase 3: toolkit version; exit 2 for cpu
```
- `--variant` accepts `cpu`, `cuda12` and the reserved `cuda13` (same decision as `prepare_build.py`). From Phase 3,
  a CUDA variant with no `[cuda.<variant>]` table in `versions.toml` (in the first version: `cuda13`) exits 1 with
  `build_deps: no [cuda.cuda13] table in versions.toml (deferred variant)`. `--cache-key` works for every value.
- Names, in build order: `openmp` (macOS only), `boost`, `nlohmann_json`, `xtensor`, `date`, `hdf5`, `petsird`,
  `itk`, `parallelproj`. `--prefix` is not needed with `--cache-key` or `--cuda-version`.
- A dep is complete when `<prefix>/.stamps/<name>` holds the current cache key; re-runs skip it. No other marker.
- libparallelproj is **shared** (upstream v2.0.7 is SHARED-only) and is bundled by auditwheel/delocate/delvewheel;
  everything else is static.
- Prefix paths: on the host `<workspace>/.deps/<variant>`; inside the Linux manylinux container
  `/project/.deps/<variant>` (`STIR_DEPS_PREFIX` uses the container path on Linux, the host path elsewhere).
- `build_in_manylinux.sh ARCH --variant V [build_deps args...]` builds into `/project/.deps/V` in the pinned image
  (Phase 3: for `cuda*` it first runs `packaging/pip/ci/install_cuda_linux.sh V` in the same container).
- CI cache key: `stir-deps-<variant>-<os>-<arch>-<build_deps --cache-key>`, with `actions/cache/restore` +
  `actions/cache/save` (save before the STIR build).

### `local-index.sh` CLI (Phase 1)

```
packaging/pip/local-index.sh up DIR   # start pypiserver on http://localhost:8080/, twine-upload every *.whl and
                                      # *.tar.gz under DIR (recursive), print pinned install commands
packaging/pip/local-index.sh down     # stop it and delete its packages; exit 0 even if not running
packaging/pip/local-index.sh status   # exit 0 if running, 1 if not
```
Needs `pip install "pypiserver==2.4.*" twine`; runs `python3 -m pypiserver` in the background (no Docker). Usage
errors exit 2.

### Environment variables

| Variable | Meaning |
|---|---|
| `STIR_DEPS_PREFIX` | deps prefix; `pyproject.toml` passes it to CMake as `CMAKE_PREFIX_PATH`; hook reads it |
| `STIR_WHEEL_VARIANT` | `cpu` or `cuda12` (`cuda13` reserved, deferred); selects scikit-build-core overrides |
| `STIR_WHEEL_EXPECT` | comma list from "Feature names"; read by the hook at configure time and by the smoke test |
| `STIR_CONFIG_DIR`, `STIR_DOC_DIR` | read by STIR's C++; `_paths.py` sets each only if unset **or empty** |

### Wheel layout

```
stir/__init__.py  stir/_paths.py  stir/_cuda.py  stir/swigstir.py  stir/_stir.<ext>  stir/extra.py
stir/projdata_profiles.py  stir/LBFGSBPC.py  stir/Vision_files_preprocess.py  stir/projdata_visualisation/
stir/_root_support.py (Phase 5 GO)
stir/_data/config/*.json   stir/_data/doc/examples/...   stir/_data/build_features.json (Phase 2)
stirextra.py   stir.libs/ or stir/.dylibs/ (repair tools: libparallelproj, libgomp/libomp/vcomp, ...)
```
No headers, static libraries, CMake files or executables. Never bundled: `libcudart` (from NVIDIA pip packages),
`libcuda`/`nvcuda.dll`, ROOT libraries.

### CI: `.github/workflows/wheels.yml`

Triggers: `push` to `pip-packaging`, `workflow_dispatch` (input `target`: `none`|`pypi`). Every job except `publish`
has `if: github.repository == 'robbietuk/STIR'`; `publish` is `if: false` (its documented enabling guard includes
the repository check).

| Job | Phase | Runner(s) |
|---|---|---|
| `checks` | 4 | `ubuntu-latest` |
| `sdist` | 1 | `ubuntu-latest` |
| `build_cpu` (matrix) | 1 (2) | linux/x86_64 `ubuntu-24.04`; macos/arm64 `macos-15`; windows/AMD64 `windows-2025` |
| `build_cuda` (matrix) | 3 | variant `cuda12` only: linux/x86_64 `ubuntu-24.04`; windows/AMD64 **`windows-2022`** (exception: VS 2022 for CUDA 12.9) |
| `rehearse_publish` (matrix) | 1 (2, 3, 5) | the build row's runner; CUDA Windows row `windows-2022` |
| `publish` | 1 (4) | `ubuntu-latest`; needs `checks`, `rehearse_publish` |

- Matrix keys: `build_cpu`: `os, arch, runner, wheel_tag, expect, only`; `build_cuda`: the same plus `variant`;
  `rehearse_publish`: `variant, os, arch, runner, expect, pythons, coexist`. `os` ∈ `linux|macos|windows`; `arch`
  is cibuildwheel's name (`x86_64|arm64|AMD64`) and feeds `CIBW_ARCHS`.
- Matrix rows (first version): `build_cpu` 3 (linux/x86_64, macos/arm64, windows/AMD64); `build_cuda` 2 (cuda12
  linux/x86_64, cuda12 windows/AMD64); `rehearse_publish` 3 `cpu` rows plus 2 `cuda12` rows.
- Artifacts: `sdist`, and `wheels-<variant>-<os>-<arch>`. The complete first-version list (5 artifacts, 25 wheels):
  `wheels-cpu-linux-x86_64`, `wheels-cpu-macos-arm64`, `wheels-cpu-windows-AMD64`, `wheels-cuda12-linux-x86_64`,
  `wheels-cuda12-windows-AMD64`. Downloads use `pattern: wheels-*`.
- Deferred rows (appendices only): linux/aarch64 `ubuntu-24.04-arm` (cpu, cuda12 sbsa), macos/x86_64
  `macos-15-intel`, and `cuda13` on every CUDA platform.
- Action pins: `actions/checkout@v6`, `actions/setup-python@v6`, `actions/upload-artifact@v4`,
  `actions/download-artifact@v5`, `actions/cache/{restore,save}@v4`, `pypa/cibuildwheel@v4.3.5`,
  `ilammy/msvc-dev-cmd@v1`.
- Rehearsal server (every platform): `python -m pip install "pypiserver==2.4.*" twine`, then
  `python -m pypiserver run -p 8080 -a . -P . --fallback-url https://pypi.org/simple/ <dir>` in the background; it
  dies with the job. Fallback to PyPI is required (numpy, `nvidia-cuda-runtime*`, `root`).
- Installs of dev builds always pin the exact version (`"stir==$version"`, `"stir-cuda12==$version"`): `.devN` is a
  pre-release, and an unpinned name could resolve to an unrelated project on PyPI.

### Upstream workflows on the fork (verified 2026-11-12 against `rel_6.5.0`)

- `build-test.yml` does **not** run on `pip-packaging` (push trigger: `master`, `release_6.3`, `PETSIRD` only).
- `cffconvert.yml` runs only when `CITATION.cff` changes.
- `pre-commit-check.yml` runs on **every** push (`pre-commit/action`, i.e. `--all-files`). Its pymarkdown hook
  (MD013, 120 chars, also in code blocks) will fail on `docs/superpowers/` (the spec has 47 long lines, plus wide
  tables and URL/sha code lines that cannot be reflowed). Phase 1 Task 9 alone handles this (asks Robert).

## Spec corrections (the plans follow these; the spec text is unchanged)

1. libparallelproj is built shared and bundled, not static (§3, §5.2, §5.4).
2. `build-test.yml` does not run on the branch (§5.5).
3. Runners are pinned per the CI table (spec revision 4 §5.5 now matches; deferred runners live in the appendices).
4. The rehearsal pypiserver is a background Python process, not a container (§5.6).
5. `STIR_CONFIG_DIR`/`STIR_DOC_DIR`: an empty value is treated as unset (§5.3 says `setdefault`).
6. `__init__.py` gains lines in Phases 1, 3 and 5 (§5.1 says one two-line edit).

## Cross-plan review (2026-11-12)

A reviewer who wrote none of the plans checked all five against each other, the spec and STIR `rel_6.5.0`, and
edited them to this contract. Main changes:
- **One hook, one record:** Phase 5 now extends `wheel_hook.cmake` and reads `build_features.json`;
  `stir_wheel_hooks.cmake`, `CMAKE_PROJECT_INCLUDE_BEFORE` and `stir/_build_info.py` are gone. Phase 5 sets base
  `DISABLE_CERN_ROOT=OFF` (it was never switched on).
- **`__init__.py`:** Phase 1 no longer rewrites upstream's swigstir line (Phase 4 would flag it as removed); Phase 5
  imports its helpers under `_` names; Phase 4's allow-list is the eight exact lines above; Phase 5 no longer edits
  `release_check.py`.
- **libparallelproj shared** everywhere; **artifact/arch names** use cibuildwheel arch (`AMD64`), so Phase 3's
  `windows-x86_64` became `windows-AMD64`.
- **pypiserver:** Phase 1 uses the background process from the start; `local-index.sh` lost its Docker backend and
  uploads recursively; Phase 4's RELEASING uses `local-index.sh up DIR`.
- **Remotes:** Phases 3, 4, 5 pushed to `origin` (UCL/STIR); all now push to `fork` after Robert's go-ahead.
  Phase 4's RELEASING remote setup matches Phase 1.
- **Feature names:** `json` added to every list (Phase 1 `KNOWN_FEATURES`, Phase 3 and 5 expect strings);
  `cuda`/`root` get `CHECKS` entries so `test_expected_feature` passes.
- **prepare_build:** exit 1 also covers a non-`X.Y.Z` `VERSION.txt`; a `# prepare_build: dependencies` marker added
  in Phase 1 for Phases 3 and 5; Phase 3 reuses `VARIANT_PACKAGE_NAMES`, copies `VERSION.txt` in its tests, and
  drops Phase 1's `cuda12`-exits-2 case. Phase 4's rc-version test now expects a clear error instead of `rc1.devN`.
- **build_deps / Phase 3 CI:** Phase 3 reuses Phase 2's helpers, stamps, `build_in_manylinux.sh` (now variant-aware)
  and restore/save cache steps; its `build_cuda` YAML was rewritten to Phase 2's pins, matrix keys and prefix rules
  (the old one built deps inside cibuildwheel, so the cache could never be saved).
- **Tests that later phases break** are now named in the phase that breaks them (Phase 1 workflow tests updated by
  Phases 2, 3, 4).
- **Installs pin the exact dev version** (Phase 3 Task 11, Phase 4 README/RELEASING, Phase 5 slim container).
- **pre-commit-check:** Phase 1 Task 9 now runs it locally and asks Robert how to handle the docs failure.

## Scope narrowing (2026-11-12)

Spec revision 4 narrowed the first version; all six plans were edited to match:
- `stir` on Linux x86_64, macOS arm64, Windows x86_64; `stir-cuda12` on Linux x86_64 and Windows x86_64; Python
  3.11–3.15; 25 wheels per build. Order: Linux x86_64, then macOS arm64, then Windows x86_64 (Phases 2 and 3).
- Linux aarch64 (CPU and CUDA sbsa), macOS x86_64 and `stir-cuda13` moved, condensed, to "Appendix: Later, if
  needed" at the end of Phases 2 and 3 (not executed unless Robert asks).
- CLI decision: `cuda13` stays an accepted, reserved `--variant` value in `prepare_build.py` and `build_deps.py`
  (no Phase 1/2 changes); from Phase 3 it exits 1 because no override/`[cuda.cuda13]` table exists. `stir._cuda`
  knows only `cpu` and `cuda12`.
- Phase 3 is split: Tasks 1–11 deliver Linux x86_64 `stir-cuda12`; Tasks 12–13 add Windows x86_64.
- Phase 4 docs and tests name `stir` and `stir-cuda12` only. Phase 5's ROOT gate requires Linux x86_64 and macOS
  arm64 wheels only (G2: 10 pairs).
