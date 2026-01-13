# -*- mode: python ; coding: utf-8 -*-
# Legacy reference: retained for future GUI/PyInstaller packaging work.
"""
PyInstaller spec file for XNATIO Uploader.

Build commands:
    # One-file executable (recommended for distribution)
    pyinstaller xnatio-uploader.spec

    # Or build both CLI and GUI versions
    pyinstaller xnatio-uploader.spec --name xnatio-uploader-cli
"""

import sys
from pathlib import Path

block_cipher = None

# Determine platform-specific settings
is_windows = sys.platform == 'win32'
is_macos = sys.platform == 'darwin'

# Main analysis
a = Analysis(
    ['src/xnatio_uploader/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'xnatio_uploader',
        'xnatio_uploader.cli',
        'xnatio_uploader.gui',
        'xnatio_uploader.uploader',
        'xnatio_uploader.config',
        'xnatio_uploader.defaults',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
        'torch',
        'tensorflow',
        'pytest',
        'setuptools',
        'pip',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Single executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='xnatio-uploader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Keep console for CLI mode
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Windows icon (if available)
    icon='assets/icon.ico' if is_windows and Path('assets/icon.ico').exists() else None,
)

# macOS app bundle (optional)
if is_macos:
    app = BUNDLE(
        exe,
        name='XNATIO Uploader.app',
        icon='assets/icon.icns' if Path('assets/icon.icns').exists() else None,
        bundle_identifier='io.xnatio.uploader',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'CFBundleShortVersionString': '1.0.0',
        },
    )
