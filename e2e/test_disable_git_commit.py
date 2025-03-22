#!/usr/bin/env python3

"""Tests for the disable_git_commit configuration option."""

import os
import sys
import unittest
import re

from codemcp import config
from codemcp.testing import MCPEndToEndTestCase


class DisableGitCommitTest(MCPEndToEndTestCase):
    """Test the disable_git_commit configuration option."""

    async def test_normal_commit_behavior(self):
        """Test the default behavior with disable_git_commit=False."""
        # Create a file to edit
        test_file_path = os.path.join(self.temp_dir.name, "normal_test.txt")
        initial_content = "Initial content for normal commit test"

        # Create the file
        with open(test_file_path, "w") as f:
            f.write(initial_content)

        # Add it to git
        await self.git_run(["add", test_file_path])
        await self.git_run(["commit", "-m", "Add file for normal commit test"])

        async with self.create_client_session() as session:
            # Initialize the project to get a chat_id
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for normal commit test",
                    "subject_line": "test: initialize for normal commit test",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract chat_id from the init result
            chat_id = self.extract_chat_id_from_text(init_result_text)

            # Make an edit with normal behavior (disable_git_commit=False)
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "EditFile",
                    "path": test_file_path,
                    "old_string": "Initial content for normal commit test",
                    "new_string": "Modified content for normal commit test",
                    "description": "Normal commit edit",
                    "chat_id": chat_id,
                },
            )

            # Verify that the HEAD commit contains our changes
            file_content = await self.git_run(
                ["show", "HEAD:normal_test.txt"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                file_content,
                "Modified content for normal commit test",
                "HEAD should contain the modified content",
            )

            # Verify the commit message doesn't mention "without updating working tree"
            self.assertNotIn("without updating working tree", result_text)

            # Verify the file content matches the expected content
            with open(test_file_path, "r") as f:
                actual_content = f.read()
            self.assertEqual(
                actual_content,
                "Modified content for normal commit test",
                "File content should match the edit",
            )

    async def test_disable_git_commit_behavior(self):
        """Test behavior with disable_git_commit=True."""
        # Create a file to edit
        test_file_path = os.path.join(self.temp_dir.name, "disabled_test.txt")
        initial_content = "Initial content for disabled commit test"

        # Create the file
        with open(test_file_path, "w") as f:
            f.write(initial_content)

        # Add it to git
        await self.git_run(["add", test_file_path])
        await self.git_run(["commit", "-m", "Add file for disabled commit test"])

        # First, do InitProject with normal configuration
        async with self.create_client_session() as session:
            # Initialize the project to get a chat_id
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for disabled commit test",
                    "subject_line": "test: initialize for disabled commit test",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract chat_id from the init result
            chat_id = self.extract_chat_id_from_text(init_result_text)

            # Get the initial HEAD commit hash after initialization
            initial_head = await self.git_run(
                ["rev-parse", "HEAD"], capture_output=True, text=True
            )

            # Now enable disable_git_commit
            original_value = config.DEFAULT_CONFIG["git"]["disable_git_commit"]
            config.DEFAULT_CONFIG["git"]["disable_git_commit"] = True

            try:
                # Make an edit with disable_git_commit=True
                result_text = await self.call_tool_assert_success(
                    session,
                    "codemcp",
                    {
                        "subtool": "EditFile",
                        "path": test_file_path,
                        "old_string": "Initial content for disabled commit test",
                        "new_string": "Modified content for disabled commit test",
                        "description": "Disabled commit edit",
                        "chat_id": chat_id,
                    },
                )

                # Verify that the commit message mentions "without updating working tree"
                self.assertIn("without updating working tree", result_text)

                # Get the current HEAD commit hash
                current_head = await self.git_run(
                    ["rev-parse", "HEAD"], capture_output=True, text=True
                )

                # Verify that HEAD hasn't changed
                self.assertEqual(
                    initial_head,
                    current_head,
                    "HEAD should not have changed when disable_git_commit=True",
                )

                # Verify that the ref for this chat_id exists and contains a new commit
                ref_name = f"refs/codemcp/{chat_id}"
                ref_exists = await self.git_run(
                    ["show-ref", "--verify", ref_name],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(
                    ref_exists, "", "A reference should be created for the chat_id"
                )

                # Extract the commit hash from the reference
                ref_commit = await self.git_run(
                    ["rev-parse", ref_name], capture_output=True, text=True
                )

                # Verify that the virtual-head reference exists and points to the same commit
                virtual_head_ref = "refs/codemcp/virtual-head"
                virtual_head_exists = await self.git_run(
                    ["show-ref", "--verify", virtual_head_ref],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(
                    virtual_head_exists, "", "Virtual HEAD reference should be created"
                )

                # Get the virtual-head commit hash
                virtual_head_commit = await self.git_run(
                    ["rev-parse", virtual_head_ref], capture_output=True, text=True
                )

                # Verify that virtual-head and the chat-id reference point to the same commit
                self.assertEqual(
                    ref_commit,
                    virtual_head_commit,
                    "Virtual HEAD should point to the same commit as the chat_id reference",
                )

                # Verify that the file content in the reference commit matches the edit
                ref_file_content = await self.git_run(
                    ["show", f"{ref_commit}:disabled_test.txt"],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(
                    ref_file_content,
                    "Modified content for disabled commit test",
                    "Reference commit should contain the modified content",
                )

                # Check the file content in the working tree matches the edit
                with open(test_file_path, "r") as f:
                    actual_content = f.read()
                self.assertEqual(
                    actual_content,
                    "Modified content for disabled commit test",
                    "File content should match the edit",
                )
            finally:
                # Restore the original config value
                config.DEFAULT_CONFIG["git"]["disable_git_commit"] = original_value

    async def test_subsequent_edits_with_disable_git_commit(self):
        """Test that subsequent edits with disable_git_commit=True update the reference correctly."""
        # Create a file to edit
        test_file_path = os.path.join(self.temp_dir.name, "subsequent_test.txt")
        initial_content = "Initial content for subsequent edits test"

        # Create the file
        with open(test_file_path, "w") as f:
            f.write(initial_content)

        # Add it to git
        await self.git_run(["add", test_file_path])
        await self.git_run(["commit", "-m", "Add file for subsequent edits test"])

        # First, do InitProject with normal configuration
        async with self.create_client_session() as session:
            # Initialize the project to get a chat_id
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for subsequent edits test",
                    "subject_line": "test: initialize for subsequent edits test",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract chat_id from the init result
            chat_id = self.extract_chat_id_from_text(init_result_text)

            # Get the initial HEAD commit hash after initialization
            initial_head = await self.git_run(
                ["rev-parse", "HEAD"], capture_output=True, text=True
            )

            # Now enable disable_git_commit
            original_value = config.DEFAULT_CONFIG["git"]["disable_git_commit"]
            config.DEFAULT_CONFIG["git"]["disable_git_commit"] = True

            try:
                # First edit with disable_git_commit=True
                result1_text = await self.call_tool_assert_success(
                    session,
                    "codemcp",
                    {
                        "subtool": "EditFile",
                        "path": test_file_path,
                        "old_string": "Initial content for subsequent edits test",
                        "new_string": "First edit for subsequent edits test",
                        "description": "First disabled commit edit",
                        "chat_id": chat_id,
                    },
                )

                # Get the first reference commit
                ref_name = f"refs/codemcp/{chat_id}"
                first_ref_commit = await self.git_run(
                    ["rev-parse", ref_name], capture_output=True, text=True
                )

                # Get the first virtual-head commit
                virtual_head_ref = "refs/codemcp/virtual-head"
                first_virtual_head_commit = await self.git_run(
                    ["rev-parse", virtual_head_ref], capture_output=True, text=True
                )

                # Verify that virtual-head and the reference point to the same commit
                self.assertEqual(
                    first_ref_commit,
                    first_virtual_head_commit,
                    "Virtual HEAD should point to the same commit as the chat_id reference after first edit",
                )

                # Second edit with the same chat_id
                result2_text = await self.call_tool_assert_success(
                    session,
                    "codemcp",
                    {
                        "subtool": "EditFile",
                        "path": test_file_path,
                        "old_string": "First edit for subsequent edits test",
                        "new_string": "Second edit for subsequent edits test",
                        "description": "Second disabled commit edit",
                        "chat_id": chat_id,
                    },
                )

                # Verify that HEAD still hasn't changed
                current_head = await self.git_run(
                    ["rev-parse", "HEAD"], capture_output=True, text=True
                )
                self.assertEqual(
                    initial_head,
                    current_head,
                    "HEAD should not have changed after second edit",
                )

                # Get the updated reference commit
                second_ref_commit = await self.git_run(
                    ["rev-parse", ref_name], capture_output=True, text=True
                )

                # Get the updated virtual-head commit
                second_virtual_head_commit = await self.git_run(
                    ["rev-parse", virtual_head_ref], capture_output=True, text=True
                )

                # Verify that virtual-head and the reference point to the same commit
                self.assertEqual(
                    second_ref_commit,
                    second_virtual_head_commit,
                    "Virtual HEAD should point to the same commit as the chat_id reference after second edit",
                )

                # Verify that the reference has been updated to a new commit
                self.assertNotEqual(
                    first_ref_commit,
                    second_ref_commit,
                    "Reference should point to a new commit after second edit",
                )

                # Verify that virtual-head has been updated to a new commit
                self.assertNotEqual(
                    first_virtual_head_commit,
                    second_virtual_head_commit,
                    "Virtual HEAD should point to a new commit after second edit",
                )

                # Check the file content matches the second edit
                with open(test_file_path, "r") as f:
                    actual_content = f.read()
                self.assertEqual(
                    actual_content,
                    "Second edit for subsequent edits test",
                    "File content should match the second edit",
                )
            finally:
                # Restore the original config value
                config.DEFAULT_CONFIG["git"]["disable_git_commit"] = original_value


if __name__ == "__main__":
    unittest.main()
