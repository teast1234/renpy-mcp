"""Build tools: compile_project, lint_project, check_project, manage_saves.

Wraps Ren'Py CLI commands via subprocess.
"""

import subprocess
import re
import os
import glob as glob_mod
import time
from .config import get_python_exe, get_renpy_script


def _clear_cache(project_path: str):
    """Remove all .rpyc cache files in the game directory."""
    game_dir = os.path.join(project_path, "game")
    if not os.path.isdir(game_dir):
        return
    for rpyc in glob_mod.glob(os.path.join(game_dir, "**", "*.rpyc"), recursive=True):
        try:
            os.remove(rpyc)
        except OSError:
            pass


def compile_project(project_path: str, force: bool = False) -> dict:
    """Compile a Ren'Py project (.rpy -> .rpyc).

    Args:
        project_path: Absolute path to the Ren'Py project root directory.
        force: If True, clear .rpyc cache before compiling.

    Returns {ok: bool, errors: list[dict], raw_output: str}
    """
    if force:
        _clear_cache(project_path)
    return _run_renpy_command(project_path, "compile")


def lint_project(project_path: str) -> dict:
    """Run Ren'Py lint on a project.

    Returns {ok: bool, warnings: list[dict], raw_output: str}
    """
    return _run_renpy_command(project_path, "lint")


def check_project(project_path: str, force: bool = True) -> dict:
    """Run compile then lint in one call. Returns combined structured result.

    If compile fails, returns immediately with compile errors (no point linting
    broken syntax). If compile passes, runs lint and merges warnings.

    Args:
        project_path: Absolute path to the Ren'Py project root directory.
        force: If True, clear .rpyc cache before compiling (default True).

    Returns:
        {
            "ok": bool,
            "compile_errors": [...],
            "lint_warnings": [...],
            "raw_output": str,
        }
    """
    compile_result = compile_project(project_path, force=force)
    if not compile_result.get("ok"):
        return {
            "ok": False,
            "compile_errors": compile_result.get("errors", []),
            "lint_warnings": [],
            "raw_output": compile_result.get("raw_output", ""),
            "note": "Compile failed, lint skipped.",
        }

    lint_result = lint_project(project_path)
    all_ok = lint_result.get("ok", True)
    return {
        "ok": all_ok,
        "compile_errors": [],
        "lint_warnings": lint_result.get("warnings", []),
        "raw_output": compile_result.get("raw_output", "") + "\n" + lint_result.get("raw_output", ""),
    }


# ── Save state management ─────────────────────────────────────────────

_STALE_PATTERNS = ["_reload-*", "_tracesave-*"]


def manage_saves(project_path: str, action: str = "list") -> dict:
    """List, clear, or clear-stale Ren'Py save files.

    Ren'Py stores saves under game/saves/. Stale saves (_reload-*, _tracesave-*)
    can retain old call stacks that cause 'Could not find return label' errors
    after script refactors.

    Args:
        project_path: Absolute path to the Ren'Py project root directory.
        action: One of:
            - "list": list all save files with size + mtime
            - "clear": delete ALL save files (game restarts from 'start')
            - "clear_stale": delete only _reload-* and _tracesave-* files

    Returns:
        {
            "ok": bool,
            "action": str,
            "saves": [{name, size, mtime}],   # for "list"
            "deleted": [name],               # for clear/clear_stale
            "message": str,
        }
    """
    saves_dir = os.path.join(project_path, "game", "saves")
    if not os.path.isdir(saves_dir):
        return {
            "ok": True,
            "action": action,
            "saves": [],
            "deleted": [],
            "message": "No saves directory found (no saves yet).",
        }

    if action == "list":
        saves = _list_save_files(saves_dir)
        return {
            "ok": True,
            "action": "list",
            "saves": saves,
            "deleted": [],
            "message": f"Found {len(saves)} save file(s).",
        }

    if action == "clear":
        deleted = _delete_save_files(saves_dir, pattern="*")
        return {
            "ok": True,
            "action": "clear",
            "saves": [],
            "deleted": deleted,
            "message": f"Deleted {len(deleted)} save file(s). Game will restart from 'start'.",
        }

    if action == "clear_stale":
        deleted = []
        for pat in _STALE_PATTERNS:
            deleted.extend(_delete_save_files(saves_dir, pattern=pat))
        return {
            "ok": True,
            "action": "clear_stale",
            "saves": [],
            "deleted": deleted,
            "message": f"Deleted {len(deleted)} stale save file(s).",
        }

    return {
        "ok": False,
        "action": action,
        "saves": [],
        "deleted": [],
        "message": f"Unknown action: {action}. Use list / clear / clear_stale.",
    }


def _list_save_files(saves_dir: str) -> list[dict]:
    """List all files in saves dir with metadata."""
    saves = []
    for f in sorted(os.listdir(saves_dir)):
        full = os.path.join(saves_dir, f)
        if not os.path.isfile(full):
            continue
        stat = os.stat(full)
        saves.append({
            "name": f,
            "size": stat.st_size,
            "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
        })
    return saves


def _delete_save_files(saves_dir: str, pattern: str = "*") -> list[str]:
    """Delete files matching glob pattern in saves dir. Returns deleted names."""
    deleted = []
    for f in glob_mod.glob(os.path.join(saves_dir, pattern)):
        if not os.path.isfile(f):
            continue
        name = os.path.basename(f)
        try:
            os.remove(f)
            deleted.append(name)
        except OSError:
            pass
    return deleted


def _run_renpy_command(project_path: str, command: str) -> dict:
    """Execute a Ren'Py CLI command and parse output."""
    try:
        python_exe = get_python_exe()
        renpy_script = get_renpy_script()
    except FileNotFoundError as e:
        return {"ok": False, "errors": [{"message": str(e)}], "raw_output": str(e)}

    cmd = [python_exe, renpy_script, project_path, command]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=False,
            timeout=120,
            cwd=os.path.dirname(renpy_script),
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "errors": [{"message": "Command timed out (120s)"}], "raw_output": ""}
    except FileNotFoundError:
        return {"ok": False, "errors": [{"message": f"Python executable not found: {python_exe}"}], "raw_output": ""}

    try:
        out = result.stdout.decode("utf-8", errors="replace")
        err = result.stderr.decode("utf-8", errors="replace")
    except Exception:
        # Fallback to system's preferred encoding (Windows may use cp936/gbk,
        # macOS/Linux typically use utf-8 already handled above)
        import locale
        pref = locale.getpreferredencoding(False) or "utf-8"
        out = result.stdout.decode(pref, errors="replace")
        err = result.stderr.decode(pref, errors="replace")
    output = out + "\n" + err

    if command == "compile":
        errors = _parse_compile_errors(output)
        return {"ok": result.returncode == 0, "errors": errors, "raw_output": output}
    elif command == "lint":
        warnings = _parse_lint_output(output)
        return {"ok": result.returncode == 0, "warnings": warnings, "raw_output": output}

    return {"ok": result.returncode == 0, "raw_output": output}


def _parse_compile_errors(output: str) -> list[dict]:
    """Parse Ren'Py compile errors from CLI output."""
    errors = []
    # Ren'Py error format: File "game/script.rpy", line 42: expected ':' ...
    pattern = re.compile(
        r'File\s+"([^"]+)",\s*line\s+(\d+):\s*(.+)'
    )
    for match in pattern.finditer(output):
        errors.append({
            "file": match.group(1),
            "line": int(match.group(2)),
            "message": match.group(3).strip(),
        })

    # Also catch lines like: game/script.rpy:42: error message
    alt_pattern = re.compile(
        r'(game/[^\s:]+):(\d+):\s*(.+)'
    )
    for match in alt_pattern.finditer(output):
        errors.append({
            "file": match.group(1),
            "line": int(match.group(2)),
            "message": match.group(3).strip(),
        })

    return errors


def _parse_lint_output(output: str) -> list[dict]:
    """Parse Ren'Py lint warnings from CLI output."""
    warnings = []
    # Similar pattern to compile errors
    pattern = re.compile(
        r'(game/[^\s:]+):(\d+):\s*(.+)'
    )
    for match in pattern.finditer(output):
        warnings.append({
            "file": match.group(1),
            "line": int(match.group(2)),
            "message": match.group(3).strip(),
        })

    # Check for summary line: "Ren'Py lint found N errors"
    summary = re.search(r"found (\d+) (?:error|warning|issue)", output, re.IGNORECASE)
    if summary:
        count = int(summary.group(1))
        if count == 0 and not warnings:
            warnings.append({"message": "Lint passed with no issues."})

    return warnings
