# 🎮 renpy-mcp — Ren'Py AI-Native Development Assistant

**Language / Languages:** [简体中文](./README.md) | **English**

An MCP (Model Context Protocol) server that turns AI agents (Cursor, Claude, etc.) into **native Ren'Py development assistants** — read code, write code, search official docs, auto-fix bugs, and compile-verify, all in one closed loop.

Built with [FastMCP](https://github.com/jlowin/fastmcp), bundles 23 pages of Ren'Py official Chinese documentation (580KB), cross-platform support for Windows / macOS / Linux.

> ⭐ **If this project helps you, please star the repo to support it!**
> 👉 [https://gitee.com/gdouage/renpy-mcp](https://gitee.com/gdouage/renpy-mcp)
> Your star is the biggest motivation for a solo developer to keep updating ❤️

| | |
|---|---|
| Repository | [gitee.com/gdouage/renpy-mcp](https://gitee.com/gdouage/renpy-mcp) |
| License | [MIT](./LICENSE) |
| Author | abbuibuibui |
| Contact | [3244940576@qq.com](mailto:3244940576@qq.com) |
| Docs source | [doc.renpy.cn](https://doc.renpy.cn/zh-CN/) |

---

## 📌 Introduction

Ren'Py has no built-in editor — developers manually write `.rpy` text files and click "Launch Project" to test. This MCP lets AI directly understand Ren'Py project structure: read code, search docs, write code, compile-verify, and auto-fix bugs — without you manually pasting error logs.

| Capability | Description |
|------------|-------------|
| Read code | List all labels / read specific label scripts / inventory characters, images, screens / find jump-call references |
| Search docs | Bundled 23-page Ren'Py Chinese official docs, keyword search returns relevant sections, works offline |
| Write code | Inject code into any .rpy file (8 positioning modes), auto-create files, preserve BOM |
| Compile & verify | Compile + lint in one call, returns structured errors (file + line + message) |
| Auto-fix | Detect and fix 5 common issues: `return True/False`, missing `from` clause, BOM inconsistency, missing labels, stale saves |
| **Translation checks** | **List all languages / deep-check translation coverage (catches "string-only, missing block translation" silent bugs) / verify language picker config** |
| Save management | List / clear / clear-stale saves (fixes `Could not find return label` errors) |
| Asset management | Copy images / fonts / audio into project, get image dimensions for sprite positioning |
| Generic CLI | Run any Ren'Py CLI subcommand directly (compile / lint / translate / etc.) with custom timeout |
| Cross-platform | Windows / macOS / Linux fully supported, SDK path auto-detected |

**Core workflow:**

```text
search_docs → list_labels → exec_rpy → check_project → auto_fix
```

---

## 🏗️ Architecture

```text
┌──────────────────────────────────────────────┐
│              AI Agent (Cursor / Claude)        │
│            via MCP Protocol calls              │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│              renpy-mcp Server                  │
│           (FastMCP, 19 tools)                  │
├──────────┬──────────┬──────────┬──────────────┤
│  Read    │  Write   │  Verify  │   Docs KB     │
│ (4 tools)│ (1 tool) │ (5 tools)│  (2 tools)   │
├──────────┴──────────┴──────────┴──────────────┤
│ Translation(3) GenericCLI(1) Saves(1) Assets(2)│
├───────────────────────────────────────────────┤
│              Core capabilities                  │
│  ┌─────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Regex   │  │ File I/O │  │ subprocess    │  │
│  │ .rpy    │  │ BOM-safe │  │ Ren'Py SDK    │  │
│  └─────────┘  └──────────┘  └───────────────┘  │
└──────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│           Ren'Py SDK (renpy.py)               │
│     compile · lint · project files (.rpy)     │
└──────────────────────────────────────────────┘
```

**Directory structure:**

```text
renpy-mcp/
├── src/renpy_mcp/
│   ├── server.py              # MCP server entry + tool registration
│   ├── project.py             # Label parsing: list_labels / read_script / find_references / list_definitions
│   ├── executor.py            # Code injection: exec_rpy (8 positions + CJK font)
│   ├── build.py               # Build tools: compile / lint / check_project / manage_saves / run_renpy_command
│   ├── fixer.py               # Auto-fix: auto_fix (5 fixers)
│   ├── assets.py              # Asset management: copy_asset / get_image_size
│   ├── translation.py         # Translation: list_translations / check_translation / check_language_picker
│   ├── docs_search.py         # Doc search: search_docs / list_doc_pages
│   ├── config.py              # SDK path config (cross-platform auto-detection)
│   └── docs/                  # Bundled official docs (23 pages, 580KB)
│       ├── quickstart.txt
│       ├── screens.txt        # Screen language (77KB)
│       ├── screen_actions.txt # Screen actions (60KB)
│       ├── transforms.txt     # Transforms & ATL (43KB)
│       ├── gui.txt            # GUI customization (44KB)
│       └── ...                # 23 doc pages total
├── AI_GUIDE.md                # AI Agent operational guide
├── CHANGELOG.md               # Changelog
├── pyproject.toml             # Package config
├── LICENSE                    # MIT License
├── README.md                  # Chinese (default, Gitee homepage)
└── README.en.md               # English
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Protocol | MCP (Model Context Protocol) |
| Framework | FastMCP |
| Language | Python 3.12+ |
| Doc parsing | Python stdlib html.parser |
| Image processing | Pillow |
| Build system | setuptools |
| SDK calls | subprocess invoking Ren'Py SDK |

---

## 🚀 Quick Start

### 1. Requirements

- Python **3.12+**
- Ren'Py SDK **8.0+** (for compile and lint)
- An MCP-compatible AI client (Cursor, Claude Desktop, etc.)

### 2. Clone

```bash
git clone https://gitee.com/gdouage/renpy-mcp.git
cd renpy-mcp
```

### 3. Install

```bash
# Create venv
python -m venv .venv

# Windows
.venv\Scripts\pip install -e .

# macOS / Linux
.venv/bin/pip install -e .
```

### 4. Configure MCP Client

#### Cursor

Add to `~/.cursor/mcp.json` (create if it doesn't exist):

```json
{
  "mcpServers": {
    "renpy-mcp": {
      "command": "/absolute/path/to/renpy-mcp/.venv/Scripts/python.exe",
      "args": ["-m", "renpy_mcp.server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/renpy-mcp/src",
        "RENPY_SDK_PATH": "/absolute/path/to/renpy-sdk"
      }
    }
  }
}
```

#### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "renpy-mcp": {
      "command": "/absolute/path/to/renpy-mcp/.venv/bin/python",
      "args": ["-m", "renpy_mcp.server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/renpy-mcp/src",
        "RENPY_SDK_PATH": "/absolute/path/to/renpy-sdk"
      }
    }
  }
}
```

> **Note:** Use `bin/python` instead of `Scripts/python.exe` on macOS/Linux.
> Set `RENPY_SDK_PATH` to your Ren'Py SDK directory (e.g. `renpy-8.5.3-sdk`). If not set, the server auto-scans common locations.

### 5. Restart Client 🎬

Restart Cursor / Claude Desktop. The MCP server starts automatically. Your AI can now directly operate on your Ren'Py project.

---

## 📡 19 Tools Overview

### Read Code (4)

| Tool | Description |
|------|-------------|
| `list_labels` | List all labels (optional rich mode: params, jumps, calls, return values) |
| `read_script` | Read a specific label's full code block (BOM-safe) |
| `find_references` | Find all jump/call references to a label or screen across the project |
| `list_definitions` | Inventory all characters, images, transforms, screens, defaults, defines |

### Write Code (1)

| Tool | Description |
|------|-------------|
| `exec_rpy` | Inject code into any .rpy file (8 positions: end/top/inside/after/before/replace/replace_all/auto-create) |

### Compile & Verify (3)

| Tool | Description |
|------|-------------|
| `compile_project` | Compile .rpy → .rpyc, catch syntax errors (optional cache clear) |
| `lint_project` | Run Ren'Py lint static analysis (undefined vars, unreachable code, etc.) |
| `check_project` | Run compile + lint in one call (skips lint if compile fails) |

### Auto-Fix (2)

| Tool | Description |
|------|-------------|
| `auto_fix` | Detect and fix 5 common issues, then re-compile to verify |
| `list_fixers` | List all available fixers |

**5 auto-fixers:**

| Fixer | Type | What it does |
|-------|------|-------------|
| `return_values` | Modifies | `return True/False` → `$ _label_result = True/False` + `return` |
| `missing_from` | Modifies | `call xxx` → `call xxx from _call_xxx_N` |
| `bom_normalize` | Modifies | Add BOM to CJK files, remove BOM from non-CJK files |
| `missing_labels` | Report only | Detect jump/call to undefined labels |
| `stale_saves` | Report only | Detect `_reload-*`/`_tracesave-*` stale save files |

### Save Management (1)

| Tool | Description |
|------|-------------|
| `manage_saves` | list (list saves) / clear (delete all) / clear_stale (remove stale only) |

### Asset Management (2)

| Tool | Description |
|------|-------------|
| `copy_asset` | Copy images/fonts/audio into project (auto-prefixes `game/`) |
| `get_image_size` | Get image dimensions (for sprite positioning transforms) |

### Doc Search (2)

| Tool | Description |
|------|-------------|
| `search_docs` | Search bundled Ren'Py Chinese official docs (23 pages), return relevant sections |
| `list_doc_pages` | List all available doc pages |

### Translation Checks (3)

| Tool | Description |
|------|-------------|
| `list_translations` | List all languages under `game/tl/`; for each: file count, dialogue block-translation count, string-translation entry count, GUI file completeness, plus the source language (`config.language`) |
| `check_translation` | Deep-check translation coverage. **Key detection**: a translation file with `translate <lang> strings:` (old/new) but NO `translate <lang> <hash>:` block translations — Ren'Py does NOT translate say-statement dialogue via string translation, so such a file leaves dialogue silently in the source language. Also detects: duplicate `old` strings (runtime error), untranslated blocks, source files with dialogue but no translation file |
| `check_language_picker` | Verify `screens.rpy` language picker: catches an "English" button miswired to `Language(None)` (show source text) instead of `Language("english")` (apply translation), dead buttons pointing at non-existent `tl/` folders, and missing buttons for available translations |

### Generic CLI (1)

| Tool | Description |
|------|-------------|
| `run_renpy` | Run any Ren'Py CLI subcommand directly (compile / lint / translate / rtc / etc.) with a custom timeout. Useful for generating/refreshing translation files (`translate english`) or as a fallback when dedicated tools time out |

---

## 📝 Typical Workflows

### Scenario 1: Onboarding an unfamiliar project

```text
list_labels(rich=True)        → See project structure and jump/call relationships
list_definitions()             → See what characters/images/screens exist
read_script("start")          → Read the entry label's code
find_references("chapter_01") → See who calls this label
```

### Scenario 2: Writing a new feature

```text
search_docs("Movie")          → Look up how to play videos in official docs
exec_rpy(...)                  → Write correct code based on docs
check_project(force=True)      → Compile + lint to verify
```

### Scenario 3: Auto-fixing errors

```text
auto_fix()                     → Auto-detect and fix 5 common issues
manage_saves("clear_stale")    → Clear stale saves causing crashes
```

### Scenario 4: Checking impact before refactoring

```text
find_references("arrow_round")  → See all callers (12 places)
find_references("chapter_03")   → No callers = dead code
find_references("typo_label")   → defined=False = jump to non-existent label
```

### Scenario 5: Translation debugging ("I selected English but text is still Chinese")

```text
list_translations()          → See what languages exist and how much is translated
check_translation("english") → Catch "string-only, missing block translation" silent bugs
                             + duplicate old strings + missing translation files
check_language_picker()      → Verify the "English" button isn't miswired to Language(None)
run_renpy("translate",["english"]) → Regenerate block-translation skeletons
```

> **Real case**: a chapter's translation file was written in string-translation format (old/new).
> It compiled fine, but in-game the dialogue stayed in the source language — because Ren'Py
> translates dialogue only via block translation. `check_translation` catches this instantly.

---

## 💡 Design Notes

- **Docs work offline**: 23 pages bundled in `src/renpy_mcp/docs/`, no network needed
- **BOM-safe**: All file I/O uses `utf-8-sig`, never misses a label on line 1
- **CJK font is opt-in**: `exec_rpy`'s `auto_cjk_font` defaults to off, no silent gui.rpy changes
- **SDK auto-detection**: Scans common paths if `RENPY_SDK_PATH` not set, picks newest match
- **Modifiers preserve BOM**: When writing, detects and preserves original file's BOM
- **Read-only checkers don't modify**: `missing_labels` and `stale_saves` report only
- **Compile never hangs**: subprocess uses `stdin=DEVNULL`; timeout adjustable via `RENPY_MCP_TIMEOUT` env var (default 180s)
- **Translation checks are read-only**: `check_translation` / `check_language_picker` only analyze and report, never modify your translation files
- **Precise dialogue detection**: when counting source dialogue, only defined `Character` variable names are counted — screen/style property lines like `color "#fff"` or `key "K_SPACE"` are not mistaken for dialogue

---

## 💬 Feedback & Contributing

If this project helps you, please:

1. ⭐ Star the repo: [renpy-mcp](https://gitee.com/gdouage/renpy-mcp)
2. 🐛 Report issues: [Issues](https://gitee.com/gdouage/renpy-mcp/issues)
3. ✉️ Contact: [3244940576@qq.com](mailto:3244940576@qq.com) (Author: abbuibuibui)

Pull requests welcome (please describe the change purpose and testing method)~

---

## 📄 License

This project is open-sourced under the [MIT License](./LICENSE).

```text
Copyright (c) 2026 abbuibuibui
```
