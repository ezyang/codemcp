#!/usr/bin/env python3

"""End-to-end test for InitProject subtool in a git repo with no initial commit."""

import os
import unittest

from codemcp.testing import MCPEndToEndTestCase


class InitProjectNoCommitsTest(MCPEndToEndTestCase):
    """Test the InitProject subtool functionality in a git repo with no initial commit."""

    async def test_init_project_no_commits(self):
        """Test InitProject in a git repo with no initial commit and unversioned codemcp.toml."""
        # Create a simple codemcp.toml file
        toml_path = os.path.join(self.temp_dir.name, "codemcp.toml")
        with open(toml_path, "w") as f:
            f.write("""
project_prompt = "Test project with no initial commit"
[commands]
test = ["./run_test.sh"]
""")

        # Set up a git repository but don't make an initial commit
        await self.git_run(["init"])
        await self.git_run(["config", "user.email", "test@example.com"])
        await self.git_run(["config", "user.name", "Test User"])

        # At this point:
        # - We have a git repo
        # - We have no commits in the repo
        # - We have an unversioned codemcp.toml file

        async with self.create_client_session() as session:
            # Call InitProject and expect it to succeed
            result_text = await self.call_tool_assert_success(
                session,
                "codemcp",
                {
                    "subtool": "InitProject",
                    "path": self.temp_dir.name,
                    "user_prompt": "Test initialization in empty repo",
                    "subject_line": "feat: initialize project in empty repo",
                    "reuse_head_chat_id": False,
                },
            )

            # Verify the result contains expected system prompt elements
            self.assertIn("You are an AI assistant", result_text)
            self.assertIn("Test project with no initial commit", result_text)


if __name__ == "__main__":
    unittest.main()
