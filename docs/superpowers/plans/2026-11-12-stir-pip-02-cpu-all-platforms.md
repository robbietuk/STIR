# STIR pip Phase 2: full-feature CPU wheels, implementation plan

Platforms: Linux x86_64, macOS arm64, then Windows x86_64.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce `stir` CPU wheels for the three first-version platforms, Linux x86_64, macOS arm64 and Windows
x86_64 (Python 3.11–3.15; 15 wheels).
They include HDF5, PETSIRD, nlohmann_json, ITK image IO and libparallelproj (CPU). Every feature is
proven by a runtime check. Any feature left out on a platform is documented.

**Architecture:** `packaging/pip/deps/build_deps.py` builds every native dependency from pinned sources into a
per-platform "deps prefix" (`.deps/cpu`), static where the upstream build allows it. The prefix is cached in CI
under `build_deps.py --cache-key`. `pyproject.toml` passes `STIR_DEPS_PREFIX` to CMake as `CMAKE_PREFIX_PATH`
and turns the features on. Phase 1's `wheel_hook.cmake` gains the prefix-specific settings and a
configure-time feature report. That report (`stir/_data/build_features.json`) makes the configure fail when a
feature named in `STIR_WHEEL_EXPECT` was not found. The smoke test then proves each feature at runtime. The
work starts with one platform (Linux x86_64) and widens one platform per task: macOS arm64 (Task 8), then
Windows x86_64 (Task 9). Linux aarch64 and macOS x86_64 are deferred to the appendix at the end of this plan.

**Tech Stack:** Python 3.11+ (`tomllib`, `argparse`, `hashlib`, `urllib`), CMake ≥ 3.31 + Ninja (pip),
scikit-build-core, cibuildwheel v4.3.5, manylinux_2_28 images pinned by digest, auditwheel / delocate /
delvewheel, GitHub Actions (`actions/cache/restore|save`), yardl 0.6.7 (PETSIRD code generator), pytest.

**Spec:** `docs/superpowers/specs/2026-11-12-stir-pip-packaging-design.md`. **Contract:**
`docs/superpowers/plans/2026-11-12-stir-pip-00-overview.md` (its names win). **Builds on:**
`docs/superpowers/plans/2026-11-12-stir-pip-01-skeleton.md` (Phase 1 names reused below: `wheel_hook.cmake`,
`test_ci_config.py`, `test_cmake_hooks.py`, `CHECKS`, `run_stir`, `expected_features`, matrix keys `os/arch/runner`).

## Global Constraints

- Wheels for Linux x86_64, macOS arm64 and Windows x86_64, in that order. Python 3.11 through 3.15 (3 × 5 = 15
  wheels). Linux uses `manylinux_2_28`.
- Linux aarch64 and macOS x86_64 are **not part of the first version** (spec §7 "Later, if needed"). Their tasks
  sit in "Appendix: Later, if needed" at the end; do not execute them unless Robert asks.
- Feature parity with conda-forge wherever the platform allows: core STIR, OpenMP, HDF5 (GE data), PETSIRD,
  nlohmann_json, ITK image IO, parallelproj (CPU everywhere).
- **No changes to STIR's C++ code**, and no edits to any protected file (the overview's list; `packaging/` is
  exempt). Third-party sources may be patched inside the deps build tree only.
- Nothing goes to UCL/STIR, and nothing is published to PyPI or TestPyPI. Pushes go to the `fork` remote
  (`robbietuk/STIR`), branch `pip-packaging`, and need Robert's go-ahead (Phase 1 Task 9 rule).
- Every job keeps `if: github.repository == 'robbietuk/STIR'`.
- Anti-goal: "A package that installs cleanly but quietly can't read data the conda build can, with no clear
  message. Every feature left out on a platform must be documented."
- Anti-goal: "A package that only works with environment variables set, or that breaks when the venv is moved."
- Pins: PETSIRD `0.12.2`, libparallelproj `2.x`, ITK `≥ 5.4` (conda-forge uses 5.4), HDF5 at the same
  major/minor as conda-forge's STIR build (it builds 1.14.6 and 2.x; this plan takes **1.14.6**).
- No headers, static libraries, CMake files or executables in the wheel (Phase 1's `wheel.exclude` stays).
- Wheel files must be < 100 MB (PyPI default per-file limit; Phase 1's size check stays).
- Markdown lines ≤ 120 characters (STIR's pre-commit pymarkdown MD013).

## Review Focus

1. **macOS: STIR's bundled `libomp` loaded alongside another wheel's `libomp` (scikit-learn, PyTorch).** LLVM's
   runtime aborts with `OMP: Error #15` when a second copy initialises. Expected: both work in one process.
   Test: `test_sklearn_openmp_then_stir_parallelproj` (Task 7 creates it; Task 8 runs it on macOS).
2. **STIR imported in the same process as `h5py` or `itk`, which ship their own HDF5/ITK.** Static HDF5/ITK symbols
   exported from `_stir` could interpose on Linux. Expected: both libraries work and agree on the data. Tests:
   `test_h5py_then_stir_hdf5` and `test_itk_then_stir_itk_roundtrip` (Task 7). The fix is in Task 5
   (`--exclude-libs,ALL`).
3. **Data in folders with spaces and non-ASCII names** (`C:\Users\Zoë Smith\scans`). Expected: ITK/HDF5/PETSIRD
   files there are read. Test: every file-based check in Task 6 writes under `dir with spaces é/`.
4. **A bundled library built for a newer OS than the wheel tag claims** (macOS deployment target, glibc).
   Expected: tags stay `macosx_11_0_*`, `manylinux_2_28_*` and `win_amd64`, and the repair tools neither bump
   nor fail. Test: the `wheel_tag` check in `build_cpu` (Task 7, extended per platform).
5. **Building from the sdist without a deps prefix** (an unsupported platform, or a user's `pip install` from
   source). Expected: the build succeeds with the optional features off and `build_features.json` reports them
   honestly. Test: Task 5 Step 7 (local) and the `sdist` job's no-prefix build check (Task 7).

---

## Findings that shape this plan (from recon, 2026-11-12)

- **libparallelproj 2.0.7 hard-codes `add_library(parallelproj SHARED ...)`**, so it cannot be built static
  without a patch. It is built shared, and auditwheel/delocate/delvewheel bundle it. The wheel finds it through
  `CMAKE_INSTALL_RPATH` (Unix) or `delvewheel --add-path` (Windows). It requires CMake ≥ 3.31. Repo:
  `KUL-recon-lab/libparallelproj`. `gschramm/parallelproj` is the Python package.
- **PETSIRD's C++ sources must be generated** with `yardl generate` (`model/` → `cpp/generated/`). The generated
  CMake needs `date`, `xtensor` (+`xtl`), `HDF5 COMPONENTS CXX` and `nlohmann_json`, and its helpers need
  `xtensor-blas`. STIR's `PETSIRDInfo.cxx` includes `petsird_helpers/geometry.h`, which calls `xt::linalg::dot`.
  That needs an external BLAS unless `XTENSOR_USE_FLENS_BLAS` is defined, so both the PETSIRD build and the STIR
  build get that define. xtensor 0.26+ requires C++20, and STIR builds as C++17, so xtensor is pinned to 0.25.0.
- **HDF5 static via CMake config:** STIR calls `find_package(HDF5 COMPONENTS CXX)` (FindHDF5 module mode → config
  mode). With only static libs installed it must have `HDF5_USE_STATIC_LIBRARIES=ON` to select
  `hdf5::hdf5_cpp-static`. FindHDF5 then creates the `hdf5::hdf5_cpp` target STIR links. HDF5's external zlib is
  only exported with `HDF5_PACKAGE_EXTLIBS=ON`.
- **ITK headers used by STIR** (`src/IO/ITKImageInputFileFormat.cxx`, `ITKOutputFileFormat.cxx`): `itkImage.h`,
  `itkImageRegionIterator.h`, `itkImageFileReader.h`, `itkImageFileWriter.h`, `itkImageSeriesReader.h`,
  `itkOrientImageFilter.h`, `itkGDCMImageIO.h` and `itkGDCMSeriesFileNames.h`. STIR's multi-component read needs
  `NiftiImageIO`. ITK's output default extension is `.nhdr`, and STIR's docs name `.mhd`. Note that
  `ITKGroup_Core` defaults to ON and must be switched off.
- **conda-forge's STIR 6.5.0 feedstock** leaves HDF5 out on Windows and on osx-arm64, and ITK out on osx-arm64
  (its build.sh cites UCL/STIR#1165, which could not be fetched here). It leaves libpetsird out on win,
  linux-aarch64 and osx-x86_64 (both deferred here), but only because libpetsird isn't packaged there. We try
  every feature everywhere and let the checks decide (Known-gap procedure below).
- **macOS has no OpenMP runtime.** LLVM `libomp` 21.1.8 is built from source with deployment target 11.0. A
  Homebrew `libomp` targets the runner's macOS and would make delocate bump or reject the wheel tag.
- Windows: `delvewheel` vendors `vcomp140.dll` (its VC-redist regex is not on the ignore list). cibuildwheel 4.x
  already uses delvewheel by default. It runs repair commands through `cmd` (`shell=True`), so use `%VAR%`.
- (Deferred platform, appendix A2.) `macos-15-intel` is GitHub's last x86_64 macOS image (until it retires in
  fall 2027), so macOS x86_64 would build natively.
- GitHub tag tarballs are not fetchable from every network and their checksums are not guaranteed. Release assets
  are pinned by sha256, and tag-only projects by git commit.

## File Structure

| Path | Status | Responsibility |
|---|---|---|
| `packaging/pip/deps/versions.toml` | Create | every dependency pin, toolchain pins (macOS target, manylinux digests) |
| `packaging/pip/deps/itk_modules.txt` | Create | ITK modules to enable, one per line, `#` comments |
| `packaging/pip/deps/requirements.txt` | Create | build tools for `build_deps.py` (`cmake`, `ninja`) |
| `packaging/pip/deps/build_deps.py` | Create | CLI: fetch, verify, build, install, stamp, probe; `--cache-key` |
| `packaging/pip/deps/build_in_manylinux.sh` | Create | runs `build_deps.py` in the pinned manylinux image |
| `packaging/pip/deps/probe/` (`CMakeLists.txt`, `probe.cxx`) | Create | finds and links each dep as STIR does |
| `packaging/pip/deps/patches/` | Create only if a fallback needs it | patches applied to third-party sources |
| `packaging/pip/cmake/wheel_hook.cmake` | Modify (Phase 1) | prefix settings, RPATH, macOS OpenMP, feature guard |
| `pyproject.toml` | Modify | `CMAKE_PREFIX_PATH` from env, DISABLE_* off, cibuildwheel per-platform settings |
| `packaging/pip/tests/test_build_deps.py` | Create | unit tests: CLI, selection, cache key, stamps, pins, cmake args |
| `packaging/pip/tests/_feature_probes.py` | Create | pure helpers: `KNOWN_FEATURES`, probe classification, fixtures |
| `packaging/pip/tests/test_feature_probes.py` | Create | unit tests for `_feature_probes.py` (no compiled STIR) |
| `packaging/pip/tests/data/ge_signature.h5` | Create (generated) | tiny HDF5 file with STIR's GE signature |
| `packaging/pip/tests/test_wheel_smoke.py` | Modify (Phase 1) | new `CHECKS`; build-features test |
| `packaging/pip/tests/test_coexistence.py` | Create | h5py / itk / scikit-learn in one process (CI only) |
| `packaging/pip/tests/test_ci_config.py`, `test_cmake_hooks.py` | Modify (Phase 1) | new config and hook assertions |
| `.github/workflows/wheels.yml` | Modify (Phase 1) | `build_cpu` ×3 with deps cache; `rehearse_publish` ×3 |
| `packaging/pip/README.md` | Modify (Phase 1) | deps prefix how-to, per-platform feature status, known gaps |

## Known-gap procedure (used by the platform tasks' fallback steps)

Use it when a dependency cannot be built on a platform, or its smoke check fails there, after the task's listed
fallbacks. Never drop a feature silently:

1. In `.github/workflows/wheels.yml`, set that platform's `only:` (both jobs) to the deps that still build. Remove
   the feature from that platform's `expect:` in `build_cpu` **and** `rehearse_publish`. HDF5 out also means
   PETSIRD out (PETSIRD's generated code needs HDF5).
2. In `pyproject.toml`, add an override so CMake doesn't half-find the dependency:

   ```toml
   [[tool.scikit-build.overrides]]
   if.platform-system = "darwin"      # sys.platform value: "linux" | "darwin" | "win32"
   if.platform-machine = "arm64"      # platform.machine(): "x86_64" | "aarch64" | "arm64" | "AMD64"
   cmake.define.DISABLE_ITK = "ON"
   ```

3. In `packaging/pip/README.md`, mark the cell ✗ in "Feature status by platform", with a footnote: what fails
   (error excerpt), the upstream issue if any, and "use `conda install -c conda-forge stir`" if conda has it.
4. Commit: `git commit -m "Document known gap: <feature> on <platform>"`.

`test_build_features_match_expect` (Task 6) fails if steps 1 and 2 disagree. The configure guard (Task 5) fails if
`expect` names a feature the build did not find.

---

### Task 1: Dependency manifest and `build_deps.py` CLI core

**Files:**

- Create: `packaging/pip/deps/versions.toml`, `packaging/pip/deps/itk_modules.txt`,
  `packaging/pip/deps/requirements.txt`, `packaging/pip/deps/build_deps.py`
- Test: `packaging/pip/tests/test_build_deps.py`

**Interfaces:**

- Consumes: nothing from this phase.
- Produces (module `build_deps`, importable with `importlib.util.spec_from_file_location`; Phase 3 does this):
  - `DEPS_DIR: Path` (the script's folder), `DEP_ORDER: tuple[str, ...] = ("openmp", "boost", "nlohmann_json",
    "xtensor", "date", "hdf5", "petsird", "itk", "parallelproj")`
  - `PLATFORM_ONLY: dict[str, frozenset[str]] = {"openmp": frozenset({"darwin"})}`
  - `REQUIRES: dict[str, tuple[str, ...]] = {"petsird": ("date", "xtensor", "nlohmann_json", "hdf5"),
    "parallelproj": ("openmp",)}`. A prerequisite that is not built on the platform is ignored.
  - `class UsageError(Exception)`
  - `parse_args(argv: Sequence[str]) -> argparse.Namespace`. Flags: `--prefix DIR`, `--variant {cpu,cuda12,cuda13}`
    (required; `cuda13` is the overview's reserved, deferred value), `--only NAME[,NAME...]`, `--jobs N` (default
    `os.cpu_count()`), `--cache-key`. `--prefix` is
    required unless `--cache-key` is given. Bad input → `SystemExit(2)`.
  - `select_deps(only: str | None, platform: str) -> list[str]`: `platform` is a `sys.platform` value. Returns the
    deps in `DEP_ORDER` order, drops the ones that are not built on `platform`, and raises `UsageError` for
    unknown names (the message lists the valid names).
  - `cache_key(variant: str, deps_dir: Path = DEPS_DIR) -> str`: 16 lowercase hex chars, the start of a sha256
    over `"variant=<v>\n"` plus, for each key file sorted by relative POSIX path, the path and its bytes with
    CRLF→LF. Key files: every file under `deps_dir` except `__pycache__/` and `*.pyc`. That covers
    `versions.toml`, `build_deps.py`, `itk_modules.txt`, `requirements.txt`, `build_in_manylinux.sh`, `probe/`
    and `patches/`.
  - `load_versions(path: Path = DEPS_DIR / "versions.toml") -> dict[str, Any]`
  - `read_stamp(prefix: Path, name: str) -> str | None` and `write_stamp(prefix: Path, name: str, key: str) ->
    None`. The stamp file is `<prefix>/.stamps/<name>` and holds the cache key. This is "the marker that shows a
    prefix is complete" that Phase 3 refers to.
  - `plan_build(prefix: Path, deps: list[str], key: str, platform: str) -> list[tuple[str, str]]`: returns
    `(name, "build" | "skip")`. A dep is skipped when its stamp equals `key`. It raises `UsageError` when a
    `REQUIRES` prerequisite is neither in `deps` nor stamped with `key`.
  - `main(argv: Sequence[str] | None = None) -> int`: with `--cache-key`, prints the key and returns 0. With a
    `cuda*` variant it returns 2 with `build_deps: variant 'cuda12' is implemented in Phase 3` on stderr
    (`--cache-key` still works for every variant). `UsageError` → 2. A failed build step → 1.

- [ ] **Step 1: Write `versions.toml`, `itk_modules.txt` and `requirements.txt` (full content)**

`packaging/pip/deps/versions.toml`:

<!-- pyml disable md013-->
```toml
# Native dependency pins for the STIR pip wheels. Single source of truth (contract).
# Every byte of this directory feeds `build_deps.py --cache-key`: editing it rebuilds the CI deps cache.
# Source tables have either url+sha256 (release assets) or git+commit (tag commit; tag tarballs aren't stable).

[toolchain]
# Also set in pyproject.toml [tool.cibuildwheel.macos] environment; test_ci_config.py checks they match.
macos_deployment_target = "11.0"
# Same digests as cibuildwheel v4.3.5's pinned manylinux_2_28 images (tag 2026.11.01-2). Deps and STIR are built
# in the same image, so static libraries match the toolchain that links them.
manylinux_x86_64_image = "quay.io/pypa/manylinux_2_28_x86_64@sha256:7e41b1c7fd64dfc69703a1124b43c404382973ee06ec5d764b85c34d2221fded"
# Deferred platform (Linux aarch64, appendix A1): pinned now so adding it later is CI-only.
manylinux_aarch64_image = "quay.io/pypa/manylinux_2_28_aarch64@sha256:54b271d9562a3686298880df05367909e949ed317e7b1b79b59c696d75f78676"

[deps.boost]  # headers only: boost-1.90.0/boost/ is copied to <prefix>/include/boost
version = "1.90.0"
url = "https://github.com/boostorg/boost/releases/download/boost-1.90.0/boost-1.90.0-b2-nodocs.tar.gz"
sha256 = "e848446c6fec62d8a96b44ed7352238b3de040b8b9facd4d6963b32f541e00f5"

[deps.nlohmann_json]
version = "3.12.0"
url = "https://github.com/nlohmann/json/releases/download/v3.12.0/json.tar.xz"
sha256 = "42f6e95cad6ec532fd372391373363b62a14af6d771056dbfc86160e6dfff7aa"

[deps.xtensor.xtl]
version = "0.7.7"
git = "https://github.com/xtensor-stack/xtl"
commit = "a7c1c5444dfc57f76620391af4c94785ff82c8d6"

[deps.xtensor.xtensor]
version = "0.25.0"  # 0.26+ requires C++20; STIR builds as C++17
git = "https://github.com/xtensor-stack/xtensor"
commit = "3634f2ded19e0cf38208c8b86cea9e1d7c8e397d"

[deps.xtensor.xtensor_blas]
version = "0.21.0"  # last release compatible with xtensor 0.25
git = "https://github.com/xtensor-stack/xtensor-blas"
commit = "5dcbab5f41636a678a9ec715a058fbe6501aba77"

[deps.date]
version = "3.0.4"
git = "https://github.com/HowardHinnant/date"
commit = "f94b8f36c6180be0021876c4a397a054fe50c6f2"

[deps.hdf5]
version = "1.14.6"
url = "https://github.com/HDFGroup/hdf5/releases/download/hdf5_1.14.6/hdf5-1.14.6.tar.gz"
sha256 = "e4defbac30f50d64e1556374aa49e574417c9e72c6b1de7a4ff88c4b1bea6e9b"

[deps.hdf5.zlib]  # handed to HDF5 as local content (ZLIB_USE_LOCALCONTENT), built static and exported by HDF5
version = "1.3.1"
url = "https://github.com/madler/zlib/releases/download/v1.3.1/zlib-1.3.1.tar.gz"
sha256 = "9a93b2b7dfdac77ceba5a558a580e74667dd6fede4585b91eefb60f03b72df23"

[deps.petsird]
version = "0.12.2"
git = "https://github.com/ETSInitiative/PETSIRD"
commit = "4b4931306df60786b4e470179db46ebabaaa8a38"

[deps.petsird.yardl]  # code generator binary, chosen by platform_key()
version = "0.6.7"
linux-x86_64 = { url = "https://github.com/microsoft/yardl/releases/download/v0.6.7/yardl_0.6.7_linux_x86_64.tar.gz", sha256 = "4bfb815fce1302595f5d5d87e3c88e020422c2be331fdf10071040370ccd3012" }
# linux-aarch64 and darwin-x86_64: deferred platforms (appendix A1/A2), pinned now so adding them is CI-only.
linux-aarch64 = { url = "https://github.com/microsoft/yardl/releases/download/v0.6.7/yardl_0.6.7_linux_arm64.tar.gz", sha256 = "55fdfc29fd85792ad4d5826e81a99b49719226c2c5b08b1b905810c49f59deec" }
darwin-x86_64 = { url = "https://github.com/microsoft/yardl/releases/download/v0.6.7/yardl_0.6.7_darwin_x86_64.tar.gz", sha256 = "7b82cc90a4f6294995045fe006c9de1a112501c0d5bcc485a195ec0b9e86dbcb" }
darwin-arm64 = { url = "https://github.com/microsoft/yardl/releases/download/v0.6.7/yardl_0.6.7_darwin_arm64.tar.gz", sha256 = "213d96d2c0214cf51006cbe2d6bf294ab1f545fad34bb3be93bf1119c5d82e4b" }
win32-x86_64 = { url = "https://github.com/microsoft/yardl/releases/download/v0.6.7/yardl_0.6.7_windows_x86_64.zip", sha256 = "94f84e2daf08d13abaae66c28d8e4efeaa3573dd3e5db8ed94baeac7e4974e10" }

[deps.itk]
version = "5.4.5"  # newest 5.4.x with a release asset (v5.4.6-5.4.8 tags have no InsightToolkit tarball)
url = "https://github.com/InsightSoftwareConsortium/ITK/releases/download/v5.4.5/InsightToolkit-5.4.5.tar.gz"
sha256 = "ecab9119664e2571b90740ba9ab3ca11cb46942dbd7bb87c0de5bb15309a36c9"
modules_file = "itk_modules.txt"

[deps.parallelproj]  # libparallelproj (C++). SHARED only upstream; bundled by the wheel repair tools.
version = "2.0.7"
git = "https://github.com/KUL-recon-lab/libparallelproj"
commit = "93f0b1db3163793a59bb982e47dd051eac52bc30"

[deps.openmp]  # macOS only: LLVM libomp runtime, standalone build
version = "21.1.8"
url = "https://github.com/llvm/llvm-project/releases/download/llvmorg-21.1.8/openmp-21.1.8.src.tar.xz"
sha256 = "856b023748b41ac7b2c83fd8e9f765ff48a4df2fe6777d2811ef7c7ed8f2f977"

[deps.openmp.llvm_cmake]  # must sit next to openmp/ as cmake/ (LLVM_COMMON_CMAKE_UTILS = ../cmake)
url = "https://github.com/llvm/llvm-project/releases/download/llvmorg-21.1.8/cmake-21.1.8.src.tar.xz"
sha256 = "85735f20fd8c81ecb0a09abb0c267018475420e93b65050cc5b7634eab744de9"
```
<!-- pyml enable md013-->

`packaging/pip/deps/itk_modules.txt`:

```text
# ITK modules for the STIR wheels (ITK_BUILD_DEFAULT_MODULES=OFF, ITKGroup_Core=OFF; ITK adds dependencies itself).
# Derived from the itk*.h includes in src/IO/ITKImageInputFileFormat.cxx and src/IO/ITKOutputFileFormat.cxx (6.5.0).
ITKCommon        # itkImage.h, itkImageRegionIterator.h, itk::VectorImage, itk::MetaDataObject
ITKIOImageBase   # itkImageFileReader.h, itkImageFileWriter.h, itkImageSeriesReader.h
ITKImageGrid     # itkOrientImageFilter.h
ITKIOGDCM        # itkGDCMImageIO.h, itkGDCMSeriesFileNames.h (DICOM series)
ITKIONIFTI       # NIfTI factory; STIR's multi-component (displacement field) read requires NiftiImageIO
ITKIONRRD        # NRRD factory; ITKOutputFileFormat's default extension is .nhdr
ITKIOMeta        # MetaImage factory (.mhd/.mha)
```

`packaging/pip/deps/requirements.txt`:

```text
cmake>=3.31,<5
ninja>=1.11
```

- [ ] **Step 2: Write the failing tests** in `packaging/pip/tests/test_build_deps.py`

Use the module loader Phase 3 uses: `load_build_deps()` via `spec_from_file_location("build_deps", SCRIPT)`, and
`run(*args)` = `subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)`.

```python
def test_cache_key_cli_prints_16_hex():
    r = run("--cache-key", "--variant", "cpu")
    assert r.returncode == 0 and re.fullmatch(r"[0-9a-f]{16}\n", r.stdout)

def test_cache_key_is_stable_and_ignores_prefix_and_jobs():
    a = run("--cache-key", "--variant", "cpu").stdout
    assert a == run("--cache-key", "--variant", "cpu", "--prefix", "/x", "--jobs", "3").stdout

def test_cache_key_differs_per_variant():
    bd = load_build_deps()
    assert len({bd.cache_key(v) for v in ("cpu", "cuda12", "cuda13")}) == 3   # cuda13: reserved (deferred)

def test_cache_key_tracks_every_deps_file(tmp_path):
    bd = load_build_deps(); copy = tmp_path / "deps"; shutil.copytree(bd.DEPS_DIR, copy)
    base = bd.cache_key("cpu", copy)
    (copy / "versions.toml").write_text((copy / "versions.toml").read_text() + "\n# x\n")
    assert bd.cache_key("cpu", copy) != base

def test_cache_key_ignores_crlf_and_pycache(tmp_path):
    bd = load_build_deps(); copy = tmp_path / "deps"; shutil.copytree(bd.DEPS_DIR, copy)
    base = bd.cache_key("cpu", copy)
    p = copy / "itk_modules.txt"; p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    (copy / "__pycache__").mkdir(exist_ok=True); (copy / "__pycache__" / "x.pyc").write_bytes(b"\0")
    assert bd.cache_key("cpu", copy) == base

@pytest.mark.parametrize("args", [["--variant", "cpu"], ["--prefix", "p"], ["--prefix", "p", "--variant", "gpu"],
                                  ["--prefix", "p", "--variant", "cpu", "--jobs", "0"]])
def test_bad_arguments_exit_2(args):
    assert run(*args).returncode == 2

def test_unknown_only_name_exits_2_and_lists_names():
    r = run("--prefix", "p", "--variant", "cpu", "--only", "hdf5,vtk")
    assert r.returncode == 2 and "vtk" in r.stderr and "parallelproj" in r.stderr

def test_cuda_build_is_phase3():
    r = run("--prefix", "p", "--variant", "cuda12")
    assert r.returncode == 2 and "Phase 3" in r.stderr

def test_select_deps_orders_and_filters_by_platform():
    bd = load_build_deps()
    assert bd.select_deps("itk,hdf5", "linux") == ["hdf5", "itk"]
    assert bd.select_deps(None, "linux") == ["boost", "nlohmann_json", "xtensor", "date", "hdf5", "petsird",
                                             "itk", "parallelproj"]
    assert bd.select_deps(None, "darwin")[0] == "openmp"
    assert bd.select_deps("openmp", "win32") == []

def test_plan_build_skips_stamped_and_checks_prerequisites(tmp_path):
    bd = load_build_deps()
    with pytest.raises(bd.UsageError, match="hdf5"):
        bd.plan_build(tmp_path, ["petsird"], "k1", "linux")
    for d in ("date", "xtensor", "nlohmann_json", "hdf5"):
        bd.write_stamp(tmp_path, d, "k1")
    assert bd.plan_build(tmp_path, ["hdf5", "petsird"], "k1", "linux") == [("hdf5", "skip"), ("petsird", "build")]
    assert bd.plan_build(tmp_path, ["hdf5"], "k2", "linux") == [("hdf5", "build")]   # new key → rebuild
    assert bd.plan_build(tmp_path, ["parallelproj"], "k1", "linux") == [("parallelproj", "build")]  # no openmp off-mac

def test_every_source_is_pinned():
    def tables(t):
        yield t
        for v in t.values():
            if isinstance(v, dict): yield from tables(v)
    v = load_build_deps().load_versions()
    assert set(v["deps"]) == {"boost", "nlohmann_json", "xtensor", "date", "hdf5", "petsird", "itk",
                              "parallelproj", "openmp"}
    for t in tables(v["deps"]):
        if "url" in t: assert re.fullmatch(r"[0-9a-f]{64}", t["sha256"]) and t["url"].startswith("https://")
        if "git" in t: assert re.fullmatch(r"[0-9a-f]{40}", t["commit"])

def test_itk_module_list():
    mods = load_build_deps().read_itk_modules()
    assert len(mods) == len(set(mods)) and all(m.startswith("ITK") for m in mods)
    assert {"ITKCommon", "ITKIOImageBase", "ITKImageGrid", "ITKIOGDCM", "ITKIONIFTI", "ITKIONRRD",
            "ITKIOMeta"} <= set(mods)
```

Add `read_itk_modules(path: Path = DEPS_DIR / "itk_modules.txt") -> list[str]` to Produces: strip `#` comments,
skip blank lines.

- [ ] **Step 3: Run them to verify they fail**

Run: `python -m pytest packaging/pip/tests/test_build_deps.py -v`
Expected: FAIL. The script doesn't exist (`FileNotFoundError` from the loader, non-zero CLI exit codes).

- [ ] **Step 4: Implement the CLI core in `packaging/pip/deps/build_deps.py`**

Implement the Interfaces above. Pure standard library (`tomllib` needs Python ≥ 3.11; the shebang line is
`#!/usr/bin/env python3`). Argument errors go through `argparse`'s `parser.error` (exit 2). `UsageError` is
printed as `build_deps: <message>`. In this task `main` stops after `plan_build`: it prints one line per dep,
`hdf5 1.14.6: build` or `hdf5 1.14.6: up to date`, and builds nothing yet. Task 2 adds the build.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest packaging/pip/tests/test_build_deps.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add packaging/pip/deps packaging/pip/tests/test_build_deps.py
git commit -m "Add dependency manifest and build_deps.py CLI for the pip deps prefix"
```

---

### Task 2: Fetching sources; header-only deps, `date` and static HDF5

**Files:**

- Modify: `packaging/pip/deps/build_deps.py`
- Create: `packaging/pip/deps/build_in_manylinux.sh`, `packaging/pip/deps/probe/CMakeLists.txt`,
  `packaging/pip/deps/probe/probe.cxx`
- Test: `packaging/pip/tests/test_build_deps.py`

**Interfaces:**

- Consumes: Task 1.
- Produces:
  - `class ChecksumError(Exception)`
  - `@dataclass(frozen=True) class BuildContext: prefix: Path; work: Path; platform: str; machine: str;
    versions: dict; variant: str; jobs: int`. `work` is `Path(str(prefix) + ".work")`, deleted after a
    successful run. `machine` is normalised to `x86_64 | arm64` (Windows `AMD64` → `x86_64`; `aarch64` passes
    through unchanged for the deferred Linux aarch64 build).
  - `platform_key(platform: str, machine: str) -> str` → e.g. `"darwin-arm64"`, `"win32-x86_64"`.
  - `fetch_source(src: Mapping[str, str], dest: Path, downloads: Path) -> Path`: `url`+`sha256` → download into
    `downloads/` (reused if the hash matches), verify, extract (`tar.gz`/`tar.xz`/`zip`) into `dest`, stripping a
    single top-level folder. `git`+`commit` → `git init`, `git fetch --depth 1 <git> <commit>`,
    `git checkout FETCH_HEAD` in `dest`. Hash mismatch → `ChecksumError` naming the file and both hashes.
  - `common_cmake_args(ctx: BuildContext) -> list[str]`: `-G Ninja`, `-DCMAKE_BUILD_TYPE=Release`,
    `-DCMAKE_INSTALL_PREFIX=<prefix>`, `-DCMAKE_INSTALL_LIBDIR=lib`, `-DCMAKE_PREFIX_PATH=<prefix>`,
    `-DCMAKE_POSITION_INDEPENDENT_CODE=ON`, `-DBUILD_SHARED_LIBS=OFF`, `-DBUILD_TESTING=OFF`, plus
    `-DCMAKE_OSX_DEPLOYMENT_TARGET=<toolchain.macos_deployment_target>` when `platform == "darwin"`.
  - `hdf5_cmake_args(ctx: BuildContext, zlib_dir: Path) -> list[str]` (values in Step 1's test).
  - `cmake_build(name: str, src: Path, args: list[str], ctx: BuildContext, env: Mapping[str, str] | None = None)
    -> None`: configure into `<work>/<name>/b`, `cmake --build --parallel <jobs>`, `cmake --install`. On
    darwin, `MACOSX_DEPLOYMENT_TARGET` is put into the subprocess environment.
  - `run_probe(ctx: BuildContext, deps: list[str]) -> None`: configures `probe/` with
    `-DPROBE_DEPS=<;-list>`, builds it, runs `stir_deps_probe` and raises if it doesn't print
    `probe: <dep> ok` for each dep in the list that has a probe.
  - `main` now builds: `select_deps` → `plan_build` → per dep `fetch_source` + recipe → `write_stamp` →
    `run_probe` (for every dep stamped with the current key) → remove `work`.
- `build_in_manylinux.sh ARCH --variant V [build_deps args...]`: reads `toolchain.manylinux_<ARCH>_image` from
  `versions.toml` with the host `python3`, takes `V` from the `--variant` argument (exit 2 if missing), then:
  `docker run --rm -v "$PWD:/project" -w /project "$IMAGE" bash -euo pipefail -c '/opt/python/cp312-cp312/bin/python
  -m pip install -r packaging/pip/deps/requirements.txt && PATH=/opt/python/cp312-cp312/bin:$PATH python
  packaging/pip/deps/build_deps.py --prefix "/project/.deps/$V" "$@"' _ "$@"` (pass `V` into the container with
  `-e V`). Must run from the repo root (it checks for `pyproject.toml` and exits 2 otherwise). Phase 3 adds a CUDA
  toolkit install before `build_deps.py` for `cuda*` variants.

Source sub-folders: `<work>/<name>/s`, build `<work>/<name>/b`. These short names keep ITK under its 50-character
Windows path check.

- [ ] **Step 1: Write the failing tests** (append to `test_build_deps.py`)

```python
def make_tar(tmp_path):
    d = tmp_path / "pkg-1.0"; d.mkdir(); (d / "hello.txt").write_text("hi")
    t = tmp_path / "pkg-1.0.tar.gz"
    with tarfile.open(t, "w:gz") as tf: tf.add(d, arcname="pkg-1.0")
    return t, hashlib.sha256(t.read_bytes()).hexdigest()

def test_fetch_url_verifies_and_strips_top_folder(tmp_path):
    bd = load_build_deps(); t, sha = make_tar(tmp_path)
    out = bd.fetch_source({"url": t.as_uri(), "sha256": sha}, tmp_path / "s", tmp_path / "dl")
    assert (out / "hello.txt").read_text() == "hi"
    with pytest.raises(bd.ChecksumError, match=sha):
        bd.fetch_source({"url": t.as_uri(), "sha256": "0" * 64}, tmp_path / "s2", tmp_path / "dl2")

def test_fetch_git_commit(tmp_path):
    bd = load_build_deps(); repo = tmp_path / "r"; repo.mkdir()
    git = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True, text=True)
    git("init", "-q"); (repo / "f").write_text("v1"); git("add", "f")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "1")
    commit = git("rev-parse", "HEAD").stdout.strip()
    out = bd.fetch_source({"git": repo.as_uri(), "commit": commit}, tmp_path / "s", tmp_path / "dl")
    assert (out / "f").read_text() == "v1"

def ctx(bd, platform="linux", machine="x86_64", tmp=Path("/p")):
    return bd.BuildContext(prefix=tmp, work=Path(str(tmp) + ".work"), platform=platform, machine=machine,
                           versions=bd.load_versions(), variant="cpu", jobs=2)

def test_common_args():
    bd = load_build_deps()
    lin = bd.common_cmake_args(ctx(bd)); mac = bd.common_cmake_args(ctx(bd, "darwin", "arm64"))
    assert {"-DBUILD_SHARED_LIBS=OFF", "-DCMAKE_POSITION_INDEPENDENT_CODE=ON", "-DCMAKE_INSTALL_LIBDIR=lib",
            "-DCMAKE_BUILD_TYPE=Release"} <= set(lin)
    assert "-DCMAKE_OSX_DEPLOYMENT_TARGET=11.0" in mac and not any("OSX" in a for a in lin)

def test_hdf5_args():
    bd = load_build_deps(); a = set(bd.hdf5_cmake_args(ctx(bd), Path("/z")))
    assert {"-DBUILD_STATIC_LIBS=ON", "-DHDF5_BUILD_CPP_LIB=ON", "-DHDF5_BUILD_HL_LIB=OFF",
            "-DHDF5_BUILD_TOOLS=OFF", "-DHDF5_BUILD_EXAMPLES=OFF", "-DHDF5_BUILD_FORTRAN=OFF",
            "-DHDF5_BUILD_JAVA=OFF", "-DHDF5_ENABLE_Z_LIB_SUPPORT=ON", "-DHDF5_ENABLE_SZIP_SUPPORT=OFF",
            "-DHDF5_ALLOW_EXTERNAL_SUPPORT=TGZ", "-DZLIB_USE_LOCALCONTENT=ON", f"-DTGZPATH={Path('/z')}",
            "-DZLIB_TGZ_NAME=zlib-1.3.1.tar.gz", "-DHDF5_PACKAGE_EXTLIBS=ON"} <= a

def test_platform_key():
    bd = load_build_deps()
    assert bd.platform_key("win32", "x86_64") == "win32-x86_64" and bd.platform_key("darwin", "arm64") == "darwin-arm64"
    assert all(bd.platform_key(p, m) in bd.load_versions()["deps"]["petsird"]["yardl"]
               for p, m in [("linux", "x86_64"), ("darwin", "arm64"), ("win32", "x86_64")])
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest packaging/pip/tests/test_build_deps.py -v`
Expected: the new tests FAIL with `AttributeError` (`fetch_source`, `BuildContext`, ...).

- [ ] **Step 3: Implement fetching and the first recipes**

Recipes (each is a function `build_<name>(ctx) -> None`):

- `boost`: fetch, then copy `s/boost` to `<prefix>/include/boost` (no CMake). STIR's `find_package(Boost)` (FindBoost,
  CMP0167 OLD under STIR's `cmake_minimum_required(3.14)`) finds it through `CMAKE_PREFIX_PATH`.
- `nlohmann_json`: `cmake_build` with `-DJSON_BuildTests=OFF -DJSON_Install=ON`.
- `xtensor`: three `cmake_build`s in order `xtl`, `xtensor`, `xtensor_blas` (header-only; defaults).
- `date`: `-DBUILD_TZ_LIB=OFF -DENABLE_DATE_TESTING=OFF -DENABLE_DATE_INSTALL=ON`.
- `hdf5`: fetch `zlib` into `<work>/downloads` (verified; this folder is `TGZPATH`), then `cmake_build` with
  `hdf5_cmake_args`.

Probe (`probe/CMakeLists.txt`, CMake ≥ 3.24, `project(stir_deps_probe CXX)`, C++17): for each name in
`PROBE_DEPS` it does the `find_package` exactly as STIR's `CMakeLists.txt` does. Then `probe.cxx`, with
`#ifdef PROBE_<DEP>` blocks, prints `probe: <dep> ok`:

- `boost`: `find_package(Boost 1.36.0 REQUIRED)`; uses `boost::format`.
- `nlohmann_json`: `find_package(nlohmann_json 3.2.0 CONFIG REQUIRED)`; parses `{"a":1}`.
- `hdf5`: `set(HDF5_USE_STATIC_LIBRARIES ON)`; `find_package(HDF5 COMPONENTS CXX REQUIRED)`; links
  `HDF5::HDF5;hdf5::hdf5_cpp` (STIR's `HDF5_TARGET`); calls `H5::H5File::isHdf5("<nonexistent>")` inside
  `try { } catch (...) {}`.
- Task 3 adds `petsird`, Task 4 adds `itk` and `parallelproj`. `boost`, `date`, `xtensor` and `openmp` have no
  probe of their own (they are covered by `petsird` and `parallelproj`).

`build_in_manylinux.sh` as in Interfaces. `set -euo pipefail`; check that `docker` exists.

- [ ] **Step 4: Run the unit tests**

Run: `python -m pytest packaging/pip/tests/test_build_deps.py -v`
Expected: all PASS.

- [ ] **Step 5: Build the first deps in the pinned manylinux image**

Run (repo root, Docker on a Linux x86_64 machine):

```bash
bash packaging/pip/deps/build_in_manylinux.sh x86_64 --variant cpu --jobs 8 \
  --only boost,nlohmann_json,xtensor,date,hdf5
```

Expected: ends with `probe: boost ok`, `probe: nlohmann_json ok`, `probe: hdf5 ok`, exit 0. Then
`ls .deps/cpu/lib/libhdf5*.a .deps/cpu/include/boost/version.hpp .deps/cpu/.stamps` lists the static HDF5 C and C++
libraries, the Boost header and five stamps. A second identical run prints `... up to date` for all five in
under a minute.

Fallback: if `hdf5` fails at the STIR-style `find_package` in the probe with `hdf5::hdf5_cpp-static` not found,
print `HDF5_FIND_DEBUG=ON` output and check that `<prefix>/cmake/hdf5-targets.cmake` defines the `-static` targets.
If `zlib-static` is reported missing, `HDF5_PACKAGE_EXTLIBS=ON` did not take effect: check the configure log for
`ZLIB_USE_EXTERNAL`.

- [ ] **Step 6: Commit**

```bash
git add packaging/pip/deps packaging/pip/tests/test_build_deps.py
git commit -m "Build header-only deps, date and static HDF5 into the deps prefix"
```

---

### Task 3: PETSIRD (yardl code generation)

**Files:**

- Modify: `packaging/pip/deps/build_deps.py`, `packaging/pip/deps/probe/CMakeLists.txt`, `probe.cxx`
- Test: `packaging/pip/tests/test_build_deps.py`

**Interfaces:**

- Consumes: Task 2 (`fetch_source`, `cmake_build`, `platform_key`, `BuildContext`).
- Produces: `petsird_cmake_args(ctx: BuildContext) -> list[str]` and `petsird_env(ctx: BuildContext) -> dict[str,
  str]`. After this task, `<prefix>/lib/cmake/PETSIRD-0.11/PETSIRDConfig.cmake` exists (upstream's directory
  name). STIR's `find_package(PETSIRD CONFIG)` matches it through the `<name>*` glob.

- [ ] **Step 1: Write the failing tests**

```python
def test_petsird_args_and_env():
    bd = load_build_deps(); c = ctx(bd)
    assert "-DHDF5_USE_STATIC_LIBRARIES=ON" in bd.petsird_cmake_args(c)
    assert "-DXTENSOR_USE_FLENS_BLAS" in bd.petsird_env(c)["CXXFLAGS"].split()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest packaging/pip/tests/test_build_deps.py -k petsird -v`
Expected: FAIL with `AttributeError: ... petsird_cmake_args`.

- [ ] **Step 3: Implement `build_petsird(ctx)`**

1. Fetch PETSIRD at the pinned commit into `<work>/petsird/s`.
2. Fetch yardl for `platform_key(ctx.platform, ctx.machine)` into `<work>/petsird/yardl`. Its executable is
   `yardl` (or `yardl.exe`); `chmod +x` it.
3. Run `<yardl> generate` with `cwd=<work>/petsird/s/model`. This writes `../cpp/generated/petsird`.
4. `cmake_build("petsird", <s>/cpp, common + petsird_cmake_args(ctx), ctx, env=os.environ | petsird_env(ctx))`.
   `petsird_env` appends `-DXTENSOR_USE_FLENS_BLAS` to any existing `CXXFLAGS`. CMake adds `CXXFLAGS` to its
   initial flags on every compiler, and MSVC accepts `-D`, so the helper executables link without a BLAS
   library.

Probe `petsird` block: `find_package(PETSIRD CONFIG REQUIRED)`, link `PETSIRD::petsird`. Compile with
`XTENSOR_USE_FLENS_BLAS`, include `petsird_helpers/geometry.h` and call
`petsird_helpers::geometry::mult_transforms({})` (forces `xt::linalg::dot` to be instantiated, as STIR's
`PETSIRDInfo.cxx` does). Also construct a `petsird::binary::PETSIRDReader` on a missing file inside
`try/catch`.

- [ ] **Step 4: Run tests and build**

Run: `python -m pytest packaging/pip/tests/test_build_deps.py -v` → all PASS.
Run: `bash packaging/pip/deps/build_in_manylinux.sh x86_64 --variant cpu --jobs 8 --only petsird`
Expected: `✅ Wrote C++ to .../cpp/generated/petsird.` in the log, then `probe: petsird ok`, exit 0.

Fallback: if linking the probe or `petsird_generator` fails with undefined `cblas_sgemm`/`sgemm_`, the define did
not reach that compile. Check that `-DXTENSOR_USE_FLENS_BLAS` appears in `<work>/petsird/b/compile_commands.json`
(add `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`).

- [ ] **Step 5: Commit**

```bash
git add packaging/pip/deps packaging/pip/tests/test_build_deps.py
git commit -m "Build PETSIRD (yardl-generated) into the deps prefix"
```

---

### Task 4: ITK (static, selected modules) and libparallelproj (CPU)

**Files:**

- Modify: `packaging/pip/deps/build_deps.py`, `packaging/pip/deps/probe/CMakeLists.txt`, `probe.cxx`
- Test: `packaging/pip/tests/test_build_deps.py`

**Interfaces:**

- Consumes: Tasks 1–3; `read_itk_modules()`.
- Produces:
  - `itk_cmake_args(ctx: BuildContext) -> list[str]`
  - `parallelproj_cmake_args(variant: str, versions: Mapping[str, Any]) -> list[str]`. This exact signature is
    the one Phase 3 extends. For `cpu` it returns `-DUSE_CUDA=OFF -DBUILD_LIBRARY=ON -DINSTALL_DEVEL=ON
    -DBUILD_PYTHON=OFF -DBUILD_TESTS=OFF`. Any other variant raises `UsageError` until Phase 3.
  - `openmp_cmake_args(ctx: BuildContext) -> list[str]`: `[]` except on darwin (filled in Task 8). The
    parallelproj recipe appends it.
  - The whole prefix for Linux: `<prefix>/lib/cmake/ITK-5.4/ITKConfig.cmake`,
    `<prefix>/lib/cmake/parallelproj/parallelprojConfig.cmake` and `<prefix>/lib/libparallelproj.so.2`.

- [ ] **Step 1: Write the failing tests**

```python
def test_itk_args_enable_exactly_the_listed_modules():
    bd = load_build_deps(); a = bd.itk_cmake_args(ctx(bd))
    assert {"-DITK_BUILD_DEFAULT_MODULES=OFF", "-DITKGroup_Core=OFF", "-DBUILD_EXAMPLES=OFF",
            "-DITK_WRAP_PYTHON=OFF"} <= set(a)
    assert sorted(x for x in a if x.startswith("-DModule_")) == sorted(
        f"-DModule_{m}=ON" for m in bd.read_itk_modules())

def test_parallelproj_cpu_args():
    bd = load_build_deps(); a = bd.parallelproj_cmake_args("cpu", bd.load_versions())
    assert {"-DUSE_CUDA=OFF", "-DBUILD_PYTHON=OFF", "-DBUILD_TESTS=OFF", "-DINSTALL_DEVEL=ON"} <= set(a)
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest packaging/pip/tests/test_build_deps.py -k "itk or parallelproj" -v`
Expected: FAIL with `AttributeError`.

- [ ] **Step 3: Implement both recipes**

- `itk`: fetch the tarball, `cmake_build` with `common + itk_cmake_args`. ITK honours `BUILD_SHARED_LIBS=OFF`.
  Do not set `ITK_SKIP_PATH_LENGTH_CHECKS`: the short `s`/`b` dirs pass it.
- `parallelproj`: fetch at the commit, `cmake_build` with `common + parallelproj_cmake_args(ctx.variant,
  ctx.versions) + openmp_cmake_args(ctx)`. Upstream ignores `BUILD_SHARED_LIBS` and installs a shared library.

Probe blocks:

- `itk`: `find_package(ITK 4.9 CONFIG REQUIRED)`, `include(${ITK_USE_FILE})` (generates the IO factory
  registration, as STIR does), link `${ITK_LIBRARIES}`. For each of `x.nii`, `x.nhdr`, `x.mhd`, print
  `probe: itk <ext> <ImageIO class>` from `itk::ImageIOFactory::CreateImageIO(name, WriteMode)`. Print
  `probe: itk ok` only if all three are non-null.
- `parallelproj`: `find_package(parallelproj CONFIG REQUIRED)`, link `parallelproj::parallelproj`. Print
  `probe: parallelproj ok <parallelproj_version()> cuda=<parallelproj_cuda_enabled()>`.

- [ ] **Step 4: Run tests and build the complete Linux prefix**

Run: `python -m pytest packaging/pip/tests/test_build_deps.py -v` → all PASS.
Run: `rm -rf .deps/cpu && time bash packaging/pip/deps/build_in_manylinux.sh x86_64 --variant cpu --jobs 8`
Expected output, in order: `probe: boost ok`, `probe: nlohmann_json ok`, `probe: hdf5 ok`, `probe: petsird ok`,
`probe: itk .nii NiftiImageIO`, `probe: itk .nhdr NrrdImageIO`, `probe: itk .mhd MetaImageIO`, `probe: itk ok`,
`probe: parallelproj ok 2.0.7 cuda=0`. Exit 0, and `.deps/cpu.work` is gone. Record the wall time and
`du -sh .deps/cpu` in the commit message body. Expect roughly 20–40 min and a few hundred MB.

- [ ] **Step 5: Commit**

```bash
git add packaging/pip/deps packaging/pip/tests/test_build_deps.py
git commit -m "Build static ITK IO modules and libparallelproj into the deps prefix"
```

---

### Task 5: Wire the deps prefix into the STIR build

This task also adds a configure-time feature guard.

**Files:**

- Modify: `packaging/pip/cmake/wheel_hook.cmake`, `pyproject.toml`
- Test: `packaging/pip/tests/test_cmake_hooks.py`, `packaging/pip/tests/test_ci_config.py`

**Interfaces:**

- Consumes: Phase 1 `wheel_hook.cmake` (runs right after `project(STIR)` via `CMAKE_PROJECT_STIR_INCLUDE`), and
  the deps prefix from Task 4.
- Produces:
  - Wheel file `stir/_data/build_features.json`: one JSON object whose keys are exactly
    `openmp, json, hdf5, petsird, itk, parallelproj, cuda, root` (booleans).
  - Configure fails with `stir-wheel: STIR_WHEEL_EXPECT lists features this build did not find: <names>` when a
    build feature named in `$ENV{STIR_WHEEL_EXPECT}` is false. Unknown names and `config` are ignored here; the
    smoke test validates the names.
  - `pyproject.toml`: `CMAKE_PREFIX_PATH = {env = "STIR_DEPS_PREFIX", default = ""}` (contract).

Feature expressions, evaluated at the end of the top-level directory (`cmake_language(DEFER CALL ...)`,
CMake ≥ 3.19). All of these variables are set in STIR's top-level scope:

| key | true when |
|---|---|
| `openmp` | `STIR_OPENMP` |
| `json` | `HAVE_JSON` |
| `hdf5` | `NOT DISABLE_HDF5 AND HDF5_FOUND` (the same test as `src/CMakeLists.txt`'s `HAVE_HDF5`) |
| `petsird` | `HAVE_PETSIRD` |
| `itk` | `NOT DISABLE_ITK AND ITK_FOUND` |
| `parallelproj` | `STIR_WITH_Parallelproj_PROJECTOR` |
| `cuda` | `STIR_WITH_CUDA` |
| `root` | `NOT DISABLE_CERN_ROOT AND CERN_ROOT_FOUND` |

- [ ] **Step 1: Write the failing tests**

`test_cmake_hooks.py`: add a second fake project, `features_project(tmp_path, sets: dict[str, str])`, whose
`CMakeLists.txt` is `cmake_minimum_required(VERSION 3.14)`, `project(STIR NONE)`, then one `set(K V)` per entry,
then `install(CODE "")`. Run it with `-DCMAKE_PROJECT_STIR_INCLUDE=<HOOK> -DSKBUILD_PLATLIB_DIR=<tmp>/platlib`,
reusing Phase 1's `configure` pattern, plus an `env` argument.

```python
ALL_ON = {"STIR_OPENMP": "ON", "HAVE_JSON": "ON", "HDF5_FOUND": "TRUE", "HAVE_PETSIRD": "ON", "ITK_FOUND": "TRUE",
          "STIR_WITH_Parallelproj_PROJECTOR": "ON"}

def test_hook_writes_build_features(tmp_path):
    r = features_project(tmp_path, ALL_ON)
    assert r.returncode == 0, r.stderr
    data = json.loads((tmp_path / "build" / "stir_build_features.json").read_text())
    assert data == {"openmp": True, "json": True, "hdf5": True, "petsird": True, "itk": True,
                    "parallelproj": True, "cuda": False, "root": False}
    assert "stir-wheel: build features: openmp=ON json=ON hdf5=ON" in r.stdout

def test_disable_option_wins_over_found(tmp_path):
    r = features_project(tmp_path, ALL_ON | {"DISABLE_ITK": "ON"})
    assert json.loads((tmp_path / "build" / "stir_build_features.json").read_text())["itk"] is False

def test_guard_fails_when_expected_feature_missing(tmp_path):
    r = features_project(tmp_path, ALL_ON | {"HDF5_FOUND": "FALSE"},
                         env={"STIR_WHEEL_EXPECT": "config,openmp,hdf5,itk"})
    assert r.returncode != 0 and "did not find: hdf5" in r.stderr

def test_guard_silent_without_expectation(tmp_path):
    assert features_project(tmp_path, {}, env={"STIR_WHEEL_EXPECT": ""}).returncode == 0
```

`test_ci_config.py`: replace Phase 1's `test_phase1_disables_every_optional_dependency` with:

```python
def test_disable_switches():
    assert {k: v for k, v in DEFINES.items() if k.startswith("DISABLE_")} == {
        "DISABLE_CERN_ROOT": "ON", "DISABLE_HDF5": "OFF", "DISABLE_ITK": "OFF", "DISABLE_LLN_MATRIX": "ON",
        "DISABLE_NLOHMANN_JSON": "OFF", "DISABLE_NiftyPET_PROJECTOR": "ON", "DISABLE_PETSIRD": "OFF",
        "DISABLE_Parallelproj_PROJECTOR": "OFF", "DISABLE_STIR_CUDA": "ON", "DISABLE_STIR_LOCAL": "ON",
        "DISABLE_UPENN": "ON"}

def test_deps_prefix_wiring():
    assert DEFINES["CMAKE_PREFIX_PATH"] == {"env": "STIR_DEPS_PREFIX", "default": ""}
    assert {".deps/"} <= set(SKB["sdist"]["exclude"])
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest packaging/pip/tests/test_cmake_hooks.py packaging/pip/tests/test_ci_config.py -v`
Expected: the new tests FAIL (no `stir_build_features.json`; `DISABLE_HDF5 == "ON"`).

- [ ] **Step 3: Extend `wheel_hook.cmake` and `pyproject.toml`**

Append to `packaging/pip/cmake/wheel_hook.cmake`, after Phase 1's lines (full content of the addition):

```cmake
# ---- Phase 2: native deps prefix (packaging/pip/deps/build_deps.py) --------------------------------------
if(DEFINED ENV{STIR_DEPS_PREFIX} AND NOT "$ENV{STIR_DEPS_PREFIX}" STREQUAL "")
  file(TO_CMAKE_PATH "$ENV{STIR_DEPS_PREFIX}" _stir_deps)
  # The prefix has static HDF5 only; FindHDF5 (config mode) must pick the hdf5::*-static targets.
  set(HDF5_USE_STATIC_LIBRARIES ON CACHE BOOL "pip wheel: static HDF5 from the deps prefix")
  # PETSIRD's geometry helpers use xt::linalg::dot; use xtensor-blas's built-in BLAS, not an external one.
  add_compile_definitions(XTENSOR_USE_FLENS_BLAS)
  # Lets auditwheel/delocate find the shared libparallelproj (and libomp on macOS) at repair time.
  if(UNIX)
    set(CMAKE_INSTALL_RPATH "${_stir_deps}/lib")
  endif()
endif()
# Keep static HDF5/ITK/... symbols private to _stir, so h5py's or itk's own copies are never interposed.
if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
  add_link_options("LINKER:--exclude-libs,ALL")
endif()

function(_stir_wheel_report_features)
  # body: compute the 8 booleans from the table in the plan (Task 5), write
  # ${CMAKE_BINARY_DIR}/stir_build_features.json, message(STATUS "stir-wheel: build features: k=ON|OFF ..."),
  # install(FILES ... DESTINATION "${PYTHON_DEST}/stir/_data" RENAME build_features.json),
  # then FATAL_ERROR listing every name in $ENV{STIR_WHEEL_EXPECT} that is a build feature and is false.
endfunction()
cmake_language(DEFER DIRECTORY "${CMAKE_SOURCE_DIR}" CALL _stir_wheel_report_features)
```

The function body is yours to write. The table, the file names, the messages and the destination are fixed
above. Write the JSON with `file(WRITE)` and keys in the table's order.

In `pyproject.toml`:

- `[tool.scikit-build.cmake.define]`: add `CMAKE_PREFIX_PATH = {env = "STIR_DEPS_PREFIX", default = ""}`. Set
  `DISABLE_HDF5`, `DISABLE_ITK`, `DISABLE_NLOHMANN_JSON`, `DISABLE_PETSIRD` and `DISABLE_Parallelproj_PROJECTOR`
  to `"OFF"`, and leave the rest as in Phase 1. Replace the "Phase 1: core STIR + OpenMP only" comment with
  `# Optional features come from the deps prefix (STIR_DEPS_PREFIX); see packaging/pip/deps/.`
- `sdist.exclude`: add `".deps/"`.
- `[tool.cibuildwheel.linux]`: delete `before-all = "dnf install -y boost-devel"` (Boost now comes from the
  prefix) and add `environment-pass = ["STIR_DEPS_PREFIX", "STIR_WHEEL_EXPECT", "STIR_WHEEL_VARIANT"]`.
- `[tool.cibuildwheel]`: delete `test-environment = { STIR_WHEEL_EXPECT = "config,openmp" }`. The expectation now
  comes from the workflow matrix (`expect`) for both build and test. Update Phase 1's `test_cibuildwheel_targets`
  to assert `"STIR_WHEEL_EXPECT" not in CIBW.get("test-environment", {})` and
  `"before-all" not in CIBW["linux"]`.

- [ ] **Step 4: Run the unit tests**

Run: `python -m pytest packaging/pip/tests --ignore=packaging/pip/tests/test_wheel_smoke.py -v`
Expected: all PASS.

- [ ] **Step 5: Build one wheel against the prefix (local, Linux x86_64)**

Run (repo root, after Task 4's prefix exists):

<!-- pyml disable md013-->
```bash
STIR_DEPS_PREFIX=/project/.deps/cpu STIR_WHEEL_EXPECT=config,openmp,json,hdf5,petsird,itk,parallelproj \
  pipx run cibuildwheel==4.3.5 --platform linux --only cp312-manylinux_x86_64 2>&1 | tee /tmp/cibw.log
grep -E "HDF5 support enabled|ITK libraries added|PETSIRD support enabled|Parallelproj projector support enabled|nlohmann JSON library 3.12.0 found|stir-wheel: build features" /tmp/cibw.log
```
<!-- pyml enable md013-->

Expected: six matching lines. The last one is `stir-wheel: build features: openmp=ON json=ON hdf5=ON petsird=ON
itk=ON parallelproj=ON cuda=OFF root=OFF`. The run ends with `1 wheels produced` (Phase 1's smoke test passes;
the feature checks come in Task 6), and `wheelhouse/` holds `stir-6.5.0-cp312-cp312-manylinux_2_28_x86_64.whl`.

- [ ] **Step 6: Check the wheel's contents and symbols**

<!-- pyml disable md013-->
```bash
unzip -l wheelhouse/stir-*-cp312-*.whl | grep -E "build_features.json|stir.libs/libparallelproj"
unzip -o -q wheelhouse/stir-*-cp312-*.whl -d /tmp/w && cd /tmp/w
nm -D --defined-only stir/_stir*.so | grep -c -E " (H5|_ZN3itk|_ZN2H5)" ; nm -D --undefined-only stir/_stir*.so | grep -E "sgemm|cblas" ; cd -
```
<!-- pyml enable md013-->

Expected: both files are listed. The first `nm` prints `0` (static symbols are not exported). The second prints
nothing (no external BLAS needed).

- [ ] **Step 7: No-prefix build still works (Review Focus 5)**

Run: `python -m pip wheel . --no-deps -w /tmp/noprefix -Cbuild-dir=/tmp/noprefix-build` on the host, with
`STIR_DEPS_PREFIX` and `STIR_WHEEL_EXPECT` unset.
Expected: the wheel builds. `unzip -p /tmp/noprefix/stir-*.whl stir/_data/build_features.json` shows `"openmp":
true` and `"hdf5": false`, unless the host has system HDF5, in which case it shows what CMake found. Then run
`STIR_WHEEL_EXPECT=hdf5 python -m pip wheel . --no-deps -w /tmp/x`. Expected: it fails during configure with
`stir-wheel: STIR_WHEEL_EXPECT lists features this build did not find: hdf5` (when the host lacks HDF5).

- [ ] **Step 8: Commit**

<!-- pyml disable md013-->
```bash
git add packaging/pip/cmake/wheel_hook.cmake pyproject.toml packaging/pip/tests/test_cmake_hooks.py packaging/pip/tests/test_ci_config.py
git commit -m "Enable HDF5, PETSIRD, nlohmann_json, ITK and parallelproj from the deps prefix"
```
<!-- pyml enable md013-->

---

### Task 6: Smoke checks that prove each feature at runtime

**Files:**

- Create: `packaging/pip/tests/_feature_probes.py`, `packaging/pip/tests/test_feature_probes.py`,
  `packaging/pip/tests/data/ge_signature.h5`
- Modify: `packaging/pip/tests/test_wheel_smoke.py` (Phase 1)

**Interfaces:**

- Consumes: Phase 1 `test_wheel_smoke.py`: `expected_features`, `run_stir`, `CHECKS`. Also Task 5's
  `build_features.json`.
- Produces (`_feature_probes.py`, no `import stir`; Phase 3 and 5 add to `KNOWN_FEATURES`'s users):
  - `KNOWN_FEATURES = frozenset({"config", "openmp", "json", "hdf5", "petsird", "itk", "parallelproj", "cuda",
    "root"})`. Moved unchanged from `test_wheel_smoke.py` (Phase 1 already lists `json`), which re-imports it.
  - `BUILD_FEATURES = ("openmp", "json", "hdf5", "petsird", "itk", "parallelproj", "cuda", "root")`
  - `NO_READER = "no file format found"` (STIR's `InputFileFormatRegistry` error text)
  - `@dataclass(frozen=True) class ProbeResult: recognised: bool; detail: str`
  - `classify_probe(returncode: int | None, stdout: str, stderr: str) -> ProbeResult`. `returncode=None` means it
    timed out. If `PROBE-IMPORTED` is not in stdout: not recognised, `"child failed at 'import stir': <last 5 lines
    of stderr>"`. If `NO_READER` appears in stdout or stderr: not recognised, `"STIR has no reader for this file:
    the feature is not compiled in"`. Otherwise: recognised, `"a STIR reader accepted the file (exit code N:
    <first 120 chars of the child's READ-ERROR line, if any>)"`.
  - `compare_build_features(built: Mapping[str, bool], expected: frozenset[str]) -> list[str]`: one message per
    problem. `"<f>: in STIR_WHEEL_EXPECT but not built"`, `"<f>: built but not in STIR_WHEEL_EXPECT (update the
    platform's expect list or README)"`, or `"build_features.json keys != BUILD_FEATURES: <diff>"`. `config` is
    ignored.
  - `write_petsird_signature_file(path: Path) -> None`: `b"yardl"` + 59 bytes of `0xFF`.
  - `write_ge_signature_h5(path: Path) -> None` (imports `h5py` lazily): scalar fixed-length string datasets
    `/HeaderData/ExamData/manufacturer = b"GE MEDICAL SYSTEMS"` and `/HeaderData/ExamData/scannerDesc =
    b"STIR wheel smoke test"`, `track_times=False`.
  - `GE_FIXTURE = Path(__file__).parent / "data" / "ge_signature.h5"`
  - `python packaging/pip/tests/_feature_probes.py --write-ge-fixture` regenerates `GE_FIXTURE`.
- Produces (`test_wheel_smoke.py`): `probe_reader(reader: str, path: Path, timeout: float = 300) -> ProbeResult`.
  It runs a child with the same cwd and environment rules as `run_stir`. The child prints `PROBE-IMPORTED` after
  `import stir`, then calls `stir.<reader>.read_from_file(str(path))`. On an exception it prints
  `READ-ERROR: <msg>`. `CHECKS` gains `json`, `hdf5`, `petsird`, `itk` and `parallelproj`.

Why a child process: once STIR accepts a GE or PETSIRD file, the reader can throw `H5::Exception`. That is not a
`std::exception`, so SWIG doesn't catch it and the process aborts. The question being tested is only "did a
compiled-in reader accept the file?". The abort answers it too.

- [ ] **Step 1: Write the failing unit tests** (`test_feature_probes.py`)

<!-- pyml disable md013-->
```python
from _feature_probes import (BUILD_FEATURES, GE_FIXTURE, classify_probe, compare_build_features,
                             write_petsird_signature_file)

def test_import_failure_is_not_recognised():
    r = classify_probe(1, "", "Traceback...\nImportError: libfoo.so")
    assert not r.recognised and "import stir" in r.detail and "libfoo" in r.detail

def test_no_reader_is_not_recognised():
    r = classify_probe(0, "PROBE-IMPORTED\nREAD-ERROR: no file format found that can read file 'x'", "")
    assert not r.recognised and "not compiled in" in r.detail

@pytest.mark.parametrize("rc", [0, -6, 3, 0xC0000409])
def test_reader_error_or_abort_after_import_is_recognised(rc):
    assert classify_probe(rc, "PROBE-IMPORTED\nREAD-ERROR: yardl: bad version", "").recognised

def test_timeout_is_not_recognised():
    assert not classify_probe(None, "PROBE-IMPORTED", "").recognised

def test_compare_build_features():
    built = dict.fromkeys(BUILD_FEATURES, False) | {"openmp": True, "hdf5": True}
    assert compare_build_features(built, frozenset({"config", "openmp", "hdf5"})) == []
    assert compare_build_features(built, frozenset({"openmp"})) == [
        "hdf5: built but not in STIR_WHEEL_EXPECT (update the platform's expect list or README)"]
    assert compare_build_features(built, frozenset({"openmp", "hdf5", "itk"})) == ["itk: in STIR_WHEEL_EXPECT but not built"]
    assert compare_build_features({"openmp": True}, frozenset())[0].startswith("build_features.json keys")

def test_fixtures(tmp_path):
    p = tmp_path / "a.petsird"; write_petsird_signature_file(p)
    assert p.read_bytes()[:5] == b"yardl"
    assert GE_FIXTURE.read_bytes()[:8] == b"\x89HDF\r\n\x1a\n" and GE_FIXTURE.stat().st_size < 20_000
```
<!-- pyml enable md013-->

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest packaging/pip/tests/test_feature_probes.py -v`
Expected: collection error `ModuleNotFoundError: No module named '_feature_probes'`.

- [ ] **Step 3: Implement `_feature_probes.py` and generate the fixture**

Run: `python -m pip install h5py && python packaging/pip/tests/_feature_probes.py --write-ge-fixture`
Expected: `packaging/pip/tests/data/ge_signature.h5` is created (a few KB). Commit it as a binary file.

- [ ] **Step 4: Run the unit tests**

Run: `python -m pytest packaging/pip/tests/test_feature_probes.py -v` → all PASS.

- [ ] **Step 5: Add the feature checks to `test_wheel_smoke.py`**

Each check works under `tempfile.TemporaryDirectory()` / `"dir with spaces é"` (Review Focus 3) and fails with a
message that starts with the feature name:

```python
def check_json():
    out = run_stir("import json, stir; m = stir.ImagingModality(stir.ImagingModality.PT); "
                   "r = stir.RadionuclideDB().get_radionuclide(m, '^68^Gallium'); "
                   "print(json.dumps({'name': r.get_name(), 'half_life': r.get_half_life()}))")
    assert out["name"] == "^68^Gallium" and abs(out["half_life"] - 4069.8) < 0.1, (
        f"json: STIR's radionuclide database was not used (got {out}); built without nlohmann_json?")

def check_hdf5():   # GE RDF HDF5 reader accepts a file carrying the GE signature
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "dir with spaces é" / "ge_signature.h5"; p.parent.mkdir(); shutil.copy(GE_FIXTURE, p)
        r = probe_reader("ListModeData", p)
        assert r.recognised, f"hdf5: {r.detail}"

def check_petsird():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "dir with spaces é" / "sig.petsird"; p.parent.mkdir(); write_petsird_signature_file(p)
        r = probe_reader("ListModeData", p)
        assert r.recognised, f"petsird: {r.detail}"

def check_itk():    # STIR writes and reads back through ITK in three formats
    code = """..."""   # see below
    out = run_stir(code)
    for ext, res in out.items():
        assert res["error"] is None, f"itk {ext}: {res['error']}"
        assert res["shape_equal"] and res["voxel_size_equal"] and res["max_abs_diff"] < 1e-6, f"itk {ext}: {res}"

def check_parallelproj():
    out = run_stir(PARALLELPROJ_CODE)
    assert out["has_class"], "parallelproj: stir.ForwardProjectorByBinParallelproj missing (built without parallelproj)"
    assert out["finite"] and out["max"] > 0, f"parallelproj: forward projection of a uniform image gave {out}"

CHECKS |= {"json": check_json, "hdf5": check_hdf5, "petsird": check_petsird, "itk": check_itk,
           "parallelproj": check_parallelproj}

def test_build_features_match_expect():
    files = importlib.resources.files("stir") / "_data" / "build_features.json"
    problems = compare_build_features(json.loads(files.read_text()), expected_features(os.environ))
    assert not problems, "\n".join(problems)
```

The `check_itk` child code, in prose (it prints one JSON object keyed by extension). It builds
`img = stir.FloatVoxelsOnCartesianGrid(stir.IndexRange3D(stir.Int3BasicCoordinate(0), stir.Int3BasicCoordinate((4,
5, 6))), stir.FloatCartesianCoordinate3D(0, 0, 0), stir.FloatCartesianCoordinate3D(2, 3, 4))`. It fills it
from `numpy.arange` so the array is asymmetric (axis flips would show), using `img.fill(arr.flat)`. Then, for each
of `.nii`, `.nhdr` and `.mhd`, under a `dir with spaces é` temp folder:
`stir.ITKOutputFileFormat().write_to_file(path, img)`, then `img2 =
stir.FloatVoxelsOnCartesianGrid.read_from_file(path)`. It records `error` (exception text or `None`),
`shape_equal`, `voxel_size_equal` (`get_voxel_size()` equality) and `max_abs_diff` of `as_array()`.

`PARALLELPROJ_CODE`, in prose: `s = stir.Scanner.get_scanner_from_name("ECAT 962")`,
`pdi = stir.ProjDataInfo.construct_proj_data_info(s, 3, 6, 8, 6)`,
`proj = stir.ProjDataInMemory(stir.ExamInfo(), pdi)`,
`img = stir.FloatVoxelsOnCartesianGrid(proj.get_exam_info(), pdi)`, `img.fill(1)`. Then, if
`hasattr(stir, "ForwardProjectorByBinParallelproj")`: `fwd = stir.ForwardProjectorByBinParallelproj()`,
`fwd.set_up(pdi, img)`, `fwd.forward_project(proj, img)`, `a = proj.as_array()`. It prints
`{"has_class", "finite": bool(np.isfinite(a).all()), "max": float(a.max())}`.

Change Phase 1's `test_wheel_smoke.py` so it imports `KNOWN_FEATURES` from `_feature_probes` instead of defining
it.

- [ ] **Step 6: Run the smoke test against the Task 5 wheel**

```bash
python3.12 -m venv /tmp/v && /tmp/v/bin/pip install wheelhouse/stir-*-cp312-*.whl pytest
cd /tmp && STIR_WHEEL_EXPECT=config,openmp,json,hdf5,petsird,itk,parallelproj \
  /tmp/v/bin/python -m pytest -v -rs /home/claude/src/STIR/packaging/pip/tests/test_wheel_smoke.py
```

Expected: `test_expected_feature[<f>]` PASSES for all seven features, and `test_build_features_match_expect` and
Phase 1's tests PASS. Negative check: `STIR_WHEEL_EXPECT=config,openmp` fails
`test_build_features_match_expect` with five `built but not in STIR_WHEEL_EXPECT` lines. That proves the check
bites.

Fallback: if `check_itk` shows `max_abs_diff` > 0 with equal shapes, compare `arr` against `numpy.flip` of the
result along each axis to identify the axis. That is a STIR ITK orientation behaviour, not packaging: report it
to Robert (and check whether conda's STIR does the same with the same script) before changing the assertion.

- [ ] **Step 7: Commit**

```bash
git add packaging/pip/tests
git commit -m "Prove json, HDF5, PETSIRD, ITK and parallelproj at runtime in the wheel smoke test"
```

---

### Task 7: CI for Linux x86_64 with the cached deps prefix

**Files:**

- Modify: `.github/workflows/wheels.yml`, `packaging/pip/tests/test_ci_config.py`, `packaging/pip/README.md`,
  `pyproject.toml`
- Create: `packaging/pip/tests/test_coexistence.py`

**Interfaces:**

- Consumes: `build_in_manylinux.sh`, `build_deps.py --cache-key`, Phase 1 jobs.
- Produces: matrix keys used by both `build_cpu` and `rehearse_publish`: `os`, `arch` (cibuildwheel arch:
  `x86_64 | arm64 | AMD64`), `runner`, `wheel_tag`, `expect`, `only`. `rehearse_publish` rows have
  `variant` (always `cpu` in this phase; Phase 3 adds CUDA rows), `os`, `arch`, `runner`, `expect`, `pythons` and
  `coexist`. Artifact names are unchanged: `wheels-cpu-${{ matrix.os }}-${{ matrix.arch }}`. Cache
  key: `stir-deps-cpu-${{ matrix.os }}-${{ matrix.arch }}-<build_deps --cache-key>`. Env inside the wheel build:
  `STIR_DEPS_PREFIX` (Linux `/project/.deps/cpu`, otherwise `<workspace>/.deps/cpu`), `STIR_WHEEL_EXPECT`, and
  `STIR_WHEEL_VARIANT=cpu`.

- [ ] **Step 0: Confirm the go-ahead to push** (Phase 1 Task 9 rule). Ask Robert once: "Phase 2 needs pushes of
  `pip-packaging` to `fork` (robbietuk/STIR) for each platform task. OK?" Do not push without his yes.

- [ ] **Step 1: Write the failing config tests** (`test_ci_config.py`; replace Phase 1's matrix assertion in
  `test_artifact_names` with `EXPECTED_PLATFORMS`)

```python
VERSIONS = tomllib.loads((REPO / "packaging/pip/deps/versions.toml").read_text())
EXPECTED_PLATFORMS = {("linux", "x86_64")}          # each platform task (8, 9) adds its entry here
MATRIX_KEYS = {"os", "arch", "runner", "wheel_tag", "expect", "only"}

def matrix(job): return JOBS[job]["strategy"]["matrix"]["include"]

def test_build_matrix_platforms_and_keys():
    assert {(m["os"], m["arch"]) for m in matrix("build_cpu")} == EXPECTED_PLATFORMS
    assert all(set(m) == MATRIX_KEYS for m in matrix("build_cpu"))

def test_rehearsal_covers_every_build_platform_with_same_expect():
    b = {(m["os"], m["arch"]): m["expect"] for m in matrix("build_cpu")}
    r = {(m["os"], m["arch"]): m["expect"] for m in matrix("rehearse_publish")}
    assert b == r

def test_expect_lists_use_known_features():
    from _feature_probes import KNOWN_FEATURES
    for m in matrix("build_cpu"):
        assert set(m["expect"].split(",")) <= KNOWN_FEATURES

def test_deps_cache_uses_cache_key():
    text = "\n".join(runs("build_cpu"))
    assert "build_deps.py --cache-key --variant cpu" in text
    keys = {s["with"]["key"] for s in JOBS["build_cpu"]["steps"] if s.get("uses", "").startswith("actions/cache/")}
    assert keys == {"stir-deps-cpu-${{ matrix.os }}-${{ matrix.arch }}-${{ env.DEPS_KEY }}"}

def test_manylinux_images_match_versions_toml():
    assert CIBW["linux"]["manylinux-x86_64-image"] == VERSIONS["toolchain"]["manylinux_x86_64_image"]
```

Adapt Phase 1's `test_rehearsal_installs_exact_dev_version` to the new install line (Step 3). Keep its
`needs == ["sdist", "build_cpu"]` assertion. `test_rehearsal_covers_numpy1` keeps its strings, inside the
Linux-only step. In Phase 1's `test_cibuildwheel_targets`, drop the `manylinux-x86_64-image == "manylinux_2_28"`
assertion (`test_manylinux_images_match_versions_toml` replaces it).

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest packaging/pip/tests/test_ci_config.py -v`
Expected: the new tests FAIL (`KeyError: 'wheel_tag'`, missing cache steps, image `manylinux_2_28`).

- [ ] **Step 3: Rewrite `build_cpu`, generalise `rehearse_publish`, and pin the images**

`pyproject.toml` `[tool.cibuildwheel.linux]`: set `manylinux-x86_64-image` to the x86_64 digest from
`versions.toml` (same string).

`build_cpu` (full job; the YAML is the decision):

<!-- pyml disable md013-->
```yaml
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
            runner: ubuntu-24.04
            wheel_tag: manylinux_2_28_x86_64
            expect: config,openmp,json,hdf5,petsird,itk,parallelproj
            only: ""
    env:
      STIR_WHEEL_VARIANT: cpu
      STIR_WHEEL_EXPECT: ${{ matrix.expect }}
    steps:
      - uses: actions/checkout@v6
        with:
          submodules: recursive
          persist-credentials: false
      - uses: actions/setup-python@v6
        with:
          python-version: "3.13"
      - name: Locate the deps prefix and its cache key
        shell: bash
        run: |
          set -euo pipefail
          if [[ "$RUNNER_OS" == Windows ]]; then host="${GITHUB_WORKSPACE}\\.deps\\cpu"; else host="${GITHUB_WORKSPACE}/.deps/cpu"; fi
          if [[ "$RUNNER_OS" == Linux ]]; then prefix=/project/.deps/cpu; else prefix="$host"; fi
          {
            echo "STIR_DEPS_HOST=$host"
            echo "STIR_DEPS_PREFIX=$prefix"
            echo "DEPS_KEY=$(python packaging/pip/deps/build_deps.py --cache-key --variant cpu)"
          } >> "$GITHUB_ENV"
      - name: Restore deps prefix
        id: deps-cache
        uses: actions/cache/restore@v4
        with:
          path: ${{ env.STIR_DEPS_HOST }}
          key: stir-deps-cpu-${{ matrix.os }}-${{ matrix.arch }}-${{ env.DEPS_KEY }}
      - name: MSVC environment for the deps build
        if: runner.os == 'Windows' && steps.deps-cache.outputs.cache-hit != 'true'
        uses: ilammy/msvc-dev-cmd@v1
      - name: Build deps prefix (Linux, pinned manylinux image)
        if: runner.os == 'Linux' && steps.deps-cache.outputs.cache-hit != 'true'
        run: >-
          bash packaging/pip/deps/build_in_manylinux.sh ${{ matrix.arch }} --variant cpu --jobs 4
          ${{ matrix.only != '' && format('--only {0}', matrix.only) || '' }}
      - name: Build deps prefix (macOS, Windows)
        if: runner.os != 'Linux' && steps.deps-cache.outputs.cache-hit != 'true'
        shell: pwsh
        run: |
          python -m pip install -r packaging/pip/deps/requirements.txt
          python packaging/pip/deps/build_deps.py --prefix "$env:STIR_DEPS_HOST" --variant cpu --jobs 4 ${{ matrix.only != '' && format('--only {0}', matrix.only) || '' }}
      - name: Save deps prefix (before the STIR build, so a STIR failure keeps it)
        if: steps.deps-cache.outputs.cache-hit != 'true'
        uses: actions/cache/save@v4
        with:
          path: ${{ env.STIR_DEPS_HOST }}
          key: stir-deps-cpu-${{ matrix.os }}-${{ matrix.arch }}-${{ env.DEPS_KEY }}
      - name: Prepare pyproject.toml (cpu, dev version)
        run: python packaging/pip/prepare_build.py --variant cpu --dev-number ${{ github.run_number }}
      - name: Build and test wheels
        uses: pypa/cibuildwheel@v4.3.5
        env:
          CIBW_ARCHS: ${{ matrix.arch }}
        with:
          output-dir: wheelhouse
      - name: Check wheel set, tags and sizes
        shell: bash
        run: |
          set -euo pipefail
          python - "$(cat VERSION.txt).dev${{ github.run_number }}" "${{ matrix.wheel_tag }}" <<'EOF'
          import pathlib, sys
          version, tag = sys.argv[1:]
          wheels = sorted(pathlib.Path("wheelhouse").glob("*.whl"))
          for w in wheels: print(f"{w.name}  {w.stat().st_size / 1e6:.1f} MB")
          want = {f"cp3{m}" for m in range(11, 16)}
          got = {w.name.split("-")[2] for w in wheels}
          assert got == want and len(wheels) == 5, f"expected one wheel per {sorted(want)}, got {sorted(got)}"
          bad = [w.name for w in wheels if not w.name.startswith(f"stir-{version}-") or not w.stem.endswith(tag)]
          assert not bad, f"wrong version or platform tag (want ...{tag}): {bad}"
          big = [w.name for w in wheels if w.stat().st_size >= 104857600]
          assert not big, f"over the 100 MB PyPI limit: {big}"
          EOF
      - uses: actions/upload-artifact@v4
        with:
          name: wheels-cpu-${{ matrix.os }}-${{ matrix.arch }}
          path: wheelhouse/*.whl
          if-no-files-found: error
```
<!-- pyml enable md013-->

`rehearse_publish` becomes a matrix with the same `os/arch/runner/expect`, plus `variant: cpu`, `pythons` and
`coexist`. For Linux x86_64: `pythons: "3.11 3.12 3.13 3.14 3.15"`, `coexist: true`.

- Keep Phase 1's steps unchanged: checkout, setup-python (all five versions, multi-line), downloads, the
  background-process pypiserver step (it already works on macOS and Windows, which have no Linux containers), twine
  upload, index check. Give the server step `shell: bash` on every platform.
- The install loop iterates `for py in ${{ matrix.pythons }}`. The interpreter is `py -$py` on Windows and
  `python$py` elsewhere. The venv's Python is `$venv/Scripts/python.exe` on Windows and `$venv/bin/python`
  elsewhere. `STIR_WHEEL_EXPECT: ${{ matrix.expect }}`. The install line stays
  `--index-url http://localhost:8080/simple/ "stir==$version" pytest`.
- `NumPy 1.x at runtime` gets `if: matrix.os == 'linux' && matrix.arch == 'x86_64'`.
- New step `Coexistence with h5py / itk / scikit-learn` with `if: matrix.coexist`, Python 3.12. It installs
  `"stir==$version" pytest h5py itk-io`, plus `scikit-learn` when `RUNNER_OS == macOS`, then runs
  `STIR_TEST_COEXIST=1 python -m pytest -v -rs .../packaging/pip/tests/test_coexistence.py`.

`sdist` job (Review Focus 5): add a step after `Check sdist contents` that builds a wheel from the sdist without
a prefix and checks the guard stays quiet. The runner has no Boost headers (Boost now comes from the prefix), so
install them first: `sudo apt-get install -y libboost-dev && python -m pip wheel dist/stir-*.tar.gz --no-deps -w
/tmp/noprefix && unzip -p /tmp/noprefix/*.whl stir/_data/build_features.json`. Expected: `"openmp":
true`, and no failure.

`packaging/pip/tests/test_coexistence.py`. At module top:
`pytestmark = pytest.mark.skipif(os.environ.get("STIR_TEST_COEXIST") != "1", reason="CI rehearsal only")`, then
lazy imports inside the tests:

- `test_h5py_then_stir_hdf5(tmp_path)`: `write_ge_signature_h5` (h5py) into `tmp_path`, then
  `probe_reader`-style child that does `import h5py, stir` and reads it. Assert `recognised`, with a message
  naming Review Focus 2.
- `test_itk_then_stir_itk_roundtrip(tmp_path)`: child does `import itk, stir`. STIR writes an asymmetric image to
  `.nii`; `itk.array_from_image(itk.imread(path))` must equal STIR's `as_array()` (same axis order, z,y,x);
  STIR reads it back too.
- `test_sklearn_openmp_then_stir_parallelproj()`: skip unless `sys.platform == "darwin"`. Child:
  `from sklearn.utils._openmp_helpers import _openmp_effective_n_threads; _openmp_effective_n_threads()`, then
  `PARALLELPROJ_CODE`. Assert return code 0 and `"OMP: Error #15"` not in stderr. The failure message says:
  `two OpenMP runtimes loaded (STIR's bundled libomp and scikit-learn's); see plan Review Focus 1`.

`packaging/pip/README.md`: replace Phase 1's "Phase 1 limits" with three sections. (1) "Native dependencies":
what the deps prefix is, `versions.toml`, the local command (`build_in_manylinux.sh x86_64 --variant cpu`), and
`STIR_DEPS_PREFIX=/project/.deps/cpu` for local cibuildwheel. (2) "Feature status by platform": a table with rows
for the 3 first-version platforms and columns config, OpenMP, json, HDF5, PETSIRD, ITK,
parallelproj. The Linux x86_64 row is
✓ everywhere; the other rows say "pending (Phase 2 Task N)". (3) "Known gaps": empty list plus a pointer to the
Known-gap procedure in this plan.

- [ ] **Step 4: Run the config tests**

Run: `python -m pytest packaging/pip/tests --ignore=packaging/pip/tests/test_wheel_smoke.py -v`
Expected: all PASS, and `test_coexistence.py` is SKIPPED ("CI rehearsal only").

- [ ] **Step 5: Commit, push to the fork, watch CI**

<!-- pyml disable md013-->
```bash
git add .github/workflows/wheels.yml pyproject.toml packaging/pip/tests packaging/pip/README.md
git commit -m "Build Linux x86_64 wheels with the full CPU feature set and a cached deps prefix"
git push fork pip-packaging
gh run watch "$(gh run list --repo robbietuk/STIR --workflow wheels.yml --branch pip-packaging -L 1 --json databaseId -q '.[0].databaseId')" --repo robbietuk/STIR --exit-status
```
<!-- pyml enable md013-->

Expected: `build_cpu (linux-x86_64)` passes. Its log shows `probe: parallelproj ok 2.0.7 cuda=0`, the
`stir-wheel: build features: ... parallelproj=ON ...` line and five wheels `...manylinux_2_28_x86_64.whl`.
`rehearse_publish (linux-x86_64)` passes, including the coexistence step (2 passed, 1 skipped). `publish` is
skipped.

- [ ] **Step 6: Prove the cache works**

Run: `gh run rerun <run-id> --repo robbietuk/STIR` and watch it.
Expected: `Restore deps prefix` logs `Cache restored from key: stir-deps-cpu-linux-x86_64-<16 hex>`. Both
`Build deps prefix` steps and `Save deps prefix` are skipped. The job is shorter by the deps build time.

Fallback: if `test_h5py_then_stir_hdf5` or `test_itk_then_stir_itk_roundtrip` crashes, check
`nm -D --defined-only` on the CI wheel's `_stir*.so` for `H5`/`itk` symbols. If they are there,
`--exclude-libs` did not reach the module's link line: inspect the cibuildwheel log for
`-Wl,--exclude-libs,ALL`.

- [ ] **Step 7: Commit the README run record** (`git commit -m "Record first full-feature Linux wheel run"`;
  push to `fork`).

---

### Task 8: macOS arm64 (libomp from LLVM, delocate)

**Files:**

- Modify: `packaging/pip/deps/build_deps.py`, `packaging/pip/cmake/wheel_hook.cmake`, `pyproject.toml`,
  `.github/workflows/wheels.yml`, `packaging/pip/tests/test_build_deps.py`, `test_ci_config.py`, `test_cmake_hooks.py`,
  `packaging/pip/README.md`

**Interfaces:**

- Consumes: `openmp_cmake_args` stub (Task 4), `BuildContext`.
- Produces: `build_openmp(ctx)`. `openmp_cmake_args(ctx)` on darwin returns
  `-DOpenMP_C_FLAGS=-Xclang -fopenmp -I<prefix>/include`, the same for `CXX`, `-DOpenMP_C_LIB_NAMES=omp`,
  `-DOpenMP_CXX_LIB_NAMES=omp` and `-DOpenMP_omp_LIBRARY=<prefix>/lib/libomp.dylib`.
  `wheel_hook.cmake` sets the same five cache variables when `APPLE` and the prefix is set. STIR's
  `add_definitions(${OpenMP_CXX_FLAGS})` passes `-Xclang -fopenmp` through as two arguments (checked with
  CMake 3.28).

- [ ] **Step 1: Write the failing tests**

```python
def test_openmp_args_darwin_only():
    bd = load_build_deps()
    assert bd.openmp_cmake_args(ctx(bd)) == []
    a = bd.openmp_cmake_args(ctx(bd, "darwin", "arm64"))
    assert "-DOpenMP_CXX_FLAGS=-Xclang -fopenmp -I/p/include" in a and "-DOpenMP_omp_LIBRARY=/p/lib/libomp.dylib" in a

def test_openmp_build_args():
    bd = load_build_deps(); a = set(bd.openmp_build_cmake_args(ctx(bd, "darwin", "arm64")))
    assert {"-DLIBOMP_ENABLE_SHARED=ON", "-DOPENMP_ENABLE_LIBOMPTARGET=OFF", "-DLIBOMP_OMPD_SUPPORT=OFF",
            "-DOPENMP_ENABLE_OMPT_TOOLS=OFF", "-DLIBOMP_INSTALL_ALIASES=OFF", "-DLIBOMP_USE_HWLOC=OFF",
            "-DCMAKE_OSX_DEPLOYMENT_TARGET=11.0"} <= a
```

`test_ci_config.py`: `EXPECTED_PLATFORMS |= {("macos", "arm64")}`, and:

```python
def test_macos_settings():
    assert CIBW["macos"]["environment"]["MACOSX_DEPLOYMENT_TARGET"] == VERSIONS["toolchain"]["macos_deployment_target"]
```

`test_cmake_hooks.py`: add `test_apple_openmp_hints_only_on_apple`. On Linux, configuring the fake project with
`STIR_DEPS_PREFIX` set must leave `OpenMP_omp_LIBRARY` out of `CMakeCache.txt`. The Apple branch is exercised
by CI.

- [ ] **Step 2: Run them to verify they fail**

```bash
python -m pytest packaging/pip/tests -k "openmp or macos or apple" \
  --ignore=packaging/pip/tests/test_wheel_smoke.py -v
```

Expected: FAIL (`openmp_cmake_args` returns `[]` on darwin; no `macos` key; no `openmp_build_cmake_args`).

- [ ] **Step 3: Implement**

- `build_openmp(ctx)`: fetch `openmp` to `<work>/openmp/openmp` and `llvm_cmake` to `<work>/openmp/cmake`
  (sibling, as LLVM expects), then `cmake_build` with `common_cmake_args(ctx)` (its `BUILD_SHARED_LIBS=OFF` is
  overridden by `LIBOMP_ENABLE_SHARED=ON`) and `openmp_build_cmake_args(ctx)`. Expected install:
  `<prefix>/lib/libomp.dylib` with install name `@rpath/libomp.dylib`.
- `wheel_hook.cmake`: inside the prefix block, `if(APPLE)`, set the five OpenMP cache variables (`CACHE STRING`
  / `FILEPATH`) from `_stir_deps`.
- `pyproject.toml`: `[tool.cibuildwheel.macos] environment = { MACOSX_DEPLOYMENT_TARGET = "11.0" }`. Repair stays
  cibuildwheel's default delocate command. `CMAKE_INSTALL_RPATH` lets it resolve `@rpath/libomp.dylib` and
  `@rpath/libparallelproj.2.dylib`.
- Workflow: add to both matrices

  ```yaml
          - os: macos
            arch: arm64
            runner: macos-15
            wheel_tag: macosx_11_0_arm64
            expect: config,openmp,json,hdf5,petsird,itk,parallelproj
            only: ""
  ```

  `rehearse_publish` entry: `pythons: "3.11 3.15"`, `coexist: true`.
- README: fill the macOS arm64 row.

- [ ] **Step 4: Unit tests, commit, push, watch**

Run: `python -m pytest packaging/pip/tests --ignore=packaging/pip/tests/test_wheel_smoke.py -v` → all PASS.

```bash
git add -A packaging/pip pyproject.toml .github/workflows/wheels.yml
git commit -m "Build macOS arm64 wheels with LLVM libomp and the full CPU feature set"
git push fork pip-packaging
```

Expected CI: `build_cpu (macos-arm64)` passes with five `...macosx_11_0_arm64.whl`. delocate's log lists
`libomp.dylib` and `libparallelproj.2.dylib` copied into `stir/.dylibs/`. `rehearse_publish (macos-arm64)` passes,
including `test_sklearn_openmp_then_stir_parallelproj`.

- [ ] **Step 5: Fallbacks (only if Step 4 fails)**

- delocate can't find `@rpath/...`: set `[tool.cibuildwheel.macos] repair-wheel-command =
  "DYLD_LIBRARY_PATH=$STIR_DEPS_PREFIX/lib delocate-wheel --require-archs {delocate_archs} -w {dest_dir} -v
  {wheel}"`.
- delocate reports a library whose minimum macOS is newer than 11.0: find it with `otool -l <lib> | grep -A3
  LC_BUILD_VERSION` and make sure its recipe got `CMAKE_OSX_DEPLOYMENT_TARGET`. Never raise the wheel's target to
  work around this.
- `check_hdf5` or `check_itk` fails, or STIR's own `src/swig/test/python` fails only with HDF5/ITK on: this is the
  case conda-forge hit (`UCL/STIR#1165`). Apply the Known-gap procedure for that feature on `darwin`/`arm64`, and
  quote the failing output in the README footnote.
- `test_sklearn_openmp_then_stir_parallelproj` fails with `OMP: Error #15`: **stop and ask Robert.** Possible
  remedies, each with a cost: (a) document `KMP_DUPLICATE_LIB_OK=TRUE`, which breaks the "no environment
  variables" anti-goal; (b) ship macOS without OpenMP (slower, and a documented gap); (c) find a shared libomp
  provider on PyPI that STIR, scikit-learn and PyTorch could all use. Record the decision in the README.

---

### Task 9: Windows x86_64 (MSVC, delvewheel, vcomp)

**Files:**

- Modify: `pyproject.toml`, `.github/workflows/wheels.yml`, `packaging/pip/tests/test_ci_config.py`,
  `packaging/pip/README.md`. Only if a fallback needs it: `packaging/pip/deps/build_deps.py`,
  `packaging/pip/deps/patches/`, `packaging/pip/deps/versions.toml`.

**Interfaces:**

- Consumes: the MSVC step and pwsh deps step already in `build_cpu` (Task 7).
- Produces: `[tool.cibuildwheel.windows] repair-wheel-command`. If the PETSIRD fallback is used:
  `versions.toml` `[deps.petsird] patches_win32 = ["petsird-0.12.2-msvc-no-werror.patch"]`, and
  `apply_patches(name: str, src: Path, ctx: BuildContext) -> None` (applies `patches_<platform>` with
  `git apply`).

- [ ] **Step 1: Write the failing tests** (`test_ci_config.py`)

```python
EXPECTED_PLATFORMS |= {("windows", "AMD64")}

def test_windows_repair_adds_deps_bin():
    cmd = CIBW["windows"]["repair-wheel-command"]
    assert cmd.startswith("delvewheel repair") and "--add-path %STIR_DEPS_PREFIX%\\bin" in cmd
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest packaging/pip/tests/test_ci_config.py -v` → the two new assertions FAIL.

- [ ] **Step 3: Implement**

- `pyproject.toml`: `[tool.cibuildwheel.windows] repair-wheel-command = "delvewheel repair --add-path
  %STIR_DEPS_PREFIX%\\bin -w {dest_dir} -v {wheel}"`. cibuildwheel runs this through `cmd`. `parallelproj.dll`
  is in `<prefix>/bin`. delvewheel vendors `vcomp140.dll` and `msvcp140.dll` itself.
- Workflow: add the entry to both matrices (`rehearse_publish`: `pythons: "3.11 3.15"`, `coexist: false`):

  ```yaml
          - os: windows
            arch: AMD64
            runner: windows-2025
            wheel_tag: win_amd64
            expect: config,openmp,json,hdf5,petsird,itk,parallelproj
            only: ""
  ```

- README: fill the Windows row.

- [ ] **Step 4: Unit tests, commit, push, watch**

Run the unit tests (all PASS), then
`git commit -am "Build Windows x86_64 wheels with the full CPU feature set" && git push fork pip-packaging`.
Expected CI: `build_cpu (windows-AMD64)` passes. The delvewheel log shows `parallelproj.dll` and `vcomp140.dll`
repaired into `stir.libs`, and there are five `...win_amd64.whl`. `rehearse_publish (windows-AMD64)` passes.

- [ ] **Step 5: Fallbacks (only if Step 4 fails)**

- PETSIRD fails to compile with `error C2220: the following warning is treated as an error`. Upstream adds
  `/W3 /WX` with `add_compile_options`, which comes after `CMAKE_CXX_FLAGS`, so no flag can undo it. Create
  `packaging/pip/deps/patches/petsird-0.12.2-msvc-no-werror.patch`, removing `/WX` from `cpp/CMakeLists.txt`'s
  `add_compile_options(/W3 /WX)`. Then add `patches_win32` and `apply_patches` (Interfaces), with the test
  `test_apply_patches_only_on_matching_platform(tmp_path)` (a git repo fixture; the patch applies on `win32`, not
  on `linux`).
- ITK stops with `ITK source code directory path length is too long`: shorten the Windows prefix to `C:\d\cpu`
  in the "Locate" step (host and prefix). Phase 3 must then use the same root (note it in the commit message).
- `check_hdf5` or `check_itk` fails for the `é` folder but passes for plain ASCII: that is STIR's narrow-string file
  API on Windows, not packaging. Keep the check strict and apply the Known-gap procedure as "non-ASCII paths on
  Windows" (README footnote), rather than dropping the feature.
- HDF5 or PETSIRD cannot be made to work (conda-forge ships neither on Windows): Known-gap procedure.
- The `py -3.11` launcher can't find a setup-python interpreter: give each needed version its own
  `actions/setup-python` step with an `id`, and use `steps.<id>.outputs.python-path`.
- The background pypiserver doesn't survive into the next step: move the server start, upload and install into
  one step for Windows.

---

### Task 10: First-version acceptance (three platforms)

**Files:**

- Modify: `packaging/pip/README.md` (final table and run record)

- [ ] **Step 1: Unit tests**

Run: `python -m pytest packaging/pip/tests --ignore=packaging/pip/tests/test_wheel_smoke.py -v`
Expected: all PASS. `EXPECTED_PLATFORMS` is exactly `{("linux", "x86_64"), ("macos", "arm64"), ("windows", "AMD64")}`.

- [ ] **Step 2: A clean full run**

Trigger: `gh workflow run wheels.yml --repo robbietuk/STIR --ref pip-packaging`, then watch it.
Expected: 3 `build_cpu` and 3 `rehearse_publish` jobs green, and `publish` skipped. `gh run download <id> --repo
robbietuk/STIR --dir /tmp/a && ls /tmp/a/wheels-cpu-*/ | grep -c whl` prints `15`. All restore steps report a
cache hit (the deps were built in Tasks 7–9 with the same key).

- [ ] **Step 3: Cache key invalidation works**

On a scratch commit, add a comment line to `versions.toml` and push. Expected: every platform logs
`Cache not found for input keys: stir-deps-cpu-...` and rebuilds the prefix. Revert the scratch commit (`git
revert`) and push. Expected: the old cache entries hit again.

- [ ] **Step 4: README final state**

Every cell in "Feature status by platform" is ✓, or ✗ with a footnote from the Known-gap procedure. Record the
run URL, the wheel size range per platform and the cold and warm `build_cpu` durations. Run
`pre-commit run --files packaging/pip/README.md`. Expected: Passed.

- [ ] **Step 5: Commit and push**

```bash
git add packaging/pip/README.md
git commit -m "Record Phase 2 three-platform CPU wheel run and feature status"
git push fork pip-packaging
```

---

## Appendix: Later, if needed

**Not part of the first version; do not execute unless Robert asks.** These are the researched tasks for the two
deferred CPU platforms (spec §7). Each is additive: matrix rows in `build_cpu` and `rehearse_publish`
(`pythons: "3.11 3.15"`, `coexist: false`), an `EXPECTED_PLATFORMS` entry, and a README row. When one is added,
Task 10's counts grow by one job pair and 5 wheels, and the README "Feature status by platform" gains its row.

### A1: Linux aarch64 (deferred)

**Files:**

- Modify: `.github/workflows/wheels.yml`, `packaging/pip/tests/test_ci_config.py`, `packaging/pip/README.md`

**Interfaces:**

- Consumes: `build_in_manylinux.sh aarch64` (it reads `manylinux_aarch64_image`), and the yardl `linux-aarch64`
  asset (both already pinned in `versions.toml` by Task 1).
- Also: set `[tool.cibuildwheel.linux] manylinux-aarch64-image` to the aarch64 digest, add
  `assert CIBW["linux"]["manylinux-aarch64-image"] == VERSIONS["toolchain"]["manylinux_aarch64_image"]` to
  `test_manylinux_images_match_versions_toml`, and add `("linux", "aarch64")` to `test_platform_key`'s list.
  Phase 3's appendix B2 (CUDA sbsa) depends on this.

- [ ] **Step 1: Failing test:** `EXPECTED_PLATFORMS |= {("linux", "aarch64")}`. Run `pytest
  packaging/pip/tests/test_ci_config.py -v` → FAIL.

- [ ] **Step 2: Add the entries** (`rehearse_publish`: `pythons: "3.11 3.15"`, `coexist: false`):

  ```yaml
          - os: linux
            arch: aarch64
            runner: ubuntu-24.04-arm
            wheel_tag: manylinux_2_28_aarch64
            expect: config,openmp,json,hdf5,petsird,itk,parallelproj
            only: ""
  ```

- [ ] **Step 3: Tests pass, commit, push, watch**

`git commit -am "Build Linux aarch64 wheels natively on ubuntu-24.04-arm" && git push fork pip-packaging`
Expected CI: `build_cpu (linux-aarch64)` passes with five `...manylinux_2_28_aarch64.whl`, and the probe lines
match Task 4's. `rehearse_publish (linux-aarch64)` passes. README row filled.

- [ ] **Step 4: Fallbacks (only if needed)**

- The job times out building ITK: raise `timeout-minutes` to 360 if it is lower. The prefix is cached after the
  first success, so this cost is paid once per `versions.toml` change.
- `check_hdf5` fails on aarch64 only (`char` is unsigned on aarch64 Linux): Known-gap procedure, quoting the
  output.

---

### A2: macOS x86_64 (deferred)

**Files:**

- Modify: `.github/workflows/wheels.yml`, `packaging/pip/tests/test_ci_config.py`, `packaging/pip/README.md`

**Interfaces:**

- Consumes: Task 8's macOS settings (`openmp` dep, deployment target 11.0, delocate) and the yardl `darwin-x86_64`
  asset already pinned in `versions.toml`.

- [ ] **Step 1: Failing test:** `EXPECTED_PLATFORMS |= {("macos", "x86_64")}` → FAIL. Add `("darwin", "x86_64")`
  to `test_platform_key`'s list (the yardl `darwin-x86_64` asset is already pinned).

- [ ] **Step 2: Add the entries** (`rehearse_publish`: `pythons: "3.11 3.15"`, `coexist: false`):

  ```yaml
          - os: macos
            arch: x86_64
            runner: macos-15-intel
            wheel_tag: macosx_11_0_x86_64
            expect: config,openmp,json,hdf5,petsird,itk,parallelproj
            only: ""
  ```

  `macos-15-intel` is native x86_64 (GitHub's last Intel image; it retires in fall 2027).

- [ ] **Step 3: Tests pass, commit, push, watch**

`git commit -am "Build macOS x86_64 wheels on the macos-15-intel runner" && git push fork pip-packaging`
Expected CI: five `...macosx_11_0_x86_64.whl`; rehearsal passes; README row filled.

- [ ] **Step 4: Fallback if `macos-15-intel` is unavailable:** cross-build on `macos-15`. Set `runner: macos-15`,
  keep `arch: x86_64`, and add `CMAKE_OSX_ARCHITECTURES: x86_64` to the deps build step's `env:`. CMake reads
  that variable from the environment, and yardl runs natively on the arm64 host. cibuildwheel tests x86_64
  wheels under Rosetta. Run the rehearsal for this entry on `macos-15` too. Note it in the README, along with
  the 2027 runner retirement.

---

## Self-review notes

- Spec §5.2 (3 CPU platforms × 5 Pythons, feature table rows HDF5/PETSIRD/nlohmann_json/ITK/parallelproj CPU,
  OpenMP runtimes per OS) → Tasks 4–9. §5.4 (deps prefix, static where possible, cached by hash, repair tools)
  → Tasks 1–4 and 7. §5.5 (runners; smoke test proves ITK read, HDF5 read, parallelproj projector)
  → Tasks 6–9. §7 "Later, if needed" (Linux aarch64, macOS x86_64) → appendix A1, A2.
  §5.6 (rehearsal on each platform) → Task 7 plus the platform tasks. §9 (ITK module list, HDF5/ITK pins, macOS
  targets, x86_64 runner) → Task 1, versions.toml, Task 8 (the x86_64 runner strategy: appendix
  A2). Anti-goal (no silent feature loss) →
  configure guard (Task 5), `test_build_features_match_expect` (Task 6) and the Known-gap procedure.
- Names checked against the contract and Phase 1/3: `STIR_DEPS_PREFIX`, `STIR_WHEEL_EXPECT`,
  `STIR_WHEEL_VARIANT`, the `build_deps.py` flags, `wheels-<variant>-<os>-<arch>`, `CHECKS`, `run_stir`,
  `expected_features`, `wheel_hook.cmake`, `parallelproj_cmake_args(variant, versions)`, `.deps/<variant>`.

## Contract concerns

Resolved in the overview's "Cross-plan review (2026-11-12)"; the overview wins where these notes differ.

1. **Dependency names.** The contract lists `hdf5, date, petsird, itk, parallelproj`. Reality needs four more
   `--only` names: `boost` (header copy; replaces Phase 1's `dnf install boost-devel` so all platforms match),
   `nlohmann_json` (a spec feature, and needed by PETSIRD's generated CMake), `xtensor` (xtl + xtensor +
   xtensor-blas, needed by PETSIRD) and `openmp` (macOS-only LLVM libomp). zlib is built inside `hdf5`, and yardl
   is fetched inside `petsird`.
2. **libparallelproj cannot be static** (upstream `add_library(parallelproj SHARED ...)`). Spec §5.4 says
   "static". It is shared and bundled by auditwheel/delocate/delvewheel instead. That is no change for users,
   but `stir.libs/` / `.dylibs/` holds `libparallelproj`.
3. **`STIR_WHEEL_EXPECT` gains `json`** (contract list: `config,openmp,hdf5,petsird,itk,parallelproj,cuda,root`).
   It is also read at **configure** time by `wheel_hook.cmake` to fail fast. And the wheel layout gains
   `stir/_data/build_features.json`. Phase 5's plan proposes a new `stir_wheel_hooks.cmake` with
   `CMAKE_PROJECT_INCLUDE_BEFORE` and a `stir/_build_info.py`. It should extend `wheel_hook.cmake` and
   `build_features.json` (the `root` key already exists) instead.
4. **`build_deps.py` CLI details** the contract leaves open: `--prefix` is not needed with `--cache-key`, cuda
   variants exit 2 until Phase 3, and the key is 16 hex chars. The "prefix complete" marker is
   `<prefix>/.stamps/<name>` (Phase 3 asks for Phase 2's marker).
5. **`STIR_DEPS_PREFIX` is not the same path on host and in the build on Linux** (`$GITHUB_WORKSPACE/.deps/cpu` is
   cached; the container sees `/project/.deps/cpu`). The deps are built in the same pinned image at the same
   in-container path, so CMake configs stay valid.
6. **Rehearsal on macOS/Windows can't use a Docker pypiserver** (spec §5.6 says "container"). Every platform's
   `rehearse_publish` runs `pypiserver` 2.4 as a background Python process with the same arguments. Phase 3's
   Task 9 assumed either shape. This plan keeps one job name, `rehearse_publish`, as a matrix.
7. **Runners differ from the original spec §5.5:** `macos-15` (arm64) instead of `macos-14`, and
   `windows-2025` / `ubuntu-24.04` instead of `-latest`, for reproducibility. (Deferred: `macos-15-intel` native
   instead of cross-build + Rosetta, kept as the appendix A2 fallback.)
8. **Matrix `arch` uses cibuildwheel's names** (Phase 1 passes `CIBW_ARCHS: ${{ matrix.arch }}`), so artifacts
   are `wheels-cpu-windows-AMD64` and `wheels-cpu-macos-arm64`. Phase 4's docs should use these names.
9. **Phase 4's "Features by platform" user table** must take its ✗ cells from this phase's README "Feature status
   by platform" and its Known gaps, not only from spec §5.2.

## References

- conda-forge STIR feedstock (recipe.yaml host deps per platform; build.sh disables HDF5+ITK on osx-arm64 citing
  UCL/STIR#1165; `.ci_support` shows hdf5 1.14.6 and 2.x, libitk-devel 5.4, macOS target 11.0):
  https://github.com/conda-forge/stir-feedstock
- libparallelproj v2.0.7 CMakeLists (`SHARED`, `USE_CUDA`, `BUILD_PYTHON`, `INSTALL_DEVEL`, CMake ≥ 3.31):
  https://github.com/KUL-recon-lab/libparallelproj
- PETSIRD v0.12.2 (yardl model, `cpp/CMakeLists.txt` with `/W3 /WX`, `PETSIRD-0.11` config dir) and yardl 0.6.7
  releases: https://github.com/ETSInitiative/PETSIRD, https://github.com/microsoft/yardl/releases/tag/v0.6.7
- xtensor-blas performance/linking (`-DXTENSOR_USE_FLENS_BLAS` uses its built-in BLAS):
  https://xtensor-blas.readthedocs.io/en/latest/performance.html
- HDF5 1.14.6 `CMakeFilters.cmake` / `hdf5-config.cmake.in` (`ZLIB_USE_LOCALCONTENT`, `HDF5_PACKAGE_EXTLIBS`);
  CMake `FindHDF5.cmake` config-mode `-static` suffix selection via `HDF5_USE_STATIC_LIBRARIES`:
  https://github.com/HDFGroup/hdf5/releases/tag/hdf5_1.14.6
- ITK 5.4 module files (`Modules/IO/GDCM`, `IO/NIFTI`, `IO/NRRD`, `IO/Meta`, `Filtering/ImageGrid`),
  `CMake/ITKGroups.cmake` (`ITKGroup_Core` default ON), Windows 50-char path check:
  https://github.com/InsightSoftwareConsortium/ITK/releases/tag/v5.4.5
- LLVM openmp 21.1.8 standalone build (`LLVM_COMMON_CMAKE_UTILS = ../cmake`, `LIBOMP_*` options):
  https://github.com/llvm/llvm-project/releases/tag/llvmorg-21.1.8
- cibuildwheel v4.3.5 (`pinned_docker_images.cfg` manylinux_2_28 digests 2026.11.01-2; macOS default deployment
  targets; Windows default repair `delvewheel`; commands run with `shell=True`): https://github.com/pypa/cibuildwheel ;
  v4.0.0 / v4.2.0 release notes: https://newreleases.io/project/github/pypa/cibuildwheel/release/v4.0.0 ,
  https://newreleases.io/project/github/pypa/cibuildwheel/release/v4.2.0
- delvewheel README and `_dll_list.py` (`--add-path`; VC-redist DLLs such as `vcomp140.dll` are vendored):
  https://github.com/adang1345/delvewheel
- (Appendix A2) GitHub changelog, macOS 13 closing down and `macos-15-intel` (x86_64 until the macOS 15 image
  retires in fall
  2027): https://github.blog/changelog/2025-09-19-github-actions-macos-13-runner-image-is-closing-down/
- Not verifiable from here: the text of UCL/STIR#1165 (GitHub issue pages and the API were not reachable for that
  repo in this session).
