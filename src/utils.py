import os
from pathlib import Path

# src/ directory — where this file lives
_SRC_DIR = Path(__file__).parent

def get_project_root() -> Path:
    """Returns the absolute path to the project root directory."""
    # This file is at /app/src/utils.py so parent.parent = /app
    return _SRC_DIR.parent

def get_config_path(filename: str) -> str:
    """Returns the absolute path to a config file inside root/config/."""
    # FIX: config/ lives at project root /app/config/, NOT inside src/
    return str(get_project_root() / "config" / filename)

def get_output_path(filename: str) -> str:
    """Returns the absolute path to an output file inside root/output/."""
    return str(get_project_root() / "output" / filename)