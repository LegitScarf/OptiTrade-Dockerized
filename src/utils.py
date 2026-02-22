import os
from pathlib import Path

# src/ directory — where this file lives
_SRC_DIR = Path(__file__).parent

def get_project_root() -> Path:
    """Returns the absolute path to the project root directory."""
    return _SRC_DIR.parent

def get_config_path(filename: str) -> str:
    """Returns the absolute path to a config file inside src/config/."""
    # FIX: Config files live in src/config/, not root/config/.
    # Using _SRC_DIR instead of get_project_root() ensures the path resolves
    # to /app/src/config/ regardless of what directory the process runs from.
    return str(_SRC_DIR / "config" / filename)

def get_output_path(filename: str) -> str:
    """Returns the absolute path to an output file inside root/output/."""
    # Output is at project root level /app/output/ — this one is correct.
    return str(get_project_root() / "output" / filename)