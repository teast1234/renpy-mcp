# Changelog

## [0.3.0] — 2026-08-08

### Added
- `find_references` tool — find all jump/call references to a label or screen across the project, detect dead code and missing targets
- `list_definitions` tool — inventory all characters, images, transforms, screens, defaults, and defines
- `check_project` tool — run compile + lint in one call (skips lint if compile fails)
- `manage_saves` tool — list, clear, or clear-stale save files (fixes "Could not find return label" bugs caused by stale saves)
- `list_labels` rich mode — optional params, jumps_to, calls_to, returns_value per label
- `exec_rpy` `replace_all:` mode — replace all occurrences instead of just the first
- Cross-platform SDK auto-detection (Windows, macOS, Linux scan paths)
- Cross-platform CJK font detection (Windows, macOS, Linux font directories)
- `RENPY_SDK_PATH` environment variable support

### Fixed
- UTF-8 BOM handling — files with BOM header and label on line 1 were invisible to `list_labels` and `read_script`
- `exec_rpy` CJK font auto-setup is now opt-in (`auto_cjk_font=False` by default) to avoid surprising side effects
- `exec_rpy` preserves BOM when overwriting files that have one
- `list_labels` rich mode no longer mistakes default values for params (e.g. `info="挑战"` → just `info`)
- `list_labels` rich mode no longer mistakes `return # comment` for `return <value>`
- `build.py` encoding fallback uses `locale.getpreferredencoding()` instead of hardcoded `gbk`

### Changed
- `mcp` dependency pinned to `>=1.0.0,<2.0.0` (2.0.0 breaks `mcp.server.fastmcp` compatibility)
- `pyproject.toml` — added full metadata (authors, classifiers, URLs, keywords)
- `README.md` — updated for 11 tools, added Cursor and Claude Desktop configs, added cross-platform instructions

## [0.2.0] — 2026-06-01

### Added
- `copy_asset` tool — copy images, fonts, audio into Ren'Py projects
- `get_image_size` tool — get image dimensions for sprite positioning
- CJK font auto-detection and configuration in `exec_rpy`
- `replace` mode in `exec_rpy` — search-and-replace text in .rpy files
- Auto-create target file in `exec_rpy` when it doesn't exist
- `force` parameter in `compile_project` — clear .rpyc cache before compile
- `AI_GUIDE.md` — operational guide for AI agents using this MCP

### Fixed
- `copy_asset` auto-prefixes `game/` to destination paths
- CJK text no longer requires manual font setup

## [0.1.0] — 2026-05-31

### Added
- Initial release with 5 core tools:
  - `list_labels` — scan project labels
  - `read_script` — read label content line-by-line
  - `exec_rpy` — universal code injection (end/top/inside/after/before)
  - `compile_project` — validate .rpy syntax
  - `lint_project` — static analysis
- Built with FastMCP
