import os
from pathlib import Path

def get_project_root() -> Path:
    """Returns the absolute path to the project root directory."""
    # Since this file is in src/, the root is one level up
    return Path(__file__).parent.parent

def get_config_path(filename: str) -> str:
    """Returns the absolute path to a config file."""
    path = get_project_root() / "config" / filename
    return str(path)

def get_output_path(filename: str) -> str:
    """Returns the absolute path to an output file."""
    path = get_project_root() / "output" / filename
    return str(path)