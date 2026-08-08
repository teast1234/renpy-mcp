"""Ren'Py MCP Server - registers all tools with FastMCP."""

import sys
import os

# Ensure src is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from renpy_mcp.project import list_labels, read_script, find_references, list_definitions
from renpy_mcp.executor import exec_rpy
from renpy_mcp.build import compile_project, lint_project, check_project, manage_saves
from renpy_mcp.assets import copy_asset, get_image_size
from renpy_mcp.fixer import auto_fix, list_fixers
from renpy_mcp.docs_search import search_docs, list_doc_pages

mcp = FastMCP("Ren'Py MCP")


@mcp.tool()
def tool_list_labels(project_path: str, rich: bool = False) -> list[dict]:
    """List all labels in a Ren'Py project.

    Scans all .rpy files under project_path/game/ and returns label names,
    their source files, and line numbers.

    Args:
        project_path: Absolute path to the Ren'Py project root directory.
        rich: If True, also parse each label's params, jumps, calls, and
              return-value status (slower, reads every label block).
    """
    return list_labels(project_path, rich)


@mcp.tool()
def tool_read_script(project_path: str, label_name: str) -> str:
    """Read the script content of a specific label.

    Returns the complete Ren'Py script block under the given label,
    including all dialogue, menus, and nested logic.

    Args:
        project_path: Absolute path to the Ren'Py project root directory.
        label_name: The label name to read (e.g. "start", "chapter_01").
    """
    return read_script(project_path, label_name)


@mcp.tool()
def tool_find_references(project_path: str, name: str) -> dict:
    """Find all jump/call references to a label or screen across the project.

    Parses jump and call statements to build a reference map. Useful for
    refactoring (find all callers before renaming), detecting dead code
    (labels never jumped/called), and catching missing targets (jump to a
    label that doesn't exist).

    Args:
        project_path: Absolute path to the Ren'Py project root directory.
        name: The label or screen name to search for (e.g. "arrow_round").

    Returns:
        dict with {name, defined, definition, is_screen, callers, caller_count}.
    """
    return find_references(project_path, name)


@mcp.tool()
def tool_list_definitions(project_path: str) -> dict:
    """Inventory all declarations in a Ren'Py project.

    Scans all .rpy files and returns characters, images, transforms, screens,
    defaults, and defines. Useful for understanding project structure without
    reading every file.

    Args:
        project_path: Absolute path to the Ren'Py project root directory.

    Returns:
        dict with {characters, images, transforms, screens, defaults, defines}.
    """
    return list_definitions(project_path)


@mcp.tool()
def tool_exec_rpy(
    project_path: str,
    file: str,
    code: str,
    position: str = "end",
    auto_compile: bool = True,
    auto_cjk_font: bool = False,
) -> dict:
    """Inject arbitrary Ren'Py code into a project file.

    This is the universal "escape hatch" tool. Use it to write any Ren'Py
    script code: define characters, declare images, create screens, add
    dialogue to labels, write init python blocks, etc.

    If the target file doesn't exist, it will be auto-created. BOM is
    preserved when overwriting an existing file that has one.

    Args:
        project_path: Absolute path to the Ren'Py project root directory.
        file: Target .rpy file, relative to project_path (e.g. "game/script.rpy").
        code: Raw Ren'Py script code to inject.
        position: Where to place the code:
            - "end": Append at end of file (default)
            - "top": Prepend at start of file
            - "inside:<label>": Insert at end of a label block
            - "after:<label>": Insert right after a label block ends
            - "before:<label>": Insert right before a label definition
            - "replace:<old_text>": Replace first occurrence of old_text with code
            - "replace_all:<old_text>": Replace ALL occurrences of old_text with code
        auto_compile: Whether to run compile_project after writing (default True).
        auto_cjk_font: If True and code contains CJK text, auto-configure a CJK
            font in gui.rpy. Defaults to False to avoid surprising side effects.

    Returns:
        dict with {ok, message, compile_result, font_setup?, cjk_warning?}.
    """
    return exec_rpy(project_path, file, code, position, auto_compile, auto_cjk_font)


@mcp.tool()
def tool_compile_project(project_path: str, force: bool = False) -> dict:
    """Compile a Ren'Py project (validate syntax).

    Runs Ren'Py's compiler on all .rpy files. Returns structured errors
    with file paths and line numbers if compilation fails.

    Args:
        project_path: Absolute path to the Ren'Py project root directory.
        force: If True, clear .rpyc cache before compiling (to pick up file changes).

    Returns:
        dict with {ok: bool, errors: [{file, line, message}], raw_output: str}.
    """
    return compile_project(project_path, force)


@mcp.tool()
def tool_lint_project(project_path: str) -> dict:
    """Run Ren'Py lint on a project (static analysis).

    Checks for undefined variables, unreachable code, missing labels, etc.
    More thorough than compile but may produce false positives.

    Args:
        project_path: Absolute path to the Ren'Py project root directory.

    Returns:
        dict with {ok: bool, warnings: [{file, line, message}], raw_output: str}.
    """
    return lint_project(project_path)


@mcp.tool()
def tool_check_project(project_path: str, force: bool = True) -> dict:
    """Run compile then lint in one call. Returns combined structured result.

    If compile fails, returns immediately with compile errors (no point
    linting broken syntax). If compile passes, runs lint and merges warnings.

    Args:
        project_path: Absolute path to the Ren'Py project root directory.
        force: If True, clear .rpyc cache before compiling (default True).

    Returns:
        dict with {ok, compile_errors, lint_warnings, raw_output}.
    """
    return check_project(project_path, force)


@mcp.tool()
def tool_manage_saves(project_path: str, action: str = "list") -> dict:
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
        dict with {ok, action, saves|deleted, message}.
    """
    return manage_saves(project_path, action)


@mcp.tool()
def tool_copy_asset(project_path: str, source: str, dest: str) -> dict:
    """Copy an asset file (image, font, audio) into a Ren'Py project.

    Copies a file from anywhere on the system into the project's game directory.
    Automatically creates subdirectories as needed.
    Auto-prefixes 'game/' to dest if not already present.

    Args:
        project_path: Absolute path to the Ren'Py project root directory.
        source: Absolute path to the source file on disk.
        dest: Relative path within project (e.g. "images/char_happy.png").

    Returns:
        dict with {ok, message, dest_path}.
    """
    return copy_asset(project_path, source, dest)


@mcp.tool()
def tool_get_image_size(project_path: str, image_path: str) -> dict:
    """Get dimensions and format of an image file.

    Useful for calculating correct sprite positioning transforms.
    Supports absolute paths or paths relative to project_path.

    Args:
        project_path: Absolute path to the Ren'Py project root directory.
        image_path: Path to image file (absolute, or relative to project_path).

    Returns:
        dict with {ok, width, height, format, file_size}.
    """
    return get_image_size(project_path, image_path)


@mcp.tool()
def tool_auto_fix(project_path: str, fixes: list[str] | None = None) -> dict:
    """Detect and repair common Ren'Py issues automatically, then re-compile to verify.

    Runs a set of safe, targeted fixers on a project. Each fixer handles a
    specific class of problem. After applying fixes, re-compiles to verify
    the project still builds.

    Available fixers:
        - "return_values": Convert `return True/False` in labels to global
          variable + bare `return` (fixes 'Could not find return label' errors)
        - "missing_from": Add `from _call_<label>_<N>` to `call` statements
          missing the `from` clause (fixes save/load issues)
        - "bom_normalize": Ensure .rpy files with CJK content have consistent BOM
        - "missing_labels": Detect jump/call to undefined labels (report only)
        - "stale_saves": Detect stale save files that may cause runtime errors

    Args:
        project_path: Absolute path to the Ren'Py project root directory.
        fixes: List of fixer names to run. If None, runs all fixers.

    Returns:
        dict with {ok, applied, skipped, applied_count, skipped_count,
                   compile_before, compile_after}.
    """
    return auto_fix(project_path, fixes)


@mcp.tool()
def tool_list_fixers() -> dict:
    """List all available auto-fixers and their descriptions.

    Returns a dict mapping fixer names to {description, modifies} info.
    Use this to see what auto_fix can do before running it.
    """
    return list_fixers()


@mcp.tool()
def tool_search_docs(query: str, max_results: int = 5) -> dict:
    """Search the bundled Ren'Py official documentation (Chinese, from doc.renpy.cn).

    Searches through the local copy of the Ren'Py documentation and returns the
    most relevant sections. Works offline.

    Use this BEFORE writing Ren'Py code if you're unsure about syntax, function
    names, or best practices. For example:
      - search_docs("Movie") to learn how to play videos
      - search_docs("screen") to understand screen language
      - search_docs("transform") to learn about ATL transforms
      - search_docs("call from") to understand call/from semantics
      - search_docs("存档") to find save/load documentation
      - search_docs("label return") to learn about label return mechanics

    Args:
        query: Search query (supports both English and Chinese).
        max_results: Maximum number of results to return (default 5).

    Returns:
        dict with {ok, query, results: [{file, title, snippet, score}], result_count}.
    """
    return search_docs(query, max_results)


@mcp.tool()
def tool_list_doc_pages() -> dict:
    """List all available documentation pages in the local docs index.

    Returns a list of doc page names and their sizes. Use this to see what
    documentation is available before searching.

    Returns:
        dict with {ok, pages: [{name, size}], total_pages, total_size}.
    """
    return list_doc_pages()


def main():
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
