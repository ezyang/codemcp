#!/usr/bin/env python3

"""End-to-end tests for the ChmodExec tool."""

import os
import stat
import unittest

from codemcp.testing import MCPEndToEndTestCase


class ChmodExecTest(MCPEndToEndTestCase):
    """Test the ChmodExec subtool functionality."""

    async def test_chmod_exec_file(self):
        """Test making a file executable using the ChmodExec subtool."""
        # Create a test file
        test_file_path = os.path.join(self.temp_dir.name, "file_to_chmod.sh")
        with open(test_file_path, "w") as f:
            f.write("#!/bin/sh\necho 'Hello World'")

        # Add the file using git
        await self.git_run(["add", "file_to_chmod.sh"])
        await self.git_run(["commit", "-m", "Add file that will be made executable"])

        # Check initial permissions (should not be executable)
        initial_mode = os.stat(test_file_path).st_mode
        initial_executable = bool(initial_mode & stat.S_IXUSR)

        # Initial count of commits
        initial_log = await self.git_run(
            ["log", "--oneline"], capture_output=True, text=True
        )
        initial_commit_count = len(initial_log.strip().split("\n"))

        async with self.create_client_session() as session:
            # Get a valid chat_id
            chat_id = await self.get_chat_id(session)

            # For debugging, print some path information
            print(f"DEBUG - Test file path: {test_file_path}")
            # Check if file is executable before
            print(f"DEBUG - File is executable before: {initial_executable}")

            # Call the ChmodExec tool with the chat_id - use absolute path
            result = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "ChmodExec",
                    "path": test_file_path,  # Use absolute path
                    "description": "Make shell script executable",
                    "chat_id": chat_id,
                },
            )

            # Print the result for debugging
            print(f"DEBUG - ChmodExec result: {result}")

            # Check that the file is now executable
            final_mode = os.stat(test_file_path).st_mode
            final_executable = bool(final_mode & stat.S_IXUSR)
            print(f"DEBUG - File is executable after: {final_executable}")

            self.assertTrue(final_executable, "File should have been made executable")

            # Verify the output message indicates success
            self.assertIn("Successfully made", result)
            self.assertIn("executable", result)

            # Verify a commit was created for the change
            final_log = await self.git_run(
                ["log", "--oneline"], capture_output=True, text=True
            )
            final_commit_count = len(final_log.strip().split("\n"))
            self.assertEqual(
                final_commit_count,
                initial_commit_count + 1,
                "Should have one more commit",
            )

            # Verify the commit message contains the description
            latest_commit_msg = await self.git_run(
                ["log", "-1", "--pretty=%B"], capture_output=True, text=True
            )
            self.assertIn("Make file_to_chmod.sh executable", latest_commit_msg)
            self.assertIn("Make shell script executable", latest_commit_msg)

    async def test_chmod_exec_file_does_not_exist(self):
        """Test attempting to make a non-existent file executable."""
        async with self.create_client_session() as session:
            # Get a valid chat_id
            chat_id = await self.get_chat_id(session)

            # Attempt to chmod a file that doesn't exist - should fail
            result = await self.call_tool_assert_error(
                session,
                "codemcp",
                {
                    "subtool": "ChmodExec",
                    "path": "non_existent_file.sh",
                    "description": "Make non-existent file executable",
                    "chat_id": chat_id,
                },
            )

            # Verify the operation failed with proper error message
            self.assertIn("File does not exist", result)

    async def test_chmod_exec_directory(self):
        """Test attempting to make a directory executable."""
        # Create a test directory
        test_dir_path = os.path.join(self.temp_dir.name, "test_directory")
        os.makedirs(test_dir_path, exist_ok=True)

        async with self.create_client_session() as session:
            # Get a valid chat_id
            chat_id = await self.get_chat_id(session)

            # Attempt to chmod a directory - should fail
            result = await self.call_tool_assert_error(
                session,
                "codemcp",
                {
                    "subtool": "ChmodExec",
                    "path": test_dir_path,
                    "description": "Make directory executable",
                    "chat_id": chat_id,
                },
            )

            # Verify the operation failed with proper error message
            self.assertIn("is a directory", result.lower())


if __name__ == "__main__":
    unittest.main()
