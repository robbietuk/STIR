# STIR pip Phase 5: ROOT / GATE Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the Linux and macOS wheels read GATE/ROOT listmode data (`.hroot` + `.root`). They do this by
compiling against the official `root` wheel from PyPI and depending on it at runtime, without bundling it. This only
happens if that wheel passes an explicit go/no-go gate. Otherwise the documented outcome is "ROOT stays off", and the
gate is re-checked on every STIR release.

**Architecture:** STIR already supports ROOT through its own build files. `CMakeLists.txt:145-151` calls
`find_package(CERN_ROOT 6.28.00)`, which uses `src/cmake/FindCERN_ROOT.cmake`. That module runs
`find_package(ROOT CONFIG)` via `ROOT_DIR` and then calls `UseCXX(${CERN_ROOT_CXX_STANDARD})`, which raises STIR's
C++ standard to ROOT's. When ROOT is found, `HAVE_CERN_ROOT` adds five sources:
- `src/IO/InputStreamFromROOTFile{,ForCylindricalPET,ForECATPET}.cxx`;
- `src/listmode_buildblock/CListModeDataROOT.cxx` and `CListRecordROOT.cxx`.

Those sources link `ROOT::Tree` (`src/IO/CMakeLists.txt:102-109`) and register the `.hroot` format in
`src/IO/IO_registries.cxx:108-112`. No STIR file changes. Phase 1's project hook
`packaging/pip/cmake/wheel_hook.cmake` (injected via `CMAKE_PROJECT_STIR_INCLUDE`) gains a ROOT block that:
- sets `ROOT_DIR` from the `root` distribution installed in the isolated build environment;
- adds a relative install RPATH to ROOT's library directory.

Whether ROOT was actually found is already recorded by Phase 2's `stir/_data/build_features.json` (`root` key) and
enforced by its configure guard when `STIR_WHEEL_EXPECT` contains `root`.

The wheel repair tools are told to leave ROOT's libraries out. The `root` dependency is declared with
Linux/macOS environment markers. Windows builds set `DISABLE_CERN_ROOT=ON`, and reading a `.hroot` file there raises
a clear Python error.

**Tech Stack:** scikit-build-core (`cmake.define`, `overrides`), CMake ≥ 3.19 (`cmake_language(DEFER)`), cibuildwheel,
auditwheel/delocate, `importlib.metadata`, `packaging`, `uproot` (test-only, writes ROOT files without Cling),
pytest.

**Spec:** `docs/superpowers/specs/2026-11-12-stir-pip-packaging-design.md` (§3 ROOT row, §5.2 "ROOT / GATE input",
§7 Phase 5). The shared names come from `docs/superpowers/plans/2026-11-12-stir-pip-00-overview.md`.

## Global Constraints

- No changes to any STIR C++ file (`*.cxx`, `*.h`, `*.inl`, `*.cu`) or STIR `CMakeLists.txt`/`*.cmake`.
  `python packaging/pip/release_check.py check` (Phase 4) must stay `OK`.
- ROOT is **not bundled**. Wheels depend on the official `root` wheel, pinned as `root==X.Y.*`, on Linux and macOS
  only. Windows wheels have no ROOT (conda has none on Windows either) and must say so at the point of use.
- ROOT's C++ standard decides STIR's (`UseCXX(${CERN_ROOT_CXX_STANDARD})`). STIR has been tested with 17 and 20.
- STIR needs ROOT ≥ 6.28.00 (`CMakeLists.txt:146`).
- Platforms and Python versions are as in §5.2: Linux x86_64/aarch64 (`manylinux_2_28`), macOS arm64/x86_64,
  Python 3.11–3.15. Windows x86_64 has no ROOT.
- Feature name in `STIR_WHEEL_EXPECT`: `root` (contract). It gets a `CHECKS["root"]` entry in the smoke test.
- The only `__init__.py` change is the overview's two Phase 5 lines (already on Phase 4's allow-list).
- One CMake hook (`wheel_hook.cmake`) and one build-features record (`build_features.json`); no new hook file.
- Never publish. Never push to `UCL/STIR`. Pushes go to `fork` only, after Robert's go-ahead for this phase.

## Review Focus

1. **`import stir` on a machine with no C++ compiler.** ROOT's Cling needs system headers at startup. The CHEP 2024
   wheel slides report `import ROOT` failing without `g++`. Users expect `import stir` and a `.hroot` read to work on
   a bare machine. (Task 6: `rehearse_publish` runs the root smoke test in `python:3.12-slim`.)
2. **ROOT libraries copied into the stir wheel.** Two copies of `libCore` in one process (one copy from `import ROOT`)
   would crash or misbehave. (Task 4: `test_root_libs_not_bundled`, `test_import_root_then_stir_reads_gate_file`.)
3. **Moved venv or no `LD_LIBRARY_PATH`.** ROOT libraries must be found through a relative RPATH, never through
   environment variables. (Task 4: `check_root`, run as `test_expected_feature[root]`, uses a subprocess with
   `LD_LIBRARY_PATH` and `DYLD_LIBRARY_PATH` removed.)
4. **A `.hroot` file read on a build without ROOT.** This covers Windows, and any platform where the gate fails.
   STIR's own error ("no file format found that can read file") does not tell the user why. (Task 5:
   `test_root_absent_gives_clear_message`.)
5. **CUDA variants losing the `root` dependency** when `prepare_build.py` rewrites dependencies for `cuda12`/`cuda13`.
   (Task 3: `test_cuda_variants_keep_root_dependency`.)

---

## Findings from the investigation (2026-11-12)

- `root` on PyPI: latest is **0.1a12** (pre-release, 2026-05-20). Its only wheels are
  `manylinux_2_28_x86_64` for cp310–cp314. There are no macOS, aarch64 or cp315 wheels. ROOT's release notes call
  pip installs "alpha mode … on Linux". CERN staff on the ROOT forum: "I wouldn't suggest using it for production just
  yet." A PyHEP.dev talk (8 Sep 2026) reports that the wheels are still under development. No source documents
  headers or `ROOTConfig.cmake` in the wheel. The wheel's version scheme (`0.1aN`) is not ROOT's (`6.xx`).
  **Expected gate result today: NO-GO.**
- `FindCERN_ROOT.cmake:48-50` contains `set(ROOT_DIR:PATH ${ROOTSYS}/cmake)`. This sets a variable literally named
  `ROOT_DIR:PATH`, so `ROOTSYS` does **not** reach `find_package(ROOT)`. Pass `ROOT_DIR` itself.
- Python already has what it needs: `stir.ListModeData.read_from_file(path)` (`src/swig/stir_listmode.i:43-50`).
  `src/swig/test/python/test_listmode.py` reads `recon_test_pack/root_header.hroot` + `test_PET_GATE.root` (10 MB)
  but *silently returns* when ROOT is missing, so it cannot serve as a feature check.
- GATE Cylindrical PET reader (`InputStreamFromROOTFile.cxx:135-142`, `…ForCylindricalPET.cxx:206-213`). It needs a
  TTree, named via `name of input TChain`, with these branches:
  - `time1`, `time2` (double);
  - `eventID1/2`, `comptonPhantom1/2`, `crystalID1/2`, `submoduleID1/2`, `moduleID1/2`, `rsectorID1/2` (int32);
  - `energy1`, `energy2` (float).
- ROOT-dependent STIR tests (`src/test/test_time_of_flight.cxx`, `src/recon_test/CMakeLists.txt:48+`,
  `recon_test_pack/run_root_GATE.sh`) need executables, which wheels do not build (`BUILD_EXECUTABLES=OFF`).

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `packaging/pip/root_gate.py` | Create | Evaluate the go/no-go criteria against PyPI metadata and, optionally, one wheel |
| `packaging/pip/tests/test_root_gate.py` | Create | Gate logic on fixture metadata and fake wheels |
| `packaging/pip/RELEASING.md` | Modify | Gate re-check step and gate log |
| `packaging/pip/README.md` | Modify | ROOT row and GATE guidance |
| *(GO only)* `packaging/pip/find_root_cmake_dir.py` | Create | Locate `ROOTConfig.cmake` and ROOT's lib dir in an installed `root` distribution, without importing ROOT |
| *(GO only)* `packaging/pip/cmake/wheel_hook.cmake` | Modify (Phase 1/2) | ROOT block: set `ROOT_DIR`, add relative RPATH |
| *(GO only)* `pyproject.toml` | Modify | `root` build and runtime requirement with markers, hook define, Windows override, repair excludes |
| *(GO only)* `packaging/pip/deps/versions.toml` | Modify | `[root]` pin |
| *(GO only)* `src/swig/python/stir/_root_support.py` | Create | `root_built()`, `install_root_hint()`: clear error for `.hroot` reads without ROOT |
| *(GO only)* `src/swig/python/stir/__init__.py` | Modify | The overview's two Phase 5 lines, after the swigstir import |
| *(GO only)* `packaging/pip/tests/test_root_packaging.py` | Create | Pins, markers, overrides, `find_root_cmake_dir` |
| *(GO only)* `packaging/pip/tests/test_root_support.py` | Create | Hint logic with fake classes |
| *(GO only)* `packaging/pip/tests/test_wheel_smoke.py` | Modify | `root` feature tests |
| *(GO only)* `.github/workflows/wheels.yml` | Modify | `root` in `STIR_WHEEL_EXPECT`, macOS x86_64 runner, no-compiler check |

---

### Task 1: The go/no-go gate (`root_gate.py`)

**Files:**
- Create: `packaging/pip/root_gate.py`
- Test: `packaging/pip/tests/test_root_gate.py`

**Interfaces:**
- Produces:
  - `REQUIRED_PYTHONS = ("cp311", "cp312", "cp313", "cp314", "cp315")`
  - `REQUIRED_TARGETS = ("manylinux_x86_64", "manylinux_aarch64", "macosx_arm64", "macosx_x86_64")`
  - `MAX_GLIBC = (2, 28)`, `MIN_ROOT = Version("6.28")`, `OK_CXX = {17, 20}`
  - `@dataclass class Criterion: id: str; status: Literal["PASS","FAIL","SKIP","MANUAL"]; detail: str`
  - `wheel_targets(filename: str) -> set[tuple[str, str]]`: `{(python_tag, target)}`. Uses
    `packaging.utils.parse_wheel_filename`. `universal2` counts as both macOS targets, and `manylinux_2_N` counts
    only if `(2, N) <= MAX_GLIBC`.
  - `inspect_wheel(path: Path) -> dict`: keys `cmake_dir`, `headers` (set of found basenames), `libs` (set of found
    library stems), `cxx_standard: int | None`, `root_release: str | None`. It reads zip member names, plus the
    contents of `ROOTConfig.cmake` and `RVersion.h` only.
  - `evaluate(meta: dict, wheel: dict | None) -> list[Criterion]`. `meta` is the PyPI JSON
    (`info.version`, `urls[].filename`).
  - `main(argv=None) -> int`
  - CLI: `root_gate.py [--version V] [--json-file F] [--inspect-wheel | --wheel-file W]`.
    - Exit codes: 0 = GO (all automatic criteria pass), 1 = NO-GO, 2 = bad arguments, 3 = network error.
    - The last line is `RESULT: GO`, or `RESULT: NO-GO (<failing ids>)`.

Criteria:

| Id | Check | How |
|---|---|---|
| G1 | Latest `root` is a final release, numbered as ROOT itself (`major >= 6`) and `>= 6.28` | `Version(info.version)`: not `is_prerelease`, not `is_devrelease` |
| G2 | A wheel for every `REQUIRED_PYTHONS` × `REQUIRED_TARGETS` pair | union of `wheel_targets` over `urls` |
| G3 | The wheel has `ROOTConfig.cmake`, `TTree.h`, `TChain.h`, `TFile.h`, `RVersion.h` and libs `Core`, `RIO`, `Tree` | `inspect_wheel`; SKIP without `--inspect-wheel` or `--wheel-file` |
| G4 | `set(ROOT_CXX_STANDARD N)` in `ROOTConfig.cmake` with `N in OK_CXX` | regex `set\(ROOT_CXX_STANDARD\s+(\d+)\)` |
| M1 | `import ROOT` works with no C++ compiler | MANUAL; print the command below |
| M2 | The PyPI page and ROOT release notes no longer call it alpha or "not for production" | MANUAL; print both URLs |

`--inspect-wheel` downloads the `cp312` `manylinux_2_28_x86_64` file from `urls` into a new empty temp dir. It only
reads the zip; nothing is extracted or executed.

The M1 command:
`docker run --rm python:3.12-slim sh -c 'pip install "root==<V>" && python -c "import ROOT; print(ROOT.gROOT.GetVersion())"'`
Expected output: the ROOT version and no compiler error.

- [ ] **Step 1: Write the failing tests**

```python
TODAY = {"info": {"version": "0.1a12"},
         "urls": [{"filename": f"root-0.1a12-{p}-{p}-manylinux_2_28_x86_64.whl"} for p in
                  ("cp310", "cp311", "cp312", "cp313", "cp314")]}

def _full(version="6.40.2", plat_override=None):    # one wheel per REQUIRED_PYTHONS x 4 platform tags
    ...

def test_today_is_no_go():
    crit = {c.id: c for c in evaluate(TODAY, None)}
    assert crit["G1"].status == "FAIL" and "pre-release" in crit["G1"].detail
    assert crit["G2"].status == "FAIL" and "missing 16 of 20" in crit["G2"].detail
    assert crit["G3"].status == crit["G4"].status == "SKIP"

def test_complete_final_release_passes_g1_g2():
    crit = {c.id: c for c in evaluate(_full(), None)}
    assert crit["G1"].status == crit["G2"].status == "PASS"

def test_too_new_glibc_does_not_count():
    assert wheel_targets("root-6.40.2-cp312-cp312-manylinux_2_34_x86_64.whl") == set()

def test_universal2_counts_for_both_macos():
    assert wheel_targets("root-6.40.2-cp312-cp312-macosx_11_0_universal2.whl") == {
        ("cp312", "macosx_arm64"), ("cp312", "macosx_x86_64")}

def test_old_root_fails_g1():
    assert {c.id: c for c in evaluate(_full("6.26.0"), None)}["G1"].status == "FAIL"

def test_inspect_wheel_reads_cxx_standard(tmp_path):     # zip with ROOT/cmake/ROOTConfig.cmake, include/*.h, lib/lib*.so
    w = make_fake_wheel(tmp_path, cxx=20, release="6.40/02")
    info = inspect_wheel(w)
    assert info["cxx_standard"] == 20 and info["root_release"] == "6.40/02"
    assert {"Core", "RIO", "Tree"} <= info["libs"]

def test_cxx23_fails_g4(tmp_path):
    crit = {c.id: c for c in evaluate(_full(), inspect_wheel(make_fake_wheel(tmp_path, cxx=23)))}
    assert crit["G4"].status == "FAIL"

def test_missing_cmake_config_fails_g3(tmp_path):
    crit = {c.id: c for c in evaluate(_full(), inspect_wheel(make_fake_wheel(tmp_path, cmake=False)))}
    assert crit["G3"].status == "FAIL" and "ROOTConfig.cmake" in crit["G3"].detail

def test_cli_today_exit_1(tmp_path, capsys):
    f = tmp_path / "root.json"; f.write_text(json.dumps(TODAY))
    assert main(["--json-file", str(f)]) == 1
    assert capsys.readouterr().out.strip().splitlines()[-1] == "RESULT: NO-GO (G1, G2)"
```

- [ ] **Step 2: Run the tests and check they fail**

Run: `python -m pytest packaging/pip/tests/test_root_gate.py -v`
Expected: `ModuleNotFoundError: No module named 'root_gate'`.

- [ ] **Step 3: Implement `packaging/pip/root_gate.py`**

Use stdlib `urllib.request` plus `packaging`, and no other dependencies. Fetch `https://pypi.org/pypi/root/json`,
or `https://pypi.org/pypi/root/<V>/json` with `--version`. A network failure exits 3 with
`cannot reach pypi.org; download the JSON in a browser and use --json-file`. M1 and M2 are always printed as MANUAL
with their commands and URLs. They never change the exit code; Task 2 records them by hand.

- [ ] **Step 4: Run the tests, then run the gate for real**

Run: `python -m pytest packaging/pip/tests/test_root_gate.py -v`
Expected: all PASS.

Run: `python packaging/pip/root_gate.py --inspect-wheel`. If pypi.org is blocked, save
`https://pypi.org/pypi/root/json` from a browser and use `--json-file`.
Expected today: G1 FAIL (`0.1a12 is a pre-release`), G2 FAIL, last line `RESULT: NO-GO (G1, G2, …)`, exit 1.
Copy the full output into the Task 2 gate log.

- [ ] **Step 5: Commit**

```bash
git add packaging/pip/root_gate.py packaging/pip/tests/test_root_gate.py
git commit -m "Add ROOT wheel go/no-go gate script"
```

---

### Task 2: Record the decision (always done; ends the phase on NO-GO)

**Files:**
- Modify: `packaging/pip/RELEASING.md`: add to `## Re-check on every STIR release`, and add a `## ROOT gate log` section
- Modify: `packaging/pip/README.md`: the ROOT row and the conda section
- Test: `packaging/pip/tests/test_docs.py` (Phase 4)

**Interfaces:**
- Consumes: the `root_gate.py` CLI (Task 1); the Phase 4 RELEASING/README headings.
- Produces: the gate log table `| Date | root version | Result | Failing criteria | M1 | M2 |`.

- [ ] **Step 1: Write the failing test** (add to `test_docs.py`)

```python
def test_root_gate_in_release_checklist():
    text = RELEASING.read_text()
    checklist = text.split("## Re-check on every STIR release")[1].split("\n## ")[0]
    assert "python packaging/pip/root_gate.py --inspect-wheel" in checklist
    assert "\n## ROOT gate log\n" in text and "| Date | root version | Result |" in text

def test_readme_points_gate_users_somewhere():
    text = README.read_text()
    assert "GATE" in text and "conda install -c conda-forge stir" in text
```

- [ ] **Step 2: Run the tests and check they fail**

Run: `python -m pytest packaging/pip/tests/test_docs.py -v -k "root_gate or gate_users"`
Expected: `test_root_gate_in_release_checklist` FAILS.

- [ ] **Step 3: Edit the docs**

- RELEASING checklist item: "Run `python packaging/pip/root_gate.py --inspect-wheel` (and the printed M1/M2 manual
  checks). Add a row to the ROOT gate log. If the result changes to GO, execute Tasks 3–6 of
  `docs/superpowers/plans/2026-11-12-stir-pip-05-root.md`."
- Gate log first row: `| 2026-11-12 | 0.1a12 | NO-GO | G1, G2 (<G3/G4 as observed>) | not run | fails (alpha) |`.
- **On NO-GO**, the README ROOT row stays "not yet (conda)" for Linux/macOS and "—" for Windows. Add one sentence
  under "When to use conda instead": "Reading GATE output needs ROOT, which the pip packages do not include yet. The
  official `root` pip package is still an alpha (checked 2026-11-12). Use `conda install -c conda-forge stir` on Linux
  or macOS."

- [ ] **Step 4: Run the tests and the linter**

Run: `python -m pytest packaging/pip/tests/test_docs.py -v && pre-commit run pymarkdown --files packaging/pip/README.md packaging/pip/RELEASING.md`
Expected: all PASS.

- [ ] **Step 5: Commit, then stop on NO-GO**

```bash
git add packaging/pip/RELEASING.md packaging/pip/README.md packaging/pip/tests/test_docs.py
git commit -m "Record ROOT wheel gate result and re-check step"
```

**If the result is NO-GO, Phase 5 is complete here.** Report the gate output to Robert. Tasks 3–6 run only after a
later gate run prints `RESULT: GO` *and* M1 and M2 pass *and* Robert confirms.

---

### Task 3 (GO only): Find ROOT at build time

**Files:**
- Create: `packaging/pip/find_root_cmake_dir.py`
- Modify: `packaging/pip/cmake/wheel_hook.cmake`, `pyproject.toml`, `packaging/pip/deps/versions.toml`,
  `packaging/pip/tests/test_ci_config.py` (Phase 2's `test_disable_switches`)
- Test: `packaging/pip/tests/test_root_packaging.py`

**Interfaces:**
- Consumes: `prepare_build.py --variant {cpu,cuda12,cuda13}` (contract; the `# prepare_build: dependencies` line);
  versions.toml (contract); `wheel_hook.cmake` and `build_features.json` (Phases 1–2).
- Produces:
  - `@dataclass RootLayout: site_dir: Path; cmake_dir: Path; lib_dir: Path`
  - `find_root_layout(search_path: list[str] | None = None) -> RootLayout`. It uses
    `importlib.metadata.distributions(name="root", path=search_path)` and the dist's `files`. It never imports ROOT.
    It raises `LookupError("root distribution not installed")` or `LookupError("ROOTConfig.cmake not found in root distribution")`.
  - CLI: `find_root_cmake_dir.py {--cmake-dir | --lib-dir | --lib-dir-relative | --auditwheel-excludes}`.
    - `--lib-dir-relative` is the lib dir relative to `site_dir`.
    - `--auditwheel-excludes` prints `--exclude <soname>` for every `lib*.so*` in `lib_dir`, space-separated.
    - Exits 1 with the `LookupError` text on stderr.
  - versions.toml `[root] pin = "X.Y.*"` (from the GO gate run), plus `gate_checked = "YYYY-MM-DD"`.
  - Requirement string `ROOT_REQ = "root==X.Y.*; sys_platform == 'linux' or sys_platform == 'darwin'"`, in both
    `[build-system].requires` and `[project].dependencies` (the single-line array Phase 3's `prepare_build.py`
    rewrites; it keeps `root`).

- [ ] **Step 1: Write the failing tests**

```python
def test_root_pin_matches_versions_toml():
    pin = tomllib.loads(VERSIONS.read_text())["root"]["pin"]
    py = tomllib.loads(PYPROJECT.read_text())
    for reqs in (py["build-system"]["requires"], py["project"]["dependencies"]):
        (r,) = [Requirement(s) for s in reqs if Requirement(s).name == "root"]
        assert str(r.specifier) == f"=={pin}"
        assert r.marker.evaluate({"sys_platform": "linux"}) and r.marker.evaluate({"sys_platform": "darwin"})
        assert not r.marker.evaluate({"sys_platform": "win32"})

@pytest.mark.parametrize("variant", ["cuda12", "cuda13"])
def test_cuda_variants_keep_root_dependency(tmp_path, variant):
    # copy pyproject.toml + VERSION.txt to tmp_path; run prepare_build.py --variant V --pyproject tmp/pyproject.toml
    deps = tomllib.loads((tmp_path / "pyproject.toml").read_text())["project"]["dependencies"]
    assert any(Requirement(d).name == "root" for d in deps)

def test_windows_disables_root_and_hook_is_set():
    sk = tomllib.loads(PYPROJECT.read_text())["tool"]["scikit-build"]
    assert sk["cmake"]["define"]["CMAKE_PROJECT_STIR_INCLUDE"] == "packaging/pip/cmake/wheel_hook.cmake"
    assert sk["cmake"]["define"]["DISABLE_CERN_ROOT"] == "OFF"
    win = [o for o in sk["overrides"] if o.get("if", {}).get("platform-system") == "^win32$"]
    assert any(o.get("cmake", {}).get("define", {}).get("DISABLE_CERN_ROOT") == "ON" for o in win)

def test_find_root_layout_fake_dist(tmp_path):
    make_fake_dist(tmp_path, files=["ROOT/cmake/ROOTConfig.cmake", "ROOT/lib/libCore.so", "ROOT/lib/libTree.so"])
    lay = find_root_layout([str(tmp_path)])
    assert lay.cmake_dir == tmp_path / "ROOT/cmake" and lay.lib_dir == tmp_path / "ROOT/lib"

def test_find_root_layout_missing(tmp_path):
    with pytest.raises(LookupError, match="root distribution not installed"):
        find_root_layout([str(tmp_path)])
```

`make_fake_dist` writes `root-6.40.2.dist-info/{METADATA,RECORD}` and the listed files. Search for the lib dir as
"the directory of the file whose name starts with `libCore.`".

- [ ] **Step 2: Run the tests and check they fail**

Run: `python -m pytest packaging/pip/tests/test_root_packaging.py -v`
Expected: FAIL (`KeyError: 'root'` / `ModuleNotFoundError`).

- [ ] **Step 3: Implement the finder, the hook and the pyproject/versions edits**

Append this ROOT block to `wheel_hook.cmake` (it runs right after STIR's `PROJECT(STIR)`, before STIR's
`find_package(CERN_ROOT)`). `CMAKE_CURRENT_LIST_DIR` is `packaging/pip/cmake`:

```cmake
# ---- Phase 5: ROOT from the official root wheel (Linux/macOS) ----------------------------------------------
if(NOT DISABLE_CERN_ROOT AND NOT DEFINED ROOT_DIR)
  execute_process(COMMAND "${Python_EXECUTABLE}" "${CMAKE_CURRENT_LIST_DIR}/../find_root_cmake_dir.py" --cmake-dir
                  OUTPUT_VARIABLE _d RESULT_VARIABLE _rc OUTPUT_STRIP_TRAILING_WHITESPACE)
  if(_rc EQUAL 0)
    set(ROOT_DIR "${_d}" CACHE PATH "ROOT from the root wheel")
    execute_process(COMMAND "${Python_EXECUTABLE}" "${CMAKE_CURRENT_LIST_DIR}/../find_root_cmake_dir.py"
                    --lib-dir-relative OUTPUT_VARIABLE _rel OUTPUT_STRIP_TRAILING_WHITESPACE)
    if(APPLE)
      list(APPEND CMAKE_INSTALL_RPATH "@loader_path/../${_rel}")
    else()
      list(APPEND CMAKE_INSTALL_RPATH "$ORIGIN/../${_rel}")
    endif()
  endif()
endif()
```

Phase 2's deferred feature report already writes `root` into `build_features.json`; nothing else is generated.

If scikit-build-core does not pass
`Python_EXECUTABLE`, fall back to `Python3_EXECUTABLE`.

In `pyproject.toml`:
- add `ROOT_REQ` to both requirement lists, and update Phase 1's `test_build_backend_and_requirements` and
  `test_project_metadata` to include it;
- set the base `DISABLE_CERN_ROOT = "OFF"` (Phase 1 set it `"ON"`), and change Phase 2's `test_disable_switches` to
  expect `"OFF"`;
- add the `^win32$` override with `DISABLE_CERN_ROOT = "ON"` (and `inherit.cmake.define = "append"`, as Phase 3's
  overrides do).

- [ ] **Step 4: Run the tests and a local proof-of-concept build (Linux x86_64)**

Run: `python -m pytest packaging/pip/tests/test_root_packaging.py -v`
Expected: all PASS.

Run: `STIR_WHEEL_VARIANT=cpu STIR_DEPS_PREFIX=<prefix> pip wheel . --no-deps -w /tmp/rootpoc -v 2>&1 | tee /tmp/rootpoc.log`
Expected in the log:
- `CERN ROOT support enabled.`
- `ROOT Version: X.Y.Z. CXX version: NN.`, with NN equal to the gate's G4 value

Then run `unzip -p /tmp/rootpoc/stir-*.whl stir/_data/build_features.json`. Expected: `"root": true`.

If the hook path does not resolve relative to the source dir, stop and ask. Do not add an absolute path.

- [ ] **Step 5: Commit**

```bash
git add packaging/pip/find_root_cmake_dir.py packaging/pip/cmake/wheel_hook.cmake pyproject.toml \
        packaging/pip/deps/versions.toml packaging/pip/tests/test_root_packaging.py packaging/pip/tests/test_ci_config.py
git commit -m "Build against the root wheel on Linux and macOS"
```

---

### Task 4 (GO only): Repair without bundling ROOT; `root` feature smoke test

**Files:**
- Modify: `pyproject.toml`: `[tool.cibuildwheel.linux]` and `[tool.cibuildwheel.macos]` gain `before-build` and
  `repair-wheel-command`; `test-requires` gains `uproot`
- Test: `packaging/pip/tests/test_wheel_smoke.py`

**Interfaces:**
- Consumes: `find_root_cmake_dir.py --auditwheel-excludes | --lib-dir` (Task 3); `STIR_WHEEL_EXPECT` (contract).
- Produces: `write_gate_file(dir: Path, n_events: int = 3) -> Path`, a smoke-test helper that returns the `.hroot`
  path. Task 5 and Task 6 reuse it. `CHECKS["root"] = check_root` (Phase 1's `test_expected_feature[root]` fails
  without it).

- [ ] **Step 1: Write the failing tests**

`write_gate_file` uses `uproot.recreate`. It writes tree `Coincidences` with 3 entries:
- `time1 = time2 = [0.002, 0.003, 0.004]` (float64);
- `eventID1 = eventID2 = [1, 2, 3]`, `comptonPhantom1/2 = 0`, `crystalID1 = [0, 1, 2]`, `crystalID2 = [3, 2, 1]`,
  `submoduleID1/2 = moduleID1/2 = 0`, `rsectorID1 = [0, 10, 20]`, `rsectorID2 = [252, 262, 272]` (int32);
- `energy1 = energy2 = 511` (float32).

It writes the `.hroot` from `recon_test_pack/root_header.hroot` with:
- the three TOF lines removed;
- `name of data file := <abs path>`;
- `exclude scattered events := 0` and `exclude random events := 0`.

`EXPECT` below is `expected_features(os.environ)` (Phase 1). `check_root` takes no arguments (it makes its own
`tempfile.TemporaryDirectory()` and calls `write_gate_file` on it) and is registered as `CHECKS["root"]`. The
`root` key in `build_features.json` is already checked by Phase 2's `test_build_features_match_expect`.

```python
def check_root():   # body runs inside: with tempfile.TemporaryDirectory() as d
    hroot = write_gate_file(Path(d))
    code = textwrap.dedent(f"""
        import stir
        lm = stir.ListModeData.read_from_file({str(hroot)!r})
        s = lm.get_scanner()
        assert s.get_num_rings() == 4 and s.get_num_detectors_per_ring() == 504
        rec = lm.get_empty_record(); n = 0; first_ms = None
        while lm.get_next_record(rec).succeeded():
            if rec.is_event(): n += 1
            if first_ms is None and rec.is_time(): first_ms = rec.time().get_time_in_millisecs()
        assert (n, first_ms) == (3, 2), (n, first_ms)
    """)
    env = {k: v for k, v in os.environ.items() if k not in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH")}
    subprocess.run([sys.executable, "-c", code], check=True, env=env)

CHECKS["root"] = check_root

@pytest.mark.skipif("root" not in EXPECT, reason="root not expected")
def test_import_root_then_stir_reads_gate_file(tmp_path):
    hroot = write_gate_file(tmp_path)
    subprocess.run([sys.executable, "-c",
        f"import ROOT, stir; assert stir.ListModeData.read_from_file({str(hroot)!r}) is not None"], check=True)

@pytest.mark.skipif("root" not in EXPECT, reason="root not expected")
def test_root_libs_not_bundled():
    site = Path(stir.__file__).parent.parent
    bundled = [p.name for d in (site / "stir.libs", site / "stir" / ".dylibs") if d.is_dir() for p in d.iterdir()]
    assert not [n for n in bundled if re.match(r"lib(Core|RIO|Tree|Cling|Thread|MathCore|Imt)\b", n)], bundled
```

- [ ] **Step 2: Run the tests against the Task 3 PoC wheel and check they fail**

Run: `pip install /tmp/rootpoc/stir-*.whl uproot && STIR_WHEEL_EXPECT=config,openmp,root python -m pytest packaging/pip/tests/test_wheel_smoke.py -v -k root`
Expected: FAIL, because the unrepaired wheel's `_stir` points into a deleted isolated build env
(`ImportError: libCore.so…`). If it passes, the RPATH from Task 3 already works; carry on.

- [ ] **Step 3: Configure repair and before-build**

- Linux: `before-build = "pip install 'root==X.Y.*'"` (the same pin), and
  `repair-wheel-command = "auditwheel repair -w {dest_dir} $(python packaging/pip/find_root_cmake_dir.py --auditwheel-excludes) {wheel}"`.
  Keep any existing Phase 1–3 auditwheel flags.
- macOS: the same `before-build`, and append `--exclude "$(python packaging/pip/find_root_cmake_dir.py --lib-dir)"`
  to the existing `delocate-wheel` command.
- `build_cuda` (Phase 3) overrides the Linux repair command with `CIBW_REPAIR_WHEEL_COMMAND_LINUX` in
  `wheels.yml`: add the same `$(python packaging/pip/find_root_cmake_dir.py --auditwheel-excludes)` there, next to
  its `--exclude libcudart...` flags.
- `test-requires`: add `uproot`.

- [ ] **Step 4: Rebuild with cibuildwheel locally and run the tests**

Run: `CIBW_BUILD=cp312-manylinux_x86_64 STIR_DEPS_PREFIX=/project/.deps/cpu STIR_WHEEL_VARIANT=cpu STIR_WHEEL_EXPECT=config,openmp,json,hdf5,petsird,itk,parallelproj,root cibuildwheel --platform linux` (Phase 2's `environment-pass` forwards all three)
Expected: repair succeeds and all `test_wheel_smoke.py` tests PASS, including `test_expected_feature[root]` and the
two `root` tests.
Also run `unzip -l wheelhouse/stir-*.whl | grep -c libCore`. Expected: `0`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml packaging/pip/tests/test_wheel_smoke.py
git commit -m "Link ROOT from the root wheel without bundling and smoke-test GATE reading"
```

---

### Task 5 (GO only): Clear error where ROOT is absent

**Files:**
- Create: `src/swig/python/stir/_root_support.py`
- Modify: `src/swig/python/stir/__init__.py` (add after `from .swigstir import * # noqa: F401`)
- Test: `packaging/pip/tests/test_root_support.py`, `packaging/pip/tests/test_wheel_smoke.py`

**Interfaces:**
- Consumes: `stir/_data/build_features.json` (Phase 2); `write_gate_file` (Task 4); Phase 4's
  `INIT_PY_ALLOWED_LINES`, which already lists the two lines below (no `release_check.py` change).
- Produces:
  - `MISSING_ROOT_MESSAGE: str`
  - `root_built(package_dir: Path) -> bool | None`: the `root` value of `package_dir/_data/build_features.json`, or
    `None` when the file is absent (conda/source installs).
  - `install_root_hint(namespace: MutableMapping[str, Any], have_root: bool | None, platform: str = sys.platform)
    -> None`. It does nothing unless `have_root is False`. It wraps `namespace["ListModeData"].read_from_file` and
    `namespace["CListModeData"].read_from_file`. The wrapper carries the attribute `__stir_root_hint__ = True`.

The exact copy, with the `{note}` for `win32` being
`ROOT support is not available in the pip packages on Windows (or in conda on Windows). `, and otherwise empty:

```
STIR cannot read '{filename}': this STIR package was built without ROOT, so GATE/ROOT listmode files (.hroot) are
not supported. {note}Use the conda-forge STIR package (conda install -c conda-forge stir) on Linux or macOS, or
build STIR from source with ROOT.
```

The new `__init__.py` lines (exactly the overview's), placed after the unchanged swigstir import. Every imported
name starts with `_`, as Phase 1's `test_init_does_not_leak_helper_names` requires:

```python
from ._root_support import install_root_hint as _install_root_hint, root_built as _root_built
_install_root_hint(globals(), have_root=_root_built(_Path(__file__).parent))
```

- [ ] **Step 1: Write the failing tests**

```python
class FakeLM:
    @staticmethod
    def read_from_file(name):
        raise RuntimeError(f"no file format found that can read file '{name}'")

def test_hroot_read_without_root_gets_clear_message():
    ns = {"ListModeData": FakeLM, "CListModeData": FakeLM}
    install_root_hint(ns, have_root=False, platform="win32")
    with pytest.raises(RuntimeError) as e:
        ns["ListModeData"].read_from_file("C:/data/sim.HROOT")
    assert str(e.value).startswith("STIR cannot read 'C:/data/sim.HROOT': this STIR package was built without ROOT")
    assert "not available in the pip packages on Windows" in str(e.value)
    assert isinstance(e.value.__cause__, RuntimeError)

def test_other_files_keep_stir_error():   # "x.l.hdr" → original message unchanged
    ...

@pytest.mark.parametrize("have_root", [True, None])
def test_have_root_true_or_unknown_installs_nothing(have_root):
    ns = {"ListModeData": FakeLM, "CListModeData": FakeLM}
    install_root_hint(ns, have_root=have_root)
    assert not getattr(ns["ListModeData"].read_from_file, "__stir_root_hint__", False)

def test_root_built_reads_build_features(tmp_path):
    assert root_built(tmp_path) is None
    (tmp_path / "_data").mkdir(); (tmp_path / "_data" / "build_features.json").write_text('{"root": false}')
    assert root_built(tmp_path) is False
```

Add to `test_wheel_smoke.py`:

```python
@pytest.mark.skipif("root" in EXPECT, reason="ROOT expected in this wheel")
def test_root_absent_gives_clear_message(tmp_path):
    assert stir._root_support.root_built(Path(stir.__file__).parent) is False
    assert getattr(stir.ListModeData.read_from_file, "__stir_root_hint__", False)
    hroot = tmp_path / "x.hroot"; hroot.write_text("ROOT header :=\nend ROOT header :=\n")
    with pytest.raises(RuntimeError, match="built without ROOT"):
        stir.ListModeData.read_from_file(str(hroot))
```

- [ ] **Step 2: Run the tests and check they fail**

Run: `python -m pytest packaging/pip/tests/test_root_support.py -v`
Expected: `FileNotFoundError` for `_root_support.py` (load it by path with `spec_from_file_location`, as Phase 1's
tests load `_paths.py`; never import a compiled `stir`).

- [ ] **Step 3: Implement `_root_support.py` and the `__init__.py` lines**

The wrapper matches when `Path(name).suffix.lower() == ".hroot"` and a `RuntimeError` is raised. It then raises a
new `RuntimeError(message) from exc`. Set it with `setattr(cls, "read_from_file", staticmethod(wrapper))`. **Probe
first:** on a built wheel, `setattr` on a SWIG `-builtin` type may raise `TypeError`. If it does, stop and ask Robert.
There is no C++ fallback.

- [ ] **Step 4: Run the tests and check they pass**

Run: `python -m pytest packaging/pip/tests/test_root_support.py packaging/pip/tests/test_release_check.py packaging/pip/tests/test_paths.py -v`
Expected: all PASS (Phase 4's allow-list and Phase 1's `__init__` tests accept the two lines).

Then build a Windows wheel (or a Linux wheel with `-C cmake.define.DISABLE_CERN_ROOT=ON`) and run
`STIR_WHEEL_EXPECT=config,openmp python -m pytest packaging/pip/tests/test_wheel_smoke.py -k root -v`.
Expected: `test_root_absent_gives_clear_message` PASSES and the three `root` tests are SKIPPED.

- [ ] **Step 5: Commit**

```bash
git add src/swig/python/stir/_root_support.py src/swig/python/stir/__init__.py \
        packaging/pip/tests/test_root_support.py packaging/pip/tests/test_wheel_smoke.py
git commit -m "Explain missing ROOT support when reading .hroot files"
```

---

### Task 6 (GO only): CI, no-compiler check, docs

**Files:**
- Modify: `.github/workflows/wheels.yml`: the `build_cpu`/`build_cuda` matrices, the macOS x86_64 runner and
  `rehearse_publish`
- Modify: `packaging/pip/README.md`, `packaging/pip/RELEASING.md`
- Test: `packaging/pip/tests/test_workflow_guards.py`

**Interfaces:**
- Consumes: matrix and artifact names (contract); `write_gate_file` (Task 4).

- [ ] **Step 1: Write the failing tests**

```python
def test_root_expected_on_linux_and_macos_only():
    wf = load_workflow()
    for job in ("build_cpu", "build_cuda"):
        for entry in wf["jobs"][job]["strategy"]["matrix"]["include"]:
            has_root = "root" in entry["expect"].split(",")
            assert has_root == (entry["os"] in ("linux", "macos")), entry

def test_rehearse_runs_root_smoke_without_compiler():
    runs = "\n".join(s.get("run", "") for s in load_workflow()["jobs"]["rehearse_publish"]["steps"])
    assert "python:3.12-slim" in runs and "-k root" in runs
```

The matrix keys `expect`/`os` are whatever Phase 2/3 named them. Adapt the key names, not the assertion.

- [ ] **Step 2: Run the tests and check they fail**

Run: `python -m pytest packaging/pip/tests/test_workflow_guards.py -v -k "root"`
Expected: both FAIL.

- [ ] **Step 3: Edit the CI and the docs**

- Add `,root` to the `expect` value of every Linux and macOS matrix entry (`build_cpu`, `build_cuda` and the matching
  `rehearse_publish` rows, which must stay equal). Windows is unchanged.
- macOS x86_64 must build on a **native Intel runner**, because cross-building would resolve an arm64 `root` wheel
  in the build env. Phase 2 already uses the native `macos-15-intel`; if Phase 2 Task 11 fell back to cross-building
  on `macos-15`, that entry omits `root`, and the README says so.
- `rehearse_publish`: add a step with `if: matrix.variant == 'cpu' && matrix.os == 'linux' && matrix.arch == 'x86_64'`
  running
  `docker run --rm --network host -v "$PWD/packaging/pip/tests:/t:ro" -v "$PWD/recon_test_pack:/recon_test_pack:ro" python:3.12-slim sh -c "pip install --index-url http://localhost:8080/simple/ --extra-index-url https://pypi.org/simple 'stir==$version' uproot pytest && STIR_WHEEL_EXPECT=config,root python -m pytest /t/test_wheel_smoke.py -k root -v"`
  (`version` as in the install step; the exact pin matters because `--extra-index-url` also searches PyPI).
  Adjust the `recon_test_pack` path to match how `write_gate_file` locates the template.
- README:
  - ROOT row: `stir`/`stir-cudaXX` on Linux, `stir` on macOS, and "— (not available; see conda)" on Windows.
  - Note that installing on Linux/macOS also installs the `root` package (size as shown on PyPI).
  - Note that an existing different `root` version in the env will be changed by pip to match `X.Y.*`.
- RELEASING:
  - checklist item "check for a newer `root` X.Y; bumping = versions.toml `[root].pin` + both requirement strings + a
    full CI run";
  - a gate log row marking GO.

- [ ] **Step 4: Run the tests and check CI**

Run: `python -m pytest packaging/pip/tests -v --ignore=packaging/pip/tests/test_wheel_smoke.py` and
`actionlint .github/workflows/wheels.yml`.
Expected: PASS and no output.

With Robert's go-ahead for Phase 5 pushes (ask once), run `git push fork pip-packaging`. Expected:
- every build job is green;
- Linux/macOS smoke logs show `test_expected_feature[root] PASSED`;
- Windows logs show `test_root_absent_gives_clear_message PASSED`;
- the slim-container step passes.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/wheels.yml packaging/pip/README.md packaging/pip/RELEASING.md packaging/pip/tests/test_workflow_guards.py
git commit -m "Enable ROOT feature in Linux and macOS wheel CI"
```

---

## Undecided items (for Robert)

1. **The pin form when the gate passes.** `root` versions are currently `0.1aN`, not ROOT's own numbers. G1 requires
   ROOT's numbering, so `root==X.Y.*` makes sense. If CERN keeps a separate scheme, decide the pin then.
2. **Ship the Task 5 `.hroot` hint even on NO-GO?** It would help every platform today. It costs one more Python file
   plus the two `__init__.py` lines; it reads Phase 2's `build_features.json`, so it does not need Task 3. Default:
   no, GO only.
3. **macOS x86_64 without a native Intel runner.** Ship it without ROOT (documented), or drop ROOT from macOS
   x86_64 entirely.
4. **`import stir` now loads ROOT's libraries** on Linux/macOS (startup time and memory). This is acceptable per the
   spec. Measure it in Task 4 if it looks large.

## Contract concerns

Resolved in the overview's "Cross-plan review (2026-11-12)"; the overview wins where these notes differ. In
particular there is no `stir_wheel_hooks.cmake`, no `CMAKE_PROJECT_INCLUDE_BEFORE` and no `stir/_build_info.py`.

1. **New files beyond the contract** (GO only):
   - `packaging/pip/root_gate.py`, `packaging/pip/find_root_cmake_dir.py`, `packaging/pip/cmake/stir_wheel_hooks.cmake`;
   - `src/swig/python/stir/_root_support.py`;
   - the generated wheel file `stir/_build_info.py`. The contract's wheel layout should list it.

   `root_gate.py` exists in both outcomes.
2. **More lines in `src/swig/python/stir/__init__.py`.** The overview says the only edit is the Phase 1
   `configure_data_dirs` call. Task 5 adds the guarded `install_root_hint` lines. That is Python glue, not C++, but it
   widens the contract. `release_check.py`'s allowlist is updated to match.
3. **`.cmake` file under `packaging/`.** The Phase 4 protected-file rule excludes `packaging/`. Without that
   exclusion, `stir_wheel_hooks.cmake` would trip the no-CMake-changes check.
4. **`CMAKE_PROJECT_INCLUDE_BEFORE`** is a new `cmake.define` in `pyproject.toml`. It needs CMake ≥ 3.19 for
   `cmake_language(DEFER)`. STIR declares a 3.14 minimum, but the build uses PyPI's `cmake`, so the version actually
   running is what counts.

## References

- PyPI `root` project page (0.1a12, 2026-05-20, cp310–cp314 `manylinux_2_28_x86_64` only): https://pypi.org/project/root
- ROOT 6.38 release notes ("alpha mode … pip install root" on Linux): https://root.cern/releases/release-63800/
- ROOT forum, "Is this a legitimate release of ROOT?" ("wouldn't suggest using it for production just yet"):
  https://root-forum.cern.ch/t/is-this-a-legitimate-release-of-root/64429
- CHEP 2024 "pip install ROOT" slides (manylinux_2_28, cibuildwheel, `import ROOT` needs a compiler, planned split):
  https://indico.cern.ch/event/1447163/contributions/6093235/attachments/2948966/5183088/pip_install_ROOT.pdf
- PyHEP.dev 2026 talk on ROOT PyPI wheels (ongoing development): https://indico.nikhef.nl/event/7873/contributions/31390/
- STIR sources: `src/cmake/FindCERN_ROOT.cmake`, `CMakeLists.txt:106,145-151`, `src/CMakeLists.txt:47-52`,
  `src/IO/CMakeLists.txt:61-67,102-109`, `src/listmode_buildblock/CMakeLists.txt:48-53`,
  `src/IO/IO_registries.cxx:64-68,108-112`, `src/swig/stir_listmode.i`, `src/swig/test/python/test_listmode.py`,
  `recon_test_pack/root_header.hroot`, `build_environment.yml` (`root_base>=6.38 # not win`).
