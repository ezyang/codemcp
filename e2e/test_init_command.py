#!/usr/bin/env python3

import re
import subprocess
import tempfile
from pathlib import Path

from codemcp.main import init_codemcp_project


def test_init_command():
    """Test the init command creates a codemcp.toml file and initializes a git repo."""
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Run the init_codemcp_project function
        result = init_codemcp_project(temp_dir)

        # Check that the function reports success
        assert "Successfully initialized" in result

        # Check that codemcp.toml was created
        config_file = Path(temp_dir) / "codemcp.toml"
        assert config_file.exists()

        # Check that git repository was initialized
        git_dir = Path(temp_dir) / ".git"
        assert git_dir.is_dir()

        # Check that a commit was created
        result = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=temp_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "initialize codemcp project" in result.stdout


def test_init_command_existing_repo():
    """Test the init command works with an existing git repository."""
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Initialize git repository first
        subprocess.run(["git", "init"], cwd=temp_dir, check=True)

        # Make a dummy commit to simulate existing repository
        dummy_file = Path(temp_dir) / "dummy.txt"
        dummy_file.write_text("test content")

        subprocess.run(
            ["git", "config", "user.name", "Test User"], cwd=temp_dir, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=temp_dir,
            check=True,
        )
        subprocess.run(["git", "add", "dummy.txt"], cwd=temp_dir, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"], cwd=temp_dir, check=True
        )

        # Run the init_codemcp_project function
        result = init_codemcp_project(temp_dir)

        # Check that the function reports success
        assert "Successfully initialized" in result

        # Check that codemcp.toml was created
        config_file = Path(temp_dir) / "codemcp.toml"
        assert config_file.exists()


def test_init_command_with_python():
    """Test the init command with Python option creates Python project structure."""
    # Create a temporary directory for testing with a specific name
    with tempfile.TemporaryDirectory(prefix="test-project-") as temp_dir:
        temp_path = Path(temp_dir)
        project_name = temp_path.name  # Get the directory name
        package_name = re.sub(r"[^a-z0-9_]", "_", project_name.lower())

        # Run the init_codemcp_project function with Python option
        result = init_codemcp_project(temp_dir, python=True)

        # Check that the function reports success with Python message
        assert "Successfully initialized" in result
        assert "with Python project structure" in result

        # Check that standard files were created
        config_file = temp_path / "codemcp.toml"
        assert config_file.exists()

        # Check that git repository was initialized
        git_dir = temp_path / ".git"
        assert git_dir.is_dir()

        # Check that Python-specific files were created
        pyproject_file = temp_path / "pyproject.toml"
        assert pyproject_file.exists()

        # Check if the project name was correctly applied in pyproject.toml
        with open(pyproject_file, "r") as f:
            content = f.read()
            assert project_name in content

        readme_file = temp_path / "README.md"
        assert readme_file.exists()

        # Check package structure with correct name derived from directory
        package_dir = temp_path / package_name
        assert package_dir.is_dir()

        init_file = package_dir / "__init__.py"
        assert init_file.exists()

        # Check if __init__.py contains the correct project name
        with open(init_file, "r") as f:
            content = f.read()
            assert project_name in content

        # Check that the commit message includes Python template reference
        result = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=temp_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "with Python template" in result.stdout
