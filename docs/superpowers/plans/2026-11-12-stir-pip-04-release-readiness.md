# STIR pip Phase 4: Release Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `pip-packaging` branch safe and repeatable to maintain and, when Robert decides, to release. That
means a scripted, tested way to merge each new upstream STIR release; an automated proof that no STIR C++/CMake file
was changed; finished user docs; a recorded PyPI name check; and a publish job that is reviewed, documented and
provably still switched off.

**Architecture:** A single stdlib-plus-`packaging` script `packaging/pip/release_check.py` answers three questions:
what version is this, did VERSION.txt change, and does the branch differ from upstream tag `rel_<VERSION.txt>` in any
protected file. Static pytest checks parse `.github/workflows/wheels.yml` and fail if the publish guard is relaxed or
any other job can reach PyPI. A new CI job `checks` runs those tests plus `actionlint` on every push. The docs are
`packaging/pip/README.md` (user section added at the top) and the new `packaging/pip/RELEASING.md`. Nothing is
published and no account settings are changed. The PyPI and GitHub-environment steps are written down for Robert only.

**Tech Stack:** Python 3.11+ (`argparse`, `subprocess`, `tomllib`), `packaging`, `PyYAML`, `pytest`,
`actionlint` (via `actionlint-py`), git, GitHub Actions, `pypa/gh-action-pypi-publish@release/v1`.

**Spec:** `docs/superpowers/specs/2026-11-12-stir-pip-packaging-design.md` (sections 2, 5.1, 5.2, 5.5, 5.6 and 7
Phase 4). The shared names come from `docs/superpowers/plans/2026-11-12-stir-pip-00-overview.md`.

## Global Constraints

- Repo `robbietuk/STIR`, branch `pip-packaging`. Never push to `UCL/STIR`. Never publish to PyPI or TestPyPI.
  Remotes as in the overview: `origin` = UCL/STIR (push disabled), `fork` = robbietuk/STIR; pushes go to `fork`
  only, after Robert's go-ahead for this phase.
- No changes to any protected file; the protected list is the overview's, and `release_check.py` implements exactly
  it. The only edit to an existing STIR file is `src/swig/python/stir/__init__.py`, with exactly the eight added
  lines listed in the overview (Phases 1, 3 and 5).
- The `publish` job stays `if: false`. Enabling it needs an explicit `workflow_dispatch` input `target: pypi` *and*
  Robert editing the guard himself. TestPyPI is not used at all.
- Every job in `wheels.yml` except `publish` has `if: github.repository == 'robbietuk/STIR'`.
  Triggers stay `push` to `pip-packaging` plus `workflow_dispatch`.
- First-version packages `stir` (Linux x86_64, macOS arm64, Windows x86_64) and `stir-cuda12` (Linux x86_64,
  Windows x86_64) both provide `import stir`. Fallback names, used only if the name check fails: `stir-recon`,
  `stir-recon-cuda12`. `stir-cuda13`, Linux aarch64 and macOS x86_64 are deferred (overview); the docs mention them
  only as "not available yet".
- Dev versions are `<VERSION.txt>.devN`, with N = `github.run_number`.
- Markdown files must pass the repo's `pymarkdown` pre-commit hook (`.pymarkdown`: MD013 line length 120).
- Commits use plain imperative messages and end with the session's attribution lines.

## Review Focus

1. **Shallow or tagless clone.** The fork has no release tags and CI checkouts may be shallow. If tag `rel_X` is
   missing, `release_check.py check` must fail with a message naming the tag. It must not pass on an empty diff.
   (Task 1: `test_missing_tag_is_an_error_not_a_pass`.)
2. **A C++ file that was deleted or moved.** `git diff --name-only` with rename detection lists only the new path.
   A `.cxx` file moved into `packaging/` would then go unnoticed. (Task 1: `test_deleted_cxx_is_reported`,
   `test_renamed_cxx_reports_old_path`.)
3. **An upstream release that touches `stir/__init__.py`.** This is our one edit to an existing file, and a merge
   resolution could silently drop upstream lines or our hook. (Task 1: `test_init_py_removed_line_is_violation`,
   `test_init_py_only_gains_paths_hook`.)
4. **A release-candidate VERSION.txt** such as `6.6.0-rc1`. The tag mapping must still work, and the dev version
   must fail with a clear error naming the value (Phase 1's `prepare_build.py` accepts only `X.Y.Z`), not a crash.
   (Task 1: `test_upstream_tag_from_version`, `test_dev_version_with_rc_version_txt`.)
5. **A publish guard loosened by a quoted or expression form**, for example `if: "false"` or
   `if: ${{ inputs.target == 'pypi' }}`, or a second job that quietly gains `id-token: write`. (Task 2:
   `test_publish_job_guard_is_false`, `test_only_publish_has_id_token_write`.)

---

## File Structure

<!-- pyml disable md013-->
| Path | Action | Responsibility |
|---|---|---|
| `packaging/pip/release_check.py` | Create | Version and dev-version check, VERSION.txt change detection, protected-file diff against the upstream tag |
| `packaging/pip/tests/test_release_check.py` | Create | Unit tests on throwaway git repos, plus one test on this checkout |
| `packaging/pip/tests/test_workflow_guards.py` | Create | Static assertions on `wheels.yml`, plus an actionlint run |
| `packaging/pip/tests/test_docs.py` | Create | README and RELEASING contain the required sections, and every script path they mention exists |
| `packaging/pip/tests/requirements-checks.txt` | Create | Pinned tools for the `checks` job |
| `.github/workflows/wheels.yml` | Modify | Add the `target` dispatch input, harden `publish`, add the `checks` job |
| `packaging/pip/README.md` | Modify | Add the user section above the existing developer notes |
| `packaging/pip/RELEASING.md` | Create | Merge procedure, PyPI name check, trusted-publishing setup, enabling publish |
<!-- pyml enable md013-->

---

### Task 1: `release_check.py`: version, change detection and protected-file diff

**Files:**

- Create: `packaging/pip/release_check.py`
- Test: `packaging/pip/tests/test_release_check.py`

**Interfaces:**

- Consumes: `python packaging/pip/prepare_build.py --variant cpu --dev-number N --pyproject PATH` (Phase 1
  Task 4). It reads `VERSION.txt` from the directory that contains `--pyproject`, and exits 1 if `VERSION.txt` is
  not `X.Y.Z`.
- Produces (importable, so `sys.path` gets `packaging/pip` in tests):
  - `class ReleaseCheckError(Exception)`
  - `UPSTREAM_URL = "https://github.com/UCL/STIR.git"`
  - `read_version_txt(repo: Path) -> str`: the stripped contents of `VERSION.txt`
  - `upstream_tag(version: str) -> str`: returns `"rel_" + version`
  - `dev_version(repo: Path, dev_number: int) -> packaging.version.Version`
  - `is_protected(path: str) -> bool`
  - `protected_changes(repo: Path, tag: str) -> list[str]`: sorted; raises `ReleaseCheckError` if the tag is missing
  - `init_py_violations(repo: Path, tag: str) -> list[str]`
  - `tag_is_ancestor(repo: Path, tag: str) -> bool`
  - `fetch_upstream_tag(repo: Path, tag: str) -> None`
  - `main(argv: list[str] | None = None) -> int`
  - CLI:
    - `version [--dev-number N]` prints `<version> <dev-version> <tag>`.
    - `version-changed --base REF` prints `VERSION.txt changed: A -> B` or `VERSION.txt unchanged: A`.
      With `--github-notice`, the "changed" line is also written as `::notice::...`.
    - `check [--tag T] [--fetch-upstream]` prints `OK: ...` and exits 0, or lists the problems on stderr and exits 1.
    - Bad arguments exit 2.

- [ ] **Step 1: Write the failing tests**

Fixture `git_repo(tmp_path)`: `git init` and commit `VERSION.txt` (`6.5.0\n`), `CMakeLists.txt`,
`src/buildblock/foo.cxx`, `src/include/stir/foo.h` and `src/swig/python/stir/__init__.py`. The `__init__.py`
content is upstream's: docstring plus `from .swigstir import * # noqa: F401`. Tag the commit `rel_6.5.0`, then
commit `packaging/pip/x.py`, `pyproject.toml` and a `docs/superpowers/plans/p.md` on top. Run every git command with
`-c user.name=test -c user.email=test@example.invalid`.

```python
def test_clean_branch_has_no_protected_changes(git_repo):
    assert protected_changes(git_repo, "rel_6.5.0") == []

@pytest.mark.parametrize("path", [
    "src/buildblock/foo.cxx", "src/include/stir/foo.h", "src/include/stir/foo.inl",
    "src/recon_buildblock/CUDA/k.cu", "CMakeLists.txt", "src/cmake/FindX.cmake",
    "src/cmake/STIRConfig.h.in", "src/cmake/STIRConfig.cmake.in", "src/swig/stir.i", "src/utilities/x.c",
])
def test_modified_protected_file_is_reported(git_repo, path):
    write_and_commit(git_repo, path, "changed\n")
    assert protected_changes(git_repo, "rel_6.5.0") == [path]

def test_deleted_cxx_is_reported(git_repo):          # git rm src/buildblock/foo.cxx; commit
    assert protected_changes(git_repo, "rel_6.5.0") == ["src/buildblock/foo.cxx"]

def test_renamed_cxx_reports_old_path(git_repo):     # git mv src/buildblock/foo.cxx packaging/pip/foo.cxx
    assert "src/buildblock/foo.cxx" in protected_changes(git_repo, "rel_6.5.0")

def test_packaging_and_docs_are_not_protected():
    assert not is_protected("packaging/pip/cmake/wheel_hook.cmake")
    assert not is_protected("packaging/pip/cmake/FindPython.cmake")
    assert not is_protected("docs/superpowers/plans/x.md")
    assert not is_protected("src/swig/python/stir/_paths.py")
    assert is_protected("external_helpers/fmt")       # submodule pointer

def test_missing_tag_is_an_error_not_a_pass(git_repo):
    with pytest.raises(ReleaseCheckError, match=r"tag rel_9\.9\.9 not found.*--fetch-upstream"):
        protected_changes(git_repo, "rel_9.9.9")

def test_init_py_only_gains_paths_hook(git_repo):
    # insert the overview's six Phase 1 + Phase 3 lines before the unchanged swigstir import, and its two
    # Phase 5 lines after it, plus a blank line and a comment; commit
    assert init_py_violations(git_repo, "rel_6.5.0") == []

def test_init_py_other_added_line_is_violation(git_repo):   # insert "import os" (not the allowed alias form)
    assert init_py_violations(git_repo, "rel_6.5.0") == ["+import os"]

def test_init_py_removed_line_is_violation(git_repo):  # delete the swigstir import line
    assert init_py_violations(git_repo, "rel_6.5.0") == ["-from .swigstir import * # noqa: F401"]

def test_upstream_tag_from_version():
    assert upstream_tag("6.5.0") == "rel_6.5.0"
    assert upstream_tag("6.6.0-rc1") == "rel_6.6.0-rc1"

def test_version_changed_cli(git_repo, capsys):       # commit VERSION.txt = 6.6.0
    assert main(["--repo", str(git_repo), "version-changed", "--base", "rel_6.5.0"]) == 0
    assert capsys.readouterr().out.strip() == "VERSION.txt changed: 6.5.0 -> 6.6.0"

def test_check_fails_when_version_tag_not_merged(git_repo, capsys):  # VERSION.txt = 6.6.0, no tag rel_6.6.0
    assert main(["--repo", str(git_repo), "check"]) == 1
    assert "rel_6.6.0" in capsys.readouterr().err

def test_check_passes_on_clean_branch(git_repo, capsys):
    assert main(["--repo", str(git_repo), "check"]) == 0
    assert capsys.readouterr().out.startswith("OK: no STIR C++/CMake changes since rel_6.5.0")

def test_dev_version_of_this_checkout_parses():
    v = dev_version(REPO_ROOT, 42)
    assert v.dev == 42 and v.base_version == Version(read_version_txt(REPO_ROOT)).base_version

def test_dev_version_with_rc_version_txt(tmp_path):
    # copy REPO_ROOT/pyproject.toml and packaging/pip/prepare_build.py into tmp_path; VERSION.txt = "6.6.0-rc1"
    with pytest.raises(ReleaseCheckError, match=r"6\.6\.0-rc1"):
        dev_version(tmp_path, 7)
```

- [ ] **Step 2: Run the tests and check they fail**

Run: `python -m pytest packaging/pip/tests/test_release_check.py -v`
Expected: collection error `ModuleNotFoundError: No module named 'release_check'`.

- [ ] **Step 3: Implement `packaging/pip/release_check.py`**

<!-- pyml disable-num-lines 22 md011-->
- `is_protected(path)`: return False for paths under `packaging/`, `docs/superpowers/` or `.github/`. Otherwise return
  True if:
  - the basename is `CMakeLists.txt`,
  - the path ends in `.h.in` or `.cmake.in`,
  - the suffix is in `{".cxx", ".h", ".inl", ".cu", ".c", ".txx", ".i", ".cmake"}`, or
  - the path is in `{"external_helpers/CuVec", "external_helpers/fmt"}` (submodule pointers).
- `protected_changes`: first run `git rev-parse --verify --quiet refs/tags/<tag>`. If that fails, raise
  `ReleaseCheckError(f"tag {tag} not found; run with --fetch-upstream or 'git fetch origin tag {tag} --no-tags'")`.
  Then run `git diff --name-only --no-renames <tag> HEAD` and filter with `is_protected`.
- `init_py_violations`: run `git diff --unified=0 <tag> HEAD -- src/swig/python/stir/__init__.py`. Every `-` content
  line is a violation. Every `+` content line (trailing whitespace stripped) is a violation unless it is blank, a
  comment, or exactly one of the eight lines in `INIT_PY_ALLOWED_LINES: tuple[str, ...]`, which copies the
  overview's list verbatim (without the `# Phase N` table comments):
  `import os as _os`, `from pathlib import Path as _Path`,
  `from ._paths import configure_data_dirs as _configure_data_dirs`,
  `_configure_data_dirs(_Path(__file__).parent, _os.environ)`, `from . import _cuda`, `_cuda.prepare_runtime()`,
  `from ._root_support import install_root_hint as _install_root_hint, root_built as _root_built`,
  `_install_root_hint(globals(), have_root=_root_built(_Path(__file__).parent))`.
- `dev_version`: copy `repo/pyproject.toml` and `repo/VERSION.txt` into a `TemporaryDirectory`. Run
  `sys.executable repo/packaging/pip/prepare_build.py --variant cpu --dev-number N --pyproject <tmp>/pyproject.toml`
  (`capture_output=True`). On a non-zero exit raise `ReleaseCheckError` with its stderr (which names the bad
  `VERSION.txt` value). Return `Version(tomllib.load(...)["project"]["version"])`. Raise `ReleaseCheckError` if the
  result has no `.dev`.
- `fetch_upstream_tag`: run `git fetch --no-tags UPSTREAM_URL refs/tags/T:refs/tags/T`. This is read-only.
- `check`:
  1. version parses and `dev_version(repo, 1)` works;
  2. `tag_is_ancestor` is true (`git merge-base --is-ancestor`), else report "VERSION.txt says X but upstream tag
     rel_X is not merged into HEAD";
  3. `protected_changes` is `[]`;
  4. `init_py_violations` is `[]`.

  Report all failures, not just the first.
- `version-changed --base REF`: an all-zero sha or an unknown REF counts as "unchanged". Read the old version with
  `git show REF:VERSION.txt`.

- [ ] **Step 4: Run the tests and check they pass**

Run: `python -m pytest packaging/pip/tests/test_release_check.py -v`
Expected: all PASS.

Then, on this checkout: `python packaging/pip/release_check.py check`
Expected: `OK: no STIR C++/CMake changes since rel_6.5.0`, exit 0. The local clone already has tag `rel_6.5.0`.

- [ ] **Step 5: Commit**

```bash
git add packaging/pip/release_check.py packaging/pip/tests/test_release_check.py
git commit -m "Add release_check.py to verify upstream merges and dev versions"
```

---

### Task 2: Harden and pin down the `publish` job

**Files:**

- Modify: `.github/workflows/wheels.yml`: the `on.workflow_dispatch` block and the `publish` job
- Test: `packaging/pip/tests/test_workflow_guards.py`

**Interfaces:**

- Consumes: job names `sdist`, `build_cpu`, `build_cuda`, `rehearse_publish`, `publish` and artifact names
  `wheels-<variant>-<os>-<arch>` and `sdist` (contract). Also `checks` from Task 3, which `publish` must `need`.
- Produces: `load_workflow() -> dict`. It uses `yaml.safe_load` and normalises the YAML-1.1 key `True` back to `"on"`.
  Task 3 reuses it.

- [ ] **Step 1: Write the failing tests**

```python
REFUSE_IF = "github.event_name != 'workflow_dispatch' || inputs.target != 'pypi'"

def test_publish_job_guard_is_false():
    assert load_workflow()["jobs"]["publish"]["if"] is False            # bool, not "false" or an expression

def test_publish_job_refuses_without_pypi_target():
    first = load_workflow()["jobs"]["publish"]["steps"][0]
    assert first["if"] == REFUSE_IF and "exit 1" in first["run"]

def test_publish_job_shape():
    job = load_workflow()["jobs"]["publish"]
    assert job["environment"] == {"name": "pypi", "url": "https://pypi.org/p/stir"}
    assert job["permissions"] == {"id-token": "write"}
    assert {"checks", "rehearse_publish"} <= set(job["needs"])
    uses = [s.get("uses", "") for s in job["steps"]]
    assert "pypa/gh-action-pypi-publish@release/v1" in uses
    assert not any("repository-url" in (s.get("with") or {}) for s in job["steps"])   # default = PyPI only

def test_dispatch_target_input():
    target = load_workflow()["on"]["workflow_dispatch"]["inputs"]["target"]
    assert target == {"description": target["description"], "type": "choice",
                      "options": ["none", "pypi"], "default": "none", "required": True}

def test_only_publish_has_id_token_write():
    wf = load_workflow()
    assert (wf.get("permissions") or {}).get("id-token") != "write"
    assert [n for n, j in wf["jobs"].items() if (j.get("permissions") or {}).get("id-token") == "write"] == ["publish"]

def test_no_other_job_can_reach_pypi():
    for name, job in load_workflow()["jobs"].items():
        if name == "publish":
            continue
        text = json.dumps(job)
        for needle in ("upload.pypi.org", "pypi.org/legacy", "gh-action-pypi-publish", "TWINE_PASSWORD"):
            assert needle not in text, f"{name} mentions {needle}"

def test_testpypi_never_referenced():
    assert "test.pypi.org" not in WORKFLOW_PATH.read_text()

def test_twine_uploads_only_to_localhost():
    for line in WORKFLOW_PATH.read_text().splitlines():
        if "twine upload" in line:
            assert re.search(r"--repository-url[ =]http://(localhost|127\.0\.0\.1):\d+", line), line

def test_every_other_job_guarded_by_repository():
    for name, job in load_workflow()["jobs"].items():
        if name != "publish":
            assert "github.repository == 'robbietuk/STIR'" in str(job.get("if", "")), name
```

`WORKFLOW_PATH = REPO_ROOT / ".github/workflows/wheels.yml"`. If Phase 1 wrote a multi-line `twine upload`, the
implementer joins the `\`-continued lines before applying the regex in `test_twine_uploads_only_to_localhost`.

- [ ] **Step 2: Run the tests and check they fail**

Run: `python -m pytest packaging/pip/tests/test_workflow_guards.py -v`
Expected: `test_publish_job_guard_is_false` FAILS (Phase 1 has `if: false && github.repository == ...`, a string). The
refuse-step, shape,
dispatch-input and `needs: checks` tests FAIL. The others pass or fail depending on what Phase 1 wrote.

- [ ] **Step 3: Edit `wheels.yml`**

- Under `on.workflow_dispatch` add the `target` input: `type: choice`, `options: [none, pypi]`, `default: none`,
  `required: true`, description "Where to publish. 'pypi' only has effect after Robert enables the publish job; see
  packaging/pip/RELEASING.md".
- Rewrite `publish` as follows:
  - `if: false`, with a comment directly above it:
    `# ENABLE ONLY PER packaging/pip/RELEASING.md. Replacement guard: github.repository == 'robbietuk/STIR' &&`
    `github.event_name == 'workflow_dispatch' && inputs.target == 'pypi'`.
  - `needs: [checks, rehearse_publish]`, `runs-on: ubuntu-latest`,
    `environment: {name: pypi, url: https://pypi.org/p/stir}`, `permissions: {id-token: write}`.
  - Step 1: "Refuse unless target is pypi", `if:` exactly `REFUSE_IF`, run
    `echo "::error::publish requires workflow_dispatch with target=pypi"; exit 1`.
  - Step 2: `actions/download-artifact` (same major version as the rest of `wheels.yml`) with `pattern: wheels-*`,
    `merge-multiple: true`, `path: dist/`.
  - Step 3: download-artifact `name: sdist`, `path: dist/`.
  - Step 4: `uses: pypa/gh-action-pypi-publish@release/v1` with `packages-dir: dist/`. No `repository-url`, no
    password. Trusted publishing and attestations use the action's defaults.

- In Phase 1's `test_ci_config.py`, delete `test_publish_is_switched_off` and change
  `test_every_job_is_guarded_to_the_fork` to skip `publish` (these tests supersede them), and add `checks` to the
  expected set in `test_job_names` when Task 3 adds the job.

- [ ] **Step 4: Run the tests and check they pass**

Run:
`python -m pytest packaging/pip/tests/test_workflow_guards.py packaging/pip/tests/test_ci_config.py -v -k "not actionlint"`
Expected: all PASS. (`needs: checks` passes once the YAML names it. Task 3 adds the job itself.)

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/wheels.yml packaging/pip/tests/test_workflow_guards.py
git commit -m "Harden switched-off publish job and add workflow guard tests"
```

---

### Task 3: `checks` CI job with actionlint

**Files:**

- Modify: `.github/workflows/wheels.yml` (new job `checks`)
- Create: `packaging/pip/tests/requirements-checks.txt`
- Test: `packaging/pip/tests/test_workflow_guards.py` (add `test_actionlint_clean`, `test_checks_job_runs_guards`)

**Interfaces:**

- Consumes: `release_check.py` CLI (Task 1); `load_workflow()` (Task 2).
- Produces: job `checks`, which `publish` already `needs`.

- [ ] **Step 1: Write the failing tests**

```python
def test_actionlint_clean():
    exe = shutil.which("actionlint")
    if exe is None:
        if os.environ.get("CI") == "true":
            pytest.fail("actionlint not installed in CI")
        pytest.skip("actionlint not installed (pip install -r packaging/pip/tests/requirements-checks.txt)")
    r = subprocess.run([exe, "-color", str(WORKFLOW_PATH)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr

def test_checks_job_runs_guards():
    job = load_workflow()["jobs"]["checks"]
    runs = "\n".join(s.get("run", "") for s in job["steps"])
    assert "release_check.py check --fetch-upstream" in runs
    assert "release_check.py version --dev-number ${{ github.run_number }}" in runs
    assert "release_check.py version-changed" in runs
    assert "pytest packaging/pip/tests/test_release_check.py packaging/pip/tests/test_workflow_guards.py" in runs
    assert any(s.get("with", {}).get("fetch-depth") == 0 for s in job["steps"])
```

- [ ] **Step 2: Run the tests and check they fail**

Run:
<!-- pyml disable-next-line md013-->
`pip install -r packaging/pip/tests/requirements-checks.txt && python -m pytest packaging/pip/tests/test_workflow_guards.py -v`
Expected: `test_checks_job_runs_guards` FAILS with `KeyError: 'checks'`. `test_actionlint_clean` either passes or
lists real findings in `wheels.yml`.

- [ ] **Step 3: Add the requirements file and the job**

`requirements-checks.txt` pins: `pytest`, `PyYAML`, `packaging`, `actionlint-py==1.7.12.*`.

Job `checks`:

<!-- pyml disable-num-lines 9 md013-->
- `if: github.repository == 'robbietuk/STIR'`, `runs-on: ubuntu-latest`.
- Steps:
  1. checkout with `fetch-depth: 0` (history back to `rel_6.5.0`);
  2. setup-python `3.12`;
  3. `pip install -r packaging/pip/tests/requirements-checks.txt`;
  4. `python packaging/pip/release_check.py version-changed --base "${{ github.event.before || 'HEAD~1' }}" --github-notice`;
  5. `python packaging/pip/release_check.py check --fetch-upstream`;
  6. `python packaging/pip/release_check.py version --dev-number ${{ github.run_number }}`;
  7. `python -m pytest packaging/pip/tests/test_release_check.py packaging/pip/tests/test_workflow_guards.py packaging/pip/tests/test_docs.py -v`.

  Step 7 includes `test_docs.py` from Task 4. Until Task 4 lands, leave that path out, then add it in Task 4.

Fix every actionlint finding *inside `wheels.yml`* (for example, shellcheck quoting in `run:` blocks). Do not touch
upstream workflows. `actionlint` is only ever given `wheels.yml`.

- [ ] **Step 4: Run the tests and check they pass**

Run: `python -m pytest packaging/pip/tests/test_workflow_guards.py -v`
Expected: all PASS, with no skips.

Then, with Robert's go-ahead for Phase 4 pushes (ask once), run `git push fork pip-packaging` and run
`gh run watch --repo robbietuk/STIR $(gh run list --repo robbietuk/STIR --workflow wheels.yml -L1 --json databaseId -q '.[0].databaseId')`.
Expected: `checks` is green. Its log shows `OK: no STIR C++/CMake changes since rel_6.5.0` and
`6.5.0 6.5.0.devN rel_6.5.0`. `publish` shows as skipped.

- [ ] **Step 5: Commit**

<!-- pyml disable md013-->
```bash
git add .github/workflows/wheels.yml packaging/pip/tests/requirements-checks.txt packaging/pip/tests/test_workflow_guards.py packaging/pip/tests/test_ci_config.py
git commit -m "Add checks CI job running actionlint and release guards"
```
<!-- pyml enable md013-->

---

### Task 4: User documentation in `packaging/pip/README.md`

**Files:**

- Modify: `packaging/pip/README.md`. Insert the user section at the top. The Phase 1–3 developer notes move under a
  final `## Building and testing (developers)` heading.
- Test: `packaging/pip/tests/test_docs.py`

**Interfaces:**

- Consumes: package and variant names (contract); the feature list from spec §5.2.
- Produces: `README_REQUIRED_HEADINGS` and the `ROOT / GATE input` table row, whose cells Phase 5 edits. The test
  checks headings and key sentences, not table cells, so Phase 5 can edit the table freely.

- [ ] **Step 1: Write the failing tests**

```python
README_REQUIRED_HEADINGS = [
    "## Installing", "## Which package do I need?", "## Features by platform",
    "## Do not install more than one STIR package", "## When to use conda instead",
    "## Building and testing (developers)",
]
WARNING = "Install exactly one of `stir` or `stir-cuda12` in an environment."

def test_readme_has_user_sections():
    text = README.read_text()
    for h in README_REQUIRED_HEADINGS:
        assert f"\n{h}\n" in text, h
    assert text.index("## Installing") < text.index("## Building and testing (developers)")

def test_readme_warning_and_switch_command():
    text = README.read_text()
    assert WARNING in text
    assert "pip uninstall -y stir stir-cuda12" in text
    assert "conda install -c conda-forge stir" in text

def test_doc_script_paths_exist():
    for doc in (README, RELEASING):
        if doc.exists():
            for rel in re.findall(r"packaging/pip/[\w./-]+\.(?:py|sh|txt|toml|md)", doc.read_text()):
                assert (REPO_ROOT / rel).exists(), f"{doc.name} mentions missing {rel}"
```

- [ ] **Step 2: Run the tests and check they fail**

Run: `python -m pytest packaging/pip/tests/test_docs.py -v`
Expected: `test_readme_has_user_sections` and `test_readme_warning_and_switch_command` FAIL.

- [ ] **Step 3: Write the user section**

The section contains:

- **Installing.** Until a real release, wheels come from CI artifacts:
  `gh run download <run-id> --repo robbietuk/STIR -p 'wheels-*' -D wheels/`, then
  `pip install --find-links wheels/wheels-cpu-<os>-<arch> "stir==<version>"` (artifact names as in the overview:
  `wheels-cpu-linux-x86_64`, `wheels-cpu-macos-arm64`, `wheels-cpu-windows-AMD64`, `wheels-cuda12-linux-x86_64`,
  `wheels-cuda12-windows-AMD64`; `--find-links` is not recursive). The exact `==<version>` pin is required:
  `.devN` builds are pre-releases. After a release this becomes `pip install stir`. Then run a check:
  `python -c "import stir; print(stir.__file__)"`.
- **Which package do I need?**
  - `stir`: CPU, on Linux x86_64, macOS arm64 (Apple silicon) and Windows x86_64.
  - `stir-cuda12`: NVIDIA GPU on Linux x86_64 or Windows x86_64. Needs a driver whose "CUDA Version" in
    `nvidia-smi` is ≥ 12.0, and a GPU with compute capability ≥ 7.0.
  - Both are imported as `import stir`. macOS has no CUDA.
  - Not available yet (use conda, or build from the sdist): Linux aarch64, Intel macOS, a CUDA 13 package.
- **Features by platform.** Copy this table, which combines the two §5.2 tables:

  | Feature | Linux x86_64 | macOS arm64 | Windows x86_64 |
  |---|---|---|---|
  | Core STIR + Python API, OpenMP | all | `stir` | all |
  | HDF5 (GE), PETSIRD, JSON, ITK image IO | all | `stir` | all |
  | parallelproj CPU | all | `stir` | all |
  | parallelproj CUDA + STIR CUDA code | `stir-cuda12` | — | `stir-cuda12` |
  | ROOT / GATE input | not yet (conda) | not yet (conda) | — |
  | NiftyPET projector, MATLAB, STIR executables, C++ headers | — | — | — |

  "all" means `stir` and `stir-cuda12`. Python 3.11–3.15. Then apply Phase 2's "Known gaps" and
  "Feature status by platform" from the existing README: every ✗ there becomes a footnoted cell here.
- **Do not install more than one STIR package.** Include `WARNING` verbatim. Explain why: both provide the same
  `stir/` folder, so they overwrite each other. Show `pip list | grep -i stir` to see what is installed. To switch,
  run `pip uninstall -y stir stir-cuda12`, then install exactly one.
- **When to use conda instead** (`conda install -c conda-forge stir`):
  - reading GATE/ROOT output (`.hroot`/`.root`), until ROOT support lands;
  - command-line utilities such as `lm_to_projdata` or `OSMAPOSL` (wheels ship no executables);
  - compiling C++ against STIR (wheels ship no headers or CMake config);
  - NiftyPET, MATLAB.

  On Windows, ROOT is unavailable in conda too.
- Explain that `STIR_CONFIG_DIR` and `STIR_DOC_DIR` need no setting, and that a user's own value takes priority.

Then run `pre-commit run pymarkdown --files packaging/pip/README.md`.

- [ ] **Step 4: Run the tests and check they pass**

Run: `python -m pytest packaging/pip/tests/test_docs.py -v && pre-commit run pymarkdown --files packaging/pip/README.md`
Expected: all PASS, pymarkdown `Passed`. Add `packaging/pip/tests/test_docs.py` to the `checks` job pytest line now.

- [ ] **Step 5: Commit**

```bash
git add packaging/pip/README.md packaging/pip/tests/test_docs.py .github/workflows/wheels.yml
git commit -m "Add user documentation to pip packaging README"
```

---

### Task 5: `packaging/pip/RELEASING.md`

**Files:**

- Create: `packaging/pip/RELEASING.md`
- Test: `packaging/pip/tests/test_docs.py` (add RELEASING tests)

**Interfaces:**

- Consumes: the `release_check.py` CLI (Task 1); the `target` input and `publish` shape (Task 2); `local-index.sh`
  (Phase 1: `packaging/pip/local-index.sh up DIR | down | status`, serving `http://localhost:8080/simple/`).
- Produces: the heading `## Re-check on every STIR release`, an ordered checklist that Phase 5 appends its ROOT gate
  step to.

- [ ] **Step 1: Write the failing tests**

```python
RELEASING_REQUIRED = [
    "## One-time setup", "## Merging a new STIR release", "## Re-check on every STIR release",
    "## PyPI name check", "## Trusted publishing setup (not done)", "## Enabling the publish job",
]
def test_releasing_sections():
    text = RELEASING.read_text()
    for h in RELEASING_REQUIRED:
        assert f"\n{h}\n" in text, h

def test_releasing_key_commands():
    text = RELEASING.read_text()
    for s in ("git remote add fork https://github.com/robbietuk/STIR.git",
              "git remote set-url --push origin DISABLED-never-push-to-UCL",
              "git fetch origin tag rel_X.Y.Z --no-tags",
              "git merge --no-ff rel_X.Y.Z",
              "python packaging/pip/release_check.py check",
              "gh workflow run wheels.yml --repo robbietuk/STIR --ref merge-rel_X.Y.Z -f target=none"):
        assert s in text, s

def test_name_table_rows():
    text = RELEASING.read_text()
    for name in ("stir", "stir-cuda12", "stir-recon", "stir-recon-cuda12"):
        assert f"| `{name}` | https://pypi.org/project/{name}/ |" in text, name
```

- [ ] **Step 2: Run the tests and check they fail**

Run: `python -m pytest packaging/pip/tests/test_docs.py -v -k releasing`
Expected: FAIL with `FileNotFoundError` (RELEASING.md does not exist yet).

- [ ] **Step 3: Write RELEASING.md**

Sections, in order:

1. **One-time setup.**
   - Remotes (the same scheme as Phase 1): `origin` = `https://github.com/UCL/STIR.git`, `fork` =
     `https://github.com/robbietuk/STIR.git`. Check with `git remote -v`. In a clone of the fork, first run
     `git remote rename origin fork` and `git remote add origin https://github.com/UCL/STIR.git`; otherwise run
     `git remote add fork https://github.com/robbietuk/STIR.git`.
   - Then `git remote set-url --push origin DISABLED-never-push-to-UCL`. Expected: `git remote -v` shows
     `origin DISABLED-never-push-to-UCL (push)`.
   - Then `gh repo set-default robbietuk/STIR`.
2. **Merging a new STIR release.** Numbered commands, with `rel_X.Y.Z` as a placeholder:
   1. `git switch pip-packaging && git pull --ff-only fork pip-packaging`.
   2. `git fetch origin tag rel_X.Y.Z --no-tags`.
   3. `git switch -c merge-rel_X.Y.Z`.
   4. `git merge --no-ff rel_X.Y.Z -m "Merge STIR rel_X.Y.Z into pip-packaging"`.
   5. Resolve conflicts:
      - For any protected file (C++/CMake/SWIG), take upstream with `git checkout --theirs -- <file>`.
      - For `src/swig/python/stir/__init__.py`, take upstream's file, then re-add our lines exactly as listed in
        `INIT_PY_ALLOWED_LINES` (`release_check.py`), in that order, around the unchanged swigstir import.
      - Our `packaging/`, `pyproject.toml` and `wheels.yml` keep ours. If upstream ever adds its own
        `pyproject.toml`, stop and ask.
   6. `python packaging/pip/release_check.py check --fetch-upstream`. Expected:
      `OK: no STIR C++/CMake changes since rel_X.Y.Z`.
   7. `python -m pytest packaging/pip/tests -v --ignore=packaging/pip/tests/test_wheel_smoke.py`.
   8. `git push fork merge-rel_X.Y.Z`, then
      `gh workflow run wheels.yml --repo robbietuk/STIR --ref merge-rel_X.Y.Z -f target=none`.
   9. Verify:
      - all jobs are green;
      - the `checks` log shows `VERSION.txt changed: A -> X.Y.Z`;
      - `gh run download <id> --repo robbietuk/STIR -D dist/`, then `packaging/pip/local-index.sh up dist/`, then
        in a fresh venv `pip install --index-url http://localhost:8080/simple/ "stir==<X.Y.Z.devN>"`, then the
        smoke test, then `packaging/pip/local-index.sh down`.
   10. `git switch pip-packaging && git merge --ff-only merge-rel_X.Y.Z && git push fork pip-packaging`.
3. **Re-check on every STIR release.** A checklist:
   - Python versions (is a new CPython out? check NumPy and cibuildwheel support);
   - `packaging/pip/deps/versions.toml` against upstream's `build_environment.yml`;
   - CUDA versions;
   - the PyPI name table is still valid.
4. **PyPI name check.** Robert does this by hand in a browser; nothing is registered. Use a table with columns
   `Name | URL | Result | Checked on | By`. It has one row per name (the two primary, then the two fallback
   names; a deferred variant such as `stir-cuda13` gets its rows when Robert adds it).
   Result is `unchecked` initially. Explain:
   - a 404 page means unregistered, but PyPI can still refuse a name (similar to an existing name, or prohibited);
   - a pending publisher does **not** reserve a name;
   - only the first real upload does.

   If a primary name is taken, use both fallbacks together. That change goes through `prepare_build.py`'s
   variant→name mapping and needs Robert's approval (see Contract concerns).
5. **Trusted publishing setup (not done).** Steps for Robert, all marked "do not do until releasing":
   - On pypi.org, go to Account → Publishing → Add a new pending publisher → GitHub. Fill in: Owner `robbietuk`,
     Repository `STIR`, Workflow `wheels.yml`, Environment `pypi`, Project name `stir`. Repeat for `stir-cuda12`.
   - On GitHub, go to robbietuk/STIR → Settings → Environments → New environment `pypi`. Set required reviewer
     Robert and deployment branches limited to `pip-packaging`.
   - No API tokens or secrets.
6. **Enabling the publish job.** In one commit, by Robert:
   - replace `if: false` with the guard written in the comment;
   - change `test_publish_job_guard_is_false` to assert that exact string;
   - push.

   Then run `gh workflow run wheels.yml --repo robbietuk/STIR --ref pip-packaging -f target=pypi` and approve the
   environment deployment. Afterwards, revert the guard to `if: false` in a follow-up commit. Include the warning that
   PyPI uploads cannot be overwritten (a version number can never be reused).

- [ ] **Step 4: Run the tests, the linter and a dry run of the procedure**

Run:
`python -m pytest packaging/pip/tests/test_docs.py -v && pre-commit run pymarkdown --files packaging/pip/RELEASING.md`
Expected: all PASS.

Dry run, in a scratch worktree (`git worktree add /tmp/stir-merge-dryrun pip-packaging`), executing steps 2.1–2.6
with `X.Y.Z = 6.5.0`:

- the merge prints `Already up to date.`;
- the check prints `OK: no STIR C++/CMake changes since rel_6.5.0`.

Do not push from the dry run. Then run `git worktree remove /tmp/stir-merge-dryrun`.

- [ ] **Step 5: Commit**

```bash
git add packaging/pip/RELEASING.md packaging/pip/tests/test_docs.py
git commit -m "Add RELEASING.md with upstream merge and publish procedures"
```

---

## Contract concerns

Resolved in the overview's "Cross-plan review (2026-11-12)"; the overview wins where these notes differ.

1. **New CI job `checks`.** The contract's job list is `sdist, build_cpu, build_cuda, rehearse_publish, publish`.
   This plan adds `checks`, and `publish` needs it. It renames nothing, but the overview table should list it.
2. **`publish` has no `github.repository` guard.** The contract says "every job has
   `if: github.repository == 'robbietuk/STIR'`". `publish` has `if: false` instead, which is stricter, and the guard
   used when enabling it includes the repository check. The test exempts `publish` explicitly.
3. **`prepare_build.py` and `VERSION.txt` location.** `dev_version()` assumes `prepare_build.py` reads `VERSION.txt`
   from the directory that contains `--pyproject`. If Phase 1 reads it from the script's repo root instead,
   `test_dev_version_with_rc_version_txt` cannot use a temp dir. Either Phase 1 adopts this rule, or that test writes
   VERSION.txt into a scratch clone.
4. **`local-index.sh` CLI is not in the contract.** This plan assumes `local-index.sh WHEEL_DIR`, serving
   `http://localhost:8080/simple/` (spec §5.6 port).
5. **Fallback names.** The contract fixes `cpu→stir` and `cuda12→stir-cuda12` (`cuda13→stir-cuda13` is reserved
   for the deferred variant). Switching to
   `stir-recon*` would change `prepare_build.py`, its tests and the README. This plan only documents the switch.
6. **Wider protected set than the brief.** `release_check.py` also protects `*.c`, `*.txx`, `*.i`, `*.h.in`,
   `*.cmake.in` and the two submodule pointers. These are STIR code or build inputs too. Remove them if Robert wants
   the literal list only.
7. **The local checkout's `origin` is `https://github.com/UCL/STIR.git`** (seen in `/home/claude/src/STIR`). The
   one-time setup in RELEASING.md fixes this. Nothing in Phases 1–3 should `git push` without a remote name.

## References

- PyPI docs, "Publishing with a Trusted Publisher": https://docs.pypi.org/trusted-publishers/using-a-publisher/
  (`id-token: write` at job level, `environment: pypi`, `pypa/gh-action-pypi-publish@release/v1`).
- PyPI docs, "Creating a PyPI project with a Trusted Publisher":
  https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/ (pending publishers do not reserve names).
- PyPA guide:
  https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/
- actionlint usage (exit codes 0/1/2/3, shellcheck integration):
  https://github.com/rhysd/actionlint/blob/main/docs/usage.md
- `actionlint-py` 1.7.12.x (pip-installable actionlint binary).
- STIR `.pymarkdown` (MD013 at 120) and `.pre-commit-config.yaml` in this repo.
