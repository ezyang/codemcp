#!/usr/bin/env python3

import tempfile
import unittest
from pathlib import Path

from codemcp.rules import load_rule_from_file, match_file_with_glob


class TestRules(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

    def tearDown(self):
        # Clean up the temporary directory
        self.temp_dir.cleanup()

    def test_load_rule_from_file(self):
        # Create a test MDC file
        test_mdc_path = self.test_dir / "test_rule.mdc"
        with open(test_mdc_path, "w") as f:
            f.write(
                """---
description: Test rule description
globs: *.js,*.ts
alwaysApply: true
---
This is a test rule payload
"""
            )

        # Load the rule
        rule = load_rule_from_file(str(test_mdc_path))

        # Check that the rule was loaded correctly
        self.assertIsNotNone(rule)
        self.assertEqual(rule.description, "Test rule description")
        self.assertEqual(rule.globs, ["*.js", "*.ts"])
        self.assertTrue(rule.always_apply)
        self.assertEqual(rule.payload, "This is a test rule payload")
        self.assertEqual(rule.file_path, str(test_mdc_path))

    def test_load_rule_from_file_comma_separated_globs(self):
        # Create a test MDC file with comma-separated globs
        test_mdc_path = self.test_dir / "test_glob_rule.mdc"
        with open(test_mdc_path, "w") as f:
            f.write(
                """---
description: Test glob rule
globs: *.js, *.ts, src/**/*.jsx
alwaysApply: false
---
This is a glob test rule
"""
            )

        # Load the rule
        rule = load_rule_from_file(str(test_mdc_path))

        # Check that the globs were parsed correctly
        self.assertIsNotNone(rule)
        self.assertEqual(rule.globs, ["*.js", "*.ts", "src/**/*.jsx"])

    def test_load_rule_from_file_invalid(self):
        # Create an invalid MDC file (missing frontmatter)
        test_mdc_path = self.test_dir / "invalid_rule.mdc"
        with open(test_mdc_path, "w") as f:
            f.write("This is not a valid MDC file")

        # Attempt to load the rule
        rule = load_rule_from_file(str(test_mdc_path))

        # Check that the rule failed to load
        self.assertIsNone(rule)

    def test_match_file_with_glob(self):
        # Test basic glob matching
        self.assertTrue(match_file_with_glob("test.js", "*.js"))
        # For compatibility with existing code, *.js matches files in any directory
        self.assertTrue(match_file_with_glob("/path/to/test.js", "*.js"))
        # But **/*.js should match files in any directory
        self.assertTrue(match_file_with_glob("/path/to/test.js", "**/*.js"))
        self.assertTrue(
            match_file_with_glob("/path/to/src/components/Button.jsx", "src/**/*.jsx")
        )

        # Test non-matching paths
        self.assertFalse(match_file_with_glob("test.py", "*.js"))
        self.assertFalse(match_file_with_glob("/path/to/test.ts", "*.js"))
        self.assertFalse(match_file_with_glob("/path/to/lib/test.jsx", "src/**/*.jsx"))

    def test_match_file_with_trailing_double_star(self):
        # Test glob patterns ending with /**
        self.assertTrue(match_file_with_glob("/path/to/abc/file.txt", "abc/**"))
        self.assertTrue(match_file_with_glob("/path/to/abc/subdir/file.txt", "abc/**"))
        self.assertTrue(
            match_file_with_glob("/path/to/abc/deep/nested/file.js", "abc/**")
        )

        # Test non-matching paths for trailing /**
        self.assertFalse(match_file_with_glob("/path/to/xyz/file.txt", "abc/**"))
        self.assertFalse(match_file_with_glob("/abc-other/file.txt", "abc/**"))


if __name__ == "__main__":
    unittest.main()
