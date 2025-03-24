#!/usr/bin/env python3

"""Tests for the WriteFile subtool."""

import json
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

    async def test_write_non_string_content(self):
        """Test that WriteFile correctly serializes non-string content using json.dumps."""
        test_file_path = os.path.join(self.temp_dir.name, "non_string_content.json")

        # Create a complex data structure with different types
        content = {
            "name": "Test Data",
            "values": [1, 2, 3, 4, 5],
            "nested": {"boolean": True, "null_value": None, "number": 42.5},
        }

        # First add the file to git to make it tracked
        with open(test_file_path, "w") as f:
            f.write("")

        # Add it to git
        await self.git_run(["add", test_file_path])

        # Commit it
        await self.git_run(
            ["commit", "-m", "Add empty file for non-string content test"]
        )

        async with self.create_client_session() as session:
            # First initialize project to get chat_id
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for non-string content test",
                    "subject_line": "test: initialize for non-string content test",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract chat_id from the init result
            chat_id = self.extract_chat_id_from_text(init_result_text)

            # Call the WriteFile tool with non-string content
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "WriteFile",
                    "path": test_file_path,
                    "content": content,  # This is a dictionary, not a string
                    "description": "Create file with non-string content",
                    "chat_id": chat_id,
                },
            )

            # Verify the success message
            self.assertIn("Successfully wrote to", result_text)

            # Verify the file was created with the correct content (serialized as JSON)
            with open(test_file_path) as f:
                file_content = f.read()

            # Parse the JSON content and compare with the original dictionary
            parsed_content = json.loads(file_content)
            self.assertEqual(parsed_content, content)

            # Verify that the content was written as a properly formatted JSON string
            expected_json = json.dumps(content)
            self.assertEqual(file_content, expected_json)

            # Verify git state (working tree should be clean after automatic commit)
            status = await self.git_run(["status"], capture_output=True, text=True)
            self.assertIn("working tree clean", status)

    async def test_stdio_client_non_string_content(self):
        """True E2E test that goes through stdio_client to test non-string content serialization."""
        import re

        test_file_path = os.path.join(
            self.temp_dir.name, "stdio_non_string_content.json"
        )

        # Create a complex data structure with different types including nested structures
        content = {
            "name": "StdIO Test Data",
            "values": [1, 2, 3, 4, 5],
            "nested": {
                "boolean": True,
                "null_value": None,
                "number": 42.5,
                "array": ["a", "b", "c"],
                "deep_nested": {"key1": "value1", "key2": 123, "key3": False},
            },
            "types": [
                {"type": "int", "example": 1},
                {"type": "float", "example": 3.14},
                {"type": "string", "example": "hello"},
                {"type": "boolean", "example": False},
            ],
        }

        # First add the file to git to make it tracked
        with open(test_file_path, "w") as f:
            f.write("")

        # Add it to git
        await self.git_run(["add", test_file_path])

        # Commit it
        await self.git_run(
            ["commit", "-m", "Add empty file for stdio non-string content test"]
        )

        # Create a client session that goes through the stdio client
        async with self.create_client_session() as session:
            # First initialize project to get chat_id using the real session
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for stdio non-string content test",
                    "subject_line": "test: initialize for stdio test",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract chat_id from the result
            if isinstance(init_result_text, list) and len(init_result_text) > 0 and hasattr(init_result_text[0], "text"):
                init_result_text = init_result_text[0].text
            
            chat_id_match = re.search(r"chat ID: ([a-zA-Z0-9-]+)", init_result_text)
            self.assertIsNotNone(chat_id_match, "Could not find chat ID in response")
            chat_id = chat_id_match.group(1)

            # Call the WriteFile tool through the session with non-string content
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "WriteFile",
                    "path": test_file_path,
                    "content": content,  # This is a complex dictionary, not a string
                    "description": "Create file with non-string content via stdio",
                    "chat_id": chat_id,
                },
            )

            # Verify the success message
            self.assertIn("Successfully wrote to", result_text)

            # Verify the file was created with the correct content (serialized as JSON)
            with open(test_file_path) as f:
                file_content = f.read()

            # Parse the JSON content and compare with the original dictionary
            parsed_content = json.loads(file_content)
            self.assertEqual(parsed_content, content)

            # Verify that complex nested structures were preserved
            self.assertEqual(parsed_content["nested"]["deep_nested"]["key2"], 123)
            self.assertEqual(parsed_content["types"][1]["example"], 3.14)

            # Read the file back using ReadFile to verify it works with the client session
            read_content = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "ReadFile",
                    "path": test_file_path,
                    "chat_id": chat_id,
                },
            )

            # We already have read_content directly from call_tool_assert_success

            # ReadFile might include line numbers, let's strip those out
            if read_content.strip().startswith("1\t"):
                # Strip the line numbers and any leading whitespace
                read_lines = [
                    line.split("\t", 1)[1] if "\t" in line else line
                    for line in read_content.strip().splitlines()
                ]
                read_content = "".join(read_lines)

            # The content might have slightly different formatting, so we'll parse both as JSON objects and compare
            read_json = json.loads(read_content)
            file_json = json.loads(file_content)

            # Compare the parsed JSON objects
            self.assertEqual(read_json, file_json)


if __name__ == "__main__":
    unittest.main()
