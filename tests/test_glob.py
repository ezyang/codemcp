"""
Test for the glob module's pattern matching functionality.
"""

import os
import shutil
import tempfile

from codemcp import glob


def setup_test_directory():
    """Create a temporary directory with files for testing."""
    test_dir = tempfile.mkdtemp()

    # Create a nested directory structure with files
    dirs = [
        "",
        "a",
        "a/b",
        "a/b/c",
        "a/d",
        "a/d/e",
        "x",
        "x/y",
        "x/y/z",
    ]

    files = [
        "file1.txt",
        "file2.py",
        "a/file.txt",
        "a/file.py",
        "a/b/file.txt",
        "a/b/file.py",
        "a/b/c/deep.txt",
        "a/d/file.txt",
        "a/d/e/deep.py",
        "x/file.txt",
        "x/y/file.py",
        "x/y/z/deep.txt",
    ]

    # Create directories
    for d in dirs:
        dir_path = os.path.join(test_dir, d)
        if d:  # Skip empty string (root directory)
            os.makedirs(dir_path, exist_ok=True)

    # Create files
    for f in files:
        file_path = os.path.join(test_dir, f)
        with open(file_path, "w") as fh:
            fh.write(f"Test content for {f}")

    return test_dir


def teardown_test_directory(test_dir):
    """Remove the temporary test directory."""
    shutil.rmtree(test_dir)


def test_gitignore_simple_asterisk():
    """Test simple * pattern with gitignore behavior."""
    # * should match anything except slash
    assert glob.match("*.txt", "file1.txt")
    assert glob.match("*.txt", "a.txt")
    assert not glob.match("*.txt", "dir/file.txt")
    assert not glob.match("*.txt", "file.py")


def test_gitignore_question_mark():
    """Test ? pattern with gitignore behavior."""
    # ? should match any single character except slash
    assert glob.match("file?.txt", "file1.txt")
    assert glob.match("file?.txt", "fileA.txt")
    assert not glob.match("file?.txt", "file12.txt")
    assert not glob.match("file?.txt", "file.txt")
    assert not glob.match("file?.txt", "dir/file1.txt")


def test_gitignore_character_class():
    """Test character class patterns with gitignore behavior."""
    # [abc] should match any character in the brackets
    assert glob.match("file[123].txt", "file1.txt")
    assert glob.match("file[123].txt", "file2.txt")
    assert not glob.match("file[123].txt", "file4.txt")

    # [!abc] should match any character not in the brackets
    assert glob.match("file[!123].txt", "file4.txt")
    assert glob.match("file[!123].txt", "fileA.txt")
    assert not glob.match("file[!123].txt", "file1.txt")

    # [a-z] should match any character in the range
    assert glob.match("file[a-z].txt", "filea.txt")
    assert glob.match("file[a-z].txt", "filez.txt")
    assert not glob.match("file[a-z].txt", "file1.txt")
    assert not glob.match("file[a-z].txt", "fileA.txt")


def test_gitignore_leading_double_asterisk():
    """Test leading **/ pattern with gitignore behavior."""
    # **/ should match in all directories
    assert glob.match("**/file.txt", "file.txt")
    assert glob.match("**/file.txt", "a/file.txt")
    assert glob.match("**/file.txt", "a/b/file.txt")
    assert not glob.match("**/file.txt", "file1.txt")
    assert not glob.match("**/file.txt", "a/file1.txt")

    # **/foo/bar should match bar anywhere directly under foo
    assert glob.match("**/a/file.txt", "a/file.txt")
    assert glob.match("**/a/file.txt", "x/a/file.txt")
    assert not glob.match("**/a/file.txt", "a/b/file.txt")


def test_gitignore_trailing_double_asterisk():
    """Test trailing /** pattern with gitignore behavior."""
    # /** should match everything inside
    assert glob.match("a/**", "a/file.txt")
    assert glob.match("a/**", "a/b/file.txt")
    assert glob.match("a/**", "a/b/c/deep.txt")
    assert not glob.match("a/**", "file.txt")
    assert not glob.match("a/**", "x/file.txt")


def test_gitignore_middle_double_asterisk():
    """Test /**/pattern with gitignore behavior."""
    # /**/ should match zero or more directories
    assert glob.match("a/**/file.txt", "a/file.txt")
    assert glob.match("a/**/file.txt", "a/b/file.txt")
    assert glob.match("a/**/file.txt", "a/b/c/file.txt")
    assert not glob.match("a/**/file.txt", "file.txt")
    assert not glob.match("a/**/file.txt", "a/file.py")


def test_editorconfig_braces():
    """Test editorconfig brace expansion."""
    # {s1,s2,s3} should match any of the strings
    assert glob.match("file.{txt,py}", "file.txt", editorconfig_braces=True)
    assert glob.match("file.{txt,py}", "file.py", editorconfig_braces=True)
    assert not glob.match("file.{txt,py}", "file.md", editorconfig_braces=True)

    # {num1..num2} should match any integer in the range
    assert glob.match("file{1..3}.txt", "file1.txt", editorconfig_braces=True)
    assert glob.match("file{1..3}.txt", "file2.txt", editorconfig_braces=True)
    assert glob.match("file{1..3}.txt", "file3.txt", editorconfig_braces=True)
    assert not glob.match("file{1..3}.txt", "file4.txt", editorconfig_braces=True)
    assert not glob.match("file{1..3}.txt", "file0.txt", editorconfig_braces=True)

    # Negative ranges
    assert glob.match("file{-1..1}.txt", "file-1.txt", editorconfig_braces=True)
    assert glob.match("file{-1..1}.txt", "file0.txt", editorconfig_braces=True)
    assert glob.match("file{-1..1}.txt", "file1.txt", editorconfig_braces=True)

    # Braces can be nested
    assert glob.match("file{a,{b,c}}.txt", "filea.txt", editorconfig_braces=True)
    assert glob.match("file{a,{b,c}}.txt", "fileb.txt", editorconfig_braces=True)
    assert glob.match("file{a,{b,c}}.txt", "filec.txt", editorconfig_braces=True)


def test_editorconfig_asterisk():
    """Test editorconfig asterisk behavior."""
    # * should match any string including path separators
    assert glob.match("*.txt", "file.txt", editorconfig_asterisk=True)
    assert glob.match("*.txt", "dir/file.txt", editorconfig_asterisk=True)
    assert not glob.match("*.txt", "file.py", editorconfig_asterisk=True)


def test_editorconfig_double_asterisk():
    """Test editorconfig ** behavior."""
    # ** should match any string
    assert glob.match("**", "file.txt", editorconfig_double_asterisk=True)
    assert glob.match("**", "dir/file.txt", editorconfig_double_asterisk=True)
    assert glob.match("**", "dir/subdir/file.txt", editorconfig_double_asterisk=True)

    # More specific pattern with **
    assert glob.match("a/**/file.txt", "a/file.txt", editorconfig_double_asterisk=True)
    assert glob.match(
        "a/**/file.txt", "a/b/file.txt", editorconfig_double_asterisk=True
    )
    assert glob.match(
        "a/**/file.txt", "a/b/c/file.txt", editorconfig_double_asterisk=True
    )


def test_escaped_characters():
    """Test escaped special characters in patterns."""
    # Escaped special characters should be treated as literals
    assert glob.match(r"\*.txt", "*.txt")
    assert not glob.match(r"\*.txt", "a.txt")

    assert glob.match(r"\?.txt", "?.txt")
    assert not glob.match(r"\?.txt", "a.txt")

    assert glob.match(r"\[abc\].txt", "[abc].txt")
    assert not glob.match(r"\[abc\].txt", "a.txt")


def test_combined_features():
    """Test combining different pattern features."""
    # Combining various features
    assert glob.match(
        "**/[a-z]/{file,test}.{txt,py}", "a/file.txt", editorconfig_braces=True
    )
    assert glob.match(
        "**/[a-z]/{file,test}.{txt,py}", "x/y/z/test.py", editorconfig_braces=True
    )
    assert not glob.match(
        "**/[a-z]/{file,test}.{txt,py}", "1/file.txt", editorconfig_braces=True
    )
    assert not glob.match(
        "**/[a-z]/{file,test}.{txt,py}", "a/other.txt", editorconfig_braces=True
    )


def test_filter_function():
    """Test the filter function."""
    paths = [
        "file1.txt",
        "file2.py",
        "dir/file.txt",
        "dir/file.py",
        "dir/subdir/file.txt",
    ]

    # Filter with a single pattern
    result = glob.filter(["*.txt"], paths)
    assert result == ["file1.txt"]

    # Filter with multiple patterns
    result = glob.filter(["*.txt", "*.py"], paths)
    assert result == ["file1.txt", "file2.py"]

    # Filter with gitignore-specific pattern
    result = glob.filter(["**/file.txt"], paths)
    assert result == ["dir/file.txt", "dir/subdir/file.txt"]


def test_find_function():
    """Test the find function with a temporary directory."""
    test_dir = setup_test_directory()

    try:
        # Find with a simple pattern
        result = glob.find(["*.txt"], test_dir)
        assert len(result) == 1
        assert os.path.basename(result[0]) == "file1.txt"

        # Find with gitignore-specific pattern
        result = glob.find(["**/file.txt"], test_dir)
        filenames = [os.path.basename(path) for path in result]
        assert all(filename == "file.txt" for filename in filenames)
        # There are 4 file.txt files in our test directory structure:
        # a/file.txt, a/b/file.txt, a/d/file.txt, x/file.txt
        assert len(result) == 4

        # Find with combination of patterns
        result = glob.find(["a/**/*.py"], test_dir)
        assert len(result) == 3
        assert any("a/file.py" in path for path in result)
        assert any("a/b/file.py" in path for path in result)
        assert any("a/d/e/deep.py" in path for path in result)

    finally:
        teardown_test_directory(test_dir)


def test_make_matcher_function():
    """Test the make_matcher function."""
    # Create a matcher function
    matcher = glob.make_matcher("*.txt")

    # Test the matcher
    assert matcher("file.txt")
    assert not matcher("file.py")
    assert not matcher("dir/file.txt")

    # Create a matcher with gitignore-specific behavior
    matcher = glob.make_matcher("**/file.txt")

    # Test the matcher
    assert matcher("file.txt")
    assert matcher("dir/file.txt")
    assert matcher("dir/subdir/file.txt")
    assert not matcher("file.py")
