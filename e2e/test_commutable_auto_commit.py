#!/usr/bin/env python3

"""Tests for the commutable auto-commit mechanism in run_code_command."""

import os
import unittest

from codemcp.testing import MCPEndToEndTestCase


class CommutableAutoCommitTest(MCPEndToEndTestCase):
    """Test the commutable auto-commit mechanism in run_code_command."""

    async def test_commutable_auto_commit_successful_commutation(self):
        """Test that changes commute successfully."""
        # Create a file with some initial content
        file_path = os.path.join(self.temp_dir.name, "commutable.py")
        with open(file_path, "w") as f:
            f.write("""def example_function():
    # This is original code
    x = 1
    y = 2
    return x + y
""")

        # Add it to git
        await self.git_run(["add", file_path])
        await self.git_run(["commit", "-m", "Add commutable.py"])

        # Make a local change that will commute with formatting
        with open(file_path, "w") as f:
            f.write("""def example_function():
    # This is original code
    x = 10  # Changed value
    y = 20  # Changed value
    return x + y
""")

        # Create a simple format script that fixes indentation
        format_script_path = os.path.join(self.temp_dir.name, "run_format.sh")
        with open(format_script_path, "w") as f:
            f.write("""#!/bin/bash
# Simple formatter that adds spaces after comments and fixes indentation
if [ -f commutable.py ]; then
    # Use sed to add spaces after # and ensure 4-space indentation
    sed -i 's/# /# /g; s/^    /    /g' commutable.py
    # Add a blank line at the end of the file
    echo "" >> commutable.py
    echo "Formatted commutable.py"
fi
""")

        # Make it executable
        os.chmod(format_script_path, 0o755)

        # Create a codemcp.toml file with format subtool
        codemcp_toml_path = os.path.join(self.temp_dir.name, "codemcp.toml")
        with open(codemcp_toml_path, "w") as f:
            f.write("""[project]
name = "test-project"

[commands]
format = ["./run_format.sh"]
""")

        # Record the current commit hash before formatting
        await self.git_run(["rev-parse", "HEAD"], capture_output=True, text=True)

        async with self.create_client_session() as session:
            # Initialize project to get chat_id
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test commutable auto-commit",
                    "subject_line": "test: initialize for commutable auto-commit test",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract chat_id from the init result
            chat_id = self.extract_chat_id_from_text(init_result_text)

            # Call the RunCommand tool with format command and chat_id
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "RunCommand",
                    "path": self.temp_dir.name,
                    "command": "format",
                    "chat_id": chat_id,
                },
            )

            # Verify successful commutation message
            self.assertIn("changes commuted successfully", result_text)

            # Verify git status shows changes are still present in working tree
            status = await self.git_run(["status"], capture_output=True, text=True)

            # Verify that the working tree has uncommitted changes (our local changes)
            self.assertIn("modified:   commutable.py", status)

            # Verify file content has both our changes and the formatting changes
            with open(file_path) as f:
                file_content = f.read()

            # Our value changes should still be there
            self.assertIn("x = 10", file_content)
            self.assertIn("y = 20", file_content)

            # And the formatter should have added a blank line at the end
            self.assertTrue(file_content.endswith("\n\n"))

    async def test_commutable_auto_commit_content_updates(self):
        """Test that the command's content changes are properly applied."""
        # Create a file with some initial content
        file_path = os.path.join(self.temp_dir.name, "updatable.py")
        with open(file_path, "w") as f:
            f.write("""def process_data(data):
    # Process the data
    return data
""")

        # Add it to git
        await self.git_run(["add", file_path])
        await self.git_run(["commit", "-m", "Add updatable.py"])

        # Create a script that adds functionality
        update_script_path = os.path.join(self.temp_dir.name, "run_update.sh")
        with open(update_script_path, "w") as f:
            f.write("""#!/bin/bash
# Script that adds functionality to a file
if [ -f updatable.py ]; then
    # Add a new function
    cat > updatable.py << 'EOF'
def process_data(data):
    # Process the data
    return data

def new_function():
    # New function added by auto-update
    return "Hello World"
EOF
    echo "Updated updatable.py"
fi
""")

        # Make it executable
        os.chmod(update_script_path, 0o755)

        # Create a codemcp.toml file with the update command
        codemcp_toml_path = os.path.join(self.temp_dir.name, "codemcp.toml")
        with open(codemcp_toml_path, "w") as f:
            f.write("""[project]
name = "test-project"

[commands]
update = ["./run_update.sh"]
""")

        async with self.create_client_session() as session:
            # Initialize project to get chat_id
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test update mechanism",
                    "subject_line": "test: initialize for update test",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract chat_id from the init result
            chat_id = self.extract_chat_id_from_text(init_result_text)

            # Call the RunCommand tool with update command and chat_id
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "RunCommand",
                    "path": self.temp_dir.name,
                    "command": "update",
                    "chat_id": chat_id,
                },
            )

            # Verify successful update message
            self.assertIn("Code update successful", result_text)

            # Verify the file contains the new function
            with open(file_path) as f:
                file_content = f.read()

            self.assertIn("def new_function():", file_content)
            self.assertIn('return "Hello World"', file_content)


if __name__ == "__main__":
    unittest.main()
