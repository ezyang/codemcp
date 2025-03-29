#!/usr/bin/env python3

"""Tests for serializing non-string content using json.dumps."""

import json
import os
import unittest

from codemcp.testing import MCPEndToEndTestCase


class JsonContentSerializationTest(MCPEndToEndTestCase):
    """Test the serialization of non-string content for WriteFile subtool."""

    # Set in_process = False to ensure argument validation logic is triggered
    in_process = False

    async def test_json_serialization(self):
        """Test that non-string content is properly serialized to JSON."""
        test_file_path = os.path.join(self.temp_dir.name, "json_serialized.txt")

        # Dictionary to be serialized
        content_dict = {
            "name": "Test Object",
            "values": [1, 2, 3],
            "nested": {"key": "value", "boolean": True},
        }

        # Expected serialized string for verification
        expected_content = json.dumps(content_dict) + "\n"

        async with self.create_client_session() as session:
            # First initialize project to get chat_id
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for JSON serialization test",
                    "subject_line": "test: test json content serialization",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract chat_id from the init result
            chat_id = self.extract_chat_id_from_text(init_result_text)

            # Call the WriteFile tool with a dict as content
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "WriteFile",
                    "path": test_file_path,
                    "content": content_dict,  # Passing a dictionary instead of a string
                    "description": "Create file with JSON serialized content",
                    "chat_id": chat_id,
                },
            )

            # Verify the success message
            self.assertIn("Successfully wrote to", result_text)

            # Verify the file was created with the correct content
            with open(test_file_path) as f:
                file_content = f.read()

            self.assertEqual(file_content, expected_content)

            # Test with a list
            content_list = [1, "two", 3.0, False, None]
            expected_list_content = json.dumps(content_list) + "\n"
            list_file_path = os.path.join(self.temp_dir.name, "list_serialized.txt")

            # Call WriteFile with a list as content
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "WriteFile",
                    "path": list_file_path,
                    "content": content_list,  # Passing a list instead of a string
                    "description": "Create file with list content",
                    "chat_id": chat_id,
                },
            )

            # Verify the success message
            self.assertIn("Successfully wrote to", result_text)

            # Verify the file was created with the correct content
            with open(list_file_path) as f:
                file_content = f.read()

            self.assertEqual(file_content, expected_list_content)


if __name__ == "__main__":
    unittest.main()
