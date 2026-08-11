"""Translation tools: list_translations, check_translation, check_language_picker.

These tools inspect Ren'Py's translation system (the ``tl/<lang>/`` tree) and
the language picker in ``screens.rpy``. They catch the classes of bugs we hit
in practice:

  * A translation file that only contains ``translate <lang> strings:`` blocks
    (old/new pairs) but no ``translate <lang> <hash>:`` block translations.
    Ren'Py does NOT translate say-statement dialogue via string translation --
    only block translation does that. So a string-only file leaves dialogue
    in the source language silently.
  * Duplicate ``old`` strings inside a ``translate <lang> strings:`` block,
    which raise runtime "a translation for X already exists" errors.
  * A language picker whose "English" button is wired to ``Language(None)``
    (show source text) instead of ``Language("english")`` (apply the english
    translation), when the source language is not English.
  * Dead language buttons pointing at ``tl/`` folders that don't exist, and
    missing buttons for translations that do exist.
"""

import os
import re
import glob as glob_mod
from .project import _iter_rpy_files, _read_text, _read_lines


# ── regexes ───────────────────────────────────────────────────────────

# A translate header: "translate <lang> <what>:" where <what> is either a
# label hash (block translation) or the literal word "strings".
_TRANSLATE_RE = re.compile(r"^translate\s+(\w+)\s+(\w+)\s*:")

# old / new string pairs inside a strings block.
_OLD_RE = re.compile(r'^\s*old\s+"((?:[^"\\]|\\.)*)"')
_NEW_RE = re.compile(r'^\s*new\s+"((?:[^"\\]|\\.)*)"')

# config.language = "schinese"
_CONFIG_LANG_RE = re.compile(r"""^define\s+config\.language\s*=\s*["'](\w+)["']""")

# A language picker button: textbutton "Label" ... action Language(arg)
_LANG_BUTTON_RE = re.compile(
    r'textbutton\s+"([^"]+)"[^#]*?action\s+Language\(\s*([^)]*)\s*\)'
)

# A say statement (for counting source dialogue): "spk \"text\"" or bare "\"text\"".
_SAY_RE = re.compile(r'^(\s*)(\w+)\s+"((?:[^"\\]|\\.)*)"')
# Bare narrator form: an indented quoted string with nothing else.
_SAY_BARE_RE = re.compile(r'^(\s+)"((?:[^"\\]|\\.)*)"\s*(?:with\s+\S+)?\s*$')

# Character definition: define X = Character(...) or define X = DynamicCharacter(...)
_CHAR_DEF_RE = re.compile(r"""^\s*define\s+(\w+)\s*=\s*(?:Dynamic)?Character\s*\(""")


def _collect_character_names(project_path: str) -> set[str]:
    """Collect all character variable names defined in the project.

    Scans source .rpy files (excluding tl/) for ``define X = Character(...)``
    so that dialogue say-statements can be distinguished from screen/style
    property lines like ``color "#fff"`` or ``key "K_SPACE"``.
    """
    names: set[str] = set()
    for filepath, _ in _source_rpy_files(project_path):
        lines = _read_lines(filepath)
        if lines is None:
            continue
        for line in lines:
            m = _CHAR_DEF_RE.match(line)
            if m:
                names.add(m.group(1))
    return names


# ── helpers ───────────────────────────────────────────────────────────

def _tl_dir(project_path: str) -> str:
    return os.path.join(project_path, "game", "tl")


def _source_rpy_files(project_path: str):
    """Yield (abs_path, rel_path) for .rpy files under game/, EXCLUDING tl/."""
    for filepath, rel_path in _iter_rpy_files(project_path):
        # rel_path is like "game/script.rpy" or "game/tl/english/script.rpy"
        norm = rel_path.replace("\\", "/")
        if "/tl/" in norm:
            continue
        yield filepath, rel_path


def _get_config_language(project_path: str) -> str | None:
    """Read config.language from any .rpy file (usually options.rpy)."""
    for filepath, _ in _iter_rpy_files(project_path):
        text = _read_text(filepath)
        if text is None:
            continue
        for line in text.splitlines():
            m = _CONFIG_LANG_RE.match(line)
            if m:
                return m.group(1)
    return None


def _count_say_statements(filepath: str, speakers: set[str] | None = None) -> int:
    """Count dialogue say-statements in a source .rpy file.

    If ``speakers`` (the set of defined character variable names) is given,
    only lines whose speaker is a defined character (or a bare narrator
    string) are counted. This avoids mistaking screen/style property lines
    like ``color "#fff"`` or ``key "K_SPACE"`` for dialogue.

    If ``speakers`` is None, falls back to counting any ``word "string"`` line
    (less precise; used only when character scanning was not performed).
    """
    lines = _read_lines(filepath)
    if lines is None:
        return 0
    count = 0
    for line in lines:
        s = line.rstrip("\n")
        if s.lstrip().startswith("#"):
            continue
        m = _SAY_RE.match(s)
        if m:
            if speakers is None or m.group(2) in speakers:
                count += 1
            continue
        if _SAY_BARE_RE.match(s):
            count += 1
    return count


def _analyze_tl_file(filepath: str, lang: str) -> dict:
    """Parse one translation file and classify its contents.

    Returns {
        block_translations: int,   # translate <lang> <hash>: blocks
        string_entries: int,      # old/new pairs in strings blocks
        duplicate_olds: [str],     # old strings appearing more than once
        untranslated_blocks: int,  # blocks whose active line == comment line
        translated_blocks: int,   # blocks whose active line != comment line
    }
    """
    lines = _read_lines(filepath)
    if lines is None:
        return {"block_translations": 0, "string_entries": 0,
                "duplicate_olds": [], "untranslated_blocks": 0,
                "translated_blocks": 0}

    block_translations = 0
    string_entries = 0
    olds: list[str] = []
    untranslated_blocks = 0
    translated_blocks = 0

    # Walk lines tracking whether we are inside a "strings" block or a
    # block-translation block, and the last-seen old value.
    in_strings = False
    in_block = False
    pending_old = None
    # For block-translation untranslated detection: remember the comment text
    # of the current block so we can compare with the active say line.
    block_comment_text = None

    for line in lines:
        s = line.rstrip("\n")
        m = _TRANSLATE_RE.match(s)
        if m:
            # New translate header.
            what = m.group(2)
            in_strings = (what == "strings")
            in_block = (what != "strings")
            pending_old = None
            block_comment_text = None
            if in_block:
                block_translations += 1
            continue

        if in_strings:
            mo = _OLD_RE.match(s)
            if mo:
                pending_old = mo.group(1)
                olds.append(pending_old)
                continue
            mn = _NEW_RE.match(s)
            if mn:
                string_entries += 1
                continue

        if in_block:
            stripped = s.strip()
            # Track the comment line (the original/source text).
            if stripped.startswith("#"):
                cm = _SAY_RE.match(stripped[1:].lstrip())
                if cm:
                    block_comment_text = cm.group(3)
                continue
            # Active say statement line: compare with comment text.
            sm = _SAY_RE.match(s)
            if sm and block_comment_text is not None:
                if sm.group(3) == block_comment_text:
                    untranslated_blocks += 1
                else:
                    translated_blocks += 1
                block_comment_text = None  # only first active line per block

    # Duplicate olds (case-sensitive, exact text).
    seen: dict[str, int] = {}
    dups: list[str] = []
    for o in olds:
        seen[o] = seen.get(o, 0) + 1
    for o, c in seen.items():
        if c > 1:
            dups.append(o)

    return {
        "block_translations": block_translations,
        "string_entries": string_entries,
        "duplicate_olds": dups,
        "untranslated_blocks": untranslated_blocks,
        "translated_blocks": translated_blocks,
    }


# ── public API ────────────────────────────────────────────────────────

def list_translations(project_path: str) -> dict:
    """List all translation languages found under game/tl/.

    For each language folder, reports file count, dialogue block-translation
    count, string-translation entry count, and which GUI files are present.

    Also reports the project's source language (config.language).

    Returns:
        {
            "ok": bool,
            "source_language": str | None,
            "tl_dir": str,
            "languages": [
                {"code", "files", "dialogue_blocks", "string_entries",
                 "has_common", "has_screens", "has_options"}
            ],
        }
    """
    tl = _tl_dir(project_path)
    if not os.path.isdir(tl):
        return {"ok": True, "source_language": _get_config_language(project_path),
                "tl_dir": tl, "languages": [],
                "message": "No tl/ directory found (no translations yet)."}

    langs: list[dict] = []
    for name in sorted(os.listdir(tl)):
        lang_path = os.path.join(tl, name)
        if not os.path.isdir(lang_path):
            continue
        rpy_files = glob_mod.glob(os.path.join(lang_path, "**", "*.rpy"), recursive=True)
        dialogue_blocks = 0
        string_entries = 0
        for fp in rpy_files:
            info = _analyze_tl_file(fp, name)
            dialogue_blocks += info["block_translations"]
            string_entries += info["string_entries"]
        base_names = {os.path.basename(f) for f in rpy_files}
        langs.append({
            "code": name,
            "files": len(rpy_files),
            "dialogue_blocks": dialogue_blocks,
            "string_entries": string_entries,
            "has_common": "common.rpy" in base_names,
            "has_screens": "screens.rpy" in base_names,
            "has_options": "options.rpy" in base_names,
        })

    return {
        "ok": True,
        "source_language": _get_config_language(project_path),
        "tl_dir": tl,
        "languages": langs,
    }


def check_translation(project_path: str, language: str | None = None) -> dict:
    """Deep-check translation coverage for one language (or all if None).

    Catches:
      * "string_only" files -- translation files that have string entries but
        no block translations. Ren'Py won't translate dialogue from these.
      * duplicate ``old`` strings (runtime error risk).
      * untranslated block translations (active line still equals the source
        comment).
      * source .rpy files that have no corresponding translation file at all.

    Args:
        project_path: Absolute path to the Ren'Py project root directory.
        language: Language code to check (e.g. "english"). If None, checks all
            languages found under game/tl/.

    Returns:
        {
            "ok": bool,
            "source_language": str | None,
            "languages": [
                {
                    "code", "files": [...],
                    "issues": [{severity, file, issue, detail?}],
                    "summary": {total_files, string_only, duplicates,
                                untranslated_blocks, missing_files}
                }
            ]
        }
    """
    tl = _tl_dir(project_path)
    src_lang = _get_config_language(project_path)

    if not os.path.isdir(tl):
        return {"ok": True, "source_language": src_lang, "languages": [],
                "message": "No tl/ directory found."}

    if language is None:
        codes = sorted(d for d in os.listdir(tl) if os.path.isdir(os.path.join(tl, d)))
    else:
        codes = [language]

    # Map of source .rpy files (relative to game/) -> say-statement count.
    speakers = _collect_character_names(project_path)
    source_files: list[tuple[str, int]] = []
    for filepath, rel_path in _source_rpy_files(project_path):
        norm = rel_path.replace("\\", "/")
        # key relative to game/
        if norm.startswith("game/"):
            key = norm[len("game/"):]
        else:
            key = norm
        source_files.append((key, _count_say_statements(filepath, speakers)))

    # Set of source files that actually contain dialogue (say statements).
    dialogue_keys = {k for k, c in source_files if c > 0}

    out_langs: list[dict] = []
    for code in codes:
        lang_path = os.path.join(tl, code)
        if not os.path.isdir(lang_path):
            out_langs.append({"code": code, "issues": [
                {"severity": "error", "file": "", "issue": "Language folder not found."}
            ], "summary": {}})
            continue

        issues: list[dict] = []
        rpy_files = glob_mod.glob(os.path.join(lang_path, "**", "*.rpy"), recursive=True)

        string_only_files: list[str] = []
        dup_count = 0
        untranslated_total = 0
        translated_total = 0

        translated_keys: set[str] = set()
        for fp in rpy_files:
            rel = os.path.relpath(fp, lang_path).replace("\\", "/")
            translated_keys.add(rel)
            info = _analyze_tl_file(fp, code)
            # string-only detection: only flag if the corresponding source file
            # has dialogue. GUI/framework files (common.rpy, screens.rpy,
            # options.rpy) legitimately use string translation only.
            if info["string_entries"] > 0 and info["block_translations"] == 0:
                if rel in dialogue_keys:
                    string_only_files.append(rel)
                    issues.append({
                        "severity": "error",
                        "file": rel,
                        "issue": "string-translation only (no block translations)",
                        "detail": "Ren'Py does not translate say-statement dialogue via "
                                  "string translation. Regenerate block translations "
                                  "(renpy translate) and translate the blocks, or dialogue "
                                  "will stay in the source language.",
                    })
            # duplicate olds
            for d in info["duplicate_olds"]:
                dup_count += 1
                issues.append({
                    "severity": "error",
                    "file": rel,
                    "issue": "duplicate 'old' string",
                    "detail": d,
                })
            untranslated_total += info["untranslated_blocks"]
            translated_total += info["translated_blocks"]

        # missing translation files: source files with dialogue but no tl file
        missing_files: list[str] = []
        for key, say_count in source_files:
            if say_count == 0:
                continue
            if key not in translated_keys:
                missing_files.append(key)
                issues.append({
                    "severity": "warning",
                    "file": key,
                    "issue": "no translation file for a source file with dialogue",
                })

        # untranslated blocks (informational)
        if untranslated_total > 0:
            issues.append({
                "severity": "info",
                "file": "",
                "issue": f"{untranslated_total} block translation(s) still match the "
                         f"source text (possibly untranslated)",
            })

        out_langs.append({
            "code": code,
            "issues": issues,
            "summary": {
                "total_files": len(rpy_files),
                "string_only": len(string_only_files),
                "duplicates": dup_count,
                "untranslated_blocks": untranslated_total,
                "translated_blocks": translated_total,
                "missing_files": len(missing_files),
            },
        })

    ok = all(not any(i["severity"] == "error" for i in l.get("issues", []))
             for l in out_langs)
    return {"ok": ok, "source_language": src_lang, "languages": out_langs}


def check_language_picker(project_path: str) -> dict:
    """Verify the language picker in screens.rpy against tl/ and config.language.

    Catches:
      * Dead buttons: ``Language("foo")`` where ``tl/foo/`` does not exist.
      * Suspect ``Language(None)`` on a button labeled "English" when the
        source language is not English and ``tl/english/`` exists (should be
        ``Language("english")``).
      * Missing buttons: a ``tl/<lang>/`` folder exists but no button selects it.

    Args:
        project_path: Absolute path to the Ren'Py project root directory.

    Returns:
        {
            "ok": bool,
            "source_language": str | None,
            "available_languages": [str],     # tl/ folder names
            "buttons": [{"label", "action"}],  # parsed from screens.rpy
            "issues": [{"severity", "issue", "detail?"}],
        }
    """
    src_lang = _get_config_language(project_path)
    tl = _tl_dir(project_path)
    available: list[str] = []
    if os.path.isdir(tl):
        available = sorted(d for d in os.listdir(tl)
                           if os.path.isdir(os.path.join(tl, d)))

    # Parse screens.rpy for language buttons.
    buttons: list[dict] = []
    screens_path = os.path.join(project_path, "game", "screens.rpy")
    text = _read_text(screens_path)
    if text is not None:
        for line in text.splitlines():
            m = _LANG_BUTTON_RE.search(line)
            if m:
                label = m.group(1)
                action = m.group(2).strip()
                if action == "" or action.lower() == "none":
                    action_val = None
                else:
                    action_val = action.strip("\"'")
                buttons.append({"label": label, "action": action_val})

    issues: list[dict] = []

    # Dead buttons: action points to a tl folder that doesn't exist.
    # Language(None) is "source language" and is always valid.
    for b in buttons:
        act = b["action"]
        if act is None:
            continue
        if act not in available:
            issues.append({
                "severity": "warning",
                "issue": "dead language button",
                "detail": f'"{b["label"]}" -> Language("{act}") but tl/{act}/ does not exist',
            })

    # Suspect: a button labeled "English" using Language(None) when source is
    # non-English and tl/english exists.
    if src_lang and src_lang != "english" and "english" in available:
        for b in buttons:
            if b["label"].lower() == "english" and b["action"] is None:
                issues.append({
                    "severity": "error",
                    "issue": '"English" button uses Language(None) but source is not English',
                    "detail": f'config.language="{src_lang}" so Language(None) shows the '
                              f'source (Chinese) text. Use Language("english") to apply '
                              f'tl/english/ translations.',
                })

    # Missing buttons: a tl folder with no button selecting it.
    button_actions = {b["action"] for b in buttons}
    for lang in available:
        if lang not in button_actions:
            issues.append({
                "severity": "info",
                "issue": f"no button for available translation tl/{lang}/",
            })

    ok = not any(i["severity"] == "error" for i in issues)
    return {
        "ok": ok,
        "source_language": src_lang,
        "available_languages": available,
        "buttons": buttons,
        "issues": issues,
    }
