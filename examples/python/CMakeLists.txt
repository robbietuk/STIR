 INSTALL(FILES
          Vision_files_preprocess.py
          # Quadra_files_preprocess.py not yet ready to be installed
          projdata_profiles.py
          LBFGSBPC.py
          DESTINATION ${PYTHON_DEST}/stir/)
 INSTALL(DIRECTORY projdata_visualisation  DESTINATION ${PYTHON_DEST}/stir/)
 # PySide6/pyqtgraph projection data viewer (with TOF support), installed next to the stir package so that
 # `python -m stir_projdata_viewer` and `from stir_projdata_viewer.app import launch` work wherever `import stir`
 # does. Needs numpy, PySide6 and pyqtgraph at run time. See projdata_viewer/README.md.
 INSTALL(DIRECTORY projdata_viewer/src/stir_projdata_viewer DESTINATION ${PYTHON_DEST}/
         PATTERN "__pycache__" EXCLUDE)
