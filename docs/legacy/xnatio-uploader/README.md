# Legacy XNATIO Uploader (GUI + PyInstaller)

This folder preserves the original GUI and PyInstaller artifacts from the
standalone `xnatio-uploader` project. These files are **not** wired into the
current `xnatio` package and are kept strictly for future reference.

If the GUI is revived for internal distribution:
- Update imports to use `xnatio.uploaders.parallel_rest` and `xnatio.config`.
- Align configuration with `XNAT_SERVER`, `XNAT_USERNAME`, and `XNAT_PASSWORD`.
- Rework the PyInstaller spec to target a new GUI entry point in `xnatio`.
- Validate tkinter availability on target Windows laptops.

Contents:
- `gui.py`: Tkinter GUI prototype.
- `build.py`: PyInstaller build script template.
- `xnatio-uploader*.spec`: Example spec files for onefile builds.
