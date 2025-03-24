#!/usr/bin/env python3

"""End-to-end test for InitProject subtool in a git repo with no initial commit."""

import os
import subprocess
import tempfile
import unittest
from unittest import mock

from codemcp.git import get_ref_commit_chat_id
from codemcp.testing import MCPEndToEndTestCase


class InitProjectNoCommitsTest(MCPEndToEndTestCase):
    """Test the InitProject subtool functionality in a git repo with no initial commit."""

    async def asyncSetUp(self):
        """Override the default asyncSetUp to not create an initial commit."""
        # Create a temporary directory for testing
        self.temp_dir = tempfile.TemporaryDirectory()
        self.testing_time = "1112911993"  # Fixed timestamp for git

        # Initialize environment variables for git
        self.env = os.environ.copy()
        # Set environment variables for reproducible git behavior
        self.env.setdefault("GIT_TERMINAL_PROMPT", "0")
        self.env.setdefault("EDITOR", ":")
        self.env.setdefault("GIT_MERGE_AUTOEDIT", "no")
        self.env.setdefault("LANG", "C")
        self.env.setdefault("LC_ALL", "C")
        self.env.setdefault("PAGER", "cat")
        self.env.setdefault("TZ", "UTC")
        self.env.setdefault("TERM", "dumb")
        # For deterministic commit times
        self.env.setdefault("GIT_AUTHOR_EMAIL", "author@example.com")
        self.env.setdefault("GIT_AUTHOR_NAME", "A U Thor")
        self.env.setdefault("GIT_COMMITTER_EMAIL", "committer@example.com")
        self.env.setdefault("GIT_COMMITTER_NAME", "C O Mitter")
        self.env.setdefault("GIT_COMMITTER_DATE", f"{self.testing_time} -0700")
        self.env.setdefault("GIT_AUTHOR_DATE", f"{self.testing_time} -0700")

        # Patch get_subprocess_env to use the test environment
        self.env_patcher = mock.patch(
            "codemcp.shell.get_subprocess_env", return_value=self.env
        )
        self.env_patcher.start()

        # Note: We don't call init_git_repo() here since we want to start with no commits

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

        # Verify that we truly have no commits
        try:
            await self.git_run(
                ["rev-parse", "--verify", "HEAD"],
                capture_output=True,
                text=True,
                check=True,  # This should fail if HEAD doesn't exist
            )
            self.fail("Expected no HEAD commit to exist, but HEAD exists")
        except subprocess.CalledProcessError:
            # This is expected - HEAD shouldn't exist
            pass

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

            # Extract the chat ID from the result
            chat_id = self.extract_chat_id_from_text(result_text)
            self.assertIsNotNone(chat_id, "Chat ID should be present in result")

            # Verify the reference was created with the chat ID
            ref_name = f"refs/codemcp/{chat_id}"
            ref_chat_id = await get_ref_commit_chat_id(self.temp_dir.name, ref_name)
            self.assertEqual(
                chat_id,
                ref_chat_id,
                f"Chat ID {chat_id} should be in reference {ref_name}",
            )

            # Verify HEAD still doesn't exist (we should only create a reference, not advance HEAD)
            try:
                await self.git_run(
                    ["rev-parse", "--verify", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=True,  # This should fail if HEAD doesn't exist
                )
                self.fail(
                    "HEAD should still not exist after InitProject, but it exists"
                )
            except subprocess.CalledProcessError:
                # This is expected - HEAD still shouldn't exist
                pass


if __name__ == "__main__":
    unittest.main()
