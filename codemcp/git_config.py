#!/usr/bin/env python3

import logging
import os
from pathlib import Path
from typing import Optional

# Set up logger first
log = logging.getLogger(__name__)

# Use tomllib for Python 3.11+, fall back to tomli
tomllib = None
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        # If neither is available, we'll handle this gracefully
        log.warning("Neither tomllib nor tomli is available, will use default config values")

def get_git_config_no_commit(path: Optional[str] = None) -> bool:
    """Get the no_commit configuration value from codemcp.toml.
    
    Args:
        path: Optional path to use for finding the config file.
              If not provided, will search from current directory upwards.
    
    Returns:
        True if no_commit is enabled (default), False otherwise
    """
    try:
        config_path = find_config_file(path)
        if not config_path:
            # Default to True if no config file found
            return True
        
        with open(config_path, "rb") as f:
            if tomllib is None:
                # If tomllib is not available, return default
                log.warning("Could not load TOML library, using default no_commit=True")
                return True
            
            # Load the config file
            config = tomllib.load(f)
        
        # Check if git.no_commit is specified in the config
        if "git" in config and "no_commit" in config["git"]:
            return bool(config["git"]["no_commit"])
        
        # Default to True if not specified
        return True
    except Exception as e:
        log.warning(f"Error reading git.no_commit from config: {e}")
        # Default to True on error
        return True

def find_config_file(start_path: Optional[str] = None) -> Optional[str]:
    """Find the codemcp.toml file by searching upwards from the given path.
    
    Args:
        start_path: Path to start searching from. If None, uses current directory.
    
    Returns:
        Path to the config file, or None if not found
    """
    if start_path is None:
        start_path = os.getcwd()
    
    current_dir = Path(start_path).resolve()
    
    # Search up to the root directory
    while current_dir != current_dir.parent:
        config_path = current_dir / "codemcp.toml"
        if config_path.exists():
            return str(config_path)
        current_dir = current_dir.parent
    
    return None
