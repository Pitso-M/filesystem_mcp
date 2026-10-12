"""
Filesystem MCP Server
=====================
An MCP server that lets Claude Desktop read from and write to the local
filesystem, sandboxed to a configurable set of allowed root directories.

Read tools:
  - read_file: Read a file's text content.
  - list_directory: List entries in a directory.
  - get_file_info: Stat metadata (size, modified, permissions).
  - search_files: Grep-like recursive content search.
  - glob_files: Find files matching a glob pattern.

Write tools:
  - write_file: Create or overwrite a file.
  - edit_file: Surgical find-and-replace within a file.
  - create_directory: Create a directory (and parents).
  - move_file: Move or rename a file/directory.
  - delete_file: Delete a file.
  - delete_directory: Delete a directory.

Usage (stdio for Claude Desktop):
  python server.py

Requirements:
  pip install "mcp[cli]" python-dotenv
"""
from __future__ import annotations

import sys

from mcp.server.fastmcp import FastMCP

from client import FilesystemClient

mcp = FastMCP("Filesystem", json_response=True)

# ── Client singleton (built once, reused across tool calls) ──────────
_client: FilesystemClient | None = None
_init_error: str | None = None

try:
    _client = FilesystemClient()
    print(f"[filesystem_mcp] Initialised. Allowed roots: {_client.allowed_roots}", file=sys.stderr)
    print(f"[filesystem_mcp] Read-only: {_client.read_only}", file=sys.stderr)
except Exception as exc:  # noqa: BLE001
    _init_error = str(exc)
    print(f"[filesystem_mcp] WARNING: client init failed: {exc}", file=sys.stderr)


def _guard() -> dict | None:
    """Return an error dict if the client is unavailable, else None."""
    if _client is None:
        return {"error": f"Filesystem client not initialised: {_init_error}"}
    return None


def _safe(fn) -> dict | list | str | int:
    """Run a client call, converting exceptions into an error dict."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


# ═════════════════════════════════════════════════════════════════════
# READ TOOLS
# ═════════════════════════════════════════════════════════════════════

@mcp.tool()
def read_file(path: str) -> dict:
    """Read a file and return its text content.

    `path` must be an absolute path within one of the allowed root directories.
    """
    if err := _guard():
        return err
    result = _safe(lambda: _client.read_file(path))
    if isinstance(result, dict) and "error" in result:
        return result
    return {"path": path, "content": result}


@mcp.tool()
def list_directory(path: str) -> dict:
    """List entries in a directory.

    Returns name, type ('file' or 'directory'), and size (for files) of each entry.
    `path` must be an absolute path within one of the allowed root directories.
    """
    if err := _guard():
        return err
    result = _safe(lambda: _client.list_directory(path))
    if isinstance(result, dict) and "error" in result:
        return result
    return {"path": path, "count": len(result), "entries": result}


@mcp.tool()
def get_file_info(path: str) -> dict:
    """Return metadata about a file or directory (size, timestamps, permissions).

    `path` must be an absolute path within one of the allowed root directories.
    """
    if err := _guard():
        return err
    result = _safe(lambda: _client.get_file_info(path))
    if isinstance(result, dict) and "error" in result:
        return result
    return result


@mcp.tool()
def search_files(path: str, pattern: str, max_results: int = 100) -> dict:
    """Recursively search for files whose content contains `pattern`.

    Returns a list of matching file paths (capped at `max_results`).
    Binary files are skipped. `path` is the root directory to search from.
    """
    if err := _guard():
        return err
    result = _safe(lambda: _client.search_files(path, pattern, max_results=max_results))
    if isinstance(result, dict) and "error" in result:
        return result
    return {"path": path, "pattern": pattern, "count": len(result), "matches": result}


@mcp.tool()
def glob_files(path: str, glob_pattern: str) -> dict:
    """Find files matching a glob pattern under a directory.

    Example: glob_files("/projects", "**/*.py") finds all Python files recursively.
    `path` is the root directory, `glob_pattern` is a standard glob expression.
    """
    if err := _guard():
        return err
    result = _safe(lambda: _client.glob_files(path, glob_pattern))
    if isinstance(result, dict) and "error" in result:
        return result
    return {"path": path, "glob_pattern": glob_pattern, "count": len(result), "files": result}


# ═════════════════════════════════════════════════════════════════════
# WRITE TOOLS
# ═════════════════════════════════════════════════════════════════════

@mcp.tool()
def write_file(path: str, content: str) -> dict:
    """Create or overwrite a file with the given text content.

    Parent directories are created automatically if they don't exist.
    `path` must be an absolute path within one of the allowed root directories.
    Blocked when the server is in read-only mode.
    """
    if err := _guard():
        return err
    result = _safe(lambda: _client.write_file(path, content))
    if isinstance(result, dict) and "error" in result:
        return result
    return {"written": True, "path": path, "size": len(content)}


@mcp.tool()
def edit_file(path: str, old_text: str, new_text: str) -> dict:
    """Replace all occurrences of `old_text` with `new_text` in a file.

    Returns the number of replacements made. Fails if `old_text` is not found.
    Blocked when the server is in read-only mode.
    """
    if err := _guard():
        return err
    result = _safe(lambda: _client.edit_file(path, old_text, new_text))
    if isinstance(result, dict) and "error" in result:
        return result
    return {"edited": True, "path": path, "replacements": result}


@mcp.tool()
def create_directory(path: str) -> dict:
    """Create a directory (and any missing parent directories).

    `path` must be an absolute path within one of the allowed root directories.
    Blocked when the server is in read-only mode.
    """
    if err := _guard():
        return err
    result = _safe(lambda: _client.create_directory(path))
    if isinstance(result, dict) and "error" in result:
        return result
    return {"created": True, "path": path}


@mcp.tool()
def move_file(source: str, destination: str) -> dict:
    """Move or rename a file or directory.

    Both `source` and `destination` must be within allowed root directories.
    Blocked when the server is in read-only mode.
    """
    if err := _guard():
        return err
    result = _safe(lambda: _client.move_file(source, destination))
    if isinstance(result, dict) and "error" in result:
        return result
    return {"moved": True, "source": source, "destination": destination}


@mcp.tool()
def delete_file(path: str) -> dict:
    """Delete a file.

    `path` must be an absolute path within one of the allowed root directories.
    Use `delete_directory` for directories. Blocked when in read-only mode.
    """
    if err := _guard():
        return err
    result = _safe(lambda: _client.delete_file(path))
    if isinstance(result, dict) and "error" in result:
        return result
    return {"deleted": True, "path": path}


@mcp.tool()
def delete_directory(path: str, recursive: bool = False) -> dict:
    """Delete a directory.

    Set `recursive=True` to delete non-empty directories and all their contents.
    Without `recursive`, only empty directories can be deleted.
    Blocked when the server is in read-only mode.
    """
    if err := _guard():
        return err
    result = _safe(lambda: _client.delete_directory(path, recursive=recursive))
    if isinstance(result, dict) and "error" in result:
        return result
    return {"deleted": True, "path": path, "recursive": recursive}


# ── Entry point ──────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run(transport="stdio")
