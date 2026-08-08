"""Ren'Py SDK path configuration with cross-platform auto-detection."""

import os
import sys
import glob as glob_mod
import platform

# Common base directories to scan for Ren'Py SDK installations.
# We glob for renpy-*-sdk under each of these. Built per-platform.
def _get_scan_bases() -> list[str]:
    bases: list[str] = []
    home = os.path.expanduser("~")
    if sys.platform == "win32":
        bases = [
            os.path.join(home, "RenPy"),
            os.path.join(home, "Documents", "RenPy"),
            r"D:\RenPy",
            r"D:\RenPY",
            r"C:\RenPy",
            r"C:\Program Files\RenPy",
            r"D:\Software\RenPy",
        ]
    elif sys.platform == "darwin":
        bases = [
            "/Applications/RenPy",
            os.path.join(home, "Library", "RenPy"),
            os.path.join(home, "Documents", "RenPy"),
            os.path.join(home, "RenPy"),
            "/opt/renpy",
        ]
    else:  # Linux and other Unix
        bases = [
            os.path.join(home, "renpy"),
            os.path.join(home, "RenPy"),
            os.path.join(home, ".local", "share", "renpy"),
            "/opt/renpy",
            "/usr/local/renpy",
            "/usr/share/renpy",
        ]
    return bases


_SDK_PATH: str | None = None


def _scan_for_sdk() -> list[str]:
    """Glob common directories for renpy-*-sdk folders, newest first."""
    candidates: list[str] = []
    for base in _get_scan_bases():
        if not os.path.isdir(base):
            continue
        for hit in glob_mod.glob(os.path.join(base, "renpy-*-sdk")):
            if os.path.isdir(hit):
                candidates.append(hit)
    # Sort by modification time, newest first
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return candidates


def get_sdk_path() -> str:
    """Get the Ren'Py SDK path.

    Resolution order:
      1. Cached value
      2. RENPY_SDK_PATH environment variable
      3. Glob scan of common directories (newest match wins)
    """
    global _SDK_PATH
    if _SDK_PATH:
        return _SDK_PATH

    env_path = os.environ.get("RENPY_SDK_PATH")
    if env_path and os.path.isdir(env_path):
        _SDK_PATH = env_path
        return _SDK_PATH

    for path in _scan_for_sdk():
        _SDK_PATH = path
        return _SDK_PATH

    bases = _get_scan_bases()
    raise FileNotFoundError(
        "Ren'Py SDK not found. Set the RENPY_SDK_PATH environment variable "
        "to your Ren'Py SDK directory, or install Ren'Py SDK under one of: "
        + ", ".join(bases)
    )


def get_python_exe() -> str:
    """Get the path to Ren'Py's embedded Python executable."""
    sdk = get_sdk_path()
    if sys.platform == "win32":
        python_path = os.path.join(sdk, "lib", "py3-windows-x86_64", "python.exe")
    elif sys.platform == "darwin":
        # macOS: could be arm64 or x86_64
        for arch in ["darwin-arm64", "darwin-x86_64", "darwin"]:
            candidate = os.path.join(sdk, "lib", f"py3-{arch}", "python")
            if os.path.isfile(candidate):
                return candidate
        python_path = os.path.join(sdk, "lib", "py3-darwin", "python")
    else:
        for arch in ["linux-x86_64", "linux-aarch64", "linux"]:
            candidate = os.path.join(sdk, "lib", f"py3-{arch}", "python")
            if os.path.isfile(candidate):
                return candidate
        python_path = os.path.join(sdk, "lib", "py3-linux-x86_64", "python")
    if os.path.isfile(python_path):
        return python_path
    raise FileNotFoundError(f"Ren'Py Python not found at: {python_path}")


def get_renpy_script() -> str:
    """Get the path to renpy.py entry script."""
    sdk = get_sdk_path()
    script_path = os.path.join(sdk, "renpy.py")
    if os.path.isfile(script_path):
        return script_path
    raise FileNotFoundError(f"renpy.py not found at: {script_path}")
