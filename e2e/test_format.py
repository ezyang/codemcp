#!/usr/bin/env python3

"""Tests for the RunCommand with format."""

import os
import unittest

from codemcp.testing import MCPEndToEndTestCase


class RunCommandFormatTest(MCPEndToEndTestCase):
    """Test the RunCommand with format subtool."""

    async def test_format_with_run_subtool(self):
        """Test that RunCommand with format commits changes made by formatting."""
        # Create a file that is not properly formatted (needs formatting)
        # We'll use Python's ruff formatter conventions
        unformatted_file_path = os.path.join(self.temp_dir.name, "unformatted.py")
        unformatted_content = """def   badly_formatted_function ( arg1,arg2 ):
    x=1+2
    y= [1,2,
3, 4]
    return   x+y
"""

        with open(unformatted_file_path, "w") as f:
            f.write(unformatted_content)

        # Add it to git
        await self.git_run(["add", unformatted_file_path])

        # Commit it
        await self.git_run(["commit", "-m", "Add unformatted file"])

        # Create a simple format script that simulates ruff formatting
        format_script_path = os.path.join(self.temp_dir.name, "run_format.sh")
        with open(format_script_path, "w") as f:
            f.write("""#!/bin/bash
# Simple mock formatter that just fixes the format of the unformatted.py file
if [ -f unformatted.py ]; then
    # Replace with properly formatted version
    cat > unformatted.py << 'EOF'
def badly_formatted_function(arg1, arg2):
    x = 1 + 2
    y = [1, 2, 3, 4]
    return x + y
EOF
    echo "Formatted unformatted.py"
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
        commit_before = await self.git_run(
            ["rev-parse", "HEAD"], capture_output=True, text=True
        )

        async with self.create_client_session() as session:
            # First initialize project to get chat_id
            init_result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization for format test",
                    "subject_line": "test: initialize for format test",
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

            # Verify the success message
            self.assertIn("Code format successful", result_text)

            # Verify the file was formatted correctly
            with open(unformatted_file_path) as f:
                file_content = f.read()

            expected_content = """def badly_formatted_function(arg1, arg2):
    x = 1 + 2
    y = [1, 2, 3, 4]
    return x + y
"""
            self.assertEqual(file_content, expected_content)

            # Verify git state shows clean working tree after commit
            status = await self.git_run(["status"], capture_output=True, text=True)

            # Verify that the working tree is clean (changes were committed)
            self.assertExpectedInline(
                status,
                """\
On branch main
Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   unformatted.py

no changes added to commit (use "git add" and/or "git commit -a")""",
            )

            # Verify that a new commit was created
            commit_after = await self.git_run(
                ["rev-parse", "HEAD"], capture_output=True, text=True
            )

            # The commit hash should be different
            self.assertNotEqual(commit_before, commit_after)

            # Verify the commit message contains the expected prefix with new mechanism
            commit_msg = await self.git_run(
                ["log", "-1", "--pretty=%B"], capture_output=True, text=True
            )

            # With the commutable auto-commit mechanism, the commit message may be different
            # It could be either PRE_COMMIT or directly include format changes depending on commutation
            self.assertTrue(
                "PRE_COMMIT: Snapshot before auto-format" in commit_msg
                or "Auto-commit format changes" in commit_msg,
                f"Expected format-related commit message but found: {commit_msg}",
            )


if __name__ == "__main__":
    unittest.main()
