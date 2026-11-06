# SPDX-License-Identifier: Apache-2.0
"""Enforces the layering: model <- viewmodel <- view, with STIR confined to ``stir_interface``.

Static check: parse every source file and resolve every import (including relative and function-level).
Dynamic check: import the Qt-free layers in a clean interpreter and look at ``sys.modules``.
"""
import ast
import pathlib
import subprocess
import sys

import pytest

PKG = "stir_projdata_viewer"
SRC = pathlib.Path(__file__).resolve().parents[1] / "src"
ROOT = SRC / PKG

# layer -> internal layers it may import. Top-level package files (cli, __main__) may import anything.
ALLOWED_INTERNAL = {
    "model": {"model"},
    "sources": {"model", "sources", "stir_interface"},      # loader reaches stir_interface lazily
    "stir_interface": {"model", "stir_interface"},
    "viewmodel": {"model", "viewmodel"},
    "view": {"model", "viewmodel", "view"},          # no sources: demo data is injected into the view model
}
QT = {"PySide6", "pyqtgraph"}


def layer_of(path: pathlib.Path) -> str | None:
    rel = path.relative_to(ROOT)
    return rel.parts[0] if len(rel.parts) > 1 else None


def imports_of(path: pathlib.Path):
    """Yield (absolute module name, lineno) for every import in the file."""
    module = ".".join((PKG, *path.relative_to(ROOT).with_suffix("").parts))
    package = module if path.name == "__init__.py" else module.rsplit(".", 1)[0]
    if path.name == "__init__.py":
        package = module.rsplit(".__init__", 1)[0] if module.endswith(".__init__") else module
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name, node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")
                base = base[: len(base) - (node.level - 1)]
                name = ".".join(base + ([node.module] if node.module else []))
            else:
                name = node.module or ""
            yield name, node.lineno
            for a in node.names:                                  # `from . import x` imports submodule x
                yield f"{name}.{a.name}", node.lineno


FILES = sorted(ROOT.rglob("*.py"))


def test_there_are_files_to_check():
    assert len(FILES) > 15 and {layer_of(f) for f in FILES} >= set(ALLOWED_INTERNAL)


@pytest.mark.parametrize("path", [f for f in FILES if layer_of(f) in ALLOWED_INTERNAL],
                         ids=lambda p: str(p.relative_to(ROOT)))
def test_internal_imports_respect_layers(path):
    layer = layer_of(path)
    for name, line in imports_of(path):
        if name.split(".")[0] != PKG:
            continue
        parts = name.split(".")
        target = parts[1] if len(parts) > 1 else None
        if target in ALLOWED_INTERNAL:
            assert target in ALLOWED_INTERNAL[layer], (
                f"{path.relative_to(ROOT)}:{line} imports {name}: layer '{layer}' may not depend on '{target}'")


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_third_party_imports_are_confined(path):
    layer = layer_of(path)
    rel = path.relative_to(ROOT).as_posix()
    for name, line in imports_of(path):
        top = name.split(".")[0]
        if top in QT:
            assert layer == "view" or rel == "app.py", f"{rel}:{line}: Qt/pyqtgraph ({name}) outside the view layer"
        if top == "stir":
            assert rel == "stir_interface/swig_gateway.py", f"{rel}:{line}: only the SWIG gateway may import stir"


def test_swig_gateway_imports_stir_only_lazily():
    tree = ast.parse((ROOT / "stir_interface" / "swig_gateway.py").read_text())
    for node in tree.body:                                         # module level
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] + [getattr(node, "module", "") or ""]
            assert not any(n.split(".")[0] == "stir" for n in names)


@pytest.mark.parametrize("modules", [
    ["stir_projdata_viewer.model"],
    ["stir_projdata_viewer.sources"],
    ["stir_projdata_viewer.stir_interface"],
    ["stir_projdata_viewer.viewmodel"],
    ["stir_projdata_viewer.model", "stir_projdata_viewer.sources", "stir_projdata_viewer.stir_interface",
     "stir_projdata_viewer.viewmodel", "stir_projdata_viewer.cli"],
])
def test_qt_free_layers_import_without_loading_qt_or_stir(modules):
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(SRC)!r})\n"
        f"for m in {modules!r}:\n"
        "    __import__(m)\n"
        "bad = sorted(m for m in sys.modules if m.split('.')[0] in {'PySide6', 'pyqtgraph', 'stir', 'matplotlib'})\n"
        "assert not bad, bad\n")
    r = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_model_depends_only_on_stdlib_and_numpy():
    stdlib = set(sys.stdlib_module_names)
    for path in (ROOT / "model").rglob("*.py"):
        for name, line in imports_of(path):
            top = name.split(".")[0]
            assert top in stdlib or top in {"numpy", PKG, "__future__"}, f"{path.name}:{line} imports {name}"


def test_matplotlib_is_gone():
    for path in FILES:
        for name, _ in imports_of(path):
            assert name.split(".")[0] != "matplotlib"


def test_composition_root_is_the_only_top_level_module_that_wires_layers():
    """Only app.py (and the cli, which imports it lazily) may know about both view and sources."""
    for path in ROOT.glob("*.py"):
        if path.name in ("app.py", "cli.py", "__main__.py", "__init__.py"):
            continue
        raise AssertionError(f"unexpected top-level module {path.name}: put it in a layer")


def test_theme_and_shared_viewmodel_logic_import_without_qt():
    """The colour scheme (view.theme) and the shared choice/binding logic must stay Qt-free."""
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(SRC)!r})\n"
        "for m in ('stir_projdata_viewer.view.theme', 'stir_projdata_viewer.viewmodel.options',\n"
        "          'stir_projdata_viewer.viewmodel.bindings'):\n"
        "    __import__(m)\n"
        "bad = sorted(m for m in sys.modules if m.split('.')[0] in {'PySide6', 'pyqtgraph', 'stir'})\n"
        "assert not bad, bad\n")
    r = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_widgets_never_hard_code_colours():
    for name in ("components.py", "window.py", "styling.py"):
        text = (ROOT / "view" / name).read_text()
        assert not __import__("re").search(r"#[0-9a-fA-F]{6}\b", text), f"{name} hard-codes a colour; use the Palette"
