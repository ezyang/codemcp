#!/usr/bin/env python3

"""Tests for handling missing format command in run_formatter_without_commit."""

import os
import unittest

from codemcp.testing import MCPEndToEndTestCase


class FormatterNoCommandTest(MCPEndToEndTestCase):
    """Test run_formatter_without_commit with no format command in config."""

    async def test_no_format_command(self):
        """Test that WriteFile handles missing format command without error."""
        # Create a simple file for testing
        test_file_path = os.path.join(self.temp_dir.name, "test_file.txt")
        content = "Test content\nLine 2"

        # Add it to git
        with open(test_file_path, "w") as f:
            f.write("")

        await self.git_run(["add", test_file_path])
        await self.git_run(["commit", "-m", "Add empty file for formatter test"])

        # Create a codemcp.toml file WITHOUT a format command
        codemcp_toml_path = os.path.join(self.temp_dir.name, "codemcp.toml")
        with open(codemcp_toml_path, "w") as f:
            f.write("""[project]
name = "test-project"

[commands]
# Note: No format command is defined here
lint = ["echo", "linting"]
""")

        await self.git_run(["add", "codemcp.toml"])
        await self.git_run(["commit", "-m", "Add codemcp.toml without format command"])

        async with self.create_client_session() as session:
            # Initialize project to get chat_id
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for no format command test",
                    "subject_line": "test: initialize for no format command test",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract chat_id from the init result
            chat_id = self.extract_chat_id_from_text(init_result_text)

            # Call the WriteFile tool - this should succeed even with no format command
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "WriteFile",
                    "path": test_file_path,
                    "content": content,
                    "description": "Write file with no format command",
                    "chat_id": chat_id,
                },
            )

            # Verify the write operation succeeded without error
            self.assertIn("Successfully wrote to", result_text)
            self.assertNotIn("Auto-formatted the file", result_text)
            self.assertNotIn("Failed to auto-format", result_text)

            # Verify the file was created with the correct content
            with open(test_file_path) as f:
                file_content = f.read()
            self.assertEqual(file_content, content + "\n")

            # Now test EditFile as well
            updated_content = content + "\nAdditional line"

            # Call the EditFile tool - this should also succeed
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "EditFile",
                    "path": test_file_path,
                    "old_string": content,
                    "new_string": updated_content,
                    "description": "Edit file with no format command",
                    "chat_id": chat_id,
                },
            )

            # Verify the edit operation succeeded without error
            self.assertIn("Successfully edited", result_text)
            self.assertNotIn("Auto-formatted the file", result_text)
            self.assertNotIn("Failed to auto-format", result_text)

            # Verify the file was updated with the correct content
            with open(test_file_path) as f:
                file_content = f.read()
            self.assertEqual(file_content, updated_content + "\n")


class OutOfProcessFormatterNoCommandTest(FormatterNoCommandTest):
    in_process = False


if __name__ == "__main__":
    unittest.main()
