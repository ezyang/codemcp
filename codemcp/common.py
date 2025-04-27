#!/usr/bin/env python3

import os
from typing import List, Optional, Union

# Constants
MAX_LINES_TO_READ = 1000
MAX_LINE_LENGTH = 1000
MAX_OUTPUT_SIZE = 0.25 * 1024 * 1024  # 0.25MB in bytes
START_CONTEXT_LINES = 5  # Number of lines to keep from the beginning when truncating

__all__ = [
    "MAX_LINES_TO_READ",
    "MAX_LINE_LENGTH",
    "MAX_OUTPUT_SIZE",
    "START_CONTEXT_LINES",
    "is_image_file",
    "get_image_format",
    "normalize_file_path",
    "get_edit_snippet",
    "truncate_output_content",
    "find_codemcp_root",
]


def is_image_file(file_path: str) -> bool:
    """Check if a file is an image based on its MIME type."""
    # Stub implementation - we don't care about image support
    return False


def get_image_format(file_path: str) -> str:
    """Get the format of an image file."""
    # Stub implementation - we don't care about image support
    return "png"


def normalize_file_path(file_path: str) -> str:
    """Normalize a file path to an absolute path.

    Expands the tilde character (~) if present to the user's home directory.
    """
    # Expand tilde to home directory
    expanded_path = os.path.expanduser(file_path)

    if not os.path.isabs(expanded_path):
        return os.path.abspath(os.path.join(os.getcwd(), expanded_path))
    return os.path.abspath(expanded_path)


def get_edit_snippet(
    original_text: str,
    old_str: str,
    new_str: str,
    context_lines: int = 4,
) -> str:
    """Generate a snippet of the edited file showing the changes with line numbers.

    Args:
        original_text: The original file content
        old_str: The text that was replaced
        new_str: The new text that replaced old_str
        context_lines: Number of lines to show before and after the change

    Returns:
        A formatted string with line numbers and the edited content

    """
    # Find where the edit occurs
    before_text = original_text.split(old_str)[0]
    before_lines = before_text.split("\n")
    replacement_line = len(before_lines)

    # Get the edited content
    edited_text = original_text.replace(old_str, new_str)
    edited_lines = edited_text.split("\n")

    # Calculate the start and end line numbers for the snippet
    start_line = max(0, replacement_line - context_lines)
    end_line = min(
        len(edited_lines),
        replacement_line + context_lines + len(new_str.split("\n")),
    )

    # Extract the snippet lines
    snippet_lines = edited_lines[start_line:end_line]

    # Format with line numbers
    result: List[str] = []
    for i, line in enumerate(snippet_lines):
        line_num = start_line + i + 1
        result.append(f"{line_num:4d} | {line}")

    return "\n".join(result)


def truncate_output_content(
    content: Union[str, bytes, None], prefer_end: bool = True
) -> str:
    """Truncate command output content to a reasonable size.

    When prefer_end is True, this function prioritizes keeping content from the end
    of the output, showing some initial context and truncating the middle portion
    if necessary.

    Args:
        content: The command output content to truncate
        prefer_end: Whether to prefer keeping content from the end of the output

    Returns:
        The truncated content with appropriate indicators
    """
    if content is None:
        return ""
    if not content:
        return str(content)

    # Convert bytes to str if needed
    if isinstance(content, bytes):
        try:
            content = content.decode("utf-8")
        except UnicodeDecodeError:
            return "[Binary content cannot be displayed]"

    lines = content.splitlines()
    total_lines = len(lines)

    # If number of lines is within the limit, check individual line lengths
    if total_lines <= MAX_LINES_TO_READ:
        # Process line lengths
        processed_lines: List[str] = []
        for line in lines:
            if len(line) > MAX_LINE_LENGTH:
                processed_lines.append(line[:MAX_LINE_LENGTH] + "... (line truncated)")
            else:
                processed_lines.append(line)

        return "\n".join(processed_lines)

    # We need to truncate lines, decide based on preference
    if prefer_end:
        # Keep some lines from the start and prioritize the end
        start_lines = lines[:START_CONTEXT_LINES]

        # Calculate how many lines we can keep from the end
        end_lines_count = MAX_LINES_TO_READ - START_CONTEXT_LINES
        end_lines = lines[-end_lines_count:]

        truncated_content = (
            "\n".join(start_lines)
            + f"\n\n... (output truncated, {total_lines - START_CONTEXT_LINES - end_lines_count} lines omitted) ...\n\n"
            + "\n".join(end_lines)
        )
    else:
        # Standard truncation from the beginning (similar to read_file_content)
        truncated_content = "\n".join(lines[:MAX_LINES_TO_READ])
        if total_lines > MAX_LINES_TO_READ:
            truncated_content += f"\n... (output truncated, showing {MAX_LINES_TO_READ} of {total_lines} lines)"

    return truncated_content


def find_codemcp_root(start_path: str) -> Optional[str]:
    """Find the root directory containing codemcp.toml, starting from the given path.

    This function traverses up the directory tree from the given path until it finds
    a directory containing a codemcp.toml file, which indicates the project root.

    Args:
        start_path: The path to start searching from (can be a file or directory)

    Returns:
        The absolute path to the directory containing codemcp.toml, or None if not found
    """
    path = os.path.abspath(start_path)

    # If the path is a file, start from its parent directory
    if os.path.isfile(path):
        path = os.path.dirname(path)

    while path:
        config_path = os.path.join(path, "codemcp.toml")
        if os.path.isfile(config_path):
            return path

        parent = os.path.dirname(path)
        if parent == path:  # Reached filesystem root
            return None

        path = parent

    return None
