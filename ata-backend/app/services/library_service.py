# /app/services/library_service.py

import os
import json
from typing import List, Dict, Any
from pathlib import Path

# --- [START] HARDENED PATH LOGIC ---

# Get the directory where this very file (library_service.py) is located.
# e.g., /path/to/project/ata-backend/app/services
SERVICE_FILE_DIR = Path(__file__).parent.resolve()

# Construct an absolute path to the project's root directory
# by going up two levels (from /services to /app to /).
PROJECT_ROOT_DIR = SERVICE_FILE_DIR.parent.parent

# Construct a robust, absolute path to the Books directory.
BOOKS_ROOT_DIR = PROJECT_ROOT_DIR / "Books"

# --- [END] HARDENED PATH LOGIC ---


# In-memory cache for the library tree.
_library_cache: List[Dict[str, Any]] = []

def _scan_directory_and_build_tree(path: Path) -> List[Dict[str, Any]]:
    """
    Recursively scans a directory and builds a nested list of dictionaries
    representing the folder and file structure. Now uses pathlib.Path.
    """
    items = []
    try:
        # os.scandir works fine with Path objects
        for entry in sorted(os.scandir(path), key=lambda e: e.name):
            # For chapters, we only include .txt files
            if entry.is_file() and not entry.name.endswith('.txt'):
                continue
            
            # Use pathlib for cleaner path joining
            entry_path = Path(entry.path)
            
            item_data = {
                "id": str(entry_path),
                "name": entry_path.name.replace('.txt', ''),
                "path": str(entry_path),
                "children": _scan_directory_and_build_tree(entry_path) if entry_path.is_dir() else None
            }
            items.append(item_data)
    except FileNotFoundError:
        print(f"WARNING: Directory not found during library scan: {path}")
    except Exception as e:
        print(f"ERROR scanning library directory {path}: {e}")
        
    return items

def initialize_library_cache():
    """
    Initializes the in-memory library cache by scanning the root books directory.
    This function is intended to be called once when the FastAPI application starts up.
    """
    global _library_cache
    print("INFO: Scanning book library directory...")
    # Use the robustly constructed absolute path
    if BOOKS_ROOT_DIR.is_dir():
        _library_cache = _scan_directory_and_build_tree(BOOKS_ROOT_DIR)
        print(f"INFO: Book library scan complete. Found {len(_library_cache)} top-level items.")
    else:
        print(f"WARNING: Root books directory '{str(BOOKS_ROOT_DIR)}' not found. Library will be empty.")
        _library_cache = []

def get_library_tree() -> List[Dict[str, Any]]:
    """
    Returns the cached library tree structure.
    """
    return _library_cache