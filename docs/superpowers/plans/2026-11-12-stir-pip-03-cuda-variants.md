# STIR pip Phase 3: CUDA 12 variant (`stir-cuda12`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, test and rehearse-publish `stir-cuda12` wheels, Python 3.11–3.15 (10 wheels): Linux x86_64 first (Tasks 1–11), then Windows x86_64 as a separate, later task group (Tasks 12–13). The wheels load the CUDA runtime from NVIDIA's pip packages and explain clearly when the machine has no usable GPU. The phase ends with Robert's sign-off on a real GPU. `stir-cuda13` and Linux aarch64 (sbsa) are deferred to the appendix.

**Architecture:** The variant is chosen in two places. `prepare_build.py --variant cudaXX` sets the package name and the NVIDIA runtime dependency. `STIR_WHEEL_VARIANT=cudaXX` turns on a `[[tool.scikit-build.overrides]]` table in `pyproject.toml` that enables STIR's own CUDA code (`DISABLE_STIR_CUDA=OFF`, a fixed `CMAKE_CUDA_ARCHITECTURES`, shared cudart). `build_deps.py --variant cudaXX` builds libparallelproj with `USE_CUDA=ON` into its own cached prefix. In the wheel, `libcudart` is never bundled (auditwheel/delvewheel `--exclude`). Instead, the new `stir/_cuda.py` preloads it from the `nvidia` pip package before `_stir` is imported, and checks the driver and GPU.

**Tech Stack:** CUDA Toolkit 12.9 (nvcc; build time only), libparallelproj 2.0.7, scikit-build-core overrides, cibuildwheel (manylinux_2_28 x86_64, Windows), auditwheel, delvewheel, NVIDIA pip runtime package `nvidia-cuda-runtime-cu12`, Python `ctypes` and `importlib.metadata`, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-12-stir-pip-packaging-design.md`. **Contract:** `docs/superpowers/plans/2026-11-12-stir-pip-00-overview.md`. Read both first.

## Global Constraints

- No changes to any STIR C++ file (`*.cxx`, `*.h`, `*.inl`, `*.cu`) or any STIR `CMakeLists.txt`/`*.cmake` (full protected list: overview). All CUDA control goes through `-D` cache variables. If a task seems to need a CMake edit, stop and ask Robert.
- The only existing STIR file edited is `src/swig/python/stir/__init__.py`; this phase adds exactly the overview's two Phase 3 lines.
- Never push to `UCL/STIR`. Never publish to PyPI or TestPyPI. `publish` stays `if: false`. Pushes go to the `fork` remote only, after Robert's go-ahead for this phase (overview).
- `build_cuda` runners: `ubuntu-24.04` (Tasks 1–11) and `windows-2022` (Task 12; the one runner exception, for VS 2022 with CUDA 12.9).
- Every job in `wheels.yml` has `if: github.repository == 'robbietuk/STIR'`. Triggers stay `push` to `pip-packaging` and `workflow_dispatch`.
- Package name: `stir-cuda12`. All variants provide `import stir`. `cuda13` stays an accepted, reserved `--variant` value that exits 1 (overview); nothing in this phase builds it.
- CUDA platforms, in order: Linux x86_64, then Windows x86_64. Python 3.11, 3.12, 3.13, 3.14, 3.15 (2 × 5 = 10 wheels). Linux uses `manylinux_2_28`. No CUDA on macOS.
- **Not part of the first version:** `stir-cuda13` and Linux aarch64 (sbsa). Their researched details are in "Appendix: Later, if needed"; do not execute it unless Robert asks.
- Features in the CUDA wheels: the same as the CPU `stir` wheel, plus parallelproj (CUDA) and STIR's CUDA code.
- At runtime the wheel depends on NVIDIA's pip packages instead of bundling the runtime. The CUDA driver (`libcuda` / `nvcuda.dll`) is never bundled.
- CUDA architectures: the main ones from sm_70 to current, plus PTX for the newest (spec §5.4).
- PyPI per-file limit: 100 MB. CI fails above it.
- The wheel must work with no environment variables set, and after the venv is moved (anti-goal, spec §2).
- Artifact names: `wheels-<variant>-<os>-<arch>` with cibuildwheel arch names, exactly `wheels-cuda12-linux-x86_64` and `wheels-cuda12-windows-AMD64`.
- `STIR_WHEEL_EXPECT` for a CUDA platform is that platform's `build_cpu` `expect` plus `,cuda` (today `config,openmp,json,hdf5,petsird,itk,parallelproj,cuda`; Phase 2 known gaps carry over).
- Commits: plain imperative messages, ending with the attribution lines your session requires.

## Review Focus

1. **Someone with `nvcc` on PATH builds the CPU `stir` from the sdist.** They should get a CPU wheel. If they got one silently linked to `libcudart`, it would fail on any machine without CUDA. Pinned by `test_base_defines_disable_cuda` (Task 2), and in CI by `test_cpu_wheel_has_no_cuda` (Task 5).
2. **`stir-cudaXX` installed on a machine with no NVIDIA driver** (laptop, CI runner, container started without `--gpus`). `import stir` must still work, and should give one `RuntimeWarning` saying what is missing and what to install instead. It must not crash with a cryptic loader error. Pinned by `test_classify_no_driver` (Task 4) and `test_cuda_device_status_is_reported` (Task 5, which runs on GPU-less runners).
3. **A driver too old for the variant**, for example a 470 driver (CUDA 11.4) with `stir-cuda12`. The warning should name the CUDA version the driver supports and the one needed, and suggest a driver update or the CPU `stir`. Pinned by `test_classify_driver_too_old` (Task 4).
4. **A GPU older than the built architectures** (Pascal sm_61 with `stir-cuda12`). Without a check, this fails later with "no kernel image is available". The warning should say which compute capability was found and which is needed. Pinned by `test_classify_unsupported_gpu` (Task 4).
5. **Two variants installed in one environment**, for example `pip install stir` followed by `pip install stir-cuda12`. A warning at import should list both and say how to fix it. Pinned by `test_multiple_variants_message` (Task 4) and by the two-variant step in `rehearse_publish` (Task 9).

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `packaging/pip/deps/versions.toml` | Modify | add `[cuda.cuda12]`: toolkit version, architectures, runtime requirement |
| `packaging/pip/deps/build_deps.py` | Modify | libparallelproj CUDA build args; `--cuda-version` flag (cache key already includes variant) |
| `packaging/pip/deps/build_in_manylinux.sh` | Modify | install the CUDA toolkit in the container before `build_deps.py` for `cuda*` |
| `packaging/pip/tests/test_build_deps.py` | Modify (Phase 2) | tests for the CUDA additions to `build_deps.py` |
| `pyproject.toml` | Modify | base `DISABLE_STIR_CUDA=ON`; one override table for `cuda12` |
| `packaging/pip/prepare_build.py` | Modify | `cuda12`: name, runtime dependency, override presence check (`cuda13` exits 1) |
| `packaging/pip/tests/test_prepare_build.py` | Modify | variant tests and pyproject/versions consistency tests |
| `src/swig/python/stir/_cuda.py` | Create | variant detection, cudart preload, driver/GPU status, multi-variant warning |
| `src/swig/python/stir/__init__.py` | Modify | call `_cuda.prepare_runtime()` before `from .swigstir import *` |
| `packaging/pip/tests/test_cuda_loader.py` | Create | unit tests for `_cuda.py` (no compiled STIR, no GPU) |
| `packaging/pip/tests/test_wheel_smoke.py` | Modify | `cuda` feature checks, plus a negative check for CPU wheels |
| `packaging/pip/check_wheel_size.py` | Create | fails if any wheel is over the limit |
| `packaging/pip/tests/test_check_wheel_size.py` | Create | its tests |
| `packaging/pip/ci/install_cuda_linux.sh` | Create | installs nvcc and cudart-devel in a manylinux_2_28 container |
| `packaging/pip/ci/install_cuda_windows.ps1` | Create (Task 12) | installs nvcc and cudart on a Windows runner via NVIDIA's network installer |
| `.github/workflows/wheels.yml` | Modify | `build_cuda` job (Linux in Task 8, Windows in Task 12); `rehearse_publish` installs `stir-cuda12` and checks the two-variant warning |
| `packaging/pip/tests/gpu_check.py` | Create | manual GPU check: CPU vs GPU agreement |
| `packaging/pip/README.md` | Modify | "CUDA variants" section, GPU check instructions, sign-off table |

---

### Task 1: CUDA dependency settings and libparallelproj CUDA build

**Files:**
- Modify: `packaging/pip/deps/versions.toml`
- Modify: `packaging/pip/deps/build_deps.py`
- Test: `packaging/pip/tests/test_build_deps.py` (Phase 2's file)

**Interfaces:**
- Consumes: Phase 2 `build_deps.py` CLI (`--prefix`, `--variant`, `--only`, `--jobs`, `--cache-key`), `parallelproj_cmake_args(variant, versions)` (raises `UsageError` for CUDA until this task), the `<prefix>/.stamps/<name>` completion stamps, and the test helpers `load_build_deps()` / `run(*args)` in `test_build_deps.py`.
- Produces:
  - `versions.toml` table `[cuda.cuda12]` with keys `toolkit` (str), `architectures` (str, CMake list), `runtime_requirement` (str, PEP 508). Tasks 2, 3, 7 and 12 read it.
  - `parallelproj_cmake_args(variant: str, versions: Mapping[str, Any]) -> list[str]` in `build_deps.py`
  - CLI `python packaging/pip/deps/build_deps.py --cuda-version --variant cuda12` prints the toolkit version (`12.9.1`) and exits 0. With `--variant cpu` it exits 2. With the reserved `cuda13` (no `[cuda.cuda13]` table) it exits 1, for `--cuda-version` and for a build (overview).

Background (verified upstream at v2.0.7): libparallelproj always builds a **shared** library (`add_library(parallelproj SHARED ...)`); there is no static option. CUDA is switched on with `-DUSE_CUDA=ON`, which needs CMake ≥ 3.31 and `CUDAToolkit ≥ 12.0`. It links `CUDA::cudart` PRIVATE. Since v2.0.4 it no longer auto-detects architectures, so `CMAKE_CUDA_ARCHITECTURES` must be passed. Its installed `parallelprojConfig.cmake` sets `PARALLELPROJ_CUDA` (0/1) and `PARALLELPROJ_VERSION`, and STIR's top-level `CMakeLists.txt` reads both. It exports `int parallelproj_cuda_enabled(void)`, which Task 5 uses.

- [ ] **Step 1: Add the CUDA tables to `versions.toml`**

```toml
# CUDA variants (Phase 3). Architectures use CMake syntax: "-real" = SASS only,
# "-virtual" = PTX only. The pyproject.toml override for each variant must carry
# the identical string (enforced by test_cuda_arch_lists_agree).
# [cuda.cuda13] is deferred (plan appendix B1); its absence makes cuda13 exit 1.
[cuda.cuda12]
toolkit = "12.9.1"
architectures = "70-real;75-real;80-real;86-real;89-real;90-real;100-real;120-real;120-virtual"
runtime_requirement = "nvidia-cuda-runtime-cu12>=12.9,<13"
```

Rationale: sm_100 SASS also runs on sm_103 (B300), and sm_120 SASS runs on sm_121 (GB10 / DGX Spark), so those don't need their own entries. PTX for 120 covers future GPUs.

- [ ] **Step 2: Write the failing tests**

Append to Phase 2's `packaging/pip/tests/test_build_deps.py`, reusing its `run` and `load_build_deps`. Delete
Phase 2's `test_cuda_build_is_phase3` (this task implements CUDA builds). Phase 2 already has
`test_cache_key_differs_per_variant`.

```python
VERSIONS = load_build_deps().load_versions()

def test_cuda_version_flag():
    r = run("--cuda-version", "--variant", "cuda12")
    assert r.returncode == 0 and r.stdout.strip() == "12.9.1"

def test_cuda_version_flag_rejects_cpu():
    r = run("--cuda-version", "--variant", "cpu")
    assert r.returncode == 2 and "needs a CUDA variant" in r.stderr

def test_deferred_cuda13_exits_1():
    for args in (["--cuda-version", "--variant", "cuda13"], ["--prefix", "p", "--variant", "cuda13"]):
        r = run(*args)
        assert r.returncode == 1 and "deferred variant" in r.stderr

def test_parallelproj_args_cpu():
    args = load_build_deps().parallelproj_cmake_args("cpu", VERSIONS)
    assert "-DUSE_CUDA=OFF" in args
    assert not any(a.startswith("-DCMAKE_CUDA_ARCHITECTURES") for a in args)

@pytest.mark.parametrize("variant", ["cuda12"])
def test_parallelproj_args_cuda(variant):
    args = load_build_deps().parallelproj_cmake_args(variant, VERSIONS)
    assert "-DUSE_CUDA=ON" in args
    assert f"-DCMAKE_CUDA_ARCHITECTURES={VERSIONS['cuda'][variant]['architectures']}" in args
    assert "-DCMAKE_CUDA_RUNTIME_LIBRARY=Shared" in args
    for a in ("-DBUILD_PYTHON=OFF", "-DBUILD_TESTS=OFF", "-DINSTALL_DEVEL=ON", "-DBUILD_LIBRARY=ON"):
        assert a in args
```

- [ ] **Step 3: Run the tests to check they fail**

Run: `pytest packaging/pip/tests/test_build_deps.py -v`
Expected: `test_cuda_version_flag*` and `test_deferred_cuda13_exits_1` FAIL (unknown flag / Phase 2's exit 2) and `test_parallelproj_args_cuda` FAILS with `UsageError`. Phase 2's tests still pass.

- [ ] **Step 4: Implement `parallelproj_cmake_args(variant, versions) -> list[str]` and the `--cuda-version` flag in `build_deps.py`**

Extend Phase 2's `parallelproj_cmake_args`. For `cpu` it returns Phase 2's list unchanged (it includes `-DUSE_CUDA=OFF`). For CUDA variants it replaces `-DUSE_CUDA=OFF` and adds `-DUSE_CUDA=ON`, `-DCMAKE_CUDA_ARCHITECTURES=<architectures>` and `-DCMAKE_CUDA_RUNTIME_LIBRARY=Shared`. Without the last one, CMake links `cudart_static` into `.cu` targets as well as the shared `CUDA::cudart`, which would put two CUDA runtimes in one process. `--cuda-version` prints `versions["cuda"][variant]["toolkit"]`; like `--cache-key` it does not need `--prefix`. With `--variant cpu` it exits 2 with `build_deps: --cuda-version needs a CUDA variant (cuda12)` on stderr. A CUDA variant with no `versions["cuda"][variant]` table exits 1 with `build_deps: no [cuda.<variant>] table in versions.toml (deferred variant)`, both for `--cuda-version` and for a build (`--cache-key` still works). Remove Phase 2's "implemented in Phase 3" exit for CUDA builds. Phase 2's cache key already hashes the variant.

The CUDA variants build every dep Phase 2 builds on the platform. All except parallelproj are built exactly as for `cpu`, so each variant gets its own complete prefix (`.deps/<variant>`) and cache entry.

- [ ] **Step 5: Run the tests to check they pass**

Run: `pytest packaging/pip/tests/test_build_deps.py -v`
Expected: all PASS.

- [ ] **Step 6: Build CUDA libparallelproj locally once (any Linux machine with nvcc ≥ 12.0; no GPU needed)**

Run: `python packaging/pip/deps/build_deps.py --prefix /tmp/deps-cuda12 --variant cuda12 --only parallelproj --jobs 8 && grep -E "PARALLELPROJ_(CUDA|VERSION) " /tmp/deps-cuda12/lib*/cmake/parallelproj/parallelprojConfig.cmake && ldd /tmp/deps-cuda12/lib*/libparallelproj.so.2 | grep cudart`
Expected: `set(PARALLELPROJ_CUDA 1)`, `set(PARALLELPROJ_VERSION "2.0.7")`, and `libcudart.so.12 => ...`. To check that no static cudart was linked in, run `nm -D --defined-only /tmp/deps-cuda12/lib*/libparallelproj.so.2 | grep -c " cudaMalloc$"`. Expected: `0`.

If no local nvcc is available, skip this step: Task 8's CI log check covers the same thing.

- [ ] **Step 7: Check the pinned toolkit version exists**

Run: `curl -fsI https://developer.download.nvidia.com/compute/cuda/12.9.1/network_installers/cuda_12.9.1_windows_network.exe | head -1`
Expected: `HTTP/2 200`. (Task 12 uses this installer.)

- [ ] **Step 8: Commit**

```bash
git add packaging/pip/deps/versions.toml packaging/pip/deps/build_deps.py packaging/pip/tests/test_build_deps.py
git commit -m "Build libparallelproj with CUDA for the cuda12 deps prefix"
```

---

### Task 2: scikit-build-core overrides for `STIR_WHEEL_VARIANT`

**Files:**
- Modify: `pyproject.toml` (`[tool.scikit-build.cmake.define]` and new `[[tool.scikit-build.overrides]]`)
- Test: `packaging/pip/tests/test_prepare_build.py`

**Interfaces:**
- Consumes: `versions.toml` `[cuda.<variant>].architectures` (Task 1).
- Produces: one override keyed by `if.env.STIR_WHEEL_VARIANT` equal to `"cuda12"`. Task 3 checks it exists. Tasks 8 and 12 set the variable. (No `cuda13` override: deferred, appendix B1.)

STIR facts this depends on (top-level `CMakeLists.txt` lines 208–280): CUDA is attempted unless `DISABLE_STIR_CUDA` is set. It needs CMake ≥ 3.23. If `CMAKE_CUDA_ARCHITECTURES` is undefined it defaults to `"all"`, which is too big and includes sm_50. If nvcc or CUDAToolkit is missing, it only warns and silently turns CUDA off. Task 5's smoke test is what catches that. NiftyPET is out of scope (spec §2), so it is disabled explicitly to stop `find_package(NiftyPET)` from picking up a stray install.

- [ ] **Step 1: Write the failing tests**

```python
# add to packaging/pip/tests/test_prepare_build.py
import tomllib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text())
VERSIONS = tomllib.loads((ROOT / "packaging/pip/deps/versions.toml").read_text())

def _override(variant):
    matches = [o for o in PYPROJECT["tool"]["scikit-build"].get("overrides", [])
               if o.get("if", {}).get("env", {}).get("STIR_WHEEL_VARIANT") == variant]
    assert len(matches) == 1, f"expected exactly one override for {variant}"
    return matches[0]

def test_base_defines_disable_cuda():
    d = PYPROJECT["tool"]["scikit-build"]["cmake"]["define"]
    assert d["DISABLE_STIR_CUDA"] == "ON"
    assert d["DISABLE_NiftyPET_PROJECTOR"] == "ON"

@pytest.mark.parametrize("variant", ["cuda12"])
def test_cuda_override_enables_cuda(variant):
    o = _override(variant)
    assert o["inherit"]["cmake"]["define"] == "append"
    d = o["cmake"]["define"]
    assert d["DISABLE_STIR_CUDA"] == "OFF"
    assert d["CMAKE_CUDA_RUNTIME_LIBRARY"] == "Shared"

@pytest.mark.parametrize("variant", ["cuda12"])
def test_cuda_arch_lists_agree(variant):
    assert (_override(variant)["cmake"]["define"]["CMAKE_CUDA_ARCHITECTURES"]
            == VERSIONS["cuda"][variant]["architectures"])
```

- [ ] **Step 2: Run the tests to check they fail**

Run: `pytest packaging/pip/tests/test_prepare_build.py -k "base_defines or cuda_override or arch_lists" -v`
Expected: FAIL (`KeyError: 'DISABLE_STIR_CUDA'` / `expected exactly one override`).

- [ ] **Step 3: Edit `pyproject.toml`**

Add these keys to the existing `[tool.scikit-build.cmake.define]` and keep all of Phase 1/2's keys:

```toml
DISABLE_STIR_CUDA = "ON"
DISABLE_NiftyPET_PROJECTOR = "ON"
```

Append:

```toml
[[tool.scikit-build.overrides]]
if.env.STIR_WHEEL_VARIANT = "cuda12"
inherit.cmake.define = "append"
cmake.define.DISABLE_STIR_CUDA = "OFF"
cmake.define.CMAKE_CUDA_ARCHITECTURES = "70-real;75-real;80-real;86-real;89-real;90-real;100-real;120-real;120-virtual"
cmake.define.CMAKE_CUDA_RUNTIME_LIBRARY = "Shared"
```

`inherit.cmake.define = "append"` is required. Without it the override replaces the whole define table and drops `CMAKE_PROJECT_STIR_INCLUDE`, `BUILD_SHARED_LIBS`, `CMAKE_PREFIX_PATH` and the rest. The nvcc location is not set here. It comes from the `CUDACXX` environment variable (Tasks 8 and 12), because the path differs per platform.

- [ ] **Step 4: Run the tests to check they pass**

Run: `pytest packaging/pip/tests/test_prepare_build.py -v`
Expected: all PASS, including Phase 1's tests.

- [ ] **Step 5: Check scikit-build-core accepts the overrides**

Run: `STIR_WHEEL_VARIANT=cuda12 python -c "from scikit_build_core.settings.skbuild_read_settings import SettingsReader as R; d=R.from_file('pyproject.toml').settings.cmake.define; print(d['DISABLE_STIR_CUDA'], d['CMAKE_CUDA_RUNTIME_LIBRARY'], 'CMAKE_PROJECT_STIR_INCLUDE' in d)"`
Expected: `OFF Shared True`. The `True` shows that `append` kept the base defines. If `SettingsReader` lives elsewhere in the pinned scikit-build-core version, run `STIR_WHEEL_VARIANT=cuda12 pip wheel . -v` instead and check that the CMake command line contains both `-DDISABLE_STIR_CUDA` with `OFF` and Phase 1's `-DCMAKE_PROJECT_STIR_INCLUDE`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml packaging/pip/tests/test_prepare_build.py
git commit -m "Add the scikit-build override for the cuda12 variant"
```

---

### Task 3: `prepare_build.py` for `cuda12`

**Files:**
- Modify: `packaging/pip/prepare_build.py`
- Test: `packaging/pip/tests/test_prepare_build.py`

**Interfaces:**
- Consumes: the contract CLI `--variant {cpu,cuda12,cuda13} [--dev-number N] [--pyproject PATH]`; `versions.toml` `[cuda.<variant>].runtime_requirement` (Task 1); the overrides (Task 2).
- Produces: for `cudaXX`, `[project].name = "stir-cudaXX"` and `runtime_requirement` appended to `[project].dependencies` (the line carrying Phase 1's `# prepare_build: dependencies` marker; keep it a single-line array, and keep any other entries such as Phase 5's `root`). Exit 0 on success, 2 on bad arguments (contract), and **1** with a message on stderr when the pyproject has no override for the requested variant. `versions.toml` is found at `Path(__file__).parent / "deps" / "versions.toml"` and read only for CUDA variants (so `cpu` still works on a copied pyproject, as Phase 4's `release_check.py` does). The override check runs **before** `versions.toml` is read, so the reserved `cuda13` (no override, no table) exits 1 with the override message.

- [ ] **Step 1: Write the failing tests**

In Phase 1's `test_cli_bad_arguments_exit_2`, delete the `["--variant", "cuda12"]` case. Phase 1's module already
defines `REPO` (use it where the snippets below say `ROOT`) and `SCRIPT`.

```python
# add to packaging/pip/tests/test_prepare_build.py
import shutil, subprocess, sys

def prep(tmp_path, *args, source=ROOT / "pyproject.toml"):
    p = tmp_path / "pyproject.toml"
    if not p.exists():
        shutil.copy(source, p)
        shutil.copy(ROOT / "VERSION.txt", tmp_path / "VERSION.txt")
    r = subprocess.run([sys.executable, str(SCRIPT), "--pyproject", str(p), *args],
                       capture_output=True, text=True)
    return r, (tomllib.loads(p.read_text()) if p.exists() else None)

@pytest.mark.parametrize("variant,dep", [
    ("cuda12", "nvidia-cuda-runtime-cu12>=12.9,<13")])
def test_cuda_variant_name_and_dependency(tmp_path, variant, dep):
    r, doc = prep(tmp_path, "--variant", variant)
    assert r.returncode == 0, r.stderr
    assert doc["project"]["name"] == f"stir-{variant}"
    assert dep in doc["project"]["dependencies"]
    assert any(d.startswith("numpy") for d in doc["project"]["dependencies"])

def test_cpu_has_no_nvidia_dependency(tmp_path):
    r, doc = prep(tmp_path, "--variant", "cpu")
    assert r.returncode == 0
    assert not any(d.startswith("nvidia") for d in doc["project"]["dependencies"])

def test_cuda_variant_is_idempotent(tmp_path):
    prep(tmp_path, "--variant", "cuda12")
    r, doc = prep(tmp_path, "--variant", "cuda12")
    assert r.returncode == 0
    assert sum(d.startswith("nvidia-cuda-runtime") for d in doc["project"]["dependencies"]) == 1

def test_cuda_with_dev_number(tmp_path):
    r, doc = prep(tmp_path, "--variant", "cuda12", "--dev-number", "42")
    assert doc["project"]["name"] == "stir-cuda12"
    assert doc["project"]["version"].endswith(".dev42")

def test_cuda_variant_requires_override(tmp_path):
    text = (ROOT / "pyproject.toml").read_text()
    stripped = text[: text.index("[[tool.scikit-build.overrides]]\nif.env.STIR_WHEEL_VARIANT = \"cuda12\"")]
    src = tmp_path / "src.toml"; src.write_text(stripped)
    r, _ = prep(tmp_path, "--variant", "cuda12", source=src)
    assert r.returncode == 1
    assert 'STIR_WHEEL_VARIANT = "cuda12"' in r.stderr

def test_deferred_cuda13_exits_1(tmp_path):
    r, _ = prep(tmp_path, "--variant", "cuda13")
    assert r.returncode == 1 and 'STIR_WHEEL_VARIANT = "cuda13"' in r.stderr
```

(The `stripped` trick only works if the cuda12 override is the last table in the file. Task 2 appends it there. If Phase 2 added tables after it, build the fixture by removing that one table with the TOML library.)

- [ ] **Step 2: Run the tests to check they fail**

Run: `pytest packaging/pip/tests/test_prepare_build.py -v -k "cuda or nvidia"`
Expected: FAIL. Phase 1 rejects `cuda12`/`cuda13` (exit 2) or leaves the name unchanged.

- [ ] **Step 3: Implement it in `prepare_build.py`**

Use Phase 1's `VARIANT_PACKAGE_NAMES` and extend `rewrite_pyproject`. Remove Phase 1's exit 2 for CUDA variants. Add `runtime_requirement(variant: str) -> str | None`, which reads versions.toml and returns `None` for `cpu`, and `has_variant_override(doc, variant: str) -> bool`.

For a CUDA variant: set the name; remove any existing entry starting with `nvidia-cuda-runtime` from `dependencies`, then append the requirement (this keeps re-runs idempotent). If `has_variant_override` is false, print `prepare_build: pyproject.toml has no [[tool.scikit-build.overrides]] with if.env.STIR_WHEEL_VARIANT = "<variant>"` to stderr and exit 1. On success, print `prepare_build: remember to set STIR_WHEEL_VARIANT=<variant> when building` to stdout. Use the same marker-line rewriting as Phase 1 (parse the dependencies line's array with `tomllib`, rewrite the line, re-check the whole file with `tomllib.loads`).

- [ ] **Step 4: Run the tests to check they pass**

Run: `pytest packaging/pip/tests/test_prepare_build.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add packaging/pip/prepare_build.py packaging/pip/tests/test_prepare_build.py
git commit -m "Support the cuda12 variant in prepare_build.py"
```

---

### Task 4: `stir/_cuda.py` runtime loader, GPU status and variant check

**Files:**
- Create: `src/swig/python/stir/_cuda.py` (installed into the wheel automatically by STIR's `INSTALL(DIRECTORY python/ ...)` in `src/swig/CMakeLists.txt:147`)
- Modify: `src/swig/python/stir/__init__.py`
- Test: `packaging/pip/tests/test_cuda_loader.py`

**Interfaces:**
- Consumes: Phase 1's `__init__.py` (its `_configure_data_dirs(...)` line comes before upstream's unchanged `from .swigstir import * # noqa: F401`).
- Produces (all in `stir._cuda`; Tasks 5, 9 and 10 use them):

```python
# First version: cpu and cuda12 only. Appendix B1 adds the cuda13 entries.
VARIANT_DISTS: dict[str, str]          # {"cpu": "stir", "cuda12": "stir-cuda12"}
RUNTIME_RELPATHS: dict[tuple[str, str], str]  # (variant, sys.platform) -> path under a site-packages "nvidia" dir:
#   ("cuda12","linux"): "cuda_runtime/lib/libcudart.so.12"    ("cuda12","win32"): "cuda_runtime/bin/cudart64_12.dll"
RUNTIME_PIP_PACKAGE: dict[str, str]    # {"cuda12": "nvidia-cuda-runtime-cu12"}
MIN_DRIVER_API: dict[str, int]         # {"cuda12": 12000}  (cuDriverGetVersion units)
MIN_COMPUTE: dict[str, tuple[int, int]]  # {"cuda12": (7, 0)}

@dataclass(frozen=True)
class DriverProbe:
    loaded: bool; driver_version: int | None; init_rc: int | None
    capabilities: tuple[tuple[int, int], ...]

@dataclass(frozen=True)
class CudaStatus:
    ok: bool
    reason: str   # one of "ok","no-driver","driver-too-old","driver-error","no-device","unsupported-gpu"
    message: str  # "" when ok
    driver_version: int | None
    capabilities: tuple[tuple[int, int], ...]

def installed_variants(lookup: Callable[[str], object] = importlib.metadata.distribution) -> list[str]
def multiple_variants_message(variants: Sequence[str]) -> str | None
def nvidia_dirs() -> list[Path]
def find_cuda_runtime(variant: str, dirs: Iterable[Path], platform: str = sys.platform) -> Path | None
def preload_cuda_runtime(variant: str) -> Path        # raises ImportError
def loaded_runtime() -> Path | None
def probe_driver(platform: str = sys.platform) -> DriverProbe
def classify(variant: str, probe: DriverProbe) -> CudaStatus
def device_status(variant: str) -> CudaStatus
def require_gpu(variant: str | None = None) -> None   # raises RuntimeError(status.message)
def prepare_runtime() -> None
```

Behaviour that the signatures and tests don't fully pin down:

- `installed_variants` returns the variants whose distribution `lookup` finds (it catches `PackageNotFoundError`), in `cpu, cuda12` order. It costs two metadata lookups and does not scan the whole environment.
- `nvidia_dirs()` returns `importlib.util.find_spec("nvidia").submodule_search_locations` as Paths, or `[]`. `nvidia` is a namespace package that can span several site dirs. Nothing is hard-coded, so a moved venv still works.
- `preload_cuda_runtime`: if `find_cuda_runtime` finds the library, load it. On Linux use `ctypes.CDLL(str(path), mode=ctypes.RTLD_GLOBAL)`; glibc then matches `_stir`'s and libparallelproj's `DT_NEEDED libcudart.so.N` against the loaded SONAME. On Windows, call `os.add_dll_directory(path.parent)` (keep the handle in a module global) and then `ctypes.WinDLL(str(path))`. If it isn't found, try the bare name (`libcudart.so.12` / `cudart64_12.dll`) so a system CUDA or conda environment still works. If that also fails, raise `ImportError`: `stir-cuda12 could not load the CUDA 12 runtime (libcudart.so.12). It normally comes with the pip package nvidia-cuda-runtime-cu12. Fix: pip install --force-reinstall "nvidia-cuda-runtime-cu12>=12.9,<13"`.
- `probe_driver` loads `libcuda.so.1` (Linux) or `nvcuda.dll` (Windows) with ctypes, then calls `cuDriverGetVersion`, `cuInit(0)`, `cuDeviceGetCount`, and for each device `cuDeviceGet` plus `cuDeviceGetAttribute` with attributes 75 and 76 (compute capability major/minor). It never raises. If the library fails to load, it returns `loaded=False`.
- `classify` checks in this order: not loaded → `no-driver`; `driver_version < MIN_DRIVER_API` → `driver-too-old`; `init_rc == 100` (CUDA_ERROR_NO_DEVICE) or no capabilities → `no-device`; any other non-zero `init_rc` → `driver-error`; every capability `< MIN_COMPUTE` → `unsupported-gpu`; otherwise `ok`. Messages always start with the package name (`stir-cuda12 ...`) and end with a concrete fix. The tests pin the key wording.
- `prepare_runtime()`:
  1. `vs = installed_variants()`.
  2. If `multiple_variants_message(vs)` returns a message, `warnings.warn(msg, RuntimeWarning, stacklevel=2)`.
  3. For each CUDA variant in `vs`, call `preload_cuda_runtime(v)`. If exactly one variant is installed, let `ImportError` propagate. If several are installed, swallow it (best effort).
  4. If exactly one CUDA variant is installed and `device_status(v).ok` is false, `warnings.warn(status.message, RuntimeWarning, stacklevel=2)`.
  5. With no `stir*` distribution (source or conda install), do nothing.

- [ ] **Step 1: Check the NVIDIA wheel layouts used in `RUNTIME_RELPATHS`**

Run:
```bash
d=$(mktemp -d); for p in manylinux2014_x86_64 win_amd64; do pip download -q --no-deps --only-binary=:all: --platform $p --python-version 3.12 -d $d "nvidia-cuda-runtime-cu12>=12.9,<13"; done; for w in $d/*.whl; do python -I -m zipfile -l $w | grep -oE "nvidia/[^ ]*(libcudart\.so\.12|cudart64_12\.dll)"; done
```
Expected (one line per wheel): `nvidia/cuda_runtime/lib/libcudart.so.12`, `nvidia/cuda_runtime/bin/cudart64_12.dll`. If either differs, use the observed paths in `RUNTIME_RELPATHS` and the tests.

- [ ] **Step 2: Write the failing tests**

```python
# packaging/pip/tests/test_cuda_loader.py
import ast, importlib.util, importlib.metadata
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
PKG = ROOT / "src/swig/python/stir"
spec = importlib.util.spec_from_file_location("stir_cuda_under_test", PKG / "_cuda.py")
cu = importlib.util.module_from_spec(spec); spec.loader.exec_module(cu)

def fake_lookup(*present):
    def lookup(name):
        if name in present: return object()
        raise importlib.metadata.PackageNotFoundError(name)
    return lookup

def test_installed_variants_single():
    assert cu.installed_variants(fake_lookup("stir-cuda12")) == ["cuda12"]

def test_installed_variants_none():
    assert cu.installed_variants(fake_lookup()) == []

def test_multiple_variants_message():
    assert cu.multiple_variants_message(["cuda12"]) is None
    msg = cu.multiple_variants_message(["cpu", "cuda12"])
    assert "stir, stir-cuda12" in msg
    assert "pip uninstall -y stir stir-cuda12" in msg

@pytest.mark.parametrize("variant,platform", list(cu.RUNTIME_RELPATHS))
def test_find_cuda_runtime_in_second_dir(tmp_path, variant, platform):
    a, b = tmp_path / "a", tmp_path / "b"
    lib = b / cu.RUNTIME_RELPATHS[(variant, platform)]
    lib.parent.mkdir(parents=True); lib.write_bytes(b"")
    a.mkdir()
    assert cu.find_cuda_runtime(variant, [a, b], platform) == lib

def test_find_cuda_runtime_wrong_major(tmp_path):
    lib = tmp_path / "cu13/lib/libcudart.so.13"   # a CUDA 13 runtime must not satisfy cuda12
    lib.parent.mkdir(parents=True); lib.write_bytes(b"")
    assert cu.find_cuda_runtime("cuda12", [tmp_path], "linux") is None

def probe(**kw):
    base = dict(loaded=True, driver_version=12090, init_rc=0, capabilities=((8, 6),))
    base.update(kw); return cu.DriverProbe(**base)

def test_classify_ok():
    s = cu.classify("cuda12", probe())
    assert s.ok and s.reason == "ok" and s.message == ""

def test_classify_no_driver():
    s = cu.classify("cuda12", probe(loaded=False, driver_version=None, init_rc=None, capabilities=()))
    assert not s.ok and s.reason == "no-driver"
    assert s.message.startswith("stir-cuda12") and "pip install stir" in s.message

def test_classify_driver_too_old():
    s = cu.classify("cuda12", probe(driver_version=11040))
    assert s.reason == "driver-too-old"
    assert "11.4" in s.message and "12.0" in s.message and "pip install stir" in s.message

def test_classify_no_device():
    s = cu.classify("cuda12", probe(init_rc=100, capabilities=()))
    assert s.reason == "no-device" and "nvidia-smi" in s.message

def test_classify_driver_error():
    s = cu.classify("cuda12", probe(init_rc=999, capabilities=()))
    assert s.reason == "driver-error" and "999" in s.message

def test_classify_unsupported_gpu():
    s = cu.classify("cuda12", probe(capabilities=((6, 1),)))
    assert s.reason == "unsupported-gpu"
    assert "6.1" in s.message and "7.0" in s.message and "pip install stir" in s.message

def test_classify_mixed_gpus_ok():
    assert cu.classify("cuda12", probe(capabilities=((6, 1), (9, 0)))).ok

def test_min_compute_matches_arch_lists():
    import tomllib
    v = tomllib.loads((ROOT / "packaging/pip/deps/versions.toml").read_text())
    for variant, (maj, mnr) in cu.MIN_COMPUTE.items():
        first = v["cuda"][variant]["architectures"].split(";")[0]
        assert first == f"{maj}{mnr}-real"

def test_prepare_runtime_noop_without_dists(monkeypatch, recwarn):
    monkeypatch.setattr(cu, "installed_variants", lambda *a, **k: [])
    cu.prepare_runtime()
    assert len(recwarn) == 0

def test_prepare_runtime_missing_runtime_raises(monkeypatch):
    monkeypatch.setattr(cu, "installed_variants", lambda *a, **k: ["cuda12"])
    monkeypatch.setattr(cu, "nvidia_dirs", lambda: [])
    monkeypatch.setattr(cu.ctypes, "CDLL", lambda *a, **k: (_ for _ in ()).throw(OSError("nope")))
    monkeypatch.setattr(cu.ctypes, "WinDLL", lambda *a, **k: (_ for _ in ()).throw(OSError("nope")), raising=False)
    with pytest.raises(ImportError, match="nvidia-cuda-runtime-cu12"):
        cu.prepare_runtime()

def test_init_calls_prepare_runtime_before_swig_import():
    tree = ast.parse((PKG / "__init__.py").read_text())
    lines = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "swigstir":
            lines["swig"] = node.lineno
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "prepare_runtime":
            lines["prep"] = node.lineno
    assert lines["prep"] < lines["swig"]
```

- [ ] **Step 3: Run the tests to check they fail**

Run: `pytest packaging/pip/tests/test_cuda_loader.py -v`
Expected: collection error `FileNotFoundError: .../stir/_cuda.py`.

- [ ] **Step 4: Implement `src/swig/python/stir/_cuda.py`** with the interface and behaviour above. Use only the standard library: `ctypes`, `dataclasses`, `importlib`, `os`, `sys`, `warnings`, `pathlib`. Format driver versions as `f"{v // 1000}.{v % 1000 // 10}"` (11040 → `11.4`).

- [ ] **Step 5: Wire it into `src/swig/python/stir/__init__.py`**

Directly after Phase 1's `_configure_data_dirs(...)` line, and before upstream's unchanged `from .swigstir import * # noqa: F401`, add exactly (overview):

```python
from . import _cuda
_cuda.prepare_runtime()
```

- [ ] **Step 6: Run the tests to check they pass**

Run: `pytest packaging/pip/tests/test_cuda_loader.py packaging/pip/tests/test_paths.py -v`
Expected: all PASS.

- [ ] **Step 7: Check a source/conda-style install is unaffected**

Run, in a Phase 2 CPU wheel venv: `pip install --force-reinstall --no-deps <Phase-2 cpu wheel>` with this branch's `_cuda.py`/`__init__.py` (or a local CPU wheel built from this branch), then `python -W error -c "import stir; print(stir._cuda.installed_variants())"`
Expected: `['cpu']` and no warning.

- [ ] **Step 8: Commit**

```bash
git add src/swig/python/stir/_cuda.py src/swig/python/stir/__init__.py packaging/pip/tests/test_cuda_loader.py
git commit -m "Load CUDA runtime from NVIDIA pip packages and report GPU status"
```

---

### Task 5: `cuda` feature checks in the wheel smoke test

**Files:**
- Modify: `packaging/pip/tests/test_wheel_smoke.py`

**Interfaces:**
- Consumes: `STIR_WHEEL_EXPECT` (contract); Phase 1's `expected_features(os.environ)` and `CHECKS`; `stir._cuda.installed_variants`, `loaded_runtime`, `device_status`, `CudaStatus.reason` (Task 4); libparallelproj's exported `parallelproj_cuda_enabled()` (Task 1).
- Produces: `CHECKS["cuda"] = check_cuda` (Phase 1's `test_expected_feature[cuda]` fails without it) and tests that pass on GitHub runners **without a GPU**.

The STIR facts these tests rely on: with `STIR_WITH_CUDA`, SWIG exposes `CudaRelativeDifferencePrior3DFloat`, `CudaGibbsRelativeDifferencePenalty3DFloat` and `CudaGibbsQuadraticPenalty3DFloat` (`src/swig/stir_priors.i:183-200`). Their constructors make no CUDA calls; CUDA starts in `set_up`/`compute_*`. With libparallelproj 2.x, the CPU and CUDA versions are the same STIR class (`ForwardProjectorByBinParallelproj`); only the linked library differs. So the bundled library is asked directly.

- [ ] **Step 1: Add the tests**

Below, `expected()` stands for `expected_features(os.environ)`. Turn the four `skipif("cuda" not in ...)` tests into
plain helper functions (`_check_cuda_runtime`, `_check_cuda_priors`, `_check_parallelproj_cuda`,
`_check_device_status`) with the same bodies, add `def check_cuda(): ...` that calls all four, and register
`CHECKS["cuda"] = check_cuda`. `test_cpu_wheel_has_no_cuda` stays a test.

```python
import ctypes, importlib.metadata, sys
from pathlib import Path

def _variant():
    vs = stir._cuda.installed_variants()
    assert len(vs) == 1, f"expected exactly one stir distribution, found {vs}"
    return vs[0]

def _bundled_parallelproj() -> Path:
    dist = stir._cuda.VARIANT_DISTS[_variant()]
    files = [f for f in importlib.metadata.distribution(dist).files
             if "parallelproj" in f.name and (".so" in f.name or f.name.endswith(".dll"))]
    assert len(files) == 1, f"bundled libparallelproj not found in {dist}: {files}"
    return Path(files[0].locate())

@pytest.mark.skipif("cuda" not in expected(), reason="cuda not expected")
def test_cuda_runtime_loaded_from_nvidia_package():
    p = stir._cuda.loaded_runtime()
    assert p is not None and "nvidia" in p.parts

@pytest.mark.skipif("cuda" not in expected(), reason="cuda not expected")
def test_cuda_prior_classes_exist():
    stir.CudaRelativeDifferencePrior3DFloat()
    assert hasattr(stir, "CudaGibbsRelativeDifferencePenalty3DFloat")
    assert hasattr(stir, "CudaGibbsQuadraticPenalty3DFloat")

@pytest.mark.skipif("cuda" not in expected(), reason="cuda not expected")
def test_parallelproj_built_with_cuda():
    lib = ctypes.CDLL(str(_bundled_parallelproj()))
    assert lib.parallelproj_cuda_enabled() == 1

@pytest.mark.skipif("cuda" not in expected(), reason="cuda not expected")
def test_cuda_device_status_is_reported():
    s = stir._cuda.device_status(_variant())
    assert s.reason in {"ok", "no-driver", "driver-too-old", "driver-error", "no-device", "unsupported-gpu"}
    assert s.ok == (s.reason == "ok") and (s.ok or s.message.startswith(f"stir-{_variant()}"))

@pytest.mark.skipif("cuda" in expected(), reason="cuda wheel")
def test_cpu_wheel_has_no_cuda():
    assert not hasattr(stir, "CudaRelativeDifferencePrior3DFloat")
    if "parallelproj" in expected():
        assert ctypes.CDLL(str(_bundled_parallelproj())).parallelproj_cuda_enabled() == 0
```

Where Phase 1 imports `stir` once at module level, reuse that import. The smoke test must not run with `-W error`: on GPU-less runners, `import stir` from a CUDA wheel deliberately emits a `RuntimeWarning`.

- [ ] **Step 2: Run it against a Phase 2 CPU wheel**

Run (in a venv with a Phase 2 `stir` wheel plus this branch's Python files, as in Task 4 Step 7): `STIR_WHEEL_EXPECT=config,openmp,json,hdf5,petsird,itk,parallelproj pytest packaging/pip/tests/test_wheel_smoke.py -v -k "cuda"`
Expected: `test_cpu_wheel_has_no_cuda PASSED`; `check_cuda` is not run. The CUDA path runs for real in Task 8.

- [ ] **Step 3: Commit**

```bash
git add packaging/pip/tests/test_wheel_smoke.py
git commit -m "Add cuda feature checks to the wheel smoke test"
```

---

### Task 6: Wheel size check

**Files:**
- Create: `packaging/pip/check_wheel_size.py`
- Test: `packaging/pip/tests/test_check_wheel_size.py`

**Interfaces:**
- Produces: CLI `python packaging/pip/check_wheel_size.py DIR [--max-mb 100]` (MB = 10^6 bytes, as PyPI counts it). It prints one line per wheel, `<name>  <size> MB`, and exits 0. If any wheel is over the limit it exits 1 and prints this to stderr for each one: `ERROR: <name> is <size> MB, over the <max> MB PyPI per-file limit. Narrow CMAKE_CUDA_ARCHITECTURES in packaging/pip/deps/versions.toml and the matching pyproject.toml override, or request a PyPI file-size increase.` If DIR holds no `.whl` it exits 2 with `ERROR: no wheels in <DIR>`.

- [ ] **Step 1: Write the failing tests**

```python
# packaging/pip/tests/test_check_wheel_size.py
import subprocess, sys
from pathlib import Path
SCRIPT = Path(__file__).resolve().parents[1] / "check_wheel_size.py"

def run(d, *a):
    return subprocess.run([sys.executable, str(SCRIPT), str(d), *a], capture_output=True, text=True)

def test_under_limit(tmp_path):
    (tmp_path / "a-1-py3-none-any.whl").write_bytes(b"x" * 1_000_000)
    r = run(tmp_path, "--max-mb", "2")
    assert r.returncode == 0 and "a-1-py3-none-any.whl" in r.stdout and "1.0 MB" in r.stdout

def test_over_limit(tmp_path):
    (tmp_path / "big-1-py3-none-any.whl").write_bytes(b"x" * 2_000_001)
    r = run(tmp_path, "--max-mb", "2")
    assert r.returncode == 1
    assert "big-1-py3-none-any.whl is 2.0 MB, over the 2 MB PyPI per-file limit" in r.stderr
    assert "CMAKE_CUDA_ARCHITECTURES" in r.stderr

def test_empty_dir(tmp_path):
    assert run(tmp_path).returncode == 2
```

- [ ] **Step 2: Run them to check they fail**

Run: `pytest packaging/pip/tests/test_check_wheel_size.py -v`
Expected: FAIL (script missing).

- [ ] **Step 3: Implement `check_wheel_size.py`** (`main(argv: list[str] | None = None) -> int`, standard library only). Print sizes with one decimal place.

- [ ] **Step 4: Run them to check they pass**

Run: `pytest packaging/pip/tests/test_check_wheel_size.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add packaging/pip/check_wheel_size.py packaging/pip/tests/test_check_wheel_size.py
git commit -m "Add wheel size check against the PyPI per-file limit"
```

---

### Task 7: CUDA toolkit install script for Linux CI

**Files:**
- Create: `packaging/pip/ci/install_cuda_linux.sh`
- Modify: `packaging/pip/deps/build_in_manylinux.sh` (Phase 2)

(The Windows script, `install_cuda_windows.ps1`, is created in Task 12.)

**Interfaces:**
- Consumes: `build_deps.py --cuda-version --variant V` (Task 1).
- Produces:
  - `bash packaging/pip/ci/install_cuda_linux.sh cuda12`, run as root inside a manylinux_2_28 container. Afterwards `/usr/local/cuda` is a symlink to `/usr/local/cuda-<maj>.<min>` and `/usr/local/cuda/bin/nvcc` works.
  - `build_in_manylinux.sh ARCH --variant cudaXX ...` (Phase 2's CLI) now runs `bash packaging/pip/ci/install_cuda_linux.sh cudaXX` inside the same container before `build_deps.py`, with `CUDACXX=/usr/local/cuda/bin/nvcc` exported. `cpu` is unchanged.

Linux script decisions:
- Python for reading the version: `/opt/python/cp312-cp312/bin/python packaging/pip/deps/build_deps.py --cuda-version --variant $1`. MM = `<maj>-<min>` (e.g. `12-9`).
- Repo arch: `x86_64` (`uname -m`; any other value exits 2 with "deferred platform", see appendix B2). URL: `https://developer.download.nvidia.com/compute/cuda/repos/rhel8/x86_64/cuda-rhel8.repo` (manylinux_2_28 is AlmaLinux 8, which CUDA 12.9 supports).
- Commands: `dnf install -y dnf-plugins-core`, `dnf config-manager --add-repo <url>`, `dnf install -y cuda-nvcc-$MM cuda-cudart-devel-$MM cuda-cccl-$MM`, `ln -sfn /usr/local/cuda-<maj>.<min> /usr/local/cuda`, `/usr/local/cuda/bin/nvcc --version`, `dnf clean all`. Use `set -euo pipefail`.
- If the image's default GCC is newer than nvcc supports (nvcc fails with `unsupported GNU version`), fix it in Task 8 by adding `-allow-unsupported-compiler` to `CMAKE_CUDA_FLAGS` through `CIBW_ENVIRONMENT` (`CUDAFLAGS`). Do not pin an older gcc-toolset.

- [ ] **Step 1: Write the script** following the decisions above.

- [ ] **Step 2: Test the Linux script in the manylinux_2_28 x86_64 container**

Run: `docker run --rm -v "$PWD":/project -w /project quay.io/pypa/manylinux_2_28_x86_64 bash packaging/pip/ci/install_cuda_linux.sh cuda12 | tail -2`
Expected: `Cuda compilation tools, release 12.9, V12.9.…`.

- [ ] **Step 3: Run `shellcheck packaging/pip/ci/install_cuda_linux.sh`**
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add packaging/pip/ci/install_cuda_linux.sh packaging/pip/deps/build_in_manylinux.sh
git commit -m "Add CUDA toolkit install script for manylinux CI"
```

---

### Task 8: `build_cuda` job in `wheels.yml` (Linux x86_64)

**Files:**
- Modify: `.github/workflows/wheels.yml`
- Modify: `packaging/pip/README.md` ("Building a CUDA variant locally" subsection)

**Interfaces:**
- Consumes: everything above. From Phase 2's `build_cpu`: the action pins, the "Locate the deps prefix and its cache key" step and the restore/save cache steps (Task 12 adds the MSVC and pwsh deps steps for Windows). Copy them with `cpu` replaced by `${{ matrix.variant }}`; don't redesign. Test settings (`test-requires`, `test-command`) come from `pyproject.toml`, and `STIR_DEPS_PREFIX`, `STIR_WHEEL_EXPECT` and `STIR_WHEEL_VARIANT` reach the Linux container through Phase 2's `environment-pass`.
- Produces: artifact `wheels-cuda12-linux-x86_64` (Task 12 adds `wheels-cuda12-windows-AMD64`). Task 9 downloads it. Matrix keys: Phase 2's `os, arch, runner, wheel_tag, expect, only` plus `variant` (Phase 5's tests read `os` and `expect`).

- [ ] **Step 1: Add the job** (the YAML is the decision; if Phase 2 recorded a known gap for a platform, use that platform's `build_cpu` `expect` plus `,cuda`):

```yaml
  build_cuda:
    name: build_cuda (${{ matrix.variant }} ${{ matrix.os }}-${{ matrix.arch }})
    if: github.repository == 'robbietuk/STIR'
    runs-on: ${{ matrix.runner }}
    timeout-minutes: 360
    strategy:
      fail-fast: false
      matrix:
        include:
          - variant: cuda12
            os: linux
            arch: x86_64
            runner: ubuntu-24.04
            wheel_tag: manylinux_2_28_x86_64
            expect: config,openmp,json,hdf5,petsird,itk,parallelproj,cuda
            only: ""
    env:
      STIR_WHEEL_VARIANT: ${{ matrix.variant }}
      STIR_WHEEL_EXPECT: ${{ matrix.expect }}
      CIBW_ARCHS: ${{ matrix.arch }}
      # The deps prefix (with CUDA libparallelproj) is built before cibuildwheel; STIR itself also needs nvcc.
      CIBW_BEFORE_ALL_LINUX: bash packaging/pip/ci/install_cuda_linux.sh ${{ matrix.variant }}
      CIBW_ENVIRONMENT_LINUX: CUDACXX=/usr/local/cuda/bin/nvcc PATH=/usr/local/cuda/bin:$PATH
      CIBW_REPAIR_WHEEL_COMMAND_LINUX: >-
        auditwheel repair
        --exclude libcudart.so.12
        --exclude libcuda.so.1
        -w {dest_dir} {wheel}
    steps:
      - uses: actions/checkout@v6
        with:
          submodules: recursive
          persist-credentials: false
      - uses: actions/setup-python@v6
        with:
          python-version: "3.13"
      # Phase 2's "Locate the deps prefix and its cache key" step, with .deps/cpu -> .deps/${{ matrix.variant }}
      # and --cache-key --variant ${{ matrix.variant }}.
      - name: Restore deps prefix
        id: deps-cache
        uses: actions/cache/restore@v4
        with:
          path: ${{ env.STIR_DEPS_HOST }}
          key: stir-deps-${{ matrix.variant }}-${{ matrix.os }}-${{ matrix.arch }}-${{ env.DEPS_KEY }}
      - name: Build deps prefix (Linux, pinned manylinux image, with CUDA)
        if: runner.os == 'Linux' && steps.deps-cache.outputs.cache-hit != 'true'
        run: bash packaging/pip/deps/build_in_manylinux.sh ${{ matrix.arch }} --variant ${{ matrix.variant }} --jobs 4
      - name: Save deps prefix
        if: steps.deps-cache.outputs.cache-hit != 'true'
        uses: actions/cache/save@v4
        with:
          path: ${{ env.STIR_DEPS_HOST }}
          key: stir-deps-${{ matrix.variant }}-${{ matrix.os }}-${{ matrix.arch }}-${{ env.DEPS_KEY }}
      - name: Prepare pyproject.toml (${{ matrix.variant }}, dev version)
        run: python packaging/pip/prepare_build.py --variant ${{ matrix.variant }} --dev-number ${{ github.run_number }}
      - name: Build and test wheels
        uses: pypa/cibuildwheel@v4.3.5
        with:
          output-dir: wheelhouse
      - name: Check wheel sizes
        run: python packaging/pip/check_wheel_size.py wheelhouse --max-mb 100
      - uses: actions/upload-artifact@v4
        with:
          name: wheels-${{ matrix.variant }}-${{ matrix.os }}-${{ matrix.arch }}
          path: wheelhouse/*.whl
          if-no-files-found: error
```

Notes for the implementer:
- The deps prefix is built on the host side (Linux: `build_in_manylinux.sh` in the same pinned image, which installs CUDA first), so `actions/cache/save` can store it. Building it in cibuildwheel's `before-all` would leave it inside the container, and the cache would never be saved. Completion is Phase 2's `<prefix>/.stamps/<name>`; `build_deps.py` skips stamped deps itself.
- The Windows row, its steps and its repair command are added in Task 12.
- Update the Phase 1/2 workflow tests this job affects: `test_job_names` gains `build_cuda`, and `test_builds_use_dev_number` expects 3 `prepare_build.py` calls.

- [ ] **Step 2: Check the workflow syntax**

Run: `actionlint .github/workflows/wheels.yml`
Expected: no output.

- [ ] **Step 3: Add the README subsection.** Write 10–15 lines covering `prepare_build.py --variant cuda12`, `export STIR_WHEEL_VARIANT=cuda12`, `CUDACXX`, `STIR_DEPS_PREFIX` from `build_deps.py --variant cuda12`, then `pip wheel .`. Note that the env var and `--variant` must match, and that the smoke test with `cuda` in `STIR_WHEEL_EXPECT` catches a mismatch.

- [ ] **Step 4: Commit, push to the fork, and watch the run**

This is Phase 3's first push. Ask Robert once: "Phase 3 needs pushes of `pip-packaging` to `fork` (robbietuk/STIR). OK?" Do not push without his yes in the conversation.

```bash
git add .github/workflows/wheels.yml packaging/pip/README.md
git commit -m "Add build_cuda CI job for Linux x86_64 cuda12 wheels"
git push fork pip-packaging
gh run watch --repo robbietuk/STIR --exit-status
```
Expected:
- The `build_cuda (cuda12 linux-x86_64)` job is green.
- Its "Check wheel sizes" lists 5 wheels, all under 100 MB.
- `gh run download --repo robbietuk/STIR -n wheels-cuda12-linux-x86_64 -D /tmp/w && ls /tmp/w` shows `stir_cuda12-6.5.0.dev<N>-cp311-…-manylinux_2_28_x86_64.whl` through `cp315`.

- [ ] **Step 5: Check the build logs**

Run: `gh run view --repo robbietuk/STIR --log --job <build_cuda cuda12 linux-x86_64 job id> | grep -E "STIR CUDA support enabled|Found parallelproj|stir-wheel: build features|test_expected_feature\[cuda\]"`
Expected:
- `STIR CUDA support enabled. Using CUDA version 12.9.`
- `Found parallelproj 2.0.7 (will use its CUDA support)`
- `test_expected_feature[cuda] PASSED` (which runs the four cuda checks), for each of the 5 Pythons.

There must be no `nvidia-smi not found` failure, only the warning. If `STIR CUDA support enabled` is missing, nvcc was not found: check `CUDACXX`.

- [ ] **Step 6: Check the excluded runtime really is excluded**

Run: `unzip -l /tmp/w/stir_cuda12-*cp312*.whl | grep -Ei "cudart|libcuda" ; echo "exit=$?"`
Expected: `exit=1` (no matches). (Task 12 repeats this for a `win_amd64` wheel.)

---

### Task 9: `rehearse_publish` installs CUDA variants and checks the two-variant warning

**Files:**
- Modify: `.github/workflows/wheels.yml` (`rehearse_publish`)

**Interfaces:**
- Consumes: the `wheels-cuda12-linux-x86_64` artifact (Task 8); Phase 2's matrix `rehearse_publish` (rows `variant, os, arch, runner, expect, pythons, coexist`; background pypiserver with `--fallback-url https://pypi.org/simple/`, `twine upload`, fresh venv install, smoke test); `multiple_variants_message` wording (Task 4).
- Produces: a rehearsal that resolves `nvidia-cuda-runtime-cu12` through pypiserver's default fallback to `https://pypi.org/simple/` (the same way `numpy` already resolves), and fails if the two-variant warning ever stops firing.

- [ ] **Step 1: Extend the job**

1. Add `build_cuda` to `needs:`, and update Phase 1's `test_rehearsal_installs_exact_dev_version` to expect `needs == ["sdist", "build_cpu", "build_cuda"]`.
2. Downloads already use `pattern: wheels-*` (merge-multiple), so the CUDA wheels are uploaded with `twine` alongside the CPU ones. Change "Check the index lists every file" to check each file under `/simple/<project>/`, where `<project>` is the file name's distribution part with `_` → `-` (`stir`, `stir-cuda12`).
3. Add one matrix row with `pythons: "3.12"`, `coexist: false` and `expect: config,openmp,json,hdf5,petsird,itk,parallelproj,cuda` (or Linux x86_64's CPU expect plus `,cuda`): `{variant: cuda12, os: linux, arch: x86_64, runner: ubuntu-24.04}`. (Task 12 adds the Windows row.) In the install loop set `pkg=stir` for `cpu` and `pkg=stir-${{ matrix.variant }}` otherwise, and install `"$pkg==$version"`; update Phase 1's `test_rehearsal_installs_exact_dev_version` string to `--index-url http://localhost:8080/simple/ "$pkg==$version"`. Change Phase 2's `test_rehearsal_covers_every_build_platform_with_same_expect` so that every `rehearse_publish` row's `expect` equals the `expect` of the `build_cpu`/`build_cuda` row with the same `(variant, os, arch)`, and every `build_cpu` platform has a `cpu` rehearsal row.
4. Add one step, with `if: matrix.variant == 'cpu' && matrix.os == 'linux' && matrix.arch == 'x86_64'`, after the normal install test. Expected output: `two-variant warning OK`.

```bash
python -m venv /tmp/two && . /tmp/two/bin/activate
version="$(cat VERSION.txt).dev${{ github.run_number }}"
pip install --index-url http://localhost:8080/simple/ "stir==$version" "stir-cuda12==$version"
python - <<'EOF'
import warnings
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    import stir  # noqa: F401
msgs = [str(x.message) for x in w if issubclass(x.category, RuntimeWarning)]
assert any("stir, stir-cuda12" in m for m in msgs), msgs
print("two-variant warning OK")
EOF
```

- [ ] **Step 2: Run actionlint, then commit and push**

```bash
actionlint .github/workflows/wheels.yml
git add .github/workflows/wheels.yml
git commit -m "Rehearse publishing and installing the CUDA variants"
git push fork pip-packaging
gh run watch --repo robbietuk/STIR --exit-status
```
Expected:
- `rehearse_publish` is green.
- The `stir-cuda12` install log shows `Successfully installed ... nvidia-cuda-runtime-cu12-12.9.… stir-cuda12-6.5.0.dev<N>`.
- `test_expected_feature[cuda]` PASSES.
- The two-variant step prints `two-variant warning OK`.
- `publish` is shown as skipped.

---

### Task 10: `gpu_check.py` manual GPU script

**Files:**
- Create: `packaging/pip/tests/gpu_check.py` (pytest does not collect it, because the name doesn't start with `test_`)
- Modify: `packaging/pip/README.md` ("Checking a CUDA wheel on a real GPU" section, plus an empty sign-off table)

**Interfaces:**
- Consumes: `stir._cuda.installed_variants`, `device_status`, `CudaStatus` (Task 4); `stirextra.to_numpy`; STIR Python classes `Scanner`, `ProjDataInfo`, `ProjDataInMemory`, `ExamInfo`, `FloatVoxelsOnCartesianGrid`, `EllipsoidalCylinder`, `ForwardProjectorByBinParallelproj`, `BackProjectorByBinParallelproj`, `RelativeDifferencePrior3DFloat`, `CudaRelativeDifferencePrior3DFloat`.
- Produces this CLI:
  - `python packaging/pip/tests/gpu_check.py reference --out ref.npz`. Run it in a venv with the CPU `stir` wheel. It writes arrays `fwd`, `back` and the scalar `stir_version`.
  - `python packaging/pip/tests/gpu_check.py compare --ref ref.npz`. Run it in a venv with `stir-cudaXX` on a GPU machine.
  - Exit codes: 0 all checks pass; 1 a check failed (prints which and by how much); 2 bad arguments, or a reference made with a different STIR version or setup; 3 no usable GPU (prints `CudaStatus.message`).

Fixed setup, which must be identical in both modes (build it in one function, `make_setup() -> tuple[proj_data_info, image]`):
- Scanner `ECAT 962`, then `set_up()`.
- `ProjDataInfo.construct_proj_data_info(scanner, 3, 9, 8, 6)` (the same arguments as `src/swig/test/python/test_buildblock.py`).
- `FloatVoxelsOnCartesianGrid(proj_data_info, 1)`.
- An `EllipsoidalCylinder` of length 100 mm, radii 80 and 60 mm, centred on the image middle, painted with `construct_volume(image, IntCartesianCoordinate3D(1,1,1))`, then a second cylinder (length 50, radii 20/20, offset +30 mm in x) added at value 2.
- No random numbers, so the reference is reproducible.

Checks in `compare`:
1. **GPU status.** If `device_status(variant)` isn't ok, exit 3. Otherwise print the driver version and the compute capabilities.
2. **Forward projection.** Use `ForwardProjectorByBinParallelproj`: `set_up(proj_data_info, image)`, then `forward_project(proj_data, image)` into a `ProjDataInMemory`. Pass if `max|gpu − ref.fwd| ≤ 1e-3 · max|ref.fwd|`.
3. **Back projection.** Use `BackProjectorByBinParallelproj` on an all-ones `ProjDataInMemory` (`start_accumulating_in_new_target()`, `back_project(...)`, `get_output(...)`). Pass if `max|gpu − ref.back| ≤ 1e-3 · max|ref.back|`.
4. **RDP prior, in-process.** Use `RelativeDifferencePrior3DFloat` and `CudaRelativeDifferencePrior3DFloat`, both with `set_penalisation_factor(1.0)` and default gamma/epsilon, `set_up(image)` on image + 0.1. Pass if `|v_gpu − v_cpu| ≤ 1e-4 · |v_cpu|` and `max|g_gpu − g_cpu| ≤ 1e-3 · max|g_cpu|`.
5. Print a summary table: check, max relative difference, tolerance, PASS/FAIL, wall time.

In `reference` mode, if `"cuda"` is in the installed variant, exit 2 with `reference must be made with the CPU package 'stir'`. A CUDA wheel's parallelproj is CUDA-only, so a reference made with it would compare GPU with GPU.

- [ ] **Step 1: Write `gpu_check.py`** as specified (`main(argv: list[str] | None = None) -> int`).

- [ ] **Step 2: Check `reference` mode on a CPU wheel (no GPU needed)**

Run: `python packaging/pip/tests/gpu_check.py reference --out /tmp/ref.npz && python -c "import numpy as n;d=n.load('/tmp/ref.npz');print(d['fwd'].shape, d['back'].shape, float(d['fwd'].max())>0)"`
Expected: two shapes and `True`.

- [ ] **Step 3: Check `compare` fails cleanly without a GPU**

Run in a venv with a CI-built `stir-cuda12` wheel on a machine without an NVIDIA driver: `python packaging/pip/tests/gpu_check.py compare --ref /tmp/ref.npz; echo exit=$?`
Expected: a line starting `stir-cuda12 is installed but no NVIDIA driver was found`, then `exit=3`.

- [ ] **Step 4: Write the README section**: the two-venv procedure from Task 11, what each exit code means, and a sign-off table with columns `Date | Variant | OS / arch | GPU (compute cap.) | Driver | Python | gpu_check | smoke test | Who`.

- [ ] **Step 5: Commit**

```bash
git add packaging/pip/tests/gpu_check.py packaging/pip/README.md
git commit -m "Add manual GPU check comparing CPU and CUDA results"
```

---

### Task 11: Manual GPU sign-off (Robert)

**Files:**
- Modify: `packaging/pip/README.md` (fill in the sign-off table)

**Interfaces:**
- Consumes: CI artifacts from a green run with Tasks 1–10; `gpu_check.py` (Task 10); `test_wheel_smoke.py` (Task 5).

This task is done by Robert on real hardware. An agent prepares the commands and records the results Robert reports.

- [ ] **Step 1: Download the artifacts of the latest green run**

Run: `gh run download --repo robbietuk/STIR <run-id> -p "wheels-*" -D ~/stir-wheels`
Expected: `~/stir-wheels/wheels-cpu-linux-x86_64/`, `…/wheels-cuda12-linux-x86_64/` and the CPU artifacts for the other platforms. `<version>` below is the run's `6.5.0.devN` (from the wheel file names); always pin it, because `.devN` is a pre-release and an unpinned name could resolve to an unrelated project on PyPI.

- [ ] **Step 2: Make the CPU reference** (any machine, Python 3.12)

```bash
python3.12 -m venv ~/v-cpu && ~/v-cpu/bin/pip install --find-links ~/stir-wheels/wheels-cpu-linux-x86_64 "stir==<version>"
~/v-cpu/bin/python packaging/pip/tests/gpu_check.py reference --out ~/ref.npz
```
Expected: exit 0, and `~/ref.npz` exists.

- [ ] **Step 3: Check `stir-cuda12` on the GPU machine** (driver ≥ 525, GPU compute capability ≥ 7.0)

```bash
nvidia-smi --query-gpu=name,compute_cap,driver_version --format=csv,noheader
python3.12 -m venv ~/v-cu12 && ~/v-cu12/bin/pip install --find-links ~/stir-wheels/wheels-cuda12-linux-x86_64 "stir-cuda12==<version>"
~/v-cu12/bin/python -W error::RuntimeWarning -c "import stir; print(stir._cuda.device_status('cuda12'))"
~/v-cu12/bin/python packaging/pip/tests/gpu_check.py compare --ref ~/ref.npz
STIR_WHEEL_EXPECT=config,openmp,json,hdf5,petsird,itk,parallelproj,cuda ~/v-cu12/bin/python -m pytest packaging/pip/tests/test_wheel_smoke.py src/swig/test/python -q
```
Expected:
- `CudaStatus(ok=True, reason='ok', ...)`, with no warning (`-W error` would turn one into a failure).
- `gpu_check` prints 4 PASS rows and exits 0.
- pytest passes with no failures.

- [ ] **Step 4: Check moving the venv** (anti-goal: breaks when the venv is moved)

Run: `mv ~/v-cu12 ~/v-cu12-moved && ~/v-cu12-moved/bin/python packaging/pip/tests/gpu_check.py compare --ref ~/ref.npz`
Expected: exit 0. Note that `bin/python` symlinks survive the move, but pip's console scripts do not; only `python` is used here.

- [ ] **Step 5: Record the results and commit**

Fill in the Linux x86_64 `stir-cuda12` row with GPU, compute capability, driver, Python, results and date.

```bash
git add packaging/pip/README.md
git commit -m "Record Phase 3 Linux GPU sign-off results"
```

The Linux task group is complete when the Linux x86_64 `stir-cuda12` row says PASS. Continue with Task 12.

---

## Windows x86_64 (task group 2; start after Task 11 passes)

### Task 12: Windows x86_64 `stir-cuda12` in CI

**Files:**
- Create: `packaging/pip/ci/install_cuda_windows.ps1`
- Modify: `.github/workflows/wheels.yml` (`build_cuda` Windows row and steps; `rehearse_publish` Windows row)
- Modify: `packaging/pip/tests/test_ci_config.py` only if a Phase 2 test enumerates `build_cuda` rows

**Interfaces:**
- Consumes: `build_deps.py --cuda-version --variant cuda12` (Task 1); Task 8's `build_cuda` job; Phase 2's `build_cpu`
  MSVC step and pwsh "Build deps prefix (macOS, Windows)" step (with Phase 2 Task 9's Windows prefix root, if its
  fallback shortened it).
- Produces:
  - `pwsh packaging/pip/ci/install_cuda_windows.ps1 -Variant cuda12`, run on a GitHub Windows runner. Afterwards `CUDA_PATH` and `CUDACXX` are in `$env:GITHUB_ENV`, and `<CUDA_PATH>\bin` (plus `<CUDA_PATH>\bin\x64` if it exists) is in `$env:GITHUB_PATH`.
  - Artifact `wheels-cuda12-windows-AMD64`.

Windows script decisions:
- `$ver` comes from `python packaging/pip/deps/build_deps.py --cuda-version --variant $Variant`, and `$mm = "<maj>.<min>"`.
- Download `https://developer.download.nvidia.com/compute/cuda/$ver/network_installers/cuda_${ver}_windows_network.exe` and run it with `Start-Process -Wait -PassThru` and arguments `-s nvcc_$mm cudart_$mm thrust_$mm visual_studio_integration_$mm`. (Appendix B1 adds the CUDA 13 sub-packages.) Fail if the exit code is non-zero.
- `CUDA_PATH = C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v$mm` and `CUDACXX = $CUDA_PATH\bin\nvcc.exe`. Finish with `& $env:CUDACXX --version`.

- [ ] **Step 1: Write `install_cuda_windows.ps1`** following the decisions above.

- [ ] **Step 2: Add the Windows row and steps to `build_cuda`**

```yaml
          - variant: cuda12
            os: windows
            arch: AMD64
            runner: windows-2022
            wheel_tag: win_amd64
            expect: config,openmp,json,hdf5,petsird,itk,parallelproj,cuda
            only: ""
```
(use Phase 2's Windows `build_cpu` `expect` plus `,cuda` if Phase 2 recorded a known gap). Add to the job `env:`:

```yaml
      CIBW_REPAIR_WHEEL_COMMAND_WINDOWS: >-
        delvewheel repair
        --exclude "cudart64_12.dll;nvcuda.dll"
        --add-path %STIR_DEPS_PREFIX%\bin
        -w {dest_dir} -v {wheel}
```
and, after "Restore deps prefix":

```yaml
      - name: Install CUDA toolkit (Windows)
        if: runner.os == 'Windows'
        run: pwsh packaging/pip/ci/install_cuda_windows.ps1 -Variant ${{ matrix.variant }}
      - name: MSVC environment (Windows)
        if: runner.os == 'Windows'
        uses: ilammy/msvc-dev-cmd@v1
      # Phase 2's "Build deps prefix (macOS, Windows)" pwsh step, with --variant ${{ matrix.variant }}.
```
The Windows runner is pinned to `windows-2022`: VS 2022 is supported by CUDA 12.9, and CUDA 12.9 does not support VS 2026.

- [ ] **Step 3: Add the Windows rehearsal row**: `{variant: cuda12, os: windows, arch: AMD64, runner: windows-2022}` with `pythons: "3.12"`, `coexist: false` and the same `expect` as the `build_cuda` row.

- [ ] **Step 4: Run actionlint and the unit tests, then commit, push and watch**

```bash
actionlint .github/workflows/wheels.yml
python -m pytest packaging/pip/tests --ignore=packaging/pip/tests/test_wheel_smoke.py -q
git add packaging/pip/ci/install_cuda_windows.ps1 .github/workflows/wheels.yml packaging/pip/tests
git commit -m "Build and rehearse Windows x86_64 cuda12 wheels"
git push fork pip-packaging
gh run watch --repo robbietuk/STIR --exit-status
```
Expected:
- 2 `build_cuda` jobs green (`cuda12 linux-x86_64`, `cuda12 windows-AMD64`), each with 5 wheels under 100 MB.
- The Windows log shows `STIR CUDA support enabled. Using CUDA version 12.9.` and `test_expected_feature[cuda] PASSED` for each Python.
- `rehearse_publish (cuda12 windows-AMD64)` is green; `publish` is skipped.
- The whole run has 5 wheel artifacts (3 `cpu`, 2 `cuda12`) and 25 wheels.

- [ ] **Step 5: Check the excluded runtime really is excluded**

Run: `gh run download --repo robbietuk/STIR -n wheels-cuda12-windows-AMD64 -D /tmp/ww && unzip -l /tmp/ww/stir_cuda12-*cp312*.whl | grep -Ei "cudart|nvcuda" ; echo "exit=$?"`
Expected: `exit=1` (no matches).

---

### Task 13: Windows GPU sign-off (Robert, if he has the hardware)

**Files:**
- Modify: `packaging/pip/README.md` (sign-off table)

**Interfaces:**
- Consumes: the `wheels-cpu-windows-AMD64` and `wheels-cuda12-windows-AMD64` artifacts of a green Task 12 run;
  `gpu_check.py` (Task 10); Task 11's procedure and sign-off table.

- [ ] **Step 1: Run Task 11 Steps 2–4 on Windows** with the `wheels-cpu-windows-AMD64` and `wheels-cuda12-windows-AMD64` artifacts (PowerShell, `py -3.12 -m venv`, `<venv>\Scripts\python.exe`).
Expected: the same results as on Linux. Without suitable hardware, record the row as `not tested (no hardware)`. Don't leave it blank.

- [ ] **Step 2: Record and commit**

```bash
git add packaging/pip/README.md
git commit -m "Record Phase 3 Windows GPU sign-off results"
```

Phase 3 is complete when the Linux x86_64 `stir-cuda12` row says PASS, Task 12's CI run is green, and the Windows row is filled in (PASS or `not tested (no hardware)`).

---

## Appendix: Later, if needed

**Not part of the first version; do not execute unless Robert asks.** Condensed research for the two deferred CUDA
additions (spec §7). Each is additive to Tasks 1–13. When one is added, extend the overview's matrix and artifact
lists, Phase 4's README/docs tests (names, warning, uninstall line) and Phase 5's `build_cuda` expectations.

### B1: `stir-cuda13` (deferred)

Why deferred: CUDA 13 drops pre-Turing GPUs (no sm_50–sm_72; sm_101 renumbered sm_110, Thor) and needs driver ≥ 580,
which shared clusters often lack (spec §5.2).

- **versions.toml** (Task 1): add
  ```toml
  [cuda.cuda13]
  # CUDA 13 dropped offline compilation for sm_50..sm_72; sm_101 was renumbered sm_110 (Thor).
  toolkit = "13.4.2"
  architectures = "75-real;80-real;86-real;89-real;90-real;100-real;110-real;120-real;120-virtual"
  runtime_requirement = "nvidia-cuda-runtime>=13.4,<14"
  ```
  Check the pin: `curl -fsI .../cuda/13.4.2/network_installers/cuda_13.4.2_windows_network.exe` must give 200;
  otherwise use the newest 13.4.x that does (open question for Robert).
- **pyproject.toml** (Task 2): a second override, identical to `cuda12`'s except `if.env.STIR_WHEEL_VARIANT =
  "cuda13"` and the architectures above. Put it last so Task 3's `stripped` fixture can target it.
- **Tests:** add `"cuda13"` back to the Task 1–3 parametrizations (`test_cuda_version_flag` expects `13.4.2`;
  runtime dependency `nvidia-cuda-runtime>=13.4,<14`); delete both `test_deferred_cuda13_exits_1` tests;
  `build_deps --cuda-version --variant cpu` message becomes `needs cuda12 or cuda13`.
- **`stir/_cuda.py`** (Task 4): `VARIANT_DISTS["cuda13"] = "stir-cuda13"`;
  `RUNTIME_RELPATHS[("cuda13","linux")] = "cu13/lib/libcudart.so.13"`,
  `[("cuda13","win32")] = "cu13/bin/x86_64/cudart64_13.dll"`; `RUNTIME_PIP_PACKAGE["cuda13"] = "nvidia-cuda-runtime"`
  (`nvidia-cuda-runtime-cu13` is a deprecated stub); `MIN_DRIVER_API["cuda13"] = 13000`;
  `MIN_COMPUTE["cuda13"] = (7, 5)`. `installed_variants` order `cpu, cuda12, cuda13`; uninstall hint
  `pip uninstall -y stir stir-cuda12 stir-cuda13`. Tests to add: `classify("cuda13", driver 12020)` →
  `driver-too-old` naming `12.2`, `13.0` and suggesting `stir-cuda12`; `classify("cuda13", cc 7.0)` →
  `unsupported-gpu` naming `7.0`, `7.5`, `stir-cuda12`.
- **CI scripts:** `install_cuda_linux.sh cuda13` (dnf packages `-13-4`); Windows installer: for major ≥ 13 also add
  `crt_$mm nvvm_$mm` (CUDA 13 split these out of nvcc). VS 2022 on `windows-2022` supports 13.4.
- **Workflow:** `build_cuda` rows `cuda13` for linux/x86_64 and windows/AMD64 (same as `cuda12` rows); repair
  excludes become `${{ matrix.variant == 'cuda12' && 'libcudart.so.12' || 'libcudart.so.13' }}` and
  `${{ matrix.variant == 'cuda12' && 'cudart64_12.dll' || 'cudart64_13.dll' }};nvcuda.dll`; a `cuda13` linux/x86_64
  rehearsal row. Artifacts `wheels-cuda13-linux-x86_64`, `wheels-cuda13-windows-AMD64`; +10 wheels.
- **Sign-off:** Task 11 Step 3 for `stir-cuda13` (driver ≥ 580, compute capability ≥ 7.5) in `~/v-cu13`.

### B2: Linux aarch64 `stir-cuda12` (sbsa) (deferred)

Needs Phase 2 appendix A1 (CPU Linux aarch64) first.

- `install_cuda_linux.sh`: map `uname -m` `aarch64` → repo arch `sbsa`
  (`.../repos/rhel8/sbsa/cuda-rhel8.repo`; RHEL 8 sbsa is supported through CUDA 13.4).
- Runtime layout check (Task 4 Step 1): also download for `manylinux2014_aarch64`; expected path is the same
  `nvidia/cuda_runtime/lib/libcudart.so.12`.
- Workflow: `build_cuda` row `{variant: cuda12, os: linux, arch: aarch64, runner: ubuntu-24.04-arm, wheel_tag:
  manylinux_2_28_aarch64, expect: <Linux aarch64 CPU expect>,cuda, only: ""}` and a matching rehearsal row.
  Artifact `wheels-cuda12-linux-aarch64`; +5 wheels.
- Sign-off hardware: Grace/GH200 or DGX Spark. Jetson Orin (sm_87) stays unbuilt: sbsa wheels target server Arm and
  DGX Spark; Orin uses L4T/JetPack.

---

## Undecided items (Robert's call; the plan uses the stated default)

1. **Pascal (sm_60/61) in `stir-cuda12`.** The spec says sm_70+. CUDA 12.9 can still build `60-real;61-real` for a few MB more, and Pascal cards (GTX 10xx, P100) are still common in labs. Default: not included. Users with Pascal get the `unsupported-gpu` warning.
2. **Windows runner image.** Pinned to `windows-2022`. When GitHub retires it, the fallback is `windows-latest` plus `-allow-unsupported-compiler` for CUDA 12.9.
3. **Deps cache per variant.** Each CUDA variant rebuilds the identical hdf5/date/petsird/itk on a cache miss (simple, but slower cold builds). Reusing the `cpu` prefix and building only `parallelproj` per variant is a later optimisation if CI time hurts.
4. **GPU sign-off hardware** for Windows (Task 13): depends on what Robert can access.

(Jetson Orin and the exact CUDA 13 pin are deferred questions; see the appendix.)

## Contract concerns

Resolved in the overview's "Cross-plan review (2026-11-12)"; the overview wins where these notes differ.

1. **New files not in the contract's file table:** `src/swig/python/stir/_cuda.py`, `packaging/pip/tests/test_cuda_loader.py`, `packaging/pip/tests/test_build_deps.py` (if Phase 2 didn't create it), `packaging/pip/check_wheel_size.py`, `packaging/pip/tests/test_check_wheel_size.py`, `packaging/pip/ci/install_cuda_linux.sh`, `packaging/pip/ci/install_cuda_windows.ps1`, and `packaging/pip/tests/gpu_check.py` (named in the Phase 3 brief). The overview's file table should list them.
2. **`__init__.py` is edited again in Phase 3** (two lines calling `_cuda.prepare_runtime()`). The contract says the only edit is Phase 1's. It is the same file and still only Python glue, but the overview should say "Phase 1 (extended 3)".
3. **Where the CUDA cmake defines live.** The contract says `prepare_build.py` makes `cuda12`/`cuda13` "also set CUDA cmake defines". In this plan the defines live in `pyproject.toml` overrides selected by `STIR_WHEEL_VARIANT` (as the contract's env-var table says). `prepare_build.py` only checks that the matching override exists. Its exit code 1 for a missing override is new; the contract defines 0 and 2 only. The consequence is that a build needs both `--variant cudaXX` and `STIR_WHEEL_VARIANT=cudaXX`. The smoke test catches a mismatch.
4. **`build_deps.py` gains a `--cuda-version` flag**, which is not in the contract CLI. The install scripts use it so the toolkit version has one source (`versions.toml`).
5. **libparallelproj is shared-only.** Spec §5.4 says "libparallelproj static", but upstream v2.0.7 hard-codes `add_library(parallelproj SHARED ...)`. The wheel therefore bundles `libparallelproj` through auditwheel/delvewheel. Phase 2 must already do this for the CPU wheel. If Phase 2's plan assumes a static libparallelproj, it needs correcting.
6. **New CUDA keys in `versions.toml`**: `[cuda.<variant>]` with `toolkit`, `architectures` and `runtime_requirement`. `prepare_build.py` now reads `versions.toml`. In Phase 1 the two were independent.
7. **The rehearsal depends on pypiserver's default fallback to PyPI** for `nvidia-cuda-runtime*`. Phase 1/2 must not start pypiserver with `--disable-fallback`. If they do, Task 9 needs `--extra-index-url https://pypi.org/simple/` for the install step only.
8. **Artifact `<os>-<arch>` tokens.** This plan uses `linux-x86_64` and `windows-AMD64` (overview). If Phase 2's `build_cpu` uses other tokens (e.g. `windows-amd64`), Task 8 should use Phase 2's spelling.

## References

- STIR rel_6.5.0 sources read for this plan: `CMakeLists.txt` lines 100–280 (DISABLE_STIR_CUDA, CMAKE_CUDA_ARCHITECTURES "all" default, parallelproj CONFIG and PARALLELPROJ_CUDA), `src/swig/CMakeLists.txt:38-39,144-147`, `src/recon_buildblock/CMakeLists.txt:141-211`, `src/CMakeLists.txt:281-285`, `src/swig/stir_priors.i:63-200`, `src/swig/stir_projectors.i:111-135`. The `.cu` sources are `src/buildblock/CUDA/cuda_utilities.cu`, `src/recon_buildblock/CUDA/CudaRelativeDifferencePrior.cu` and `src/recon_buildblock/CUDA/CudaGibbsPenaltiesInstantiations.cu`.
- libparallelproj v2.0.7 `CMakeLists.txt`, `cmake/parallelprojConfig.cmake.in`, `src/parallelproj_info.cpp` (cloned from https://github.com/KUL-recon-lab/libparallelproj, tag v2.0.7). Changelog: https://libparallelproj.readthedocs.io/en/v2.0.7/_sources/changelog.rst.txt. Install docs: https://libparallelproj.readthedocs.io/en/latest/_sources/installation.rst.txt
- (Appendix B1/B2) NVIDIA runtime pip packages: https://pypi.org/project/nvidia-cuda-runtime (13.x; win_amd64 / manylinux x86_64 and aarch64), https://pypi.org/project/nvidia-cuda-runtime-cu13/ (deprecated stub pointing to `nvidia-cuda-runtime`), https://www.pypi.org/project/cuda-toolkit/13.2.0 (metapackage). Wheel library layout: https://nvidia.github.io/cuda-python/coverage/z_b173e2ae1fca2bc7_descriptor_catalog_py.html
- (Appendix B1) CUDA 13.0 release notes (dropped sm_50–72, SM101 renamed SM110, driver ≥ 580 for 13.x and ≥ 525 for 12.x): https://docs.nvidia.com/cuda/archive/13.0.0/pdf/CUDA_Toolkit_Release_Notes.pdf. Also https://developer.nvidia.com/blog/navigating-gpu-architecture-support-a-guide-for-nvidia-cuda-developers
- CUDA Linux install guide (RHEL 8 network repo, x86_64; sbsa for appendix B2): https://docs.nvidia.com/cuda/archive/13.4.1/cuda-installation-guide-linux/index.html
- CUDA Windows install guide (silent `-s` sub-packages, VS support, driver not bundled): https://docs.nvidia.com/cuda/archive/13.4.2/cuda-installation-guide-microsoft-windows/index.html
- Jimver/cuda-toolkit action (considered; NVIDIA's network installer used directly instead, so the deferred 13.x path needs no other tool): https://github.com/jimver/cuda-toolkit
- CuPy package-per-CUDA-major model, `[ctk]` extra, conflict warning: https://docs.cupy.dev/en/stable/install.html
- delvewheel `--exclude`, `--add-path`, `__init__.py` patching: https://pypi.org/project/delvewheel/
- PyPI storage limits (100 MB/file, 10 GB/project by default; increase process): https://docs.pypi.org/project-management/storage-limits
