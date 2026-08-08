"""Auto-fix tool: detect and repair common Ren'Py issues automatically.

Runs a set of safe, targeted fixers on a project, then re-compiles to verify.
Each fixer handles a specific class of problem we've hit in practice.
"""

import os
import re
import glob as glob_mod
from .build import compile_project
from .project import _iter_rpy_files, _read_lines, _LABEL_RE


# ── Fixer registry ────────────────────────────────────────────────────

_ALL_FIXERS: dict[str, dict] = {
    "return_values": {
        "description": "Convert `return True/False` in labels to global variable + bare `return` "
                       "(fixes 'Could not find return label' errors)",
        "modifies": True,
    },
    "missing_from": {
        "description": "Add `from _call_<label>_<N>` to `call` statements missing the `from` clause",
        "modifies": True,
    },
    "bom_normalize": {
        "description": "Ensure all .rpy files with CJK content have a consistent UTF-8 BOM",
        "modifies": True,
    },
    "missing_labels": {
        "description": "Detect jump/call to labels that don't exist (report only, no auto-create)",
        "modifies": False,
    },
    "stale_saves": {
        "description": "Detect stale save files (_reload-*, _tracesave-*) that may cause runtime errors",
        "modifies": False,
    },
}


def auto_fix(project_path: str, fixes: list[str] | None = None) -> dict:
    """Run automated fixes on common Ren'Py issues, then re-compile to verify.

    Args:
        project_path: Absolute path to the Ren'Py project root directory.
        fixes: List of fix names to apply. If None, applies all safe fixers.
            Available: "return_values", "missing_from", "bom_normalize",
            "missing_labels", "stale_saves".

    Returns:
        dict with:
            ok: bool (compile passed after fixes)
            applied: [{file, line, fix, description}]  — changes made
            skipped: [{file, line, issue, reason}]     — issues found but not auto-fixed
            compile_before: dict                       — compile result before fixes
            compile_after: dict                        — compile result after fixes
    """
    if fixes is None:
        fixes = list(_ALL_FIXERS.keys())

    unknown = [f for f in fixes if f not in _ALL_FIXERS]
    if unknown:
        return {
            "ok": False,
            "error": f"Unknown fixer(s): {unknown}. Available: {list(_ALL_FIXERS.keys())}",
            "applied": [],
            "skipped": [],
        }

    # 1. Compile before to get baseline
    compile_before = compile_project(project_path, force=True)

    applied: list[dict] = []
    skipped: list[dict] = []

    # 2. Run each fixer
    for fix_name in fixes:
        fixer_fn = _FIXERS.get(fix_name)
        if fixer_fn is None:
            continue
        result = fixer_fn(project_path)
        applied.extend(result.get("applied", []))
        skipped.extend(result.get("skipped", []))

    # 3. Compile after to verify
    compile_after = compile_project(project_path, force=True)

    return {
        "ok": compile_after.get("ok", False),
        "applied": applied,
        "skipped": skipped,
        "applied_count": len(applied),
        "skipped_count": len(skipped),
        "compile_before": compile_before,
        "compile_after": compile_after,
    }


def list_fixers() -> dict:
    """Return available fixers and their descriptions."""
    return _ALL_FIXERS


# ── Fixer implementations ─────────────────────────────────────────────

_FIXERS: dict = {}


def _fixer(name: str):
    """Decorator to register a fixer function."""
    def decorator(fn):
        _FIXERS[name] = fn
        return fn
    return decorator


# ── Fixer: return_values ──────────────────────────────────────────────
# Converts `return True` / `return False` inside labels to:
#   $ _<labelname>_result = True
#   return
# This fixes the "Could not find return label" error caused by returning
# values from labels called via `call`.

_RETURN_VALUE_RE = re.compile(r"^(\s*)return\s+(True|False)\s*(?:#.*)?$")


@_fixer("return_values")
def _fix_return_values(project_path: str) -> dict:
    applied: list[dict] = []
    skipped: list[dict] = []

    for filepath, rel_path in _iter_rpy_files(project_path):
        lines = _read_lines(filepath)
        if lines is None:
            continue

        # Find which label each line belongs to
        current_label = None
        changed = False
        new_lines = []

        for i, line in enumerate(lines):
            m = _LABEL_RE.match(line)
            if m:
                current_label = m.group(1)

            rm = _RETURN_VALUE_RE.match(line)
            if rm and current_label:
                indent = rm.group(1)
                value = rm.group(2)
                var_name = f"_{current_label}_result"
                new_lines.append(f"{indent}$ {var_name} = {value}\n")
                new_lines.append(f"{indent}return\n")
                changed = True
                applied.append({
                    "file": rel_path,
                    "line": i + 1,
                    "fix": "return_values",
                    "description": f"Converted `return {value}` to `$ {var_name} = {value}` + `return`",
                })
            else:
                new_lines.append(line)

        if changed:
            _write_file(filepath, new_lines, preserve_bom=True)

    if not applied:
        skipped.append({
            "file": None,
            "line": None,
            "issue": "return_values",
            "reason": "No `return True/False` found in any label.",
        })

    return {"applied": applied, "skipped": skipped}


# ── Fixer: missing_from ──────────────────────────────────────────────
# Adds `from _call_<target>_<N>` to `call <target>` statements that lack it.
# Ren'Py uses the `from` clause to handle save/load correctly.

_CALL_NO_FROM_RE = re.compile(r"^(\s*)call\s+(?:screen\s+)?(\w+)\s*(?:\([^)]*\))?\s*$")


@_fixer("missing_from")
def _fix_missing_from(project_path: str) -> dict:
    applied: list[dict] = []
    skipped: list[dict] = []

    # Track from-clause counters per target to generate unique names
    from_counters: dict[str, int] = {}

    for filepath, rel_path in _iter_rpy_files(project_path):
        lines = _read_lines(filepath)
        if lines is None:
            continue

        changed = False
        new_lines = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#"):
                new_lines.append(line)
                continue

            m = _CALL_NO_FROM_RE.match(line)
            if m:
                indent = m.group(1)
                target = m.group(2)
                # Skip "call screen" — those don't need from clauses
                if "screen" in stripped[: stripped.index(target)]:
                    new_lines.append(line)
                    continue

                # Generate unique from name
                from_counters[target] = from_counters.get(target, 0) + 1
                from_name = f"_call_{target}_{from_counters[target]}"

                # Build new line preserving any trailing content
                new_line = line.rstrip()
                # Check if there's already a from clause (shouldn't match, but safety)
                if "from" in new_line:
                    new_lines.append(line)
                    continue
                new_line += f" from {from_name}\n"
                new_lines.append(new_line)
                changed = True
                applied.append({
                    "file": rel_path,
                    "line": i + 1,
                    "fix": "missing_from",
                    "description": f"Added `from {from_name}` to `call {target}`",
                })
            else:
                new_lines.append(line)

        if changed:
            _write_file(filepath, new_lines, preserve_bom=True)

    if not applied:
        skipped.append({
            "file": None,
            "line": None,
            "issue": "missing_from",
            "reason": "No `call` statements missing `from` clause found.",
        })

    return {"applied": applied, "skipped": skipped}


# ── Fixer: bom_normalize ─────────────────────────────────────────────
# Ensures .rpy files with CJK content have a BOM (Ren'Py prefers BOM for CJK).
# Files without CJK keep their current state.

_CJK_RE = re.compile(
    "[\u2e80-\u2eff\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]",
    re.UNICODE,
)


@_fixer("bom_normalize")
def _fix_bom_normalize(project_path: str) -> dict:
    applied: list[dict] = []
    skipped: list[dict] = []

    for filepath, rel_path in _iter_rpy_files(project_path):
        try:
            with open(filepath, "rb") as f:
                raw = f.read()
        except IOError:
            continue

        has_bom = raw.startswith(b"\xef\xbb\xbf")
        content = raw[3:] if has_bom else raw

        # Check if file has CJK content
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            skipped.append({
                "file": rel_path,
                "line": None,
                "issue": "bom_normalize",
                "reason": "File is not valid UTF-8, skipped.",
            })
            continue

        has_cjk = bool(_CJK_RE.search(text))

        if has_cjk and not has_bom:
            # Add BOM
            try:
                with open(filepath, "wb") as f:
                    f.write(b"\xef\xbb\xbf" + content)
                applied.append({
                    "file": rel_path,
                    "line": 1,
                    "fix": "bom_normalize",
                    "description": "Added UTF-8 BOM (file contains CJK text).",
                })
            except IOError:
                skipped.append({
                    "file": rel_path,
                    "line": None,
                    "issue": "bom_normalize",
                    "reason": "Failed to write BOM.",
                })
        elif not has_cjk and has_bom:
            # Remove BOM (file has no CJK, BOM not needed)
            try:
                with open(filepath, "wb") as f:
                    f.write(content)
                applied.append({
                    "file": rel_path,
                    "line": 1,
                    "fix": "bom_normalize",
                    "description": "Removed unnecessary BOM (no CJK content).",
                })
            except IOError:
                skipped.append({
                    "file": rel_path,
                    "line": None,
                    "issue": "bom_normalize",
                    "reason": "Failed to remove BOM.",
                })

    if not applied:
        skipped.append({
            "file": None,
            "line": None,
            "issue": "bom_normalize",
            "reason": "All files already have correct BOM state.",
        })

    return {"applied": applied, "skipped": skipped}


# ── Checker: missing_labels ─────────────────────────────────────────
# Detects jump/call to labels that don't exist anywhere in the project.
# Report only — does NOT auto-create labels (too risky).

_JUMP_RE = re.compile(r"^\s*jump\s+(\w+)\b")
_CALL_RE = re.compile(r"^\s*call\s+(?:screen\s+)?(\w+)\b")


@_fixer("missing_labels")
def _check_missing_labels(project_path: str) -> dict:
    applied: list[dict] = []
    skipped: list[dict] = []

    # First pass: collect all defined labels and screens
    defined_labels: set[str] = set()
    defined_screens: set[str] = set()
    screen_re = re.compile(r"^\s*screen\s+(\w+)\s*(?:\([^)]*\))?\s*:")

    for filepath, _ in _iter_rpy_files(project_path):
        lines = _read_lines(filepath)
        if lines is None:
            continue
        for line in lines:
            m = _LABEL_RE.match(line)
            if m:
                defined_labels.add(m.group(1))
            m = screen_re.match(line)
            if m:
                defined_screens.add(m.group(1))

    # Second pass: find jump/call to undefined targets
    for filepath, rel_path in _iter_rpy_files(project_path):
        lines = _read_lines(filepath)
        if lines is None:
            continue
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            jm = _JUMP_RE.match(line)
            if jm:
                target = jm.group(1)
                if target not in defined_labels:
                    skipped.append({
                        "file": rel_path,
                        "line": i + 1,
                        "issue": "missing_labels",
                        "reason": f"jump to undefined label `{target}`",
                    })
                continue

            cm = _CALL_RE.match(line)
            if cm:
                target = cm.group(1)
                is_screen = "screen" in stripped[: stripped.index(target)]
                if is_screen:
                    if target not in defined_screens:
                        skipped.append({
                            "file": rel_path,
                            "line": i + 1,
                            "issue": "missing_labels",
                            "reason": f"call screen to undefined screen `{target}`",
                        })
                else:
                    if target not in defined_labels:
                        skipped.append({
                            "file": rel_path,
                            "line": i + 1,
                            "issue": "missing_labels",
                            "reason": f"call to undefined label `{target}`",
                        })

    if not skipped:
        skipped.append({
            "file": None,
            "line": None,
            "issue": "missing_labels",
            "reason": "All jump/call targets are defined. No missing labels found.",
        })

    return {"applied": applied, "skipped": skipped}


# ── Checker: stale_saves ─────────────────────────────────────────────
# Detects stale save files that may cause runtime errors.
# Report only — user must explicitly call manage_saves to delete.

_STALE_PATTERNS = ["_reload-*", "_tracesave-*"]


@_fixer("stale_saves")
def _check_stale_saves(project_path: str) -> dict:
    applied: list[dict] = []
    skipped: list[dict] = []

    saves_dir = os.path.join(project_path, "game", "saves")
    if not os.path.isdir(saves_dir):
        skipped.append({
            "file": None,
            "line": None,
            "issue": "stale_saves",
            "reason": "No saves directory found.",
        })
        return {"applied": applied, "skipped": skipped}

    stale_files: list[str] = []
    for pattern in _STALE_PATTERNS:
        for f in glob_mod.glob(os.path.join(saves_dir, pattern)):
            if os.path.isfile(f):
                stale_files.append(os.path.basename(f))

    if stale_files:
        skipped.append({
            "file": None,
            "line": None,
            "issue": "stale_saves",
            "reason": f"Found {len(stale_files)} stale save file(s): {stale_files}. "
                      f"Run manage_saves(action='clear_stale') to remove them.",
        })
    else:
        skipped.append({
            "file": None,
            "line": None,
            "issue": "stale_saves",
            "reason": "No stale save files found.",
        })

    return {"applied": applied, "skipped": skipped}


# ── Helpers ──────────────────────────────────────────────────────────

def _write_file(filepath: str, lines: list[str], preserve_bom: bool = True):
    """Write lines back to file, preserving BOM if the original had one."""
    try:
        with open(filepath, "rb") as f:
            raw = f.read()
        had_bom = raw.startswith(b"\xef\xbb\xbf")
    except IOError:
        had_bom = False

    content = "".join(lines)
    encoding = "utf-8-sig" if (preserve_bom and had_bom) else "utf-8"
    try:
        with open(filepath, "w", encoding=encoding) as f:
            f.write(content)
    except IOError:
        pass
