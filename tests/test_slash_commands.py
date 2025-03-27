#!/usr/bin/env python3

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from codemcp.tools.user_prompt import is_slash_command, resolve_slash_command


def test_is_slash_command():
    """Test the is_slash_command function."""
    # Test valid slash commands
    assert is_slash_command("/command") is True
    assert is_slash_command("  /command  ") is True
    assert is_slash_command("/user:command-name") is True

    # Test invalid cases
    assert is_slash_command("command") is False
    assert is_slash_command("") is False
    assert is_slash_command(None) is False
    assert is_slash_command("  command  ") is False


def test_resolve_slash_command():
    """Test the resolve_slash_command function."""
    # Valid command format but non-existent file
    with patch("os.makedirs"), patch("pathlib.Path.exists", return_value=False):
        success, command_name, file_path = resolve_slash_command("/user:test-command")
        assert success is False
        assert command_name == "test-command"
        assert file_path is None

    # Valid command format with existing file
    with (
        patch("os.makedirs"),
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "pathlib.Path.__truediv__",
            return_value=Path("/home/user/.claude/commands/test-command.md"),
        ),
    ):
        success, command_name, file_path = resolve_slash_command("/user:test-command")
        assert success is True
        assert command_name == "test-command"
        assert file_path == "/home/user/.claude/commands/test-command.md"

    # Invalid command format (missing user: prefix)
    success, command_name, file_path = resolve_slash_command("/test-command")
    assert success is False
    assert command_name == "test-command"
    assert file_path is None

    # Invalid command format (invalid characters)
    success, command_name, file_path = resolve_slash_command("/user:test@command")
    assert success is False
    assert command_name == "user:test@command"
    assert file_path is None


def test_get_command_content():
    """Test the get_command_content function."""
    from codemcp.tools.user_prompt import get_command_content

    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".md") as temp_file:
        temp_file.write("# Test Command\nThis is a test command content.")
        temp_file.flush()

        # Mock file_utils.async_open_text to return our test content
        with patch("codemcp.file_utils.async_open_text") as mock_open:
            # Set up the mock to return our content
            mock_open.return_value = "# Test Command\nThis is a test command content."

            # Run the coroutine in the event loop
            result = asyncio.run(get_command_content(temp_file.name))

            # Verify the result
            assert "# Test Command" in result
            assert "This is a test command content." in result

        # Test error handling
        with patch(
            "codemcp.file_utils.async_open_text", side_effect=Exception("Test error")
        ):
            # Run the coroutine in the event loop
            result = asyncio.run(get_command_content("non-existent-file"))

            # Verify error handling
            assert "Error reading command file" in result
            assert "Test error" in result


def test_user_prompt_with_slash_command():
    """Test the user_prompt function with slash commands."""
    from codemcp.tools.user_prompt import user_prompt

    # Create a temporary directory and markdown file for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Mock Path.home() to return our temporary directory
        original_home = Path.home
        Path.home = MagicMock(return_value=Path(temp_dir))

        try:
            # Create the .claude/commands directory
            commands_dir = Path(temp_dir) / ".claude" / "commands"
            os.makedirs(commands_dir, exist_ok=True)

            # Create a test command file
            command_file = commands_dir / "test-command.md"
            with open(command_file, "w") as f:
                f.write("# Test Command\nThis is a test command content.")

            # Mock file_utils.async_open_text to return our test content
            with patch("codemcp.file_utils.async_open_text") as mock_open:
                mock_open.return_value = (
                    "# Test Command\nThis is a test command content."
                )

                # Test with a valid slash command
                result = asyncio.run(user_prompt("/user:test-command", "test-chat-id"))
                assert "# Test Command" in result
                assert "This is a test command content." in result

                # Test with an invalid slash command
                result = asyncio.run(user_prompt("/user:non-existent", "test-chat-id"))
                assert "Unknown slash command: non-existent" in result

                # Test with a non-slash command
                with patch(
                    "codemcp.tools.user_prompt.find_git_root", return_value=None
                ):
                    result = asyncio.run(user_prompt("regular command", "test-chat-id"))
                    assert "User prompt received" in result
        finally:
            # Restore original Path.home
            Path.home = original_home
