"""
Configuration loader for the Filesystem MCP server.

Reads from .env (in this folder) or environment variables already set in the
shell / Claude Desktop launch config.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from this directory, if present
load_dotenv(Path(__file__).parent / ".env")


def load() -> dict:
    """Load and validate filesystem configuration from environment.

    Returns a dict with keys: allowed_roots, read_only.
    Raises RuntimeError if no roots are configured.
    """
    raw_roots = os.environ.get("FS_ALLOWED_ROOTS", "")
    if not raw_roots.strip():
        raise RuntimeError(
            "Missing required environment variable:\n"
            "  FS_ALLOWED_ROOTS: Semicolon-separated list of directories the server may access,\n"
            "                    e.g. C:\\Users\\me\\projects;D:\\shared\n\n"
            "Copy .env.example → .env and fill in the values."
        )

    roots = [os.path.realpath(r.strip()) for r in raw_roots.split(";") if r.strip()]
    if not roots:
        raise RuntimeError("FS_ALLOWED_ROOTS contained no valid paths.")

    read_only = os.environ.get("FS_READ_ONLY", "false").lower() in ("1", "true", "yes")

    return {
        "allowed_roots": roots,
        "read_only": read_only,
    }
