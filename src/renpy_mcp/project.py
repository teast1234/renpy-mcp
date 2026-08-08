"""Project structure tools: list_labels, read_script, find_references, list_definitions."""

import os
import re
import glob as glob_mod
from dataclasses import dataclass, asdict, field


@dataclass
class LabelInfo:
    name: str
    file: str
    line: int


def _iter_rpy_files(project_path: str):
    """Yield (abs_path, rel_path) for every .rpy file under game/."""
    rpy_dir = os.path.join(project_path, "game")
    if not os.path.isdir(rpy_dir):
        return
    for filepath in glob_mod.glob(os.path.join(rpy_dir, "**", "*.rpy"), recursive=True):
        rel_path = os.path.relpath(filepath, project_path)
        yield filepath, rel_path


def _read_lines(filepath: str) -> list[str] | None:
    """Read file lines with BOM-safe encoding."""
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            return f.readlines()
    except (IOError, UnicodeDecodeError):
        return None


def _read_text(filepath: str) -> str | None:
    """Read file text with BOM-safe encoding."""
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            return f.read()
    except (IOError, UnicodeDecodeError):
        return None


# ── label parsing ─────────────────────────────────────────────────────

_LABEL_RE = re.compile(r"^\s*label\s+(\w+)\s*(?:\(([^)]*)\))?\s*:")
_LABEL_PARAMS_RE = re.compile(r"(\w+)")


def list_labels(project_path: str, rich: bool = False) -> list[dict]:
    """Scan all .rpy files and list all labels.

    Args:
        project_path: Absolute path to the Ren'Py project root.
        rich: If True, also parse each label's params, jumps, calls, and
              return-value status (slower, reads every label block).

    Returns a list of dicts. Basic: {name, file, line}.
    Rich adds: {params, jumps_to, calls_to, returns_value}.
    """
    labels: list[dict] = []

    for filepath, rel_path in _iter_rpy_files(project_path):
        lines = _read_lines(filepath)
        if lines is None:
            continue
        for line_no, line in enumerate(lines, 1):
            m = _LABEL_RE.match(line)
            if not m:
                continue
            info = {"name": m.group(1), "file": rel_path, "line": line_no}
            if rich:
                info.update(_analyze_label_block(lines, line_no - 1))
            labels.append(info)

    return labels


def _analyze_label_block(lines: list[str], start_idx: int) -> dict:
    """Parse a label block for params, jumps, calls, return-value."""
    block = _extract_label_block(lines, start_idx)
    params: list[str] = []
    jumps_to: list[str] = []
    calls_to: list[str] = []
    returns_value = False

    # params from label declaration line — only capture names before '='
    m = _LABEL_RE.match(lines[start_idx])
    if m and m.group(2):
        for part in m.group(2).split(","):
            part = part.strip()
            if not part:
                continue
            pname = part.split("=")[0].strip()
            if re.match(r"\w+$", pname):
                params.append(pname)

    # jump / call / return inside the block
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # strip trailing comments so `return # foo` isn't mistaken for `return <value>`
        comment_idx = stripped.find("#")
        if comment_idx > 0:
            stripped = stripped[:comment_idx].strip()
        # jump <name>
        jm = re.match(r"jump\s+(\w+)", stripped)
        if jm:
            jumps_to.append(jm.group(1))
            continue
        # call screen <name>  /  call <name>(...)  /  call <name>
        cm = re.match(r"call\s+(?:screen\s+)?(\w+)", stripped)
        if cm:
            calls_to.append(cm.group(1))
            continue
        # return <value> (bare "return" with nothing after = no value)
        rm = re.match(r"return\s+(\S.+)", stripped)
        if rm:
            returns_value = True

    return {
        "params": params,
        "jumps_to": jumps_to,
        "calls_to": calls_to,
        "returns_value": returns_value,
    }


def read_script(project_path: str, label_name: str) -> str:
    """Read the content of a specific label. Returns empty string if not found."""
    label_pattern = re.compile(
        rf"^\s*label\s+{re.escape(label_name)}\s*(?:\(.*?\))?\s*:"
    )

    for filepath, _ in _iter_rpy_files(project_path):
        lines = _read_lines(filepath)
        if lines is None:
            continue
        for i, line in enumerate(lines):
            if label_pattern.match(line):
                return _extract_label_block(lines, i)

    return ""


def _extract_label_block(lines: list[str], start_idx: int) -> str:
    """Extract all lines belonging to a label block (same or deeper indentation)."""
    result = [lines[start_idx]]

    label_line = lines[start_idx]
    label_indent = len(label_line) - len(label_line.lstrip())

    for i in range(start_idx + 1, len(lines)):
        line = lines[i]
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            result.append(line)
            continue

        line_indent = len(line) - len(line.lstrip())
        if line_indent <= label_indent and stripped:
            break
        result.append(line)

    return "".join(result).rstrip() + "\n"


# ── find_references ──────────────────────────────────────────────────

# Matches jump/call targets. Captures the target name.
_JUMP_RE = re.compile(r"^\s*jump\s+(\w+)\b")
_CALL_RE = re.compile(r"^\s*call\s+(?:screen\s+)?(\w+)\b")


def find_references(project_path: str, name: str) -> dict:
    """Find all references to a label/screen name across the project.

    Parses jump and call statements to build a reference map.

    Returns:
        {
            "name": str,
            "defined": bool,              # is there a `label <name>:` somewhere?
            "definition": {file, line} | None,
            "callers": [                  # places that jump/call this name
                {"file": str, "line": int, "type": "jump"|"call"|"call_screen"}
            ],
            "is_screen": bool,            # is there a `screen <name>:` somewhere?
        }
    """
    callers: list[dict] = []
    defined = False
    is_screen = False
    definition: dict | None = None

    # screen definition pattern
    screen_def_re = re.compile(rf"^\s*screen\s+{re.escape(name)}\s*(?:\([^)]*\))?\s*:")

    for filepath, rel_path in _iter_rpy_files(project_path):
        lines = _read_lines(filepath)
        if lines is None:
            continue
        for line_no, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            # check definition
            if not defined:
                m = _LABEL_RE.match(line)
                if m and m.group(1) == name:
                    defined = True
                    definition = {"file": rel_path, "line": line_no}

            # check screen definition
            if not is_screen and screen_def_re.match(line):
                is_screen = True

            # check jump
            jm = _JUMP_RE.match(line)
            if jm and jm.group(1) == name:
                callers.append({"file": rel_path, "line": line_no, "type": "jump"})
                continue

            # check call / call screen
            cm = _CALL_RE.match(line)
            if cm and cm.group(1) == name:
                ctype = "call_screen" if "screen" in stripped[: stripped.index(name)] else "call"
                callers.append({"file": rel_path, "line": line_no, "type": ctype})

    return {
        "name": name,
        "defined": defined,
        "definition": definition,
        "is_screen": is_screen,
        "callers": callers,
        "caller_count": len(callers),
    }


# ── list_definitions ──────────────────────────────────────────────────

_DEFINE_CHAR_RE = re.compile(r"""^\s*define\s+(\w+)\s*=\s*Character\s*\(""")
_DEFINE_RE = re.compile(r"^\s*define\s+(\w+)\s*=")
_IMAGE_RE = re.compile(r"^\s*image\s+(\S+)\s*=")
_IMAGE_BLOCK_RE = re.compile(r"^\s*image\s+(\S+)\s*:")
_TRANSFORM_RE = re.compile(r"^\s*transform\s+(\w+)\s*(?:\([^)]*\))?\s*:")
_SCREEN_RE = re.compile(r"^\s*screen\s+(\w+)\s*(?:\([^)]*\))?\s*:")
_DEFAULT_RE = re.compile(r"^\s*default\s+(\w+)\s*=")


def list_definitions(project_path: str) -> dict:
    """Inventory all define/image/transform/screen/default declarations.

    Returns:
        {
            "characters": [{name, file, line}],
            "images": [{name, file, line}],
            "transforms": [{name, file, line}],
            "screens": [{name, file, line}],
            "defaults": [{name, file, line}],
            "defines": [{name, file, line}],
        }
    """
    result = {
        "characters": [],
        "images": [],
        "transforms": [],
        "screens": [],
        "defaults": [],
        "defines": [],
    }

    for filepath, rel_path in _iter_rpy_files(project_path):
        lines = _read_lines(filepath)
        if lines is None:
            continue
        for line_no, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            if _DEFINE_CHAR_RE.match(line):
                m = _DEFINE_CHAR_RE.match(line)
                result["characters"].append({"name": m.group(1), "file": rel_path, "line": line_no})
            elif _DEFINE_RE.match(line):
                m = _DEFINE_RE.match(line)
                name = m.group(1)
                # skip if already captured as character
                if not any(c["name"] == name and c["file"] == rel_path for c in result["characters"]):
                    result["defines"].append({"name": name, "file": rel_path, "line": line_no})
            elif _IMAGE_RE.match(line):
                m = _IMAGE_RE.match(line)
                result["images"].append({"name": m.group(1), "file": rel_path, "line": line_no})
            elif _IMAGE_BLOCK_RE.match(line):
                m = _IMAGE_BLOCK_RE.match(line)
                result["images"].append({"name": m.group(1), "file": rel_path, "line": line_no})
            elif _TRANSFORM_RE.match(line):
                m = _TRANSFORM_RE.match(line)
                result["transforms"].append({"name": m.group(1), "file": rel_path, "line": line_no})
            elif _SCREEN_RE.match(line):
                m = _SCREEN_RE.match(line)
                result["screens"].append({"name": m.group(1), "file": rel_path, "line": line_no})
            elif _DEFAULT_RE.match(line):
                m = _DEFAULT_RE.match(line)
                result["defaults"].append({"name": m.group(1), "file": rel_path, "line": line_no})

    return result
