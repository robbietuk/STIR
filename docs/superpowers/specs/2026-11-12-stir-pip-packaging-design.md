# STIR pip packages: design

Date: 2026-11-12
Status: approved by Robert (revision 4: scope narrowed to a first version, 2026-11-12)

## 1. Intent and why

STIR (Software for Tomographic Image Reconstruction, https://github.com/UCL/STIR, v6.5.0 at time of writing) is a C++ library with a SWIG-generated Python interface. Today researchers can only get a prebuilt Python STIR from conda-forge (`conda install -c conda-forge stir`), or by building from source.

The goal is that researchers can run `pip install` and get STIR, with no conda and no compiler, into whatever pip/venv environment they already use (PyTorch, notebooks, other reconstruction tools). Each platform should get **as much of the conda feature set as is technically possible**.

**Success:** on a clean machine with a supported Python, `pip install stir` (or a CUDA variant) followed by `import stir` works, reads the scanner data the conda build reads, and runs reconstruction. No environment variables to set and nothing to compile.

## 2. Goals, non-goals, anti-goals

**Goals**
- First version: wheels for Linux x86_64, macOS arm64 and Windows x86_64. Linux aarch64 and macOS x86_64 are deferred (§7, "Later, if needed").
- Python 3.11 through 3.15.
- Feature parity with conda-forge wherever the platform allows: core STIR, OpenMP, HDF5 (GE data), PETSIRD, nlohmann_json, ITK image IO, parallelproj (CPU everywhere, CUDA where available), and STIR's own CUDA code.
- GPU builds with CUDA 12 for Linux x86_64 and Windows x86_64. CUDA 13 and Linux aarch64 GPU builds are deferred.
- An sdist, so `pip install` can still build from source on a platform with no wheel.
- A complete, tested build-and-publish pipeline, exercised against a private throwaway package server (§5.6).
- Released in phases. Every phase is a complete, tested result (§7).

**Non-goals**
- **No changes to STIR's C++ code.** This was an explicit decision. All work happens in packaging files, build configuration and CI.
- **Nothing on UCL/STIR during development.** All work lives on a branch of Robert's fork (§5.1).
- **No publishing to PyPI or TestPyPI during development.** The real publish step exists but stays switched off.
- No CUDA on macOS. NVIDIA CUDA doesn't exist there, so macOS gets the CPU build, the same as conda.
- NiftyPET projector. It isn't in the conda build either, and it needs its own CUDA stack.
- MATLAB/Octave bindings.
- Replacing conda-forge. Both stay supported.

**Anti-goals** (would count as failure even if the build technically works)
- A package that installs cleanly but quietly can't read data the conda build can, with no clear message. Every feature left out on a platform must be documented, and if possible STIR should fail with a clear error at the point of use.
- A package that only works with environment variables set, or that breaks when the venv is moved.
- Anything accidentally published to the public PyPI, or pushed to UCL/STIR.

## 3. Constraints (found during recon)

| Area | Finding | Consequence |
|---|---|---|
| Build | CMake ≥ 3.14. SWIG ≥ 4.2 builds one `_stir` module with `-builtin`. Options `BUILD_EXECUTABLES`, `BUILD_TESTING` and `BUILD_SHARED_LIBS` exist. | scikit-build-core can drive it. Static STIR libs link into one extension. |
| Python install | Goes to cache var `PYTHON_DEST` (default `${CMAKE_INSTALL_PREFIX}/python`). Module is `stir/` with `swigstir.py`, `_stir.*` and `extra.py`, plus top-level `stirextra.py`. | Set `PYTHON_DEST` from outside. No CMake edits needed. |
| Config files | `STIR_CONFIG_DIR` and `STIR_DOC_DIR` are absolute paths fixed at compile time, but `get_STIR_config_dir()`/`get_STIR_doc_dir()` (`src/buildblock/find_STIR_config.cxx`) check environment variables of the same name first. | Set the variables at import time from the wheel's own location (§5.3). |
| `-builtin` SWIG | Doesn't work with the Python stable ABI (abi3). | One wheel per Python version (3.11–3.15 means 5 per platform per package). |
| parallelproj | libparallelproj (C++/CUDA) is only on conda-forge, and its docs say it can't be installed with pip. STIR finds it with `find_package(parallelproj CONFIG)`. | We build libparallelproj ourselves. v2.0.7 only builds as a shared library, so it is bundled into the wheel by auditwheel/delocate/delvewheel. |
| ITK | `pip install itk` provides Python wrappings, not C++ headers or CMake config. STIR uses `find_package(ITK CONFIG)`. | We build ITK ourselves, static, with only the modules STIR needs. |
| CUDA on pip | pip can't detect the GPU or CUDA version. | Separate package per CUDA major version (§4). |
| ROOT | Used only to read GATE output (4 source files). Official `root` wheel on PyPI is alpha (0.1a12). ROOT includes the Cling/LLVM interpreter (hundreds of MB). conda has no ROOT on Windows. | Deferred to the last phase; depend on official `root` wheel, don't bundle (§7, Phase 5). |
| Python 3.15 | Released October 2026. | Check NumPy and cibuildwheel 3.15 support first; if either is missing, 3.15 wheels wait for it without blocking others. |
| Fork | `robbietuk/STIR` is a public fork (GitHub doesn't allow private forks of public repos). It has no release tags. Existing workflows: `build-test.yml`, `cffconvert.yml`, `pre-commit-check.yml`. | Public-repo Actions minutes are free. Upstream workflows will also run on pushes to the branch (§5.5). |

## 4. Approaches considered

How the different builds (CPU, CUDA 12, CUDA 13) reach users:

- **A. A separate package name per configuration (the CuPy model). CHOSEN.** `stir` = CPU build on all platforms. `stir-cuda12` = same features plus GPU, on Linux and Windows (`stir-cuda13` later, same pattern). All provide `import stir`.
  *Pro:* proven pattern researchers know, and no STIR C++ changes.
  *Con:* installing two variants in one environment makes them overwrite each other, so the docs must warn about it.
- **B. One `stir` package plus a GPU plugin wheel (`stir[cuda12]`).** Cleanest for users and no conflicts, but STIR's parallelproj projector would have to become a runtime-loaded plugin, a C++ change. Rejected for now; possible later.
- **C. One package name, separate package servers per CUDA version (the PyTorch model).** Would need our own hosted servers, and researchers often get the URL wrong. Rejected.

Robert chose **A** because it needs no changes to STIR's code.

## 5. The design

### 5.1 Where the work lives
All work goes on a branch of Robert's fork, **`robbietuk/STIR`**, on branch **`pip-packaging`** *(my call on the name)*. The branch starts from upstream release tag **`rel_6.5.0`** *(my call: a release is a stable base; the packaging then tracks STIR releases)*. When STIR releases, the new tag is merged into the branch.

Nothing is pushed to UCL/STIR. If Robert later wants to propose this upstream, the branch can become a PR as-is, since it only adds packaging files.

New files on the branch (none of them C++):
- `pyproject.toml` (repo root, so `pip install .` works on a STIR checkout)
- `packaging/pip/`: dependency build scripts, cibuildwheel config, variant templating, local-index test scripts and README
- `.github/workflows/wheels.yml`
- `docs/superpowers/specs/` and `docs/superpowers/plans/`: this design and the plan

Python edits: `src/swig/python/stir/__init__.py` gains a few lines in Phase 1 (config dirs, §5.3), Phase 3 (CUDA loader) and Phase 5 (ROOT support). The exact allowed lines are listed in the plans overview, and a Phase 4 check enforces them. Two CMake hook files under `packaging/pip/cmake/` are loaded through CMake's `CMAKE_PROJECT_STIR_INCLUDE`; no STIR CMake file is edited. *(My call: editing it directly on the branch is simpler and safer than shipping an overlay copy. It's Python glue, not STIR's C++.)*

### 5.2 Packages and platform matrix

First version:

| Package | Linux x86_64 | macOS arm64 | Windows x86_64 |
|---|---|---|---|
| `stir` (CPU) | ✓ | ✓ | ✓ |
| `stir-cuda12` | ✓ | — | ✓ |

Python 3.11, 3.12, 3.13, 3.14 and 3.15 for each. Linux uses `manylinux_2_28`. That's 3 CPU platforms × 5 Pythons = 15 wheels, plus 2 CUDA platforms × 5 Pythons = 10 wheels: 25 wheels per build.

CUDA 12 was chosen over 13 *(my call; Robert did not object)*: CUDA 13 drops GPUs before Turing (sm_75) and needs NVIDIA driver 580+, which shared university clusters often lack.

Deferred, same design, mostly CI configuration when added: Linux aarch64 (`stir` and CUDA sbsa), macOS x86_64, `stir-cuda13`.

Feature contents per package:

| Feature | `stir` | `stir-cudaXX` | Notes |
|---|---|---|---|
| Core STIR + SWIG Python API | ✓ | ✓ | |
| OpenMP | ✓ | ✓ | libgomp (Linux), libomp (macOS) and vcomp (Windows) bundled by the repair tools |
| HDF5, PETSIRD, nlohmann_json | ✓ | ✓ | HDF5 and PETSIRD built static |
| ITK image IO | ✓ | ✓ | ITK static, IO modules only |
| parallelproj (CPU) | ✓ | ✓ | libparallelproj shared, bundled in the wheel |
| parallelproj (CUDA) + STIR CUDA code | — | ✓ | |
| ROOT / GATE input | Phase 5 | Phase 5 | Linux and macOS only |
| NiftyPET | — | — | Non-goal |

Package names: *my call* is `stir` and `stir-cuda12` (and `stir-cuda13` if added later). Because nothing is published during development, the names only matter later. Checking whether they're free on PyPI is a task before any eventual real release.

### 5.3 Making the wheel self-contained (no environment variables)
- scikit-build-core sets `PYTHON_DEST=${SKBUILD_PLATLIB_DIR}` so `stir/` lands at the top level of the wheel.
- STIR's install rules put the config JSON files under `${CMAKE_INSTALL_PREFIX}/share/<STIR-version>/config`. The packaging puts them into `stir/_data/config` (and docs/examples into `stir/_data/doc`). *(Builder decides the exact mechanism: scikit-build-core install-dir settings, `wheel.exclude`, or a small install step.)*
- `src/swig/python/stir/__init__.py` gains, before the existing import: `STIR_CONFIG_DIR` set to `<package dir>/_data/config` unless the user already set it to a non-empty value (an empty value counts as unset), and the same for `STIR_DOC_DIR`, guarded so it only applies when that `_data` folder exists. A conda or source install is then unchanged. A user's own non-empty setting still takes priority.
- Headers, static libs, CMake config and executables are excluded from the wheel (`BUILD_EXECUTABLES=OFF`, `BUILD_TESTING=OFF`, `BUILD_SHARED_LIBS=OFF`, plus `wheel.exclude` patterns).

### 5.4 Native dependencies ("deps prefix")
Every compiled dependency is built from source, static where possible, into a per-platform prefix. That prefix is cached in CI, keyed by a hash of the dependency versions and build scripts, so a normal STIR build doesn't rebuild them.

| Dependency | How | Version pin (initial) |
|---|---|---|
| Boost headers, nlohmann_json, fmt | headers only (fmt is a STIR submodule) | match STIR's `build_environment.yml` |
| HDF5 | static, C and C++ libs | same major/minor as conda-forge's STIR build |
| PETSIRD (+ howardhinnant date) | static | `0.12.2` (as in `build_environment.yml`) |
| ITK | static, `ITK_BUILD_DEFAULT_MODULES=OFF`, only the IO and core modules STIR's ITK code uses | ≥ 5.4 |
| libparallelproj | shared (v2.0.7 can't build static), bundled by the repair tools. CPU build for `stir`; CUDA build for `stir-cudaXX` | `2.x` (as in `build_environment.yml`) |
| CUDA toolkit (variants only) | build-time only. At runtime the wheel depends on NVIDIA's pip packages (`nvidia-cuda-runtime-cu12` etc.) instead of bundling the runtime | 12.x, 13.x |

The repair tools (auditwheel, delocate and delvewheel) bundle any remaining shared libraries and check manylinux compliance. The CUDA driver (`libcuda`) is never bundled.

CUDA architecture list: *my call* is the main architectures from Volta (sm_70) through current, plus PTX for the newest so future GPUs still work. Narrow the list if wheels go over the PyPI per-file size limit (100 MB by default), since that limit applies on any eventual real release.

### 5.5 Build and CI
- `pyproject.toml`: scikit-build-core backend. Build requirements: `scikit-build-core`, `swig>=4.2` (from PyPI), `numpy>=2` (wheels then work with NumPy ≥ 1.24 at runtime), `cmake`, `ninja`. Version is read from STIR's `VERSION.txt`, plus a `.devN` suffix for development builds so they can never be confused with a real release.
- CUDA variants use the same `pyproject.toml`. The package name and CUDA flags are switched by a build-time setting (e.g. an environment variable read by a small templating step), so there's one source of truth.
- `.github/workflows/wheels.yml` runs on the fork only: on push to `pip-packaging` and on manual trigger. *(My call: it also checks `github.repository == 'robbietuk/STIR'` so it can never run on UCL/STIR if the branch is ever proposed upstream.)*
- Upstream's `build-test.yml` does **not** run on pushes to `pip-packaging` (its push trigger lists other branches). Upstream's `pre-commit-check.yml` does run on every push; how to handle its markdown line-length rule on our docs is an open question for Robert (see plans overview).
- Runners are pinned per job (see plans overview); CUDA builds on Windows use `windows-2022` for CUDA 12.9 / Visual Studio compatibility.
- cibuildwheel runners: `ubuntu-24.04` (x86_64), `macos-15` (arm64) and `windows-2025` (CPU); CUDA Windows builds use `windows-2022` (see plans overview). Deferred platforms would add `ubuntu-24.04-arm` and `macos-15-intel`. CUDA variants install the toolkit in the build container (Linux) or via the NVIDIA installer (Windows).
- Tests: cibuildwheel runs STIR's own `src/swig/test/python` pytest suite against each installed wheel. A smoke test checks that config files are found and that each enabled feature is available (ITK read, HDF5 read, parallelproj projector constructs). GPU wheels run CPU-side tests in CI. GPU execution is tested by hand on a real GPU at the end of Phase 3, since GitHub's free runners have no GPU.
- An sdist is also built (including git submodules).

### 5.6 Publishing during development (no public pip)
- **Wheels as CI artifacts.** Every run uploads its wheels and sdist as GitHub Actions artifacts. Robert can download them and install with `pip install --find-links <folder> stir`.
- **Rehearsing the publish step against a throwaway private server.** A final CI job starts `pypiserver` as a background process inside the job (macOS and Windows runners have no Docker), uploads every wheel with `twine` (exactly as a real publish would), then creates fresh venvs on each platform and runs `pip install --index-url http://localhost:8080/simple/ stir` and the smoke test. The server is destroyed when the job ends. This exercises upload, metadata, package names and dependency resolution with nothing going public.
- **A local version of the same thing.** `packaging/pip/local-index.sh` runs the same `pypiserver` on Robert's machine, so he can test installs against downloaded artifacts.
- **Real publishing exists but is off.** The workflow has a `publish` job targeting PyPI via trusted publishing, but it only runs on manual trigger with an explicit `target: pypi` input, and is disabled (`if: false`) until Robert decides to release. TestPyPI is not used.

## 6. Upstream (later, Robert's call)
During development, nothing goes to UCL/STIR and nobody upstream is involved. When Robert is ready, two things are worth raising with the STIR maintainers (Kris Thielemans et al.; open issue #5 "Installing the python bindings" is a natural place): whether the packaging should go upstream, and who holds the PyPI name. Separately, Georg Schramm (libparallelproj) may be willing to publish libparallelproj wheels, which would let us drop our own build of it.

## 7. Phases (each one a complete, tested result)
1. **Skeleton:** CPU, Linux x86_64 only, Python 3.11–3.15, core STIR + OpenMP. Proves scikit-build-core, the self-contained config fix (§5.3), tests, CI artifacts and the throwaway-server publish rehearsal (§5.6).
2. **CPU on the three first-version platforms + full CPU features:** deps prefix with HDF5, PETSIRD, ITK and libparallelproj CPU. Linux x86_64 first, then macOS arm64, then Windows x86_64.
3. **CUDA 12 variant:** `stir-cuda12` on Linux x86_64, then Windows x86_64. Manual GPU test.
4. **Release readiness:** merge-a-new-STIR-release procedure, README/docs (which package, features by platform, the "don't install two variants" warning, when to use conda instead), PyPI name check, and the switched-off real publish job reviewed and ready.
5. **ROOT (Linux and macOS):** when the official `root` wheel is stable, build against it and declare it as a dependency. Until then, GATE users are pointed to conda.

**Later, if needed** (not part of the first version; each is an additive change): Linux aarch64 (CPU and CUDA sbsa), macOS x86_64, `stir-cuda13`.

## 8. Decided by Robert
- Audience: researchers who want pip instead of conda.
- Scope: as close to the conda build as possible, including ITK and GPU parallelproj. The full five-platform, two-CUDA scope was judged too large for one person, so the first version is Linux x86_64, macOS arm64 and Windows x86_64 for `stir`, plus CUDA support (`stir-cuda12`) on Linux x86_64 and Windows x86_64.
- ROOT: include if feasible, with its impact understood. Planned as Phase 5, depending on the official wheel rather than bundling.
- Approach A: separate packages per configuration, and no changes to STIR's C++ code.
- All work on a branch of his fork `robbietuk/STIR`, not on UCL/STIR.
- No publishing to pip during development. Use a private/mock publishing route instead.
- Python 3.11 through 3.15.

## 9. Left to the builder
- Exact ITK module list (derive from the ITK headers STIR includes).
- Exact mechanism for placing `share/` data into `stir/_data` (§5.3).
- CUDA architecture list tuning against wheel size.
- macOS deployment targets, and the macOS x86_64 runner strategy.
- HDF5/ITK exact version pins (match conda-forge's STIR build).
