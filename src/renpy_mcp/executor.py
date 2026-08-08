"""Universal Ren'Py code injection tool: exec_rpy.

The "swiss army knife" of the MCP - inject any Ren'Py code into any file
at any position, with automatic compile validation.

Also auto-detects CJK text and configures a compatible font automatically.
"""

import os
import re
import sys
import shutil
from .build import compile_project


# ── CJK Font Auto-Setup ──────────────────────────────────────────────

_CJK_RANGES = [
    (0x2E80, 0x2EFF),
    (0x3000, 0x303F),
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
    (0xFF00, 0xFFEF),
]

_NON_CJK_FONTS = {
    "DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans-Oblique.ttf",
    "Roboto-Regular.ttf", "Roboto-Bold.ttf", "SourceSansPro-Regular.ttf",
}

_CJK_FONT_CANDIDATES = [
    # Windows
    "simhei.ttf", "msyh.ttc", "simsun.ttc", "simkai.ttf",
    # macOS
    "PingFang.ttc", "STHeiti Light.ttc", "STHeiti Medium.ttc", "Hiragino Sans GB.ttc",
    # Linux (Noto CJK / WenQuanYi)
    "NotoSansCJK-Regular.ttc", "NotoSansCJKsc-Regular.otf", "wqy-microhei.ttc", "wqy-zenhei.ttc",
]


def _get_font_dirs() -> list[str]:
    """Return font directories for the current platform."""
    home = os.path.expanduser("~")
    if sys.platform == "win32":
        return [r"C:\Windows\Fonts"]
    elif sys.platform == "darwin":
        return [
            "/System/Library/Fonts",
            "/Library/Fonts",
            os.path.join(home, "Library", "Fonts"),
        ]
    else:  # Linux
        return [
            "/usr/share/fonts",
            "/usr/local/share/fonts",
            os.path.join(home, ".fonts"),
            os.path.join(home, ".local", "share", "fonts"),
        ]


def _has_cjk(text: str) -> bool:
    for ch in text:
        cp = ord(ch)
        for lo, hi in _CJK_RANGES:
            if lo <= cp <= hi:
                return True
    return False


def _read_gui_fonts(project_path: str) -> list[str]:
    gui_path = os.path.join(project_path, "game", "gui.rpy")
    if not os.path.isfile(gui_path):
        return []
    try:
        with open(gui_path, "r", encoding="utf-8-sig") as f:
            content = f.read()
    except (IOError, UnicodeDecodeError):
        return []
    fonts = []
    for m in re.finditer(r'''_font\s*=\s*["']([^"']+)["']''', content):
        fonts.append(m.group(1))
    return fonts


def _setup_cjk_font(project_path: str) -> dict | None:
    """Auto-configure a CJK-compatible font. Returns info dict or None."""
    fonts = _read_gui_fonts(project_path)
    needs_cjk = any(f in _NON_CJK_FONTS for f in fonts) or \
                (fonts and not any(f in _CJK_FONT_CANDIDATES for f in fonts))

    if not needs_cjk:
        return None

    font_name = None
    font_source = None
    for candidate in _CJK_FONT_CANDIDATES:
        for font_dir in _get_font_dirs():
            src = os.path.join(font_dir, candidate)
            if os.path.isfile(src):
                font_name = candidate
                font_source = src
                break
        if font_name:
            break

    if not font_name:
        return {"warning": "No CJK font found on system."}

    game_dir = os.path.join(project_path, "game")
    dest = os.path.join(game_dir, font_name)
    if not os.path.isfile(dest):
        shutil.copy2(font_source, dest)

    gui_path = os.path.join(game_dir, "gui.rpy")
    try:
        with open(gui_path, "rb") as f:
            raw = f.read()
        had_bom = raw.startswith(b"\xef\xbb\xbf")
        gui_content = raw.decode("utf-8-sig")
    except (IOError, UnicodeDecodeError):
        return {"warning": f"Font {font_name} copied but gui.rpy unreadable."}

    # Backup before modifying
    backup_path = gui_path + ".bak"
    try:
        shutil.copy2(gui_path, backup_path)
    except (IOError, OSError):
        pass  # non-fatal: proceed without backup

    for old_font in set(fonts):
        if old_font != font_name:
            gui_content = gui_content.replace(old_font, font_name)

    try:
        with open(gui_path, "w", encoding="utf-8-sig" if had_bom else "utf-8") as f:
            f.write(gui_content)
    except IOError:
        return {"warning": f"Font {font_name} copied but gui.rpy update failed."}

    return {
        "font_setup": True,
        "font": font_name,
        "replaced": [f for f in fonts if f != font_name],
    }


# ── Main Tool ─────────────────────────────────────────────────────────


def exec_rpy(
    project_path: str,
    file: str,
    code: str,
    position: str = "end",
    auto_compile: bool = True,
    auto_cjk_font: bool = False,
) -> dict:
    """Inject arbitrary Ren'Py code into a project file.

    Args:
        project_path: Root directory of the Ren'Py project.
        file: Target .rpy file path (relative to project_path).
        code: Raw Ren'Py script code to inject.
        position: "end" / "top" / "inside:<label>" / "after:<label>" / "before:<label>" /
            "replace:<old_text>" (replace first match with code) /
            "replace_all:<old_text>" (replace ALL matches with code)
        auto_compile: Run compile after writing (default True).
        auto_cjk_font: If True and code contains CJK text, auto-configure a CJK
            font in gui.rpy. Defaults to False to avoid surprising side effects.

    Returns:
        dict with {ok, message, compile_result, font_setup?, cjk_warning?}
    """
    target_path = os.path.join(project_path, file)

    # ── CJK detection (warn by default, only act if auto_cjk_font=True) ──
    font_info = None
    cjk_warning = None
    if _has_cjk(code):
        if auto_cjk_font:
            font_info = _setup_cjk_font(project_path)
        else:
            cjk_warning = (
                "Code contains CJK text. Ensure gui.rpy uses a CJK-compatible "
                "font (e.g. simhei.ttf) or pass auto_cjk_font=True to auto-configure."
            )

    # ── Read existing (auto-create file if not found) ──
    existing = ""
    created = False
    had_bom = False
    if os.path.isfile(target_path):
        try:
            with open(target_path, "rb") as f:
                raw = f.read()
            had_bom = raw.startswith(b"\xef\xbb\xbf")
            existing = raw.decode("utf-8-sig")
        except (IOError, UnicodeDecodeError) as e:
            return {"ok": False, "message": f"Failed to read file: {e}", "compile_result": None}
    else:
        created = True
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

    # ── Insert ──
    if position == "end":
        new_content = _insert_at_end(existing, code)
    elif position == "top":
        new_content = _insert_at_top(existing, code)
    elif position.startswith("inside:"):
        label_name = position[len("inside:"):]
        new_content = _insert_inside_label(existing, code, label_name)
        if new_content is None:
            return {"ok": False, "message": f"Label '{label_name}' not found in {file}", "compile_result": None}
    elif position.startswith("after:"):
        label_name = position[len("after:"):]
        new_content = _insert_after_label(existing, code, label_name)
        if new_content is None:
            return {"ok": False, "message": f"Label '{label_name}' not found in {file}", "compile_result": None}
    elif position.startswith("before:"):
        label_name = position[len("before:"):]
        new_content = _insert_before_label(existing, code, label_name)
        if new_content is None:
            return {"ok": False, "message": f"Label '{label_name}' not found in {file}", "compile_result": None}
    elif position.startswith("replace_all:"):
        old_text = position[len("replace_all:"):]
        count = existing.count(old_text)
        if count == 0:
            return {"ok": False, "message": f"Text not found in {file}: {old_text[:80]}...", "compile_result": None}
        new_content = existing.replace(old_text, code)
    elif position.startswith("replace:"):
        old_text = position[len("replace:"):]
        if old_text not in existing:
            return {"ok": False, "message": f"Text not found in {file}: {old_text[:80]}...", "compile_result": None}
        new_content = existing.replace(old_text, code, 1)
    else:
        return {"ok": False, "message": f"Unknown position: {position}", "compile_result": None}

    # ── Write (preserve BOM if original had it) ──
    try:
        with open(target_path, "w", encoding="utf-8-sig" if had_bom else "utf-8") as f:
            f.write(new_content)
    except IOError as e:
        return {"ok": False, "message": f"Failed to write file: {e}", "compile_result": None}

    # ── Build result message ──
    extra_parts = []
    if font_info:
        if font_info.get("font_setup"):
            extra_parts.append(f"auto-configured CJK font: {font_info['font']}")
        elif font_info.get("warning"):
            extra_parts.append(font_info["warning"])

    if position.startswith("replace_all:"):
        msg = f"Replaced all occurrences in {file}."
    elif position.startswith("replace:"):
        msg = f"Text replaced in {file}."
    elif created:
        msg = f"File created and code written to {file}."
    else:
        msg = f"Code injected into {file} ({position})."
    if extra_parts:
        msg += " " + " | ".join(extra_parts)

    # ── Compile ──
    compile_result = None
    if auto_compile:
        compile_result = compile_project(project_path)
        status = "OK" if compile_result.get("ok") else "FAILED"
        msg += f" Compile {status}."

    result = {"ok": True, "message": msg, "compile_result": compile_result}
    if font_info:
        result["font_setup"] = font_info
    if cjk_warning:
        result["cjk_warning"] = cjk_warning

    return result


# ── Insertion helpers ─────────────────────────────────────────────────


def _insert_at_end(existing: str, code: str) -> str:
    existing = existing.rstrip()
    code = code.strip()
    if existing:
        return existing + "\n\n" + code + "\n"
    return code + "\n"


def _insert_at_top(existing: str, code: str) -> str:
    return code.strip() + "\n\n" + existing.lstrip()


def _find_label_position(lines: list[str], label_name: str) -> tuple[int, int] | None:
    label_pattern = re.compile(rf"^\s*label\s+{re.escape(label_name)}\s*(?:\(.*?\))?\s*:")
    for i, line in enumerate(lines):
        if label_pattern.match(line):
            start = i
            label_indent = len(line) - len(line.lstrip())
            end = len(lines) - 1
            for j in range(i + 1, len(lines)):
                stripped = lines[j].strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if len(lines[j]) - len(lines[j].lstrip()) <= label_indent:
                    end = j - 1
                    break
            return (start, end)
    return None


def _insert_inside_label(existing: str, code: str, label_name: str) -> str | None:
    lines = existing.splitlines(keepends=True)
    pos = _find_label_position(lines, label_name)
    if pos is None:
        return None

    start, end = pos
    base_indent = "    "
    for j in range(start + 1, end + 1):
        stripped = lines[j].strip()
        if stripped and not stripped.startswith("#"):
            base_indent = lines[j][:len(lines[j]) - len(lines[j].lstrip())]
            break

    indented_code = "\n".join(
        (base_indent + line) if line.strip() else ""
        for line in code.strip().split("\n")
    )

    insert_at = end
    result = lines[:insert_at] + [indented_code + "\n"] + lines[insert_at:]
    return "".join(result)


def _insert_after_label(existing: str, code: str, label_name: str) -> str | None:
    lines = existing.splitlines(keepends=True)
    pos = _find_label_position(lines, label_name)
    if pos is None:
        return None
    start, end = pos
    code_block = code.strip() + "\n"
    result = lines[:end + 1] + ["\n", code_block + "\n"] + lines[end + 1:]
    return "".join(result)


def _insert_before_label(existing: str, code: str, label_name: str) -> str | None:
    lines = existing.splitlines(keepends=True)
    pos = _find_label_position(lines, label_name)
    if pos is None:
        return None
    start, end = pos
    code_block = code.strip() + "\n"
    result = lines[:start] + [code_block + "\n", "\n"] + lines[start:]
    return "".join(result)
