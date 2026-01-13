#!/usr/bin/env python3
# Legacy reference: retained for future GUI/PyInstaller packaging work.
"""
Build script for XNATIO Uploader.

Creates standalone executables for Windows, macOS, and Linux.

Usage:
    python build.py          # Build for current platform
    python build.py --clean  # Clean build artifacts first
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def get_platform_name() -> str:
    """Get a short platform name for the output file."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "windows":
        return f"windows-{machine}"
    elif system == "darwin":
        if machine == "arm64":
            return "macos-arm64"
        return "macos-x64"
    else:
        return f"linux-{machine}"


def clean_build():
    """Remove build artifacts."""
    dirs_to_remove = ["build", "dist", "__pycache__"]
    files_to_remove = ["*.spec.bak"]

    for dir_name in dirs_to_remove:
        for path in Path(".").rglob(dir_name):
            if path.is_dir():
                print(f"Removing {path}")
                shutil.rmtree(path)

    for pattern in files_to_remove:
        for path in Path(".").glob(pattern):
            print(f"Removing {path}")
            path.unlink()


def check_dependencies():
    """Check that required build dependencies are installed."""
    try:
        import PyInstaller
        print(f"PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("Error: PyInstaller not installed")
        print("Install with: pip install pyinstaller")
        sys.exit(1)


def build_executable():
    """Build the executable using PyInstaller."""
    platform_name = get_platform_name()
    print(f"Building for platform: {platform_name}")

    # Determine output name
    if platform.system() == "Windows":
        output_name = f"xnatio-uploader-{platform_name}.exe"
    else:
        output_name = f"xnatio-uploader-{platform_name}"

    # Run PyInstaller
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", output_name.replace(".exe", ""),
        "--console",  # Keep console for CLI support
        "--clean",
        "src/xnatio_uploader/__main__.py",
    ]

    # Add hidden imports
    hidden_imports = [
        "xnatio_uploader",
        "xnatio_uploader.cli",
        "xnatio_uploader.gui",
        "xnatio_uploader.uploader",
        "xnatio_uploader.config",
        "xnatio_uploader.defaults",
    ]
    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])

    # Add paths
    cmd.extend(["--paths", "src"])

    # Exclude unnecessary modules
    excludes = [
        "matplotlib", "numpy", "pandas", "scipy", "PIL",
        "cv2", "torch", "tensorflow", "pytest", "setuptools", "pip",
    ]
    for exc in excludes:
        cmd.extend(["--exclude-module", exc])

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)

    if result.returncode != 0:
        print("Build failed!")
        sys.exit(1)

    # Report output
    dist_dir = Path("dist")
    if dist_dir.exists():
        for f in dist_dir.iterdir():
            size_mb = f.stat().st_size / 1024 / 1024
            print(f"\nBuilt: {f} ({size_mb:.1f} MB)")

    print("\nBuild complete!")
    print(f"\nTo distribute, copy the executable from dist/ to the target machine.")
    print("Users should place their .env file in the same directory as the executable.")


def main():
    parser = argparse.ArgumentParser(description="Build XNATIO Uploader executable")
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts first")
    args = parser.parse_args()

    os.chdir(Path(__file__).parent)

    if args.clean:
        print("Cleaning build artifacts...")
        clean_build()

    print("Checking dependencies...")
    check_dependencies()

    print("\nBuilding executable...")
    build_executable()


if __name__ == "__main__":
    main()
