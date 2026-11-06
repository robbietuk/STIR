# SPDX-License-Identifier: Apache-2.0
# Part of STIR (see STIR/LICENSE.txt).
"""STIR INTERFACE layer (anti-corruption layer). The only package that may touch ``stir``.

    stir module -> SwigStirGateway -> StirProjDataSource -> model.ProjDataset

``gateway`` and ``source`` import nothing from STIR; only ``swig_gateway`` does, lazily.
"""
from .gateway import ProjDataLayout, StirGateway, StirNotFoundError, StirProjDataHandle
from .source import StirProjDataSource, open_stir_source

__all__ = ["ProjDataLayout", "StirGateway", "StirNotFoundError", "StirProjDataHandle",
           "StirProjDataSource", "open_stir_source"]
