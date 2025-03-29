#!/usr/bin/env python3

"""Tests for the WriteFile subtool."""

import os
import unittest

from codemcp.testing import MCPEndToEndTestCase


class WriteFileTest(MCPEndToEndTestCase):
    """Test the WriteFile subtool."""

    async def test_write_file(self):
        """Test the WriteFile subtool, which writes to a file and automatically commits the changes."""
        test_file_path = os.path.join(self.temp_dir.name, "new_file.txt")
        content = "New content\nLine 2"

        # First add the file to git to make it tracked
        with open(test_file_path, "w") as f:
            f.write("")

        # Add it to git
        await self.git_run(["add", test_file_path])

        # Commit it
        await self.git_run(["commit", "-m", "Add empty file for WriteFile test"])

        async with self.create_client_session() as session:
            # First initialize project to get chat_id
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for write_file test",
                    "subject_line": "test: initialize for write file test",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract chat_id from the init result
            chat_id = self.extract_chat_id_from_text(init_result_text)

            # Call the WriteFile tool with chat_id using our new helper method
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "WriteFile",
                    "path": test_file_path,
                    "content": content,
                    "description": "Create new file",
                    "chat_id": chat_id,
                },
            )

            # Verify the success message
            self.assertIn("Successfully wrote to", result_text)

            # Verify the file was created with the correct content
            with open(test_file_path) as f:
                file_content = f.read()
            self.assertEqual(file_content, content)

            # Verify git state (working tree should be clean after automatic commit)
            status = await self.git_run(["status"], capture_output=True, text=True)

            # Use expect test to verify git status - should show clean working tree
            self.assertExpectedInline(
                status,
                """\
On branch main
nothing to commit, working tree clean""",
            )

            # Get the commit message of the HEAD commit
            commit_message = await self.git_run(
                ["log", "-1", "--pretty=%B"], capture_output=True, text=True
            )

            # Normalize the chat_id in the commit message for expect test
            normalized_commit_message = commit_message.replace(chat_id, "test-chat-id")

            # Use expect test to verify the commit message format
            self.assertExpectedInline(
                normalized_commit_message,
                """\
test: initialize for write file test

Test initialization for write_file test

```git-revs
c9bcf9c  (Base revision)
HEAD     Create new file
```

codemcp-id: test-chat-id""",
            )

            # Second write to the same file
            updated_content = content + "\nAdded third line"

            # Call the WriteFile tool again with updated content
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "WriteFile",
                    "path": test_file_path,
                    "content": updated_content,
                    "description": "Update file with third line",
                    "chat_id": chat_id,
                },
            )

            # Verify the success message for second write
            self.assertIn("Successfully wrote to", result_text)

            # Verify the file was updated with the correct content
            with open(test_file_path) as f:
                file_content = f.read()
            self.assertEqual(file_content, updated_content)

            # Verify git state after second write
            status = await self.git_run(["status"], capture_output=True, text=True)

            # Use expect test to verify git status - should still show clean working tree
            self.assertExpectedInline(
                status,
                """\
On branch main
nothing to commit, working tree clean""",
            )

            # Get the commit message of the HEAD commit after second write
            commit_message = await self.git_run(
                ["log", "-1", "--pretty=%B"], capture_output=True, text=True
            )

            # Normalize the chat_id in the commit message for expect test
            normalized_commit_message = commit_message.replace(chat_id, "test-chat-id")

            # Use expect test to verify the commit message format for second write
            self.assertExpectedInline(
                normalized_commit_message,
                """\
test: initialize for write file test

Test initialization for write_file test

```git-revs
c9bcf9c  (Base revision)
a0816d8  Create new file
HEAD     Update file with third line
```

codemcp-id: test-chat-id""",
            )

    async def test_create_new_file_with_write_file(self):
        """Test creating a new file that doesn't exist yet with WriteFile."""
        # Path to a new file that doesn't exist yet, within the git repository
        new_file_path = os.path.join(self.temp_dir.name, "completely_new_file.txt")

        self.assertFalse(
            os.path.exists(new_file_path),
            "Test file should not exist initially",
        )

        async with self.create_client_session() as session:
            # First initialize project to get chat_id
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for creating new file",
                    "subject_line": "test: initialize for new file test",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract chat_id from the init result
            chat_id = self.extract_chat_id_from_text(init_result_text)

            # Create a new file using our helper method
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "WriteFile",
                    "path": new_file_path,
                    "content": "This is a brand new file",
                    "description": "Create a new file with WriteFile",
                    "chat_id": chat_id,
                },
            )

            # Check that the operation succeeded
            self.assertIn("Successfully wrote to", result_text)

            # Verify the file was created
            self.assertTrue(
                os.path.exists(new_file_path),
                "File was not created even though operation reported success",
            )

            # Check content
            with open(new_file_path) as f:
                content = f.read()
            self.assertEqual(content, "This is a brand new file")

            # Verify the file was added to git
            ls_files_output = await self.git_run(
                ["ls-files", new_file_path], capture_output=True, text=True
            )

            # The new file should be tracked in git
            self.assertTrue(
                ls_files_output,
                "New file was created but not added to git",
            )

    async def test_write_to_untracked_file(self):
        """Test that writes to untracked files are rejected."""
        # Create an untracked file (not added to git)
        untracked_file_path = os.path.join(
            self.temp_dir.name,
            "untracked_for_write.txt",
        )
        with open(untracked_file_path, "w") as f:
            f.write("Initial content in untracked file")

        # Verify the file exists but is not tracked by git
        file_exists = os.path.exists(untracked_file_path)
        self.assertTrue(file_exists, "Test file should exist on filesystem")

        # Check that the file is untracked
        ls_files_output = await self.git_run(
            ["ls-files", untracked_file_path], capture_output=True, text=True
        )

        self.assertEqual(ls_files_output, "", "File should not be tracked by git")

        # Save original content and modification time for comparison
        with open(untracked_file_path) as f:
            original_content = f.read()
        original_mtime = os.path.getmtime(untracked_file_path)

        async with self.create_client_session() as session:
            # First initialize project to get chat_id
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for untracked file test",
                    "subject_line": "test: initialize for untracked file test",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract chat_id from the init result
            chat_id = self.extract_chat_id_from_text(init_result_text)

            # Try to write to the untracked file
            new_content = "This content should not be written to untracked file"
            result_text = await self.call_tool_assert_error(
                session,
                "codemcp",
                {
                    "subtool": "WriteFile",
                    "path": untracked_file_path,
                    "content": new_content,
                    "description": "Attempt to write to untracked file",
                    "chat_id": chat_id,
                },
            )

            self.assertExpectedInline(
                result_text,
                """Error executing tool codemcp: File is not tracked by git. Please add the file to git tracking first using 'git add <file>'""",
            )

            # Verify the file content has not changed
            with open(untracked_file_path) as f:
                actual_content = f.read()

            self.assertEqual(
                original_content,
                actual_content,
                "File content should not change when operation is rejected",
            )

            # Verify file modification time was not changed
            current_mtime = os.path.getmtime(untracked_file_path)
            self.assertEqual(
                current_mtime,
                original_mtime,
                "File modification time should not have changed",
            )

    async def test_write_file_outside_tracked_paths(self):
        """Test that codemcp properly handles writing to paths outside tracked paths."""
        # Create a subdirectory but don't add it to git
        subdir_path = os.path.join(self.temp_dir.name, "untrackeddir")
        os.makedirs(subdir_path, exist_ok=True)

        new_file_path = os.path.join(subdir_path, "newfile.txt")

        async with self.create_client_session() as session:
            # First initialize project to get chat_id
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for untracked directory test",
                    "subject_line": "test: initialize for untracked directory test",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract chat_id from the init result
            chat_id = self.extract_chat_id_from_text(init_result_text)

            # Try to write a new file in the untracked directory
            await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "WriteFile",
                    "path": new_file_path,
                    "content": "New file in untracked directory",
                    "description": "Attempt to create file in untracked directory",
                    "chat_id": chat_id,
                },
            )

            # Since we're using call_tool_assert_success, we know the operation succeeded
            # Check if the directory and file are now tracked in git
            await self.git_run(["status"], capture_output=True, text=True)

            # The file should exist
            self.assertTrue(
                os.path.exists(new_file_path),
                "File was not created even though operation reported success",
            )

            # SECURITY CHECK: If writing to untracked directories succeeds,
            # both the directory and file should be tracked in git
            ls_files_output = await self.git_run(
                ["ls-files", new_file_path], capture_output=True, text=True
            )

            # IMPORTANT: The file should be tracked in git after writing
            self.assertTrue(
                ls_files_output,
                "SECURITY VULNERABILITY: Successfully wrote to untracked directory"
                " but did not add file to git",
            )

    async def test_write_file_with_tilde_path(self):
        """Test that WriteFile correctly handles paths with tilde (~) expansion."""
        # We'll create a file in a subdirectory of the temp_dir and then refer to it with tilde
        # First, get the user's home directory
        home_dir = os.path.expanduser("~")

        # Check if temp_dir is in the home directory for the tilde test to work
        temp_dir_abs = os.path.abspath(self.temp_dir.name)
        if not temp_dir_abs.startswith(home_dir):
            self.skipTest(
                "Test requires temp_dir to be within the user's home directory"
            )

        # Create a relative path using tilde
        rel_path = os.path.relpath(temp_dir_abs, home_dir)
        tilde_path = os.path.join("~", rel_path, "tilde_test_file.txt")

        # Expected absolute path after tilde expansion
        expected_abs_path = os.path.expanduser(tilde_path)
        self.assertEqual(
            os.path.abspath(expected_abs_path), temp_dir_abs + "/tilde_test_file.txt"
        )

        # Content to write
        content = "This file was created with a tilde path"

        async with self.create_client_session() as session:
            # First initialize project to get chat_id
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for tilde path test",
                    "subject_line": "test: initialize for tilde path test",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract chat_id from the init result
            chat_id = self.extract_chat_id_from_text(init_result_text)

            # Call the WriteFile tool with the tilde path
            await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "WriteFile",
                    "path": tilde_path,
                    "content": content,
                    "description": "Create file using tilde path",
                    "chat_id": chat_id,
                },
            )

            # Verify the file was created
            self.assertTrue(
                os.path.exists(expected_abs_path),
                "File should exist after writing with tilde path",
            )

            # Verify content
            with open(expected_abs_path) as f:
                actual_content = f.read()
            self.assertEqual(actual_content, content)

            # Verify the file was added to git
            ls_files_output = await self.git_run(
                ["ls-files", expected_abs_path], capture_output=True, text=True
            )

            # The file should be tracked in git
            self.assertTrue(
                ls_files_output,
                "New file created with tilde path should be tracked in git",
            )

    async def test_user_prompt_with_markdown_code_block(self):
        """Test handling of user prompt that contains a Markdown code block with triple backticks."""
        test_file_path = os.path.join(
            self.temp_dir.name, "markdown_code_block_test.txt"
        )
        content = "File created from a prompt with a code block"

        # Create placeholder file and add to git
        with open(test_file_path, "w") as f:
            f.write("")

        # Add it to git
        await self.git_run(["add", test_file_path])

        # Commit it
        await self.git_run(
            ["commit", "-m", "Add empty file for markdown code block test"]
        )

        # User prompt with Markdown code block
        user_prompt_with_code_block = """Please create a file with this Python code:

```
---
description: Description of when the rule is useful for the LLM
globs: *.js,*.ts
alwaysApply: false
---
Markdown to send to LLM
```

And make sure it runs correctly."""

        async with self.create_client_session() as session:
            # Initialize project to get chat_id
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": user_prompt_with_code_block,
                    "subject_line": "test: user prompt with markdown code block",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract chat_id from the init result
            chat_id = self.extract_chat_id_from_text(init_result_text)

            # Call the WriteFile tool with chat_id
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "WriteFile",
                    "path": test_file_path,
                    "content": content,
                    "description": "Write file from prompt with code block",
                    "chat_id": chat_id,
                },
            )

            # Verify the success message
            self.assertIn("Successfully wrote to", result_text)

            # Verify the file was created with the correct content
            with open(test_file_path) as f:
                file_content = f.read()
            self.assertEqual(file_content, content)

            # Get the commit message of the HEAD commit
            commit_message = await self.git_run(
                ["log", "-1", "--pretty=%B"], capture_output=True, text=True
            )

            # Normalize the chat_id in the commit message for expect test
            normalized_commit_message = commit_message.replace(chat_id, "test-chat-id")

            # Verify that the commit message contains the code block with triple backticks
            self.assertExpectedInline(
                normalized_commit_message,
                """\
test: user prompt with markdown code block

Please create a file with this Python code:

```
---
description: Description of when the rule is useful for the LLM
globs: *.js,*.ts
alwaysApply: false
---
Markdown to send to LLM
```

And make sure it runs correctly.

```git-revs
6350984  (Base revision)
HEAD     Write file from prompt with code block
```

codemcp-id: test-chat-id""",
            )

            # Now do a second write operation with the same chat_id
            updated_content = content + "\nSecond write with code block in user_prompt"

            # Call the WriteFile tool again with updated content
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "WriteFile",
                    "path": test_file_path,
                    "content": updated_content,
                    "description": "Update file with second write",
                    "chat_id": chat_id,
                },
            )

            # Verify the success message
            self.assertIn("Successfully wrote to", result_text)

            # Verify the file was updated with the correct content
            with open(test_file_path) as f:
                file_content = f.read()
            self.assertEqual(file_content, updated_content)

            # Get the commit message after second write
            commit_message = await self.git_run(
                ["log", "-1", "--pretty=%B"], capture_output=True, text=True
            )

            # Normalize the chat_id for expect test
            normalized_commit_message = commit_message.replace(chat_id, "test-chat-id")

            # Verify that the commit message still contains the code block with triple backticks
            self.assertExpectedInline(
                normalized_commit_message,
                """\
test: user prompt with markdown code block

Please create a file with this Python code:

```
---
description: Description of when the rule is useful for the LLM
globs: *.js,*.ts
alwaysApply: false
---
Markdown to send to LLM
```

And make sure it runs correctly.

```git-revs
6350984  (Base revision)
9071fd5  Write file from prompt with code block
HEAD     Update file with second write
```

codemcp-id: test-chat-id""",
            )


class OutOfProcessWriteFileTest(WriteFileTest):
    in_process = False


if __name__ == "__main__":
    unittest.main()
