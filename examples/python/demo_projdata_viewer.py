# Copyright 2026 University College London

# This file is part of STIR.
#
# SPDX-License-Identifier: Apache-2.0
#
# See STIR/LICENSE.txt for details

# demo_projdata_viewer.py
# Demo of the PySide6/pyqtgraph projection data viewer (examples/python/projdata_viewer) with STIR objects.
# Needs numpy, PySide6 and pyqtgraph. The viewer is installed with STIR next to the stir module;
# from a source checkout you can instead `pip install -e examples/python/projdata_viewer`.
import os

import stir
from stir_projdata_viewer.app import launch

filename = os.path.join(stir.get_STIR_examples_dir(), "recon_demo/smalllong.hs")
proj_data = stir.ProjData.read_from_file(filename)

# A ProjData object (e.g. one you just forward projected into), shown without writing it to disk.
# Blocks until the window is closed.
launch(proj_data)
# Could also have used
# launch(filename)
# or, from the command line:  python -m stir_projdata_viewer <path to>/smalllong.hs
print("Demo done.")
