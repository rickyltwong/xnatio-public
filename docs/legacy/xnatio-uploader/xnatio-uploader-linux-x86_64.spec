# -*- mode: python ; coding: utf-8 -*-
# Legacy reference: retained for future GUI/PyInstaller packaging work.


a = Analysis(
    ['src/xnatio_uploader/__main__.py'],
    pathex=['src'],
    binaries=[],
    datas=[],
    hiddenimports=['xnatio_uploader', 'xnatio_uploader.cli', 'xnatio_uploader.gui', 'xnatio_uploader.uploader', 'xnatio_uploader.config', 'xnatio_uploader.defaults'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'PIL', 'cv2', 'torch', 'tensorflow', 'pytest', 'setuptools', 'pip'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='xnatio-uploader-linux-x86_64',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
