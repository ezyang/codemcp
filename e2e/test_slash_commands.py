#!/usr/bin/env python3

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codemcp.tools.user_prompt import user_prompt


@pytest.fixture
def mock_commands_dir() -> Path:
    """Create a temporary directory with test command files."""
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()

    # Create the commands directory
    commands_dir = Path(temp_dir) / ".claude" / "commands"
    os.makedirs(commands_dir, exist_ok=True)

    # Create test command files
    test_cmd = commands_dir / "test-command.md"
    with open(test_cmd, "w") as f:
        f.write("# Test Command\nThis is a test command content.")

    help_cmd = commands_dir / "help.md"
    with open(help_cmd, "w") as f:
        f.write(
            "# Available Commands\n- `/user:test-command`: A test command\n- `/user:help`: This help message"
        )

    return commands_dir


def test_slash_command_e2e(mock_commands_dir: Path) -> None:
    """Test slash commands in an end-to-end scenario."""
    # Save original home
    original_home = Path.home

    try:
        # Mock Path.home to use our temp directory
        Path.home = MagicMock(return_value=mock_commands_dir.parent.parent)

        # Mock async_open_text to read the actual files
        with patch("codemcp.file_utils.async_open_text") as mock_open:
            # Set up different return values based on which file is being read
            def side_effect(file_path, **kwargs):
                if "test-command.md" in file_path:
                    return "# Test Command\nThis is a test command content."
                elif "help.md" in file_path:
                    return "# Available Commands\n- `/user:test-command`: A test command\n- `/user:help`: This help message"
                else:
                    raise FileNotFoundError(f"File not found: {file_path}")

            mock_open.side_effect = side_effect

            # Test a valid slash command
            result = asyncio.run(user_prompt("/user:test-command", "test-chat-id"))
            assert "# Test Command" in result
            assert "This is a test command content." in result

            # Test the help command
            result = asyncio.run(user_prompt("/user:help", "test-chat-id"))
            assert "# Available Commands" in result
            assert "`/user:test-command`" in result
            assert "`/user:help`" in result

            # Test an invalid slash command
            result = asyncio.run(user_prompt("/user:invalid-command", "test-chat-id"))
            assert "Unknown slash command: invalid-command" in result

            # Test a non-slash command
            with patch("codemcp.tools.user_prompt.find_git_root", return_value=None):
                result = asyncio.run(user_prompt("normal message", "test-chat-id"))
                assert "User prompt received" in result
    finally:
        # Restore original home
        Path.home = original_home

        # Clean up the temporary directory
        import shutil

        shutil.rmtree(mock_commands_dir.parent.parent)
