# Filesystem MCP Server

An MCP server that gives Claude Desktop sandboxed read/write access to the local filesystem. All operations are restricted to a configurable set of allowed root directories.

## Tools

### Read
| Tool | Description |
|---|---|
| `read_file` | Read a file's text content |
| `list_directory` | List entries in a directory (name, type, size) |
| `get_file_info` | Stat metadata (size, timestamps, permissions) |
| `search_files` | Recursive grep-like content search |
| `glob_files` | Find files matching a glob pattern |

### Write
| Tool | Description |
|---|---|
| `write_file` | Create or overwrite a file |
| `edit_file` | Find-and-replace within a file |
| `create_directory` | Create a directory (and parents) |
| `move_file` | Move or rename a file/directory |
| `delete_file` | Delete a file |
| `delete_directory` | Delete a directory (optionally recursive) |

## Setup

1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and configure:
   ```
   FS_ALLOWED_ROOTS=C:\path\to\dir1;C:\path\to\dir2
   FS_READ_ONLY=false
   ```
   **Important:** Do not use wildcards (e.g. `\*`) in `FS_ALLOWED_ROOTS`. Paths are matched using `os.path.realpath()`, which treats `\*` as a literal directory name. Access to all files and subdirectories under each root is granted automatically.

3. Add the server to `claude_desktop_config.json`:
   ```json
   {
     "mcpServers": {
       "filesystem": {
         "command": "C:\\...\\filesystem_mcp\\.venv\\Scripts\\python.exe",
         "args": ["C:\\...\\filesystem_mcp\\server.py"],
         "env": {}
       }
     }
   }
   ```

4. Restart Claude Desktop.

## Security

- All paths are resolved to absolute, canonical form via `os.path.realpath()` before any I/O.
- Every operation validates that the resolved path falls within an allowed root.
- Symlink traversal outside allowed roots is blocked.
- Set `FS_READ_ONLY=true` to disable all write operations.

## Architecture

| File | Role |
|---|---|
| `config.py` | Loads `FS_ALLOWED_ROOTS` and `FS_READ_ONLY` from `.env` |
| `client.py` | `FilesystemClient` — sandboxed I/O with path validation |
| `server.py` | FastMCP server exposing tools via stdio transport |
