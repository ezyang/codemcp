#!/usr/bin/env python3

"""Tests for the get_current_commit_hash function when passed a file path."""

import os
import unittest

from codemcp.git_query import get_current_commit_hash
from codemcp.testing import MCPEndToEndTestCase


class GitQueryFilePathTest(MCPEndToEndTestCase):
    """Test that get_current_commit_hash raises a NotADirectoryError when passed a file path."""

    async def test_file_path_raises_error(self):
        """Test that passing a file path to get_current_commit_hash raises NotADirectoryError."""
        # Create a test file in the temp dir
        test_file_path = os.path.join(self.temp_dir.name, "test_file.txt")
        with open(test_file_path, "w") as f:
            f.write("Test content")

        # Attempt to get current commit hash using a file path instead of directory
        # This should raise a NotADirectoryError
        with self.assertRaises(NotADirectoryError):
            await get_current_commit_hash(test_file_path)


if __name__ == "__main__":
    unittest.main()
