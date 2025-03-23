"""
Generic fnmatch-based glob implementation supporting both gitignore and editorconfig glob syntax.
"""

import os
import re
from typing import Callable, List


def translate_pattern(
    pattern: str,
    editorconfig_braces: bool = False,
    editorconfig_asterisk: bool = False,
    editorconfig_double_asterisk: bool = False,
) -> str:
    """
    Translate a glob pattern to a regular expression pattern.

    Args:
        pattern: The glob pattern to translate
        editorconfig_braces: Enable editorconfig brace expansion {s1,s2,s3} and {n1..n2}
        editorconfig_asterisk: If True, '*' matches any string including path separators
        editorconfig_double_asterisk: If True, '**' matches any string (editorconfig behavior)
                                     If False, uses gitignore behavior for '**'

    Returns:
        Regular expression pattern string
    """
    i, n = 0, len(pattern)
    result = []

    # Handle escaped characters
    escaped = False

    while i < n:
        c = pattern[i]
        i += 1

        if escaped:
            # If character was escaped with backslash, add it literally
            result.append(re.escape(c))
            escaped = False
            continue

        if c == "\\":
            escaped = True
            continue

        elif c == "*":
            # Check for ** pattern
            if i < n and pattern[i] == "*":
                i += 1

                if editorconfig_double_asterisk:
                    # EditorConfig: ** matches any string

                    # Handle patterns like a/**/b to match across directories
                    preceding_slash = result and result[-1] == re.escape("/")
                    following_slash = i < n and pattern[i] == "/"

                    if preceding_slash and following_slash:
                        # /**/
                        result.append("(?:.*)")
                        i += 1  # Skip the slash
                    elif preceding_slash:
                        # /**
                        result.append("(?:.*)")
                    elif following_slash:
                        # **/
                        result.append("(?:.*)")
                        i += 1  # Skip the slash
                    else:
                        # ** in other contexts
                        result.append("(?:.*)")
                else:
                    # GitIgnore: ** has special meaning in certain positions

                    # Case 1: Start of pattern: **/
                    if i < n and pattern[i] == "/" and result == []:
                        i += 1
                        result.append("(?:.*?/)?")

                    # Case 2: End of pattern: /**
                    elif i == n and result and result[-1] == re.escape("/"):
                        result[-1] = "(?:/.*)?"

                    # Case 3: Middle of pattern: /**/
                    elif (
                        i < n
                        and pattern[i] == "/"
                        and result
                        and result[-1] == re.escape("/")
                    ):
                        i += 1
                        result.append("(?:.*/)?")

                    # Case 4: Other positions: treat as two single asterisks
                    else:
                        if editorconfig_asterisk:
                            result.append(".*")
                        else:
                            result.append("[^/]*")

                        if editorconfig_asterisk:
                            result.append(".*")
                        else:
                            result.append("[^/]*")
            else:
                # Single asterisk
                if editorconfig_asterisk:
                    result.append(".*")
                else:
                    result.append("[^/]*")

        elif c == "?":
            # ? matches any single character except /
            result.append("[^/]")

        elif c == "[":
            j = i
            if j < n and pattern[j] == "!":
                j += 1
            if j < n and pattern[j] == "]":
                j += 1
            while j < n and pattern[j] != "]":
                j += 1
            if j >= n:
                result.append("\\[")
            else:
                # Handle character classes
                stuff = pattern[i:j]
                if stuff.startswith("!"):
                    stuff = "^" + stuff[1:]
                elif stuff.startswith("^"):
                    stuff = "\\" + stuff
                i = j + 1

                if stuff:
                    result.append("[" + stuff + "]")
                else:
                    result.append("\\[\\]")

        elif c == "{" and editorconfig_braces:
            # Handle EditorConfig brace expansion
            j = i
            depth = 1
            while j < n and depth > 0:
                if pattern[j] == "{":
                    depth += 1
                elif pattern[j] == "}":
                    depth -= 1
                j += 1

            if depth > 0 or j == i:  # No closing brace found or empty braces
                result.append("\\{")
            else:
                # Extract the brace content
                brace_content = pattern[i : j - 1]
                i = j

                # Check if it's a numeric range {num1..num2}
                num_range_match = re.match(r"^(-?\d+)\.\.(-?\d+)$", brace_content)
                if num_range_match:
                    num1 = int(num_range_match.group(1))
                    num2 = int(num_range_match.group(2))

                    # Generate the range alternatives
                    nums = (
                        range(num1, num2 + 1)
                        if num1 <= num2
                        else range(num1, num2 - 1, -1)
                    )
                    alternatives = "|".join(str(num) for num in nums)
                    result.append(f"(?:{alternatives})")
                else:
                    # Handle comma-separated items {s1,s2,s3}
                    # Split but respect any nested braces
                    items = []
                    start = 0
                    nested_depth = 0

                    for k, char in enumerate(brace_content):
                        if char == "{":
                            nested_depth += 1
                        elif char == "}":
                            nested_depth -= 1
                        elif char == "," and nested_depth == 0:
                            items.append(brace_content[start:k])
                            start = k + 1

                    # Add the last item
                    items.append(brace_content[start:])

                    if not items or all(not item for item in items):
                        result.append("\\{")
                        # Roll back the index to continue processing after the opening brace
                        i = i - len(brace_content) - 2
                    else:
                        # Process each item recursively to handle nested braces
                        processed_items = []
                        for item in items:
                            # For nested patterns, recursively translate but without the anchors
                            if "{" in item:
                                item_pattern = translate_pattern(
                                    item,
                                    editorconfig_braces=True,
                                    editorconfig_asterisk=editorconfig_asterisk,
                                    editorconfig_double_asterisk=editorconfig_double_asterisk,
                                )
                                # Remove the anchors (^ and $)
                                if item_pattern.startswith("^"):
                                    item_pattern = item_pattern[1:]
                                if item_pattern.endswith("$"):
                                    item_pattern = item_pattern[:-1]
                                processed_items.append(item_pattern)
                            else:
                                processed_items.append(re.escape(item))

                        alternatives = "|".join(processed_items)
                        result.append(f"(?:{alternatives})")

        else:
            result.append(re.escape(c))

    # Ensure pattern matches the entire string
    return "^" + "".join(result) + "$"


def make_matcher(pattern: str, **kwargs) -> Callable[[str], bool]:
    """
    Create a matcher function that matches paths against the given pattern.

    Args:
        pattern: The glob pattern to match against
        **kwargs: Optional features to enable

    Returns:
        A function that takes a path string and returns True if it matches
    """
    regex_pattern = translate_pattern(pattern, **kwargs)
    regex = re.compile(regex_pattern)

    def matcher(path: str) -> bool:
        return bool(regex.match(path))

    return matcher


def match(pattern: str, path: str, **kwargs) -> bool:
    """
    Test whether a path matches the given pattern.

    Args:
        pattern: The glob pattern to match against
        path: The path to test
        **kwargs: Optional features to enable

    Returns:
        True if the path matches the pattern, False otherwise
    """
    matcher = make_matcher(pattern, **kwargs)
    return matcher(path)


def filter(patterns: List[str], paths: List[str], **kwargs) -> List[str]:
    """
    Filter a list of paths to those that match any of the given patterns.

    Args:
        patterns: List of glob patterns
        paths: List of paths to filter
        **kwargs: Optional features to enable

    Returns:
        List of paths that match any of the patterns
    """
    matchers = [make_matcher(pattern, **kwargs) for pattern in patterns]
    return [path for path in paths if any(matcher(path) for matcher in matchers)]


def find(patterns: List[str], root: str, **kwargs) -> List[str]:
    """
    Find all files in the given root directory that match any of the given patterns.

    Args:
        patterns: List of glob patterns
        root: Root directory to search
        **kwargs: Optional features to enable

    Returns:
        List of paths that match any of the patterns
    """
    result = []
    matchers = [make_matcher(pattern, **kwargs) for pattern in patterns]

    for dirpath, dirnames, filenames in os.walk(root):
        rel_dirpath = os.path.relpath(dirpath, root)
        if rel_dirpath == ".":
            rel_dirpath = ""

        for filename in filenames:
            rel_path = os.path.join(rel_dirpath, filename)
            if any(matcher(rel_path) for matcher in matchers):
                result.append(os.path.join(dirpath, filename))

    return result
