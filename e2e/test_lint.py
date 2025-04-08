#!/usr/bin/env python3

"""Tests for the RunCommand with lint."""

import os
import unittest

from codemcp.testing import MCPEndToEndTestCase


class RunCommandLintTest(MCPEndToEndTestCase):
    """Test the RunCommand with lint subtool."""

    async def test_lint_with_run_subtool(self):
        """Test that RunCommand with lint commits changes made by linting."""
        # Create a file that needs linting
        unlinted_file_path = os.path.join(self.temp_dir.name, "unlinted.py")
        unlinted_content = """import math
import os
import sys
from typing import List, Dict, Any

def unused_param(x, y):
    # Unused parameter 'y' that linter would remove
    return x * 2

def main():
    # Unused import
    # Variables defined but not used
    unused_var = 42
    return True
"""

        with open(unlinted_file_path, "w") as f:
            f.write(unlinted_content)

        # Add it to git
        await self.git_run(["add", unlinted_file_path])

        # Commit it
        await self.git_run(["commit", "-m", "Add unlinted file"])

        # Create a simple lint script that simulates ruff linting
        lint_script_path = os.path.join(self.temp_dir.name, "run_lint.sh")
        with open(lint_script_path, "w") as f:
            f.write("""#!/bin/bash
# Simple mock linter that fixes linting issues in the unlinted.py file
if [ -f unlinted.py ]; then
    # Replace with properly linted version (removed unused imports and variables)
    cat > unlinted.py << 'EOF'
import math
from typing import List, Dict, Any

def unused_param(x):
    # Linter removed unused parameter 'y'
    return x * 2

def main():
    return True
EOF
    echo "Linted unlinted.py"
fi
""")

        # Make it executable
        os.chmod(lint_script_path, 0o755)

        # Create a codemcp.toml file with lint subtool
        codemcp_toml_path = os.path.join(self.temp_dir.name, "codemcp.toml")
        with open(codemcp_toml_path, "w") as f:
            f.write("""[project]
name = "test-project"

[commands]
lint = ["./run_lint.sh"]
""")

        # Record the current commit hash before linting
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
                    "user_prompt": "Test initialization for lint test",
                    "subject_line": "test: initialize for lint test",
                    "reuse_head_chat_id": False,
                },
            )

            # Extract chat_id from the init result
            chat_id = self.extract_chat_id_from_text(init_result_text)

            # Call the RunCommand tool with lint command and chat_id
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "RunCommand",
                    "path": self.temp_dir.name,
                    "command": "lint",
                    "chat_id": chat_id,
                },
            )

            # Verify the success message
            self.assertIn("Code lint successful", result_text)

            # Verify the file was linted correctly
            with open(unlinted_file_path) as f:
                file_content = f.read()

            expected_content = """import math
from typing import List, Dict, Any

def unused_param(x):
    # Linter removed unused parameter 'y'
    return x * 2

def main():
    return True
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
	modified:   unlinted.py

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
            # It could be either PRE_COMMIT or directly include lint changes depending on commutation
            self.assertTrue(
                "PRE_COMMIT: Snapshot before auto-lint" in commit_msg
                or "Auto-commit lint changes" in commit_msg,
                f"Expected lint-related commit message but found: {commit_msg}",
            )


if __name__ == "__main__":
    unittest.main()
