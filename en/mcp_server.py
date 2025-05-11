from mcp.server.fastmcp import FastMCP
import os
import pathlib
import sys

# The server name can be anything
mcp = FastMCP("DesktopFilesystem")

# Fix the root to the Desktop directory
BASE_DIR = pathlib.Path(os.path.expanduser("~/Desktop")).resolve()

def _validate_path(rel_path: str) -> pathlib.Path:
    """
    Check that the path is relative to the desktop,
    and return the absolute path. Raise an error if out of bounds.
    """
    target = (BASE_DIR / rel_path).resolve()
    if not str(target).startswith(str(BASE_DIR)):
        raise ValueError(f"Access denied: {rel_path}")
    return target

@mcp.tool()
def list_items() -> list[dict]:
    """
    Retrieve a list of files and folders under the desktop.
    Returns a list in the format [{'name': 'foo.txt', 'is_dir': False}, ...]
    """
    items = []
    for p in BASE_DIR.iterdir():
        items.append({
            "name": p.name,
            "is_dir": p.is_dir()
        })
    return items

@mcp.tool()
def create(path: str, is_dir: bool = False) -> str:
    """
    Create a folder or file on the desktop.
    - path: Relative path from the desktop (e.g., 'hoge/README.md')
    - is_dir: True to create a folder, False to create a file
    """
    target = _validate_path(path)
    if is_dir:
        target.mkdir(parents=True, exist_ok=True)
        return f"Directory created: {target}"
    else:
        # Create parent directories if they don’t exist
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch(exist_ok=True)
        return f"File created: {target}"

@mcp.tool()
def append_to_file(path: str, content: str) -> str:
    """
    Append text to an existing file on the desktop.
    - path: Relative path from the desktop (e.g., 'hoge/notes.txt')
    - content: The string to append
    """
    target = _validate_path(path)
    if not target.exists():
        raise FileNotFoundError(f"File not found: {target}")
    if target.is_dir():
        raise IsADirectoryError(f"Is a directory: {target}")
    with open(target, "a", encoding="utf-8") as f:
        f.write(content)
    return f"Appended to {target}"

if __name__ == "__main__":
    # Start the MCP server using standard input/output
    mcp.run()
