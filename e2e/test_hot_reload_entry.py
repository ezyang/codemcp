#!/usr/bin/env python3

"""End-to-end tests for the hot_reload_entry module."""

import os
import unittest

import codemcp.main
from codemcp.testing import MCPEndToEndTestCase


class TestHotReloadEntry(MCPEndToEndTestCase):
    """End-to-end tests for the hot_reload_entry module.

    These tests verify that the hot_reload_entry module correctly forwards tool calls
    to the main module and properly handles the results.
    """

    async def test_hot_reload_mechanism(self):
        """Test that the hot reload mechanism properly forwards tool calls to the main module."""
        # Create a test file
        test_file_path = os.path.join(self.temp_dir.name, "test_file.txt")
        test_content = "Test content\nLine 2\nLine 3"
        with open(test_file_path, "w") as f:
            f.write(test_content)

        # Add the file to git to avoid permission issues
        await self.git_run(["add", test_file_path])

        # First call through the normal method for comparison
        chat_id = await self.get_chat_id(None)  # We don't need a session for this

        # Make the call directly to main.codemcp
        direct_result = await codemcp.main.codemcp(
            "ReadFile", path=test_file_path, chat_id=chat_id
        )

        # Now call through hot_reload_entry (simulating by directly importing it)
        from codemcp.hot_reload_entry import codemcp as hot_reload_codemcp

        hot_reload_result_raw = await hot_reload_codemcp(
            subtool="ReadFile", path=test_file_path, chat_id=chat_id
        )

        # Extract text content from result
        if isinstance(hot_reload_result_raw, list) and hasattr(
            hot_reload_result_raw[0], "text"
        ):
            hot_reload_result = hot_reload_result_raw[0].text
        else:
            hot_reload_result = str(hot_reload_result_raw)

        # Verify both results contain our file content
        for line in test_content.splitlines():
            self.assertIn(line, direct_result)
            self.assertIn(line, hot_reload_result)

    async def test_hot_reload_with_parameters(self):
        """Test that the hot reload mechanism properly passes parameters to the main module."""
        # Create a test file for our write/edit operations
        test_file_path = os.path.join(self.temp_dir.name, "params_test.txt")
        initial_content = "Initial content\nto be edited"
        with open(test_file_path, "w") as f:
            f.write(initial_content)

        # Add the file to git so we can write to it
        await self.git_run(["add", test_file_path])
        await self.git_run(["commit", "-m", "Add params test file"])

        # Get a valid chat_id
        chat_id = await self.get_chat_id(None)

        # Import the hot_reload_entry codemcp function
        from codemcp.hot_reload_entry import codemcp as hot_reload_codemcp

        # Test WriteFile with specific parameters
        new_content = "New content\nadded through hot reload"
        await hot_reload_codemcp(
            subtool="WriteFile",
            path=test_file_path,
            content=new_content,
            description="Write test through hot reload",
            chat_id=chat_id,
        )

        # Read the file to verify contents were written correctly
        with open(test_file_path, "r") as f:
            file_content = f.read()
        self.assertEqual(file_content, new_content + "\n")

    async def test_error_handling(self):
        """Test that errors from the main module are properly propagated through hot_reload_entry."""
        # Get a valid chat_id
        chat_id = await self.get_chat_id(None)

        # Import the hot_reload_entry codemcp function
        from codemcp.hot_reload_entry import codemcp as hot_reload_codemcp

        # Call ReadFile with a non-existent file to trigger an error
        non_existent_file = os.path.join(self.temp_dir.name, "does_not_exist.txt")

        # Make the call and capture the error message
        with self.assertRaisesRegex(RuntimeError, "does_not_exist.txt"):
            await hot_reload_codemcp(
                subtool="ReadFile", path=non_existent_file, chat_id=chat_id
            )

    async def test_subprocess_reuse(self):
        """Test that multiple tool calls work through the hot reload mechanism."""
        # Create a test file
        test_file_path = os.path.join(self.temp_dir.name, "multi_call_test.txt")
        test_content = "Test content\nLine 2\nLine 3"
        with open(test_file_path, "w") as f:
            f.write(test_content)

        # Add the file to git
        await self.git_run(["add", test_file_path])

        # Get a valid chat_id
        chat_id = await self.get_chat_id(None)

        # Import the hot_reload_entry codemcp function
        from codemcp.hot_reload_entry import codemcp as hot_reload_codemcp

        # Make multiple calls to verify the mechanism works consistently
        for i in range(3):
            result_raw = await hot_reload_codemcp(
                subtool="ReadFile", path=test_file_path, chat_id=chat_id
            )

            # Extract text content from result
            if isinstance(result_raw, list) and hasattr(result_raw[0], "text"):
                result = result_raw[0].text
            else:
                result = str(result_raw)

            # Verify the result includes our file content
            for line in test_content.splitlines():
                self.assertIn(line, result)


if __name__ == "__main__":
    unittest.main()
