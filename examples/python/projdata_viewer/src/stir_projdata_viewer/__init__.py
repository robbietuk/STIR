# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""Interactive viewer for STIR projection data.

The package root imports nothing heavy: the model and sources are Qt-free and
``stir``-free; ``view`` (PySide6 + pyqtgraph) and ``stir_interface.swig_gateway`` are imported on demand.
"""
__version__ = "0.1.0"
