#!/usr/bin/env python3

import os
import subprocess
import sys
import tempfile

import pytest

from codemcp.main import init_codemcp_project


@pytest.fixture
def project_dir():
    """Create a temporary project directory with a simple codemcp.toml configuration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Initialize the project
        init_codemcp_project(temp_dir)

        # Create a codemcp.toml file with test commands
        config_path = os.path.join(temp_dir, "codemcp.toml")
        with open(config_path, "w") as f:
            f.write("""
[commands]
echo = ["echo", "Hello World"]
pwd = ["pwd"]
            """)

        # Create a subdirectory
        subdir = os.path.join(temp_dir, "subdir")
        os.makedirs(subdir, exist_ok=True)

        yield temp_dir


def test_run_command_from_subdir(project_dir):
    """Test running a command from a subdirectory of the project."""
    subdir = os.path.join(project_dir, "subdir")

    # Run pwd command from subdirectory to verify cwd
    result = subprocess.run(
        [sys.executable, "-m", "codemcp", "run", "pwd", "--path", subdir],
        capture_output=True,
        text=True,
        check=True,
    )

    # The pwd output should show the project root, not the subdirectory
    # Normalize paths for comparison (strip trailing slashes, etc.)
    normalized_output = os.path.normpath(result.stdout.strip())
    normalized_project_dir = os.path.normpath(project_dir)
    assert normalized_output == normalized_project_dir


def test_run_command_from_project_root(project_dir):
    """Test running a command from the project root."""
    result = subprocess.run(
        [sys.executable, "-m", "codemcp", "run", "echo", "--path", project_dir],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Hello World" in result.stdout
