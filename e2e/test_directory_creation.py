#!/usr/bin/env python3

"""End-to-end tests for directory creation in WriteFile and EditFile."""

import os
import unittest

from codemcp.testing import MCPEndToEndTestCase


class DirectoryCreationTest(MCPEndToEndTestCase):
    """Test recursive directory creation in WriteFile and EditFile subtools."""

    async def test_write_file_nested_directories(self):
        """Test WriteFile can create nested directories."""
        # Create a path with multiple nested directories that don't exist
        nested_path = os.path.join(
            self.temp_dir.name, "test_nest", "level1", "level2", "level3"
        )
        test_file_path = os.path.join(nested_path, "test_file.txt")

        # Verify directory doesn't exist
        self.assertFalse(
            os.path.exists(nested_path), "Nested directory should not exist initially"
        )

        content = "Content in a deeply nested directory"

        async with self.create_client_session() as session:
            # Get a valid chat_id
            chat_id = await self.get_chat_id(session)

            # Call the WriteFile tool with chat_id
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "WriteFile",
                    "path": test_file_path,
                    "content": content,
                    "description": "Create file in nested directories",
                    "chat_id": chat_id,
                },
            )

            # Check for success message
            self.assertIn("Successfully wrote to", result_text)

            # Verify the directories were created as expected
            self.assertTrue(
                os.path.exists(nested_path), "Nested directories were not created"
            )

            # Verify the file was created with the correct content
            self.assertTrue(os.path.exists(test_file_path), "File was not created")
            with open(test_file_path) as f:
                file_content = f.read()
            self.assertEqual(file_content, content + "\n")

    async def test_edit_file_nested_directories(self):
        """Test EditFile can create nested directories when old_string is empty."""
        # Create a path with multiple nested directories that don't exist
        nested_path = os.path.join(self.temp_dir.name, "edit_nest", "level1", "level2")
        test_file_path = os.path.join(nested_path, "new_file.txt")

        # Verify directory doesn't exist
        self.assertFalse(
            os.path.exists(nested_path), "Nested directory should not exist initially"
        )

        content = "Content created in nested directories by EditFile"

        async with self.create_client_session() as session:
            # Get a valid chat_id
            chat_id = await self.get_chat_id(session)

            # Call the EditFile tool with empty old_string and chat_id
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "EditFile",
                    "path": test_file_path,
                    "old_string": "",
                    "new_string": content,
                    "description": "Create file in nested directories with EditFile",
                    "chat_id": chat_id,
                },
            )

            # Check for success message
            self.assertIn("Successfully created", result_text)

            # Verify the directories were created as expected
            self.assertTrue(
                os.path.exists(nested_path), "Nested directories were not created"
            )

            # Verify the file was created with the correct content
            self.assertTrue(os.path.exists(test_file_path), "File was not created")
            with open(test_file_path) as f:
                file_content = f.read()
            self.assertEqual(file_content, content + "\n")


if __name__ == "__main__":
    unittest.main()
