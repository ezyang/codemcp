#!/usr/bin/env python3

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

import codemcp.git
from codemcp.main import cli


# Create non-async mock functions to replace async ones
def mock_is_git_repository(*args, **kwargs):
    return False


def mock_check_for_changes(*args, **kwargs):
    return False


def mock_commit_changes(*args, **kwargs):
    return (True, "Mock commit message")


# Patch the modules directly
codemcp.git.is_git_repository = mock_is_git_repository


@pytest.fixture
def test_project():
    """Create a temporary directory with a codemcp.toml file for testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a codemcp.toml file with test commands
        config_path = Path(tmp_dir) / "codemcp.toml"
        with open(config_path, "w") as f:
            f.write("""[commands]
echo = ["echo", "Hello from codemcp run!"]
echo_args = ["echo"]
invalid = []
""")

        # Initialize a git repository
        subprocess.run(["git", "init"], cwd=tmp_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"], cwd=tmp_dir, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=tmp_dir, check=True
        )
        subprocess.run(["git", "add", "codemcp.toml"], cwd=tmp_dir, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"], cwd=tmp_dir, check=True
        )

        yield tmp_dir


def test_run_command_success(test_project):
    """Test running a command successfully."""
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "echo", "--path", test_project, "--no-stream"])

    assert result.exit_code == 0
    assert "Hello from codemcp run!" in result.output
    assert "Code echo successful" in result.output


def test_run_command_with_args(test_project):
    """Test running a command with arguments."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "run",
            "echo_args",
            "Test",
            "argument",
            "string",
            "--path",
            test_project,
            "--no-stream",
        ],
    )

    assert result.exit_code == 0
    assert "Test argument string" in result.output
    assert "Code echo_args successful" in result.output


def test_run_command_not_found(test_project):
    """Test running a command that doesn't exist in config."""
    runner = CliRunner()
    result = runner.invoke(
        cli, ["run", "nonexistent", "--path", test_project, "--no-stream"]
    )

    assert "Error: Command 'nonexistent' not found in codemcp.toml" in result.output


def test_run_command_empty_definition(test_project):
    """Test running a command with an empty definition."""
    runner = CliRunner()
    result = runner.invoke(
        cli, ["run", "invalid", "--path", test_project, "--no-stream"]
    )

    assert "Error: Command 'invalid' not found in codemcp.toml" in result.output


@patch("codemcp.git.is_git_repository", mock_is_git_repository)
@patch("codemcp.code_command.check_for_changes", mock_check_for_changes)
@patch("codemcp.git.commit_changes", mock_commit_changes)
@patch(
    "asyncio.run", lambda x: False
)  # Mock asyncio.run to return False for all coroutines
def test_run_command_stream_mode(test_project):
    """Test running a command with streaming mode."""
    import subprocess

    # Create a mock for subprocess.Popen
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.wait.return_value = 0

    # Keep track of Popen calls
    popen_calls = []

    # Create a safe replacement for Popen that won't leave hanging processes
    original_popen = subprocess.Popen

    def mock_popen(cmd, **kwargs):
        if (
            isinstance(cmd, list)
            and cmd[0] == "echo"
            and "Hello from codemcp run!" in cmd
        ):
            popen_calls.append((cmd, kwargs))
            return mock_process
        # For any other command, create a safe echo process with proper cleanup
        return original_popen(
            ["echo", "Test"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

    with patch("subprocess.Popen", mock_popen):
        # Run the command with isolated stdin/stdout to prevent interference
        runner = CliRunner(mix_stderr=False)
        runner.invoke(cli, ["run", "echo", "--path", test_project])

        # Check that our command was executed with the right parameters
        assert any(cmd == ["echo", "Hello from codemcp run!"] for cmd, _ in popen_calls)

        # Find the call for our echo command
        for cmd, kwargs in popen_calls:
            if cmd == ["echo", "Hello from codemcp run!"]:
                # Verify streaming parameters
                assert kwargs.get("stdout") is None
                assert kwargs.get("stderr") is None
                assert kwargs.get("bufsize") == 0
