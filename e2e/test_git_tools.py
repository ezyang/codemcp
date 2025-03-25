#!/usr/bin/env python3

import os
from unittest import mock

from codemcp.testing import MCPEndToEndTestCase
from codemcp.tools.git_blame import git_blame
from codemcp.tools.git_diff import git_diff
from codemcp.tools.git_log import git_log
from codemcp.tools.git_show import git_show


class TestGitTools(MCPEndToEndTestCase):
    """Test the git tools functionality."""

    async def asyncSetUp(self):
        # Use the parent class's asyncSetUp to set up test environment
        await super().asyncSetUp()

        # Create a sample file
        self.sample_file = os.path.join(self.temp_dir.name, "sample.txt")
        with open(self.sample_file, "w") as f:
            f.write("Sample content\nLine 2\nLine 3\n")

        # Add and commit the file (the base class already has git initialized)
        await self.git_run(["add", "sample.txt"])
        await self.git_run(["commit", "-m", "Initial commit"])

        # Modify the file and create another commit
        with open(self.sample_file, "a") as f:
            f.write("Line 4\nLine 5\n")

        await self.git_run(["add", "sample.txt"])
        await self.git_run(["commit", "-m", "Second commit"])

    async def test_git_log(self):
        """Test the git_log tool."""
        # Test with no arguments
        result = await git_log(path=self.temp_dir.name)
        self.assertIn("Initial commit", result["output"])
        self.assertIn("Second commit", result["output"])

        # Test with arguments
        result = await git_log(arguments="--oneline -n 1", path=self.temp_dir.name)
        self.assertIn("Second commit", result["output"])
        self.assertNotIn("Initial commit", result["output"])

    async def test_git_diff(self):
        """Test the git_diff tool."""
        # Create a change but don't commit it
        with open(self.sample_file, "a") as f:
            f.write("Uncommitted change\n")

        # Test with no arguments
        result = await git_diff(path=self.temp_dir.name)
        self.assertIn("Uncommitted change", result["output"])

        # Test with arguments
        result = await git_diff(arguments="HEAD~1 HEAD", path=self.temp_dir.name)
        self.assertIn("Line 4", result["output"])

    async def test_git_show(self):
        """Test the git_show tool."""
        # Test with no arguments (should show the latest commit)
        result = await git_show(path=self.temp_dir.name)
        self.assertIn("Second commit", result["output"])

        # Test with arguments
        result = await git_show(arguments="HEAD~1", path=self.temp_dir.name)
        self.assertIn("Initial commit", result["output"])

    async def test_git_blame(self):
        """Test the git_blame tool."""
        # Test with file argument
        result = await git_blame(arguments="sample.txt", path=self.temp_dir.name)
        self.assertIn(
            "A U Thor", result["output"]
        )  # MCPEndToEndTestCase sets this author
        self.assertIn("Line 2", result["output"])

        # Test with line range
        result = await git_blame(arguments="-L 4,5 sample.txt", path=self.temp_dir.name)
        self.assertIn("Line 4", result["output"])
        self.assertNotIn("Line 2", result["output"])

    async def test_invalid_path(self):
        """Test that tools handle invalid paths."""
        with mock.patch("codemcp.tools.git_log.is_git_repository", return_value=False):
            with self.assertRaises(ValueError):
                await git_log(path="/invalid/path")

        with mock.patch("codemcp.tools.git_diff.is_git_repository", return_value=False):
            with self.assertRaises(ValueError):
                await git_diff(path="/invalid/path")

        with mock.patch("codemcp.tools.git_show.is_git_repository", return_value=False):
            with self.assertRaises(ValueError):
                await git_show(path="/invalid/path")

        with mock.patch(
            "codemcp.tools.git_blame.is_git_repository", return_value=False
        ):
            with self.assertRaises(ValueError):
                await git_blame(path="/invalid/path")
