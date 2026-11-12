# STIR pip packages, Phase 1 (Skeleton) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A tested `stir` CPU wheel for Linux x86_64 on Python 3.11–3.15 (core STIR + OpenMP) that finds its own
config files with no environment variables, built by CI, with an sdist and a publish rehearsal against a throwaway
`pypiserver`.

**Architecture:** A root `pyproject.toml` drives STIR's existing CMake through scikit-build-core. Two small CMake files
under `packaging/pip/cmake/` are injected through CMake's `CMAKE_PROJECT_STIR_INCLUDE` hook. They put the `stir`
package at the wheel root and let FindPython work without libpython (manylinux). No STIR CMake file is edited.
Config JSON and examples are copied into `stir/_data/` by `wheel.force-include`. `stir/__init__.py` points STIR's
C++ at them through `STIR_CONFIG_DIR`/`STIR_DOC_DIR` before loading the extension. cibuildwheel builds and tests
the wheels. A GitHub workflow uploads artifacts and rehearses a twine upload to a `pypiserver` process that only
lives inside the job.

**Tech Stack:** scikit-build-core ≥ 1.1, CMake ≥ 3.24, Ninja, SWIG ≥ 4.2 (PyPI `swig`), NumPy ≥ 2 (build),
cibuildwheel v4.3.5, manylinux_2_28, pytest, PyYAML (tests only), twine, pypiserver 2.4 (pip, background process),
GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-12-stir-pip-packaging-design.md`. Shared contract (names, CLIs, env vars,
jobs, artifacts): `docs/superpowers/plans/2026-11-12-stir-pip-00-overview.md`. Where this plan and the contract
disagree on a name, the contract wins. See "Contract concerns" at the end.

## Global Constraints

- **No changes to STIR's C++ code.** No edits to any protected file (list in the overview). The only edit to an
  existing STIR file is `src/swig/python/stir/__init__.py`, with exactly the overview's Phase 1 lines.
- **Nothing on UCL/STIR during development.** Work lives on branch `pip-packaging` of `robbietuk/STIR`, created
  from tag `rel_6.5.0`. The local `origin` remote points at `UCL/STIR`; never push to it.
- **No publishing to PyPI or TestPyPI during development.** The real `publish` job exists with `if: false`.
- **Python 3.11 through 3.15.** One wheel per Python version, no abi3 (SWIG `-builtin`).
- **Linux uses `manylinux_2_28`.** Phase 1: CPU only, Linux x86_64 only, core STIR + OpenMP. Every optional
  dependency is disabled.
- **Package name** `stir`. Version read from `VERSION.txt` (`6.5.0`). CI builds get `.devN` with
  `N = github.run_number`.
- **Build requirements:** `scikit-build-core`, `swig>=4.2` (from PyPI), `numpy>=2`, `cmake`, `ninja`.
- **No environment variables needed by users.** `STIR_CONFIG_DIR`/`STIR_DOC_DIR` are set only when the wheel's
  `_data` folder exists, and a user's own setting wins.
- **Headers, static libs, CMake config and executables are excluded from the wheel.**
- **Workflow:** triggers `push` to `pip-packaging` and `workflow_dispatch` only. Every job has
  `if: github.repository == 'robbietuk/STIR'`. Jobs: `sdist`, `build_cpu`, `rehearse_publish`, `publish`.
  Artifacts: `wheels-cpu-linux-x86_64`, `sdist`.
- **Commits:** plain imperative messages. End each with the attribution lines your session requires. Do not push
  until Task 9 and Robert's explicit go-ahead. Remotes: `origin` = UCL/STIR (push disabled), `fork` = robbietuk/STIR.

## Review Focus

1. **Moved venv, or site-packages under a path with spaces or non-ASCII characters.** `import stir` must still find
   its config files with no env vars. Tests: Task 2 `test_path_with_spaces_and_non_ascii`, Task 5
   `test_relocated_copy_finds_its_own_data`.
2. **User already has `STIR_CONFIG_DIR` set, possibly to an empty string.** A non-empty value must win. An empty
   value must be treated as unset; otherwise STIR would look in `/radionuclide_names.json`. Tests: Task 2
   `test_user_values_win` and `test_empty_user_value_is_treated_as_unset`, Task 5 `test_user_config_dir_wins` and
   `test_empty_config_dir_is_ignored`.
3. **Dev builds are pre-releases.** `6.5.0.devN` is never picked by a plain `pip install stir`, so the documented
   install command must pin the exact version. Tests: Task 7 `test_rehearsal_installs_exact_dev_version` (the
   rehearsal uses the README command form). Task 8 documents it.
4. **The wheel is built against NumPy 2.x but the user has NumPy 1.26 on Python 3.11.** The spec promises NumPy
   ≥ 1.24 at runtime, so `import stir` and the STIR test suite must work there. Test: Task 7 rehearsal step
   "NumPy 1.x at runtime", pinned by `test_rehearsal_covers_numpy1`.
5. **`prepare_build.py` is run twice on the same working copy** (CI re-run, local re-use). The result must still be
   valid TOML with exactly one version. Test: Task 4 `test_rewrite_is_idempotent`.

## File Structure

| Path | Task | Responsibility |
|---|---|---|
| `packaging/pip/README.md` | 1, 8 | developer notes; Python 3.15 status |
| `src/swig/python/stir/_paths.py` | 2 | `configure_data_dirs(package_dir, environ)` |
| `src/swig/python/stir/__init__.py` | 2 | calls `configure_data_dirs` before loading `swigstir` |
| `packaging/pip/tests/test_paths.py` | 2 | unit tests for `_paths.py` and the `__init__.py` wiring |
| `pyproject.toml` | 3 | scikit-build-core + cibuildwheel configuration |
| `packaging/pip/cmake/wheel_hook.cmake` | 3 | injected after `project(STIR)`: `PYTHON_DEST`, module path |
| `packaging/pip/cmake/FindPython.cmake` | 3 | wheel-only FindPython shim: `Development` → `Development.Module` |
| `packaging/pip/tests/test_ci_config.py` | 3, 7 | static checks of `pyproject.toml` and `wheels.yml` |
| `packaging/pip/tests/test_cmake_hooks.py` | 3 | configures a tiny CMake project with the hook files |
| `packaging/pip/prepare_build.py` | 4 | rewrites the working-copy `pyproject.toml` (variant, `.devN`) |
| `packaging/pip/tests/test_prepare_build.py` | 4 | unit tests for `prepare_build.py` |
| `packaging/pip/tests/test_wheel_smoke.py` | 5 | runs against an installed wheel; honours `STIR_WHEEL_EXPECT` |
| `packaging/pip/local-index.sh` | 6 | throwaway local `pypiserver` + twine upload |
| `.github/workflows/wheels.yml` | 7 | `sdist`, `build_cpu`, `rehearse_publish`, `publish` |

`packaging/pip/tests/` has no `__init__.py`. Unit tests load the modules under test by file path with
`importlib.util.spec_from_file_location`, so they never import a compiled `stir`. All tests compute the repository
root as `REPO = Path(__file__).resolve().parents[3]`. Unit tests run with
`python3 -m pytest packaging/pip/tests --ignore=packaging/pip/tests/test_wheel_smoke.py`.

---

### Task 1: Check Python 3.15 support in the toolchain

**Files:**

- Create: `packaging/pip/README.md` (only the `## Python 3.15 status` section for now)

**Interfaces:**

- Produces: a decision, recorded in the README, that Tasks 3 and 7 apply. Either **KEEP-315** (the default config
  in this plan) or **SKIP-315**, plus **MPL-315** (whether matplotlib has cp315 wheels).

- [ ] **Step 1: Query PyPI for cp315 manylinux x86_64 wheels**

```bash
python3 - <<'EOF'
import json, urllib.request
for pkg in ["numpy", "matplotlib", "swig", "scikit-build-core", "cibuildwheel"]:
    d = json.load(urllib.request.urlopen(f"https://pypi.org/pypi/{pkg}/json"))
    files = [f["filename"] for f in d["urls"] if f["filename"].endswith(".whl")]
    cp315 = any("-cp315-" in f and "manylinux" in f and "x86_64" in f for f in files)
    print(f"{pkg:18} {d['info']['version']:10} cp315_manylinux_x86_64={cp315}")
EOF
gh release view --repo pypa/cibuildwheel --json tagName,publishedAt
```

Expected (researched 2026-11-12): `numpy` ≥ 2.5.2 with `cp315_manylinux_x86_64=True`. NumPy 2.5.2 ships 3.15
wheels; NumPy 2.5 dropped 3.11, which still gets NumPy 2.4.x. `swig`, `scikit-build-core` and `cibuildwheel` are
pure/py3 wheels (cp315 False is fine). Check that `swig` ≥ 4.2 and `scikit-build-core` ≥ 1.1. `cibuildwheel` should
be `v4.3.5` or newer; v4.2.0+ builds cp315 by default. `matplotlib` is unknown: record what you see. If
`pypi.org` is unreachable from this machine, read the same JSON URLs with the web-fetch tool. Do not guess.

- [ ] **Step 2: Decide**

- numpy has cp315 manylinux x86_64 wheels **and** cibuildwheel ≥ v4.2.0 → **KEEP-315**. Change nothing.
- Otherwise → **SKIP-315**. In Task 3, add `"cp315-*"` to `[tool.cibuildwheel] skip`, with the comment
  `# Python 3.15 waits for <missing tool>; see packaging/pip/README.md`. In Task 7, drop `cp315` from the
  wheel-set loop, `3.15` from `setup-python` and the rehearsal loop, and change `-eq 5` to `-eq 4`. Other Python
  versions are not blocked (spec §3).
- matplotlib has no cp315 wheel → **MPL-315 = no**. In Task 3, add the cibuildwheel override shown in Task 3
  Step 3. Only `src/swig/test/python/test_projdata_profiles.py` imports matplotlib.
- If a later cp315 *compile* fails in CI (for example SWIG-generated code against the 3.15 C API), apply SKIP-315
  then and record the error in the README.

- [ ] **Step 3: Write `packaging/pip/README.md`**

Write a `# STIR pip packaging: developer notes` title and a `## Python 3.15 status` section. It holds the date, the
versions seen in Step 1 and the decisions. Lines must be ≤ 120 characters (STIR's pymarkdown rule MD013).

- [ ] **Step 4: Commit**

```bash
git add packaging/pip/README.md
git commit -m "Record Python 3.15 toolchain support for pip wheels"
```

---

### Task 2: Self-contained config and doc directories

**Files:**

- Create: `src/swig/python/stir/_paths.py`
- Modify: `src/swig/python/stir/__init__.py:9` (the line `from .swigstir import * # noqa: F401`)
- Test: `packaging/pip/tests/test_paths.py`

**Interfaces:**

- Produces: `configure_data_dirs(package_dir: pathlib.Path, environ: MutableMapping[str, str]) -> None`, in module
  `stir._paths`. For each pair (`STIR_CONFIG_DIR`, `_data/config`) and (`STIR_DOC_DIR`, `_data/doc`): if
  `package_dir.absolute() / sub` is a directory **and** `environ.get(var)` is missing or `""`, set
  `environ[var] = str(that absolute path)`. If `package_dir / "_data"` does not exist, do nothing (conda/source
  installs are unchanged). Use `Path.absolute()`, not `resolve()`: keep the user-visible path and don't follow
  symlinks.
- Produces: `stir/__init__.py` imports only underscore-prefixed helper names, so `stir.os` etc. do not appear.
  These four lines go between the docstring and upstream's line `from .swigstir import * # noqa: F401`, which stays
  byte-identical (Phase 4's `release_check.py` reports any changed upstream line). Phase 3 later adds two lines
  after them (overview).

```python
import os as _os
from pathlib import Path as _Path

from ._paths import configure_data_dirs as _configure_data_dirs

_configure_data_dirs(_Path(__file__).parent, _os.environ)
```

- [ ] **Step 1: Write the failing tests in `packaging/pip/tests/test_paths.py`**

Load `_paths.py` with `spec_from_file_location("stir_paths", REPO / "src/swig/python/stir/_paths.py")`. Add a
helper `make_pkg(root, *subs)` that creates `root/_data/<sub>` for each sub and returns `root`.

```python
def test_sets_both_dirs_when_data_present(tmp_path):
    pkg = make_pkg(tmp_path, "config", "doc"); env = {}
    configure_data_dirs(pkg, env)
    assert env == {"STIR_CONFIG_DIR": str(pkg / "_data" / "config"), "STIR_DOC_DIR": str(pkg / "_data" / "doc")}

def test_no_data_dir_changes_nothing(tmp_path):
    env = {"OTHER": "x"}; configure_data_dirs(tmp_path, env); assert env == {"OTHER": "x"}

def test_only_existing_subdirs_are_set(tmp_path):
    env = {}; configure_data_dirs(make_pkg(tmp_path, "config"), env); assert set(env) == {"STIR_CONFIG_DIR"}

def test_user_values_win(tmp_path):
    env = {"STIR_CONFIG_DIR": "/mine", "STIR_DOC_DIR": "/mydoc"}
    configure_data_dirs(make_pkg(tmp_path, "config", "doc"), env)
    assert env == {"STIR_CONFIG_DIR": "/mine", "STIR_DOC_DIR": "/mydoc"}

def test_empty_user_value_is_treated_as_unset(tmp_path):
    pkg = make_pkg(tmp_path, "config"); env = {"STIR_CONFIG_DIR": ""}
    configure_data_dirs(pkg, env); assert env["STIR_CONFIG_DIR"] == str(pkg / "_data" / "config")

def test_relative_package_dir_gives_absolute_paths(tmp_path, monkeypatch):
    make_pkg(tmp_path / "pkg", "config"); monkeypatch.chdir(tmp_path); env = {}
    configure_data_dirs(Path("pkg"), env)
    assert env["STIR_CONFIG_DIR"] == str(tmp_path / "pkg" / "_data" / "config")

def test_path_with_spaces_and_non_ascii(tmp_path):
    pkg = make_pkg(tmp_path / "my env ü" / "stir", "config"); env = {}
    configure_data_dirs(pkg, env); assert env["STIR_CONFIG_DIR"] == str(pkg / "_data" / "config")

def test_init_configures_before_importing_swigstir():
    tree = ast.parse((REPO / "src/swig/python/stir/__init__.py").read_text())
    stmts = [ast.unparse(s) for s in tree.body]
    call = stmts.index("_configure_data_dirs(_Path(__file__).parent, _os.environ)")
    star = stmts.index("from .swigstir import *")
    assert call < star

def test_init_does_not_leak_helper_names():
    tree = ast.parse((REPO / "src/swig/python/stir/__init__.py").read_text())
    names = [a.asname or a.name for s in tree.body if isinstance(s, (ast.Import, ast.ImportFrom))
             for a in s.names if a.name != "*"]
    assert names and all(n.startswith("_") for n in names)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest packaging/pip/tests/test_paths.py -v`
Expected: FAIL. Collection error `FileNotFoundError` for `_paths.py`, or the `__init__` tests fail with
`ValueError: ... is not in list`.

- [ ] **Step 3: Implement `configure_data_dirs` in `src/swig/python/stir/_paths.py` and edit `__init__.py`**

Add STIR's licence header (copy the SPDX style of `src/swig/python/stir/extra.py`) and a module docstring saying
why: pip wheels carry their data in `stir/_data`. Keep the existing `__init__.py` docstring and its
`from .swigstir import * # noqa: F401` line unchanged. Insert the block from Interfaces between them.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest packaging/pip/tests/test_paths.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/swig/python/stir/_paths.py src/swig/python/stir/__init__.py packaging/pip/tests/test_paths.py
git commit -m "Point STIR at config files shipped inside the pip wheel"
```

---

### Task 3: Build configuration (pyproject.toml and CMake hook files)

**Files:**

- Create: `pyproject.toml`, `packaging/pip/cmake/wheel_hook.cmake`, `packaging/pip/cmake/FindPython.cmake`
- Test: `packaging/pip/tests/test_ci_config.py` (pyproject part), `packaging/pip/tests/test_cmake_hooks.py`

**Interfaces:**

- Consumes: Task 1 decision (KEEP-315 / SKIP-315, MPL-315).
- Produces: marker comments that Task 4 edits: `# prepare_build: name`, `# prepare_build: version`,
  `# prepare_build: version-provider begin` / `end`; plus `# prepare_build: dependencies` on the single-line
  `dependencies` array, reserved for Phase 3 (CUDA runtime) and Phase 5 (`root`). Also
  `STIR_WHEEL_EXPECT = "config,openmp"` as the
  cibuildwheel test environment. The wheel layout is the contract's, plus the extra Python files STIR's own
  install rules put into `stir/` (`projdata_profiles.py`, `LBFGSBPC.py`, `Vision_files_preprocess.py`,
  `projdata_visualisation/`).

Why the hook files: scikit-build-core sets `CMAKE_INSTALL_PREFIX` to the wheel's platlib, so STIR's default
`PYTHON_DEST` (`${CMAKE_INSTALL_PREFIX}/python`) would put the package under `python/stir/`. And
`src/swig/CMakeLists.txt` asks FindPython for `Development`, which includes `Development.Embed` and needs libpython.
manylinux images have no libpython. The extension only links `Python::Module`, so `Development.Module` is enough.
`CMAKE_PROJECT_STIR_INCLUDE` (CMake ≥ 3.15) runs a file right after `project(STIR)`. A relative path is resolved
against the source dir (verified with CMake 3.28).

- [ ] **Step 1: Write the failing tests**

`packaging/pip/tests/test_ci_config.py` (pyproject part). Parse with `tomllib` at module level:
`PY = tomllib.loads((REPO / "pyproject.toml").read_text())`, `SKB = PY["tool"]["scikit-build"]`,
`DEFINES = SKB["cmake"]["define"]`, `CIBW = PY["tool"]["cibuildwheel"]`.

```python
def test_build_backend_and_requirements():
    assert PY["build-system"]["build-backend"] == "scikit_build_core.build"
    assert set(PY["build-system"]["requires"]) == {
        "scikit-build-core>=1.1", "swig>=4.2", "numpy>=2", "cmake>=3.24", "ninja>=1.11"}

def test_project_metadata():
    p = PY["project"]
    assert (p["name"], p["requires-python"], p["dynamic"], p["dependencies"]) == (
        "stir", ">=3.11", ["version"], ["numpy>=1.24"])

def test_every_disable_option_is_set_explicitly():
    names = set(re.findall(r"option\s*\(\s*(DISABLE_\w+)", (REPO / "CMakeLists.txt").read_text(), re.I))
    assert names | {"DISABLE_STIR_CUDA"} <= DEFINES.keys()

def test_phase1_disables_every_optional_dependency():   # Phase 2 rewrites this test
    assert {k: v for k, v in DEFINES.items() if k.startswith("DISABLE_")} == dict.fromkeys(
        ["DISABLE_CERN_ROOT", "DISABLE_HDF5", "DISABLE_ITK", "DISABLE_LLN_MATRIX", "DISABLE_NLOHMANN_JSON",
         "DISABLE_NiftyPET_PROJECTOR", "DISABLE_PETSIRD", "DISABLE_Parallelproj_PROJECTOR", "DISABLE_STIR_CUDA",
         "DISABLE_STIR_LOCAL", "DISABLE_UPENN"], "ON")

def test_build_switches():
    expected = {"BUILD_SWIG_PYTHON": "ON", "BUILD_EXECUTABLES": "OFF", "BUILD_TESTING": "OFF",
                "BUILD_SHARED_LIBS": "OFF", "BUILD_DOCUMENTATION": "OFF", "STIR_OPENMP": "ON", "STIR_MPI": "OFF",
                "GRAPHICS": "None", "GIT_SUBMODULE": "OFF",
                "CMAKE_PROJECT_STIR_INCLUDE": "packaging/pip/cmake/wheel_hook.cmake"}
    assert {k: DEFINES[k] for k in expected} == expected
    assert (REPO / DEFINES["CMAKE_PROJECT_STIR_INCLUDE"]).is_file()

def test_wheel_contents_config():
    assert SKB["wheel"]["packages"] == []
    assert {"include/**", "lib/**", "bin/**", "share/**"} <= set(SKB["wheel"]["exclude"])
    assert SKB["wheel"]["force-include"] == {"src/config": "stir/_data/config",
                                             "examples": "stir/_data/doc/examples"}
    assert (REPO / "src/config/radionuclide_names.json").is_file()

def test_cibuildwheel_targets():
    assert CIBW["build"] == ["cp311-*", "cp312-*", "cp313-*", "cp314-*", "cp315-*"]
    assert CIBW["test-environment"] == {"STIR_WHEEL_EXPECT": "config,openmp"}
    assert CIBW["linux"]["manylinux-x86_64-image"] == "manylinux_2_28"
    assert any("packaging/pip/tests/test_wheel_smoke.py" in c for c in CIBW["test-command"])
    assert any(c.endswith("{project}/src/swig/test/python") for c in CIBW["test-command"])
```

`packaging/pip/tests/test_cmake_hooks.py`. Each test writes this `CMakeLists.txt` into `tmp_path / "proj"`. It
mirrors the STIR lines that matter. The tests then run
`cmake -S proj -B build -DPython_LIBRARY=<tmp>/missing/libpython3.so <extra>` with
`subprocess.run(..., capture_output=True, text=True)`. The bogus `Python_LIBRARY` simulates manylinux, where there
is no libpython.

```cmake
cmake_minimum_required(VERSION 3.14)
project(STIR C CXX)
set(CMAKE_MODULE_PATH "${PROJECT_SOURCE_DIR}/src/cmake;${CMAKE_MODULE_PATH}")
set(PYTHON_DEST ${CMAKE_INSTALL_PREFIX}/python CACHE PATH "Destination for python module")
find_package(Python REQUIRED COMPONENTS Interpreter Development)
message(STATUS "PYTHON_DEST=${PYTHON_DEST}")
if(TARGET Python::Module)
  message(STATUS "HAS_PYTHON_MODULE_TARGET")
endif()
```

```python
def test_without_hook_development_fails_when_libpython_missing(tmp_path):
    assert configure(tmp_path, []).returncode != 0

def test_hook_sets_python_dest_and_finds_module(tmp_path):
    r = configure(tmp_path, [f"-DCMAKE_PROJECT_STIR_INCLUDE={HOOK}", f"-DSKBUILD_PLATLIB_DIR={tmp_path}/platlib"])
    assert r.returncode == 0, r.stderr
    assert f"PYTHON_DEST={tmp_path}/platlib" in r.stdout and "HAS_PYTHON_MODULE_TARGET" in r.stdout

def test_hook_refuses_non_scikit_build_use(tmp_path):
    r = configure(tmp_path, [f"-DCMAKE_PROJECT_STIR_INCLUDE={HOOK}"])
    assert r.returncode != 0 and "only for scikit-build-core" in r.stderr
```

`HOOK = REPO / "packaging/pip/cmake/wheel_hook.cmake"`. Tests need a `cmake` ≥ 3.24 on PATH (ubuntu-latest has
one; this machine has 3.28). They must not be skipped.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest packaging/pip/tests/test_ci_config.py packaging/pip/tests/test_cmake_hooks.py -v`
Expected: `test_ci_config.py` errors at collection (`FileNotFoundError: .../pyproject.toml`).
`test_without_hook...` passes. The two hook tests fail (hook file missing).

- [ ] **Step 3: Write the three files**

`packaging/pip/cmake/wheel_hook.cmake` (full content):

```cmake
# Included right after STIR's project() call via CMAKE_PROJECT_STIR_INCLUDE (set in pyproject.toml).
# Used only by pip wheel builds; STIR's own CMake files are not changed.
if(NOT DEFINED SKBUILD_PLATLIB_DIR)
  message(FATAL_ERROR "wheel_hook.cmake is only for scikit-build-core builds (SKBUILD_PLATLIB_DIR is not set)")
endif()
# Install the stir package at the top level of the wheel instead of under python/.
set(PYTHON_DEST "${SKBUILD_PLATLIB_DIR}" CACHE PATH "Destination for python module" FORCE)
# Make our FindPython.cmake shim visible (STIR prepends src/cmake and keeps this entry).
list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}")
```

`packaging/pip/cmake/FindPython.cmake` (full content):

```cmake
# Wheel builds only. manylinux has no libpython, so FindPython's "Development" component
# (= Development.Module + Development.Embed) cannot be found there. STIR's extension links only
# Python::Module, so request Development.Module instead, then run CMake's own FindPython.
if("Development" IN_LIST Python_FIND_COMPONENTS)
  list(TRANSFORM Python_FIND_COMPONENTS REPLACE "^Development$" "Development.Module")
  if(Python_FIND_REQUIRED_Development)
    set(Python_FIND_REQUIRED_Development.Module TRUE)
  endif()
  unset(Python_FIND_REQUIRED_Development)
endif()
include("${CMAKE_ROOT}/Modules/FindPython.cmake")
```

`pyproject.toml` (full content; under SKIP-315, add the `skip` entry from Task 1):

```toml
# pip packaging for STIR. Developer notes: packaging/pip/README.md
# CI rewrites this file with packaging/pip/prepare_build.py before building.
# Keep every "prepare_build:" marker comment; prepare_build.py edits the lines they mark.

[build-system]
requires = [
    "scikit-build-core>=1.1",
    "swig>=4.2",
    "numpy>=2",
    "cmake>=3.24",
    "ninja>=1.11",
]
build-backend = "scikit_build_core.build"

[project]
name = "stir"  # prepare_build: name
dynamic = ["version"]  # prepare_build: version
description = "Python interface to STIR, Software for Tomographic Image Reconstruction"
readme = "README.md"
requires-python = ">=3.11"
license = "Apache-2.0 AND LGPL-2.1-or-later AND LicenseRef-PARAPET-license"
license-files = ["LICENSE.txt", "LICENSES/*.txt"]
authors = [{ name = "STIR developers" }]
dependencies = ["numpy>=1.24"]  # prepare_build: dependencies
classifiers = [
    "Intended Audience :: Science/Research",
    "Operating System :: POSIX :: Linux",
    "Programming Language :: C++",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "Programming Language :: Python :: 3.15",
    "Topic :: Scientific/Engineering :: Medical Science Apps.",
]

[project.urls]
Homepage = "https://stir.sourceforge.net"
Source = "https://github.com/UCL/STIR"
Issues = "https://github.com/UCL/STIR/issues"

# prepare_build: version-provider begin
[[tool.dynamic-metadata]]
provider = "scikit_build_core.metadata.regex"
field = "version"
input = "VERSION.txt"
regex = '(?P<value>\d+\.\d+\.\d+)'
# prepare_build: version-provider end

[tool.scikit-build]
minimum-version = "build-system.requires"
cmake.version = ">=3.24"
ninja.version = ">=1.11"
cmake.build-type = "Release"
build.verbose = true
logging.level = "INFO"
# The Python package comes from STIR's own CMake install rules (src/swig/CMakeLists.txt).
wheel.packages = []
# Drop what STIR installs for C++ users: headers, static libraries, CMake config, executables, share/.
wheel.exclude = ["include/**", "lib/**", "bin/**", "share/**"]
sdist.exclude = [".github/", "recon_test_pack/", "docs/superpowers/", "build/", "dist/", "wheelhouse/"]

[tool.scikit-build.wheel.force-include]
"src/config" = "stir/_data/config"
"examples" = "stir/_data/doc/examples"

[tool.scikit-build.cmake.define]
CMAKE_PROJECT_STIR_INCLUDE = "packaging/pip/cmake/wheel_hook.cmake"
BUILD_SWIG_PYTHON = "ON"
BUILD_EXECUTABLES = "OFF"
BUILD_TESTING = "OFF"
BUILD_SHARED_LIBS = "OFF"
BUILD_DOCUMENTATION = "OFF"
STIR_OPENMP = "ON"
STIR_MPI = "OFF"
GRAPHICS = "None"
GIT_SUBMODULE = "OFF"
DOWNLOAD_ZENODO_TEST_DATA = "OFF"
# Phase 1: core STIR + OpenMP only. Phase 2 enables HDF5, PETSIRD, nlohmann_json, ITK and parallelproj.
DISABLE_CERN_ROOT = "ON"
DISABLE_HDF5 = "ON"
DISABLE_ITK = "ON"
DISABLE_LLN_MATRIX = "ON"
DISABLE_NLOHMANN_JSON = "ON"
DISABLE_NiftyPET_PROJECTOR = "ON"
DISABLE_PETSIRD = "ON"
DISABLE_Parallelproj_PROJECTOR = "ON"
DISABLE_STIR_CUDA = "ON"
DISABLE_STIR_LOCAL = "ON"
DISABLE_UPENN = "ON"

[tool.cibuildwheel]
build = ["cp311-*", "cp312-*", "cp313-*", "cp314-*", "cp315-*"]
skip = ["*-musllinux_*"]
build-verbosity = 1
test-requires = ["pytest", "matplotlib"]
test-environment = { STIR_WHEEL_EXPECT = "config,openmp" }
test-command = [
    "python -m pytest -v {project}/packaging/pip/tests/test_wheel_smoke.py",
    "python -m pytest -v {project}/src/swig/test/python",
]

[tool.cibuildwheel.linux]
manylinux-x86_64-image = "manylinux_2_28"
# STIR needs header-only Boost >= 1.36; AlmaLinux 8 (manylinux_2_28) ships 1.66.
before-all = "dnf install -y boost-devel"
```

Only if **MPL-315 = no**, append:

<!-- pyml disable md013-->
```toml
[[tool.cibuildwheel.overrides]]
select = "cp315-*"
test-requires = ["pytest"]
test-command = [
    "python -m pytest -v {project}/packaging/pip/tests/test_wheel_smoke.py",
    "python -m pytest -v {project}/src/swig/test/python --ignore={project}/src/swig/test/python/test_projdata_profiles.py",
]
```
<!-- pyml enable md013-->

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest packaging/pip/tests/test_ci_config.py packaging/pip/tests/test_cmake_hooks.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml packaging/pip/cmake packaging/pip/tests/test_ci_config.py packaging/pip/tests/test_cmake_hooks.py
git commit -m "Add scikit-build-core configuration for STIR pip wheels"
```

---

### Task 4: `prepare_build.py` (cpu variant and dev number)

**Files:**

- Create: `packaging/pip/prepare_build.py`
- Test: `packaging/pip/tests/test_prepare_build.py`

**Interfaces:**

- Consumes: the marker comments from Task 3.
- Produces (CLI as in the contract):
  `python packaging/pip/prepare_build.py --variant {cpu,cuda12,cuda13} [--dev-number N] [--pyproject PATH]`.
  `--pyproject` defaults to `<repo>/pyproject.toml`. `VERSION.txt` is read from the directory that holds the
  pyproject file. Exit 0 on success. Exit 2 on bad arguments: unknown variant, `N < 0`, and `cuda12`/`cuda13`
  in Phase 1 with the message `variant cuda12 is not supported yet (Phase 3)`. Exit 1 when the file or a marker
  is missing, or `VERSION.txt` is not `X.Y.Z` (message on stderr). Phase 3 adds exit 1 for a missing CUDA override.
  (`cuda13` is a reserved value for a deferred variant; it is accepted by argparse but never built in the first
  version; see the overview.)
- Produces (Python, used by Phase 3):
  - `VARIANT_PACKAGE_NAMES: dict[str, str] = {"cpu": "stir", "cuda12": "stir-cuda12", "cuda13": "stir-cuda13"}`
  - `read_stir_version(version_file: Path) -> str`: strips whitespace; raises `ValueError` unless it matches
    `^\d+\.\d+\.\d+$`.
  - `rewrite_pyproject(text: str, *, variant: str, version: str | None) -> str`: pure function. It replaces the
    whole `# prepare_build: name` line with `name = "<pkg>"  # prepare_build: name`. When `version` is given, it
    replaces the `# prepare_build: version` line with `version = "<version>"  # prepare_build: version`, and
    empties the lines strictly between the `version-provider begin`/`end` markers. Markers are always kept, so a
    second run works. Raises `ValueError` naming the missing marker. The result is checked with
    `tomllib.loads` before it is returned.
  - `main(argv: Sequence[str] | None = None) -> int`

- [ ] **Step 1: Write the failing tests in `packaging/pip/tests/test_prepare_build.py`**

Load the module by path as in Task 2. Use the real repository file as the fixture:
`TEXT = (REPO / "pyproject.toml").read_text()`. Add a helper `parse = tomllib.loads`.

<!-- pyml disable md013-->
```python
def test_cpu_without_dev_number_changes_nothing():
    assert pb.rewrite_pyproject(TEXT, variant="cpu", version=None) == TEXT

def test_dev_number_sets_static_version():
    d = parse(pb.rewrite_pyproject(TEXT, variant="cpu", version="6.5.0.dev42"))
    assert d["project"]["name"] == "stir" and d["project"]["version"] == "6.5.0.dev42"
    assert "dynamic" not in d["project"] and "dynamic-metadata" not in d["tool"]

def test_rewrite_is_idempotent():
    once = pb.rewrite_pyproject(TEXT, variant="cpu", version="6.5.0.dev42")
    assert pb.rewrite_pyproject(once, variant="cpu", version="6.5.0.dev42") == once
    assert parse(pb.rewrite_pyproject(once, variant="cpu", version="6.5.0.dev43"))["project"]["version"] == "6.5.0.dev43"

def test_missing_marker_raises():
    with pytest.raises(ValueError, match="prepare_build: version"):
        pb.rewrite_pyproject(TEXT.replace("# prepare_build: version\n", "\n"), variant="cpu", version="1.0.0.dev1")

@pytest.mark.parametrize("raw,ok", [("6.5.0\n", "6.5.0"), ("6.5.0\r\n", "6.5.0"), ("6.5", None), ("", None)])
def test_read_stir_version(tmp_path, raw, ok):
    f = tmp_path / "VERSION.txt"; f.write_text(raw)
    if ok: assert pb.read_stir_version(f) == ok
    else: pytest.raises(ValueError, pb.read_stir_version, f)

def test_cli_rewrites_a_copy(tmp_path):
    for n in ("pyproject.toml", "VERSION.txt"): shutil.copy(REPO / n, tmp_path / n)
    assert pb.main(["--variant", "cpu", "--dev-number", "7", "--pyproject", str(tmp_path / "pyproject.toml")]) == 0
    expected = (REPO / "VERSION.txt").read_text().strip() + ".dev7"
    assert parse((tmp_path / "pyproject.toml").read_text())["project"]["version"] == expected

@pytest.mark.parametrize("args", [["--variant", "gpu"], ["--variant", "cpu", "--dev-number", "-1"],
                                  ["--variant", "cuda12"], []])
def test_cli_bad_arguments_exit_2(tmp_path, args):
    r = subprocess.run([sys.executable, str(SCRIPT), *args, "--pyproject", str(tmp_path / "x.toml")],
                       capture_output=True, text=True)
    assert r.returncode == 2

def test_cli_missing_file_exits_1(tmp_path):
    assert pb.main(["--variant", "cpu", "--pyproject", str(tmp_path / "missing.toml")]) == 1
```
<!-- pyml enable md013-->

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest packaging/pip/tests/test_prepare_build.py -v`
Expected: collection error, `FileNotFoundError` for `prepare_build.py`.

- [ ] **Step 3: Implement `packaging/pip/prepare_build.py`**

Standard library only (`argparse`, `re`, `tomllib`, `pathlib`). argparse's own exit code 2 covers unknown
variants. Check `--dev-number` and the CUDA variants yourself and `return 2`. Print one line to stdout on success:
`prepare_build: <path> -> name=<pkg> version=<version or dynamic>`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest packaging/pip/tests/test_prepare_build.py -v`
Expected: 14 passed.

- [ ] **Step 5: Commit**

```bash
git add packaging/pip/prepare_build.py packaging/pip/tests/test_prepare_build.py
git commit -m "Add prepare_build.py to set the wheel name and dev version"
```

---

### Task 5: Installed-wheel smoke test

**Files:**

- Create: `packaging/pip/tests/test_wheel_smoke.py`

**Interfaces:**

- Consumes: `STIR_WHEEL_EXPECT` (contract), the wheel layout from Task 3, and `stir.get_STIR_config_dir`,
  `stir.find_STIR_config_file`, `stir.get_STIR_examples_dir`, `stir.set_num_threads` and
  `stir.get_max_num_threads`. All are SWIG-exposed via `stir.i` lines 1086–1087.
- Produces (Phases 2, 3 and 5 add entries to `CHECKS`):
  - `KNOWN_FEATURES = frozenset({"config", "openmp", "json", "hdf5", "petsird", "itk", "parallelproj", "cuda",
    "root"})` (the overview's list; Phase 2 moves it to `_feature_probes.py`)
  - `expected_features(environ: Mapping[str, str]) -> frozenset[str]`: splits `STIR_WHEEL_EXPECT` on commas,
    strips items, ignores empty items and always adds `"config"`. Raises `ValueError` listing any unknown names.
  - `run_stir(code: str, *, env: Mapping[str, str | None] = {}, sys_path0: Path | None = None) -> dict`: runs
    `sys.executable -c` in a subprocess. The working directory is `tempfile.gettempdir()`, so `''` on `sys.path`
    can't pick up a source tree. The environment is a copy of `os.environ` without `STIR_CONFIG_DIR`,
    `STIR_DOC_DIR` and `OMP_NUM_THREADS`, then `env` applied (`None` deletes). When `sys_path0` is given, the
    code first runs `sys.path.insert(0, ...)`. The code must print one JSON object, which is returned.
  - `CHECKS: dict[str, Callable[[], None]] = {"config": check_config, "openmp": check_openmp}`

The module does `import stir` at the top, so it fails fast when no wheel is installed.

- [ ] **Step 1: Write the tests**

```python
PROBE = ("import json, stir; print(json.dumps({'file': stir.__file__, 'config': stir.get_STIR_config_dir(),"
         " 'found': stir.find_STIR_config_file('radionuclide_names.json'), 'examples': stir.get_STIR_examples_dir()}))")

def check_config():
    out = run_stir(PROBE); pkg = Path(out["file"]).parent
    assert Path(out["config"]) == pkg / "_data" / "config"
    assert Path(out["found"]).is_file() and Path(out["found"]).parent == pkg / "_data" / "config"
    assert (Path(out["examples"]) / "samples").is_dir()

def check_openmp():
    out = run_stir("import json, stir; stir.set_num_threads(3); print(json.dumps({'n': stir.get_max_num_threads()}))")
    assert out["n"] == 3      # without OpenMP STIR always reports 1

def test_expect_list_is_valid():
    assert "config" in expected_features(os.environ)

@pytest.mark.parametrize("feature", sorted(expected_features(os.environ)))
def test_expected_feature(feature):
    assert feature in CHECKS, f"no smoke check for feature {feature!r}; add one to CHECKS"
    CHECKS[feature]()

def test_user_config_dir_wins(tmp_path):
    assert run_stir(PROBE.replace("'found': stir.find_STIR_config_file('radionuclide_names.json'), ", ""),
                    env={"STIR_CONFIG_DIR": str(tmp_path)})["config"] == str(tmp_path)

def test_empty_config_dir_is_ignored():
    out = run_stir(PROBE, env={"STIR_CONFIG_DIR": ""})
    assert Path(out["config"]) == Path(out["file"]).parent / "_data" / "config"

def test_wheel_file_list():
    dist = importlib.metadata.distribution("stir")
    assert Path(dist.locate_file("stir/__init__.py")) == Path(stir.__file__)   # imported the installed wheel
    names = {str(f) for f in dist.files}
    assert {"stir/__init__.py", "stir/_paths.py", "stir/swigstir.py", "stir/extra.py", "stirextra.py",
            "stir/_data/config/radionuclide_names.json", "stir/_data/config/radionuclide_info.json",
            "stir/_data/config/ct_slopes.json", "stir/_data/doc/examples/README.md"} <= names
    assert len([n for n in names if re.fullmatch(r"stir/_stir(\..+)?\.(so|pyd)", n)]) == 1
    assert not [n for n in names if n.split("/")[0] in {"include", "lib", "bin", "share", "python"}]
    assert not [n for n in names if not n.startswith("stir/_data/")
                and n.endswith((".h", ".hpp", ".inl", ".txx", ".a", ".lib", ".cmake"))]

def test_relocated_copy_finds_its_own_data(tmp_path):
    site = Path(stir.__file__).parent.parent
    dest = tmp_path / "moved env ü" / "site-packages"
    shutil.copytree(site / "stir", dest / "stir"); shutil.copy(site / "stirextra.py", dest)
    if (site / "stir.libs").is_dir(): shutil.copytree(site / "stir.libs", dest / "stir.libs")
    out = run_stir(PROBE, sys_path0=dest)
    assert Path(out["file"]).parent == dest / "stir"
    assert Path(out["config"]) == dest / "stir" / "_data" / "config" and Path(out["found"]).is_file()
```

- [ ] **Step 2: Run it without a wheel to verify it fails**

Run:
`cd /tmp && STIR_WHEEL_EXPECT=config,openmp python3 -m pytest -v /home/claude/src/STIR/packaging/pip/tests/test_wheel_smoke.py`
Expected: collection error `ModuleNotFoundError: No module named 'stir'`. It passes in Task 6.

- [ ] **Step 3: Commit**

```bash
git add packaging/pip/tests/test_wheel_smoke.py
git commit -m "Add installed-wheel smoke test driven by STIR_WHEEL_EXPECT"
```

---

### Task 6: Local wheel and sdist build, and the local throwaway index

This proves `pip wheel .` works before any CI run. It needs network access to PyPI and GitHub, a C++17 compiler
with OpenMP, and Boost headers. The `local-index.sh` check needs importable `pypiserver` 2.4 and `twine`. If a
prerequisite cannot be met on this machine, stop and report which one. Do not mark the step done.

**Files:**

- Create: `packaging/pip/local-index.sh` (executable)

**Interfaces:**

- Consumes: everything from Tasks 2–5.
- Produces (`local-index.sh` CLI, also documented in Task 8):
  - `packaging/pip/local-index.sh up DIR`: starts a throwaway pypiserver on `http://localhost:8080/` with
    exactly the CI arguments `run -p 8080 -a . -P . --fallback-url https://pypi.org/simple/`. It then uploads every
    `*.whl` and `*.tar.gz` under `DIR`, recursively (so a `gh run download` folder works), with
    `python3 -m twine upload --non-interactive --repository-url http://localhost:8080/ -u local -p local`. Finally
    it prints `pip install --index-url http://localhost:8080/simple/ "stir==<version>"` for each version found in
    the file names.
  - `packaging/pip/local-index.sh down`: stops the server and deletes its packages. Exit 0 even if not running.
  - `packaging/pip/local-index.sh status`: exit 0 if running, 1 if not.
  - Backend (the same as CI, no Docker): `python3 -m pypiserver` in the background, with PID file
    `${TMPDIR:-/tmp}/stir-local-index.pid` and packages dir `${TMPDIR:-/tmp}/stir-local-index-packages`. If
    `python3 -c "import pypiserver"` fails: exit 1 with `needs 'pip install "pypiserver==2.4.*"'`. If twine is missing:
    exit 1 with
    `needs 'pip install twine'`. Usage errors (no command, unknown command, `up` without an existing DIR): print
    usage, exit 2. `set -euo pipefail`. Wait for `http://localhost:8080/health` with
    `curl --retry 30 --retry-delay 1 --retry-connrefused`.

- [ ] **Step 1: Write `packaging/pip/local-index.sh` and check its usage errors**

Run:
<!-- pyml disable-next-line md013-->
`bash -n packaging/pip/local-index.sh; packaging/pip/local-index.sh; echo $?; packaging/pip/local-index.sh up /nonexistent; echo $?`
Expected: no syntax errors, the usage text twice, and `2` twice. If `shellcheck` is installed, it reports
nothing.

- [ ] **Step 2: Make a scratch checkout of the committed branch**

```bash
git worktree add --detach /tmp/stir-scratch HEAD
git -C /tmp/stir-scratch submodule update --init --recursive
cp packaging/pip/local-index.sh /tmp/stir-scratch/packaging/pip/   # not committed yet
python3 /tmp/stir-scratch/packaging/pip/prepare_build.py --variant cpu --dev-number 0
```

Expected last line: `prepare_build: /tmp/stir-scratch/pyproject.toml -> name=stir version=6.5.0.dev0`. Boost
headers are required: if `/usr/include/boost/version.hpp` is missing, run `apt-get install -y libboost-dev`.

- [ ] **Step 3: Build the wheel in a scratch venv**

<!-- pyml disable md013-->
```bash
python3.13 -m venv /tmp/stir-build-venv && /tmp/stir-build-venv/bin/python -m pip install -U pip
cd /tmp/stir-scratch && time /tmp/stir-build-venv/bin/python -m pip wheel . --no-deps -w /tmp/stir-wheels -v 2>&1 | tee /tmp/stir-build.log
```
<!-- pyml enable md013-->

Expected: `Successfully built stir` and `/tmp/stir-wheels/stir-6.5.0.dev0-cp313-cp313-linux_x86_64.whl`. The log
contains `PYTHON_DEST` under the scikit-build platlib dir (check with
`grep -n "Installing.*stir/_stir" /tmp/stir-build.log`, which shows no `/python/stir/` path) and no
`Could NOT find`. Record the wall time; it sets expectations for CI.

- If FindBoost fails under a CMake 4.x from PyPI, add `"cmake>=3.24,<4"` to both `requires` and `cmake.version`,
  update `test_build_backend_and_requirements`, and rebuild.
- If SWIG wrapping fails with the newest `swig` from PyPI (4.5.x), pin `"swig>=4.2,<4.5"` the same way.

Record any such change in the Task 8 README.

- [ ] **Step 4: Install into a fresh venv and run the smoke test and STIR's Python suite**

```bash
python3.13 -m venv /tmp/stir-test-venv
/tmp/stir-test-venv/bin/python -m pip install /tmp/stir-wheels/stir-6.5.0.dev0-*.whl pytest matplotlib
cd /tmp && STIR_WHEEL_EXPECT=config,openmp /tmp/stir-test-venv/bin/python -m pytest -v \
  /tmp/stir-scratch/packaging/pip/tests/test_wheel_smoke.py /tmp/stir-scratch/src/swig/test/python
```

Expected: all passed. `test_listmode.py` passes without ROOT; it catches the `RuntimeError` itself.

- [ ] **Step 5: Build the sdist and build a wheel from it**

```bash
cd /tmp/stir-scratch && /tmp/stir-build-venv/bin/python -m pip install build
/tmp/stir-build-venv/bin/python -m build --sdist --outdir /tmp/stir-sdist
tar -tzf /tmp/stir-sdist/stir-6.5.0.dev0.tar.gz | grep -E "external_helpers/CuVec/Makefile|recon_test_pack/|\.github/"
/tmp/stir-build-venv/bin/python -m pip wheel /tmp/stir-sdist/stir-6.5.0.dev0.tar.gz --no-deps -w /tmp/stir-sdist-wheel
```

Expected: the `grep` prints only the CuVec `Makefile` line. The sdist is under 100 MB (`ls -l`). The second build
ends with `Successfully built stir`.

- [ ] **Step 6: Rehearse locally with `local-index.sh`**

<!-- pyml disable md013-->
```bash
/tmp/stir-build-venv/bin/python -m pip install twine "pypiserver==2.4.*"
PATH=/tmp/stir-build-venv/bin:$PATH packaging/pip/local-index.sh up /tmp/stir-wheels
python3.13 -m venv /tmp/stir-index-venv
/tmp/stir-index-venv/bin/python -m pip install --index-url http://localhost:8080/simple/ "stir==6.5.0.dev0" pytest
cd /tmp && STIR_WHEEL_EXPECT=config,openmp /tmp/stir-index-venv/bin/python -m pytest -v /tmp/stir-scratch/packaging/pip/tests/test_wheel_smoke.py
packaging/pip/local-index.sh down; packaging/pip/local-index.sh status; echo $?
```
<!-- pyml enable md013-->

Expected: the upload succeeds, the install shows `Looking in indexes: http://localhost:8080/simple/`, the smoke
test passes, and the final `status` prints exit code `1`.

- [ ] **Step 7: Clean up and commit**

```bash
git worktree remove --force /tmp/stir-scratch
git add packaging/pip/local-index.sh   # plus any pin from Step 3, with its test change
git commit -m "Add local throwaway package index script for wheel testing"
```

---

### Task 7: CI workflow `.github/workflows/wheels.yml`

**Files:**

- Create: `.github/workflows/wheels.yml`
- Modify: `packaging/pip/tests/test_ci_config.py` (add workflow tests)

**Interfaces:**

- Consumes: `prepare_build.py` CLI (Task 4), cibuildwheel config (Task 3), smoke test (Task 5), Task 1 decision.
- Produces: jobs `sdist`, `build_cpu`, `rehearse_publish` and `publish`; artifacts `sdist` and
  `wheels-cpu-linux-x86_64`. Phase 2 adds matrix rows to `build_cpu`. Phase 3 adds `build_cuda`, and
  `rehearse_publish` must then also `need` it.

- [ ] **Step 1: Write the failing workflow tests (append to `test_ci_config.py`)**

`WF = yaml.safe_load((REPO / ".github/workflows/wheels.yml").read_text())`, `ON = WF.get("on", WF.get(True))`.
PyYAML reads the key `on` as `True`. Add `JOBS = WF["jobs"]` and
`def runs(job): return [s.get("run", "") for s in JOBS[job]["steps"]]`.

<!-- pyml disable md013-->
```python
GUARD = "github.repository == 'robbietuk/STIR'"

def test_triggers():
    assert set(ON) == {"push", "workflow_dispatch"} and ON["push"]["branches"] == ["pip-packaging"]

def test_job_names():
    assert set(JOBS) == {"sdist", "build_cpu", "rehearse_publish", "publish"}

def test_every_job_is_guarded_to_the_fork():
    assert all(GUARD in job["if"] for job in JOBS.values())

def test_publish_is_switched_off():
    assert JOBS["publish"]["if"].startswith("false &&")

def test_uploads_only_go_to_localhost():
    for name, job in JOBS.items():
        if name == "publish": continue
        for s in job["steps"]:
            assert "gh-action-pypi-publish" not in s.get("uses", "")
            if "twine upload" in s.get("run", ""): assert "--repository-url http://localhost:8080/" in s["run"]

def test_artifact_names():
    up = lambda j: [s["with"]["name"] for s in JOBS[j]["steps"] if s.get("uses", "").startswith("actions/upload-artifact")]
    assert up("sdist") == ["sdist"]
    assert up("build_cpu") == ["wheels-cpu-${{ matrix.os }}-${{ matrix.arch }}"]
    assert JOBS["build_cpu"]["strategy"]["matrix"]["include"] == [{"os": "linux", "arch": "x86_64", "runner": "ubuntu-latest"}]

def test_builds_use_dev_number():
    calls = [r for j in JOBS for r in runs(j) if "prepare_build.py" in r]
    assert len(calls) == 2 and all("--dev-number ${{ github.run_number }}" in r for r in calls)

def test_rehearsal_installs_exact_dev_version():
    text = "\n".join(runs("rehearse_publish"))
    assert '--index-url http://localhost:8080/simple/ "stir==$version"' in text
    assert JOBS["rehearse_publish"]["needs"] == ["sdist", "build_cpu"]

def test_rehearsal_covers_numpy1():
    assert any('"numpy==1.26.4"' in r and "python3.11" in r for r in runs("rehearse_publish"))
```
<!-- pyml enable md013-->

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m pytest packaging/pip/tests/test_ci_config.py -v`
Expected: collection error `FileNotFoundError: .../.github/workflows/wheels.yml`.

- [ ] **Step 3: Write `.github/workflows/wheels.yml` (full content; under SKIP-315 apply the Task 1 edits)**

<!-- pyml disable md013-->
```yaml
# pip wheels for STIR. Runs only on Robert's fork (robbietuk/STIR), never on UCL/STIR.
# Developer notes: packaging/pip/README.md
name: Wheels

on:
  push:
    branches: [pip-packaging]
  workflow_dispatch:
    inputs:
      target:
        description: "Publish target. The publish job is switched off (if: false) until Robert enables it."
        type: choice
        options: [none, pypi]
        default: none

permissions:
  contents: read

concurrency:
  group: wheels-${{ github.ref }}
  cancel-in-progress: true

jobs:
  sdist:
    name: sdist
    if: github.repository == 'robbietuk/STIR'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
        with:
          submodules: recursive
          persist-credentials: false
      - uses: actions/setup-python@v6
        with:
          python-version: "3.13"
      - name: Install packaging tools
        run: python -m pip install build pytest pyyaml
      - name: Packaging unit tests
        run: python -m pytest -v packaging/pip/tests --ignore=packaging/pip/tests/test_wheel_smoke.py
      - name: Prepare pyproject.toml (cpu, dev version)
        run: python packaging/pip/prepare_build.py --variant cpu --dev-number ${{ github.run_number }}
      - name: Build sdist
        run: python -m build --sdist --outdir dist
      - name: Check sdist contents
        shell: bash
        run: |
          set -euo pipefail
          version="$(cat VERSION.txt).dev${{ github.run_number }}"
          sdist="dist/stir-${version}.tar.gz"
          tar -tzf "$sdist" > sdist-files.txt
          for f in pyproject.toml VERSION.txt CMakeLists.txt src/config/radionuclide_names.json \
                   src/swig/python/stir/_paths.py packaging/pip/cmake/wheel_hook.cmake \
                   packaging/pip/cmake/FindPython.cmake external_helpers/CuVec/Makefile \
                   external_helpers/fmt/CMakeLists.txt examples/README.md documentation/STIR-UsersGuide.tex; do
            grep -qx "stir-${version}/${f}" sdist-files.txt || { echo "missing from sdist: $f"; exit 1; }
          done
          if grep -E "^stir-${version}/(\.github|recon_test_pack|docs/superpowers)/" sdist-files.txt; then
            echo "sdist contains excluded paths"; exit 1
          fi
          size=$(stat -c %s "$sdist"); echo "sdist size: $size bytes"; test "$size" -lt 104857600
      - uses: actions/upload-artifact@v4
        with:
          name: sdist
          path: dist/*.tar.gz
          if-no-files-found: error

  build_cpu:
    name: build_cpu (${{ matrix.os }}-${{ matrix.arch }})
    if: github.repository == 'robbietuk/STIR'
    runs-on: ${{ matrix.runner }}
    timeout-minutes: 360
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: linux
            arch: x86_64
            runner: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
        with:
          submodules: recursive
          persist-credentials: false
      - name: Prepare pyproject.toml (cpu, dev version)
        run: python3 packaging/pip/prepare_build.py --variant cpu --dev-number ${{ github.run_number }}
      - name: Build and test wheels
        uses: pypa/cibuildwheel@v4.3.5
        env:
          CIBW_ARCHS: ${{ matrix.arch }}
        with:
          output-dir: wheelhouse
      - name: Check wheel set
        shell: bash
        run: |
          set -euo pipefail
          version="$(cat VERSION.txt).dev${{ github.run_number }}"
          ls -l wheelhouse
          for py in cp311 cp312 cp313 cp314 cp315; do
            ls wheelhouse/stir-${version}-${py}-${py}-manylinux_*${{ matrix.arch }}.whl
          done
          test "$(ls wheelhouse/*.whl | wc -l)" -eq 5
          for w in wheelhouse/*.whl; do
            test "$(stat -c %s "$w")" -lt 104857600 || { echo "$w is over the 100 MB PyPI limit"; exit 1; }
          done
      - uses: actions/upload-artifact@v4
        with:
          name: wheels-cpu-${{ matrix.os }}-${{ matrix.arch }}
          path: wheelhouse/*.whl
          if-no-files-found: error

  rehearse_publish:
    name: rehearse_publish
    if: github.repository == 'robbietuk/STIR'
    needs: [sdist, build_cpu]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
        with:
          persist-credentials: false
      - uses: actions/setup-python@v6
        with:
          python-version: |
            3.11
            3.12
            3.13
            3.14
            3.15
      - uses: actions/download-artifact@v5
        with:
          pattern: wheels-*
          path: dist
          merge-multiple: true
      - uses: actions/download-artifact@v5
        with:
          name: sdist
          path: dist
      - name: Start throwaway pypiserver (a background process; dies with the job)
        shell: bash
        run: |
          python -m pip install "pypiserver==2.4.*" twine
          mkdir -p "$RUNNER_TEMP/pkgs"
          nohup python -m pypiserver run -p 8080 -a . -P . --fallback-url https://pypi.org/simple/ "$RUNNER_TEMP/pkgs" \
            > "$RUNNER_TEMP/pypiserver.log" 2>&1 &
          curl --silent --show-error --fail --retry 30 --retry-delay 1 --retry-connrefused http://localhost:8080/health
      - name: Upload with twine, as a real publish would
        run: |
          python -m twine check --strict dist/*
          python -m twine upload --non-interactive --repository-url http://localhost:8080/ \
            --username rehearsal --password rehearsal dist/*
      - name: Check the index lists every file
        shell: bash
        run: |
          set -euo pipefail
          curl -fsS http://localhost:8080/simple/stir/ > index.html
          for f in dist/*; do grep -q "$(basename "$f")" index.html || { echo "not on index: $f"; exit 1; }; done
      - name: Install from the index into fresh venvs and smoke test
        shell: bash
        env:
          STIR_WHEEL_EXPECT: config,openmp
        run: |
          set -euo pipefail
          version="$(cat VERSION.txt).dev${{ github.run_number }}"
          for py in 3.11 3.12 3.13 3.14 3.15; do
            venv="$RUNNER_TEMP/venv-$py"
            "python$py" -m venv "$venv"
            "$venv/bin/python" -m pip install --index-url http://localhost:8080/simple/ "stir==$version" pytest
            test "$("$venv/bin/python" -c 'import importlib.metadata as m; print(m.version("stir"))')" = "$version"
            (cd "$RUNNER_TEMP" && "$venv/bin/python" -m pytest -v "$GITHUB_WORKSPACE/packaging/pip/tests/test_wheel_smoke.py")
          done
      - name: NumPy 1.x at runtime
        shell: bash
        env:
          STIR_WHEEL_EXPECT: config,openmp
        run: |
          set -euo pipefail
          version="$(cat VERSION.txt).dev${{ github.run_number }}"
          venv="$RUNNER_TEMP/venv-numpy1"
          python3.11 -m venv "$venv"
          "$venv/bin/python" -m pip install --index-url http://localhost:8080/simple/ "stir==$version" "numpy==1.26.4" pytest matplotlib
          (cd "$RUNNER_TEMP" && "$venv/bin/python" -m pytest -v "$GITHUB_WORKSPACE/packaging/pip/tests/test_wheel_smoke.py" \
            "$GITHUB_WORKSPACE/src/swig/test/python")

  publish:
    name: publish
    # Real PyPI upload. Switched off until Robert decides to release (spec section 5.6).
    # Enabling it means removing "false &&" and running the workflow by hand with target=pypi.
    if: false && github.repository == 'robbietuk/STIR' && github.event_name == 'workflow_dispatch' && inputs.target == 'pypi'
    needs: [rehearse_publish]
    runs-on: ubuntu-latest
    environment:
      name: pypi
      url: https://pypi.org/p/stir
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v5
        with:
          pattern: wheels-*
          path: dist
          merge-multiple: true
      - uses: actions/download-artifact@v5
        with:
          name: sdist
          path: dist
      - uses: pypa/gh-action-pypi-publish@release/v1
```
<!-- pyml enable md013-->

Note that the package resolves only from the local index, because pypiserver falls back to PyPI only for
packages it doesn't have. The exact `==$version` pin is needed because `.devN` is a pre-release.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest packaging/pip/tests --ignore=packaging/pip/tests/test_wheel_smoke.py -v`
Expected: all passed. If `actionlint` is available, `actionlint .github/workflows/wheels.yml` reports nothing.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/wheels.yml packaging/pip/tests/test_ci_config.py
git commit -m "Add wheel CI with sdist, build, publish rehearsal and disabled publish"
```

---

### Task 8: Developer notes `packaging/pip/README.md`

**Files:**

- Modify: `packaging/pip/README.md` (keep the Task 1 section)

**Interfaces:**

- Consumes: CLIs and names from Tasks 3–7, and the build time and any pins from Task 6.

- [ ] **Step 1: Write the sections**

Write these sections, in this order:

1. What this is (the spec and the contract, by path).
2. Files, as a table of the File Structure above.
3. Build a wheel locally (Task 6 Steps 2–3 commands, prerequisites, measured build time).
4. Run the packaging unit tests (the `--ignore` command).
5. Smoke test and `STIR_WHEEL_EXPECT` (feature names; `config` is always checked).
6. CI (jobs, triggers, repository guard, artifacts, `.devN` = run number).
7. Installing CI wheels: `gh run download <run-id> --repo robbietuk/STIR --dir wheels`, then
   `pip install --find-links wheels/wheels-cpu-linux-x86_64 "stir==<version>"`.
8. Throwaway index (`local-index.sh up|down|status`, and why the exact `stir==<version>` pin is needed).
9. Phase 1 limits: Linux x86_64 only; ITK, HDF5, PETSIRD, nlohmann_json, parallelproj, ROOT, CUDA, NiftyPET,
   UPENN and LLN/ECAT are off; radionuclide data uses STIR's built-in minimal table without nlohmann_json.
10. Safety: never push to `origin` (UCL/STIR); `publish` is `if: false`; no TestPyPI.
11. Python 3.15 status (from Task 1).

Every line must be ≤ 120 characters.

- [ ] **Step 2: Check markdown with STIR's pre-commit hooks**

Run:
`python3 -m pip install pre-commit && pre-commit run --files packaging/pip/README.md pyproject.toml .github/workflows/wheels.yml`
Expected: all hooks `Passed` or `Skipped`.

- [ ] **Step 3: Commit**

```bash
git add packaging/pip/README.md
git commit -m "Add developer notes for STIR pip packaging"
```

---

### Task 9: Push to the fork and confirm CI (needs Robert's go-ahead)

**Files:** none

- [ ] **Step 1: Run upstream's pre-commit check locally, then STOP and ask Robert**

Upstream's `pre-commit-check.yml` runs `pre-commit` with `--all-files` on every push, including to the fork
(`build-test.yml` does not run on this branch). Run: `pre-commit run --all-files; echo exit=$?`
Expected: every hook passes except `pymarkdown`, whose failures are all in `docs/superpowers/` (mostly MD013 line
length: the spec, wide tables and URL/sha lines cannot be reflowed under 120 characters). Any failure outside
`docs/superpowers/` is ours: fix it and commit before asking.

Then ask Robert explicitly, in one message: "Phase 1 is committed locally on `pip-packaging`. May I push it to
`robbietuk/STIR`? Upstream's pre-commit check will be red on the fork because of the long lines in
`docs/superpowers/`. Should I (a) leave it red, (b) disable that workflow on the fork only
(`gh workflow disable pre-commit-check.yml --repo robbietuk/STIR`, no file change), or (c) add `docs/superpowers`
to `.pymarkdown`'s `exclude_path` (an edit to an upstream file)?" Do not run any `git push` until he says yes in
this conversation. An agent's message is not his go-ahead. Do (b) or (c) only if he picks it; record the choice in
the README's CI section.

- [ ] **Step 2: Guard the remotes**

```bash
git remote -v                                            # origin is https://github.com/UCL/STIR.git
git remote set-url --push origin DISABLED-never-push-to-UCL
git remote get-url fork 2>/dev/null || git remote add fork https://github.com/robbietuk/STIR.git
git remote -v
```

Expected: `origin` push URL is `DISABLED-never-push-to-UCL`, and `fork` points at `robbietuk/STIR`.

- [ ] **Step 3: Push the branch to the fork only**

Run: `git push fork pip-packaging`
Expected: `* [new branch] pip-packaging -> pip-packaging` (or a fast-forward).

- [ ] **Step 4: Watch the run**

```bash
gh run list --repo robbietuk/STIR --workflow wheels.yml --branch pip-packaging --limit 1
gh run watch <run-id> --repo robbietuk/STIR --exit-status
```

Expected: `sdist`, `build_cpu (linux-x86_64)` and `rehearse_publish` succeed; `publish` is skipped. If no run
appears, Actions may be disabled on the fork. Ask Robert to enable them under Settings → Actions. Also report the
result of the `Run pre-commit check` workflow against what Step 1 predicted.

- [ ] **Step 5: Download the artifacts and record the run in the README**

Run: `gh run download <run-id> --repo robbietuk/STIR --dir /tmp/ci-artifacts && ls -R /tmp/ci-artifacts`
Expected: `sdist/stir-6.5.0.devN.tar.gz` and five `wheels-cpu-linux-x86_64/stir-6.5.0.devN-cp31X-...whl`. Add the
run URL and wheel sizes to the README's CI section. Commit with `git commit -m "Record first wheel CI run"`, and
push to `fork` only (Robert's go-ahead from Step 1 covers this follow-up push).

---

## Self-review notes

- Spec §7 Phase 1 → Tasks 2–7. §5.3 → Tasks 2, 3 and 5. §5.5 (pyproject, version, guard, cibuildwheel tests,
  sdist) → Tasks 3, 4 and 7. §5.6 (artifacts, rehearsal, local index, disabled publish) → Tasks 6 and 7.
  §3 Python 3.15 row → Task 1. §5.1 fork-only → Task 9.
- Names checked against the contract: `configure_data_dirs`, `prepare_build.py` flags and exit codes,
  `STIR_WHEEL_EXPECT`, job names, artifact names.

## References

- scikit-build-core v1.1.2 docs and schema (`wheel.force-include`, `wheel.exclude` applies to CMake output,
  `[[tool.dynamic-metadata]]` regex provider, `CMAKE_INSTALL_PREFIX` set at configure time):
  https://github.com/scikit-build/scikit-build-core (docs/configuration/index.md, dynamic.md;
  src/scikit_build_core/build/common_wheel_helpers.py)
- cibuildwheel changelog: v4.2.0 builds CPython 3.15 by default; v4.3.1 uses 3.15.0 final; v4.3.5 released
  2026-10-27. Options `test-environment`, `test-command` placeholders, default `manylinux_2_28`:
  https://cibuildwheel.pypa.io/en/latest/changelog/ and https://cibuildwheel.pypa.io/en/stable/options/
- NumPy 2.5.2 notes (released 2026-08-09, "includes wheels for the newly released Python 3.15.0rc1", supports
  3.12–3.15): https://numpy.org/devdocs/release/2.5.2-notes.html. NumPy 2.5.0 dropped Python 3.11:
  https://numpy.org/doc/2.5/release/2.5.0-notes.html
- FindPython `Development` fails on manylinux; use `Development.Module`:
  https://discourse.cmake.org/t/findpython-on-manylinux-2014/5245 and
  https://gitlab.kitware.com/cmake/cmake/-/issues/20425
- pypiserver v2.4.3 README (`-a . -P .` disables auth, `--fallback-url`, `/health`); Docker tags `vX.Y.Z` and
  `vX.Y`: https://github.com/pypiserver/pypiserver
- SWIG 4.5.1 is current (RELEASENOTES), with no explicit Python 3.15 statement found; CI proves it:
  https://swig.org/Release/RELEASENOTES
- cibuildwheel example deploy workflow (action versions):
  https://github.com/pypa/cibuildwheel/blob/main/examples/github-deploy.yml

## Contract concerns

Resolved in the overview's "Cross-plan review (2026-11-12)"; the overview wins where these notes differ.

1. **New files not in the contract's Files table:** `packaging/pip/cmake/wheel_hook.cmake`,
   `packaging/pip/cmake/FindPython.cmake`, `packaging/pip/tests/test_ci_config.py` and
   `packaging/pip/tests/test_cmake_hooks.py`. The two `.cmake` files are new packaging files injected through
   CMake's documented `CMAKE_PROJECT_STIR_INCLUDE` hook. No STIR CMake file is edited. They are still CMake code,
   so **Robert should confirm this is within "no CMake changes"** before Task 3 runs. Without them, scikit-build-core
   cannot place the package at the wheel root (`PYTHON_DEST` defaults to an absolute `<prefix>/python`). And
   STIR's `find_package(Python ... Development ...)` fails on manylinux, which has no libpython.
2. **Empty `STIR_CONFIG_DIR` is treated as unset.** The contract says `setdefault`. Pure `setdefault` would keep
   `""` and break config lookup (Review Focus 2).
3. **"pypiserver service in the job":** a GitHub `services:` container cannot be given the
   `run -a . -P .` arguments that the image needs to accept unauthenticated uploads, and macOS/Windows runners have
   no Linux containers (Phase 2). The plan therefore runs `pypiserver` as a background Python process in the job,
   on every platform. It dies with the job.
4. **Spec §5.5 says upstream `build-test.yml` will run on pushes to the branch.** It won't: its `push` trigger
   only lists `master`, `release_6.3` and `PETSIRD`. The `__init__.py` edit is covered by Task 2's unit tests
   instead. Separately, upstream `pre-commit-check.yml` runs on **every** push and applies pymarkdown MD013
   (120-character lines) to all markdown outside its exclude list. The long-line markdown in
   `docs/superpowers/` (spec and plans) will make that check red. Task 9 Step 1 checks this and asks Robert.
5. **Wheel layout:** beyond the contract's list, the wheel also contains the Python files STIR's own install rules
   add to `stir/` (`projdata_profiles.py`, `LBFGSBPC.py`, `Vision_files_preprocess.py`, `projdata_visualisation/`).
   The STIR test suite needs `projdata_profiles.py`. `stir/_data/doc` holds only `examples/` (what
   `get_STIR_examples_dir()` uses), not the 15 MB `documentation/` LaTeX/PDF tree.
