"""
Filesystem client.

Provides safe, sandboxed file-system operations restricted to a set of
allowed root directories.  All paths are resolved to absolute, canonical
form and validated before any I/O is performed.

This module is a self-contained copy used by the Filesystem MCP server.
"""
from __future__ import annotations

import os
import shutil
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config as _config


class FilesystemClient:
    """Sandboxed filesystem operations restricted to allowed roots."""

    def __init__(self, cfg: dict | None = None) -> None:
        cfg = cfg or _config.load()
        self.allowed_roots: list[str] = cfg["allowed_roots"]
        self.read_only: bool = cfg.get("read_only", False)

    # ------------------------------------------------------------------
    # Path validation
    # ------------------------------------------------------------------

    def _validate(self, path: str) -> str:
        """Resolve *path* to an absolute, canonical path and verify it
        falls within one of the allowed roots.

        Raises PermissionError if the path is outside every root.
        """
        resolved = os.path.realpath(os.path.expanduser(path))
        print(f"[filesystem_mcp] _validate: input={path!r}  resolved={resolved!r}", file=sys.stderr)
        for root in self.allowed_roots:
            if resolved == root or resolved.startswith(root + os.sep):
                return resolved
        print(f"[filesystem_mcp] _validate: DENIED. Roots={self.allowed_roots!r}", file=sys.stderr)
        raise PermissionError(
            f"Access denied — path is outside allowed roots: {path}"
        )

    def _require_write(self) -> None:
        """Raise if the server is in read-only mode."""
        if self.read_only:
            raise PermissionError("Server is in read-only mode.")

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def read_file(self, path: str) -> str:
        """Return the text content of a file."""
        safe = self._validate(path)
        with open(safe, "r", encoding="utf-8") as fh:
            return fh.read()

    def list_directory(self, path: str) -> list[dict]:
        """Return a list of entries in a directory.

        Each entry is a dict with keys: name, type ('file' | 'directory'),
        size (bytes, files only).
        """
        safe = self._validate(path)
        entries: list[dict] = []
        for entry in sorted(os.scandir(safe), key=lambda e: e.name):
            info: dict[str, Any] = {
                "name": entry.name,
                "type": "directory" if entry.is_dir(follow_symlinks=True) else "file",
            }
            if entry.is_file(follow_symlinks=True):
                info["size"] = entry.stat().st_size
            entries.append(info)
        return entries

    def get_file_info(self, path: str) -> dict:
        """Return metadata about a file or directory."""
        safe = self._validate(path)
        st = os.stat(safe)
        return {
            "path": safe,
            "type": "directory" if stat.S_ISDIR(st.st_mode) else "file",
            "size": st.st_size,
            "created": datetime.fromtimestamp(st.st_ctime, tz=timezone.utc).isoformat(),
            "modified": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
            "permissions": oct(st.st_mode),
            "is_symlink": os.path.islink(path),
        }

    def search_files(
        self, path: str, pattern: str, max_results: int = 100
    ) -> list[str]:
        """Recursively search for files whose content contains *pattern*.

        Returns a list of matching file paths (capped at *max_results*).
        Binary files are skipped silently.
        """
        safe = self._validate(path)
        matches: list[str] = []
        for root, _dirs, files in os.walk(safe):
            # Stay inside allowed roots even if symlinks escape
            self._validate(root)
            for fname in files:
                if len(matches) >= max_results:
                    return matches
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as fh:
                        if pattern in fh.read():
                            matches.append(fpath)
                except (UnicodeDecodeError, PermissionError, OSError):
                    continue
        return matches

    def glob_files(self, path: str, glob_pattern: str) -> list[str]:
        """Return files matching a glob pattern under *path*.

        Example: glob_files("/projects", "**/*.py")
        """
        safe = self._validate(path)
        results = [str(p) for p in Path(safe).glob(glob_pattern) if p.is_file()]
        # Validate each result stays within roots
        return [r for r in results if self._is_allowed(r)]

    def _is_allowed(self, path: str) -> bool:
        """Check without raising."""
        try:
            self._validate(path)
            return True
        except PermissionError:
            return False

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def write_file(self, path: str, content: str) -> None:
        """Create or overwrite a file with *content*."""
        self._require_write()
        safe = self._validate(path)
        os.makedirs(os.path.dirname(safe), exist_ok=True)
        with open(safe, "w", encoding="utf-8") as fh:
            fh.write(content)

    def edit_file(self, path: str, old_text: str, new_text: str) -> int:
        """Replace all occurrences of *old_text* with *new_text* in a file.

        Returns the number of replacements made.
        Raises ValueError if old_text is not found.
        """
        self._require_write()
        safe = self._validate(path)
        with open(safe, "r", encoding="utf-8") as fh:
            original = fh.read()
        count = original.count(old_text)
        if count == 0:
            raise ValueError(f"old_text not found in {path}")
        updated = original.replace(old_text, new_text)
        with open(safe, "w", encoding="utf-8") as fh:
            fh.write(updated)
        return count

    def create_directory(self, path: str) -> None:
        """Create a directory (and parents) if it doesn't exist."""
        self._require_write()
        safe = self._validate(path)
        os.makedirs(safe, exist_ok=True)

    def move_file(self, source: str, destination: str) -> None:
        """Move or rename a file/directory."""
        self._require_write()
        safe_src = self._validate(source)
        safe_dst = self._validate(destination)
        shutil.move(safe_src, safe_dst)

    def delete_file(self, path: str) -> None:
        """Delete a file."""
        self._require_write()
        safe = self._validate(path)
        if os.path.isdir(safe):
            raise IsADirectoryError(f"Use delete_directory for directories: {path}")
        os.remove(safe)

    def delete_directory(self, path: str, recursive: bool = False) -> None:
        """Delete a directory (optionally recursive)."""
        self._require_write()
        safe = self._validate(path)
        if recursive:
            shutil.rmtree(safe)
        else:
            os.rmdir(safe)  # fails if non-empty

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def close(self) -> None:
        pass
