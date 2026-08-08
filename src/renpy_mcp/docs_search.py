"""Documentation search tool: search_docs.

Searches a local copy of the Ren'Py official documentation (Chinese, from
doc.renpy.cn) and returns relevant sections. Works offline after the docs
are downloaded.
"""

import os
import re
import math
from collections import defaultdict

DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")

# Cache: loaded docs and search index
_docs_cache: list[dict] | None = None
_index_cache: dict[str, list[int]] | None = None


def _is_cjk(text: str) -> bool:
    """Check if text contains CJK characters."""
    for ch in text:
        cp = ord(ch)
        if 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF:
            return True
    return False


def _load_docs() -> list[dict]:
    """Load all .txt doc files and split into sections by headers.

    Returns a list of section dicts:
        {file, title, content, line_start}
    """
    global _docs_cache
    if _docs_cache is not None:
        return _docs_cache

    sections: list[dict] = []

    if not os.path.isdir(DOCS_DIR):
        _docs_cache = sections
        return sections

    for filename in sorted(os.listdir(DOCS_DIR)):
        if not filename.endswith(".txt") or filename.startswith("_"):
            continue
        filepath = os.path.join(DOCS_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                content = f.read()
        except (IOError, UnicodeDecodeError):
            continue

        # Split into sections by markdown-style headers
        current_title = filename.replace(".txt", "")
        current_lines: list[str] = []
        line_no = 0

        for line in content.split("\n"):
            line_no += 1
            header_match = re.match(r"^(#{1,6})\s+(.+)", line)
            if header_match:
                # Save previous section
                if current_lines:
                    sections.append({
                        "file": filename.replace(".txt", ""),
                        "title": current_title,
                        "content": "\n".join(current_lines).strip(),
                        "line_start": line_no - len(current_lines),
                    })
                current_title = header_match.group(2).strip()
                current_lines = [line]
            else:
                current_lines.append(line)

        # Save last section
        if current_lines:
            sections.append({
                "file": filename.replace(".txt", ""),
                "title": current_title,
                "content": "\n".join(current_lines).strip(),
                "line_start": line_no - len(current_lines),
            })

    _docs_cache = sections
    return sections


def _tokenize(query: str) -> list[str]:
    """Split query into search tokens.

    For CJK text, we use the full query string and also try 2-character grams.
    For ASCII text, we split on word boundaries.
    """
    tokens: list[str] = []

    if _is_cjk(query):
        # For CJK, use the full query as one token, plus 2-char grams
        tokens.append(query)
        # Also add 2-character grams for better matching
        chars = [ch for ch in query if 0x4E00 <= ord(ch) <= 0x9FFF]
        for i in range(len(chars) - 1):
            tokens.append(chars[i] + chars[i + 1])
        # Also add individual ASCII words in the query
        for word in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", query):
            tokens.append(word.lower())
    else:
        # For ASCII, split into words
        for word in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", query):
            tokens.append(word.lower())

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


def search_docs(query: str, max_results: int = 5) -> dict:
    """Search the local Ren'Py documentation for a keyword or phrase.

    Searches through the bundled Ren'Py official documentation (Chinese, from
    doc.renpy.cn) and returns the most relevant sections. Works offline.

    Use this BEFORE writing Ren'Py code if you're unsure about syntax, function
    names, or best practices. For example:
      - search_docs("Movie") to learn how to play videos
      - search_docs("screen") to understand screen language
      - search_docs("transform") to learn about ATL transforms
      - search_docs("call from") to understand call/from semantics
      - search_docs("存档") to find save/load documentation

    Args:
        query: Search query (supports both English and Chinese).
        max_results: Maximum number of results to return (default 5).

    Returns:
        dict with:
            ok: bool
            query: str
            results: [{file, title, snippet, score, line_start}]
            total_sections_searched: int
    """
    sections = _load_docs()

    if not sections:
        return {
            "ok": False,
            "query": query,
            "results": [],
            "error": "No documentation found. Docs directory is empty or missing.",
        }

    tokens = _tokenize(query)
    if not tokens:
        return {
            "ok": False,
            "query": query,
            "results": [],
            "error": "No valid search tokens in query.",
        }

    # Score each section by counting token matches
    scored: list[tuple[float, dict]] = []

    for section in sections:
        content_lower = section["content"].lower()
        title_lower = section["title"].lower()
        score = 0.0

        for token in tokens:
            token_lower = token.lower()
            # Title matches weighted higher
            title_count = title_lower.count(token_lower)
            content_count = content_lower.count(token_lower)
            score += title_count * 3.0 + content_count * 1.0

        if score > 0:
            # Normalize by section length to prefer concise sections
            length_factor = 1.0 / (1.0 + len(section["content"]) / 5000.0)
            score *= length_factor
            scored.append((score, section))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Build results
    results = []
    for score, section in scored[:max_results]:
        # Extract a relevant snippet around the first match
        snippet = _extract_snippet(section["content"], tokens, max_chars=800)
        results.append({
            "file": section["file"],
            "title": section["title"],
            "snippet": snippet,
            "score": round(score, 2),
            "line_start": section.get("line_start", 0),
        })

    return {
        "ok": True,
        "query": query,
        "results": results,
        "result_count": len(results),
        "total_sections_searched": len(sections),
    }


def _extract_snippet(content: str, tokens: list[str], max_chars: int = 800) -> str:
    """Extract a relevant snippet from content around the first token match."""
    content_lower = content.lower()

    # Find the position of the first matching token
    best_pos = -1
    for token in tokens:
        pos = content_lower.find(token.lower())
        if pos >= 0:
            if best_pos < 0 or pos < best_pos:
                best_pos = pos

    if best_pos < 0:
        # No match found, return beginning
        return content[:max_chars].strip()

    # Extract context around the match
    start = max(0, best_pos - max_chars // 3)
    end = min(len(content), start + max_chars)

    snippet = content[start:end].strip()

    # Add ellipsis if truncated
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet = snippet + "..."

    return snippet


def list_doc_pages() -> dict:
    """List all available documentation pages.

    Returns a dict with available doc page names and their sizes.
    Useful to see what documentation is available before searching.
    """
    if not os.path.isdir(DOCS_DIR):
        return {"ok": False, "pages": [], "error": "Docs directory not found."}

    pages = []
    for filename in sorted(os.listdir(DOCS_DIR)):
        if not filename.endswith(".txt") or filename.startswith("_"):
            continue
        filepath = os.path.join(DOCS_DIR, filename)
        size = os.path.getsize(filepath)
        pages.append({
            "name": filename.replace(".txt", ""),
            "size": size,
        })

    return {
        "ok": True,
        "pages": pages,
        "total_pages": len(pages),
        "total_size": sum(p["size"] for p in pages),
    }
