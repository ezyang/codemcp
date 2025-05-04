#!/usr/bin/env python3

import os
from typing import List

from mcp.server.fastmcp import Context

from ..common import (
    MAX_LINE_LENGTH,
    MAX_LINES_TO_READ,
    MAX_OUTPUT_SIZE,
    normalize_file_path,
)
from ..git_query import find_git_root
from ..main import get_chat_id_from_context, mcp
from ..rules import get_applicable_rules_content

__all__ = [
    "read_file_content",
    "read_file",
]


async def read_file_content(
    file_path: str,
    offset: int | None = None,
    limit: int | None = None,
    chat_id: str | None = None,
) -> str:
    """Read a file's content with optional offset and limit.

    Args:
        file_path: The absolute path to the file to read
        offset: The line number to start reading from (1-indexed)
        limit: The number of lines to read
        chat_id: The unique ID of the current chat session

    Returns:
        The file content as a string

    """
    # Normalize the file path
    full_file_path = normalize_file_path(file_path)

    # Validate the file path
    if not os.path.exists(full_file_path):
        # Try to find a similar file (stub - would need implementation)
        raise FileNotFoundError(f"File does not exist: {file_path}")

    if os.path.isdir(full_file_path):
        raise IsADirectoryError(f"Path is a directory, not a file: {file_path}")

    # Check file size before reading
    file_size = os.path.getsize(full_file_path)
    if file_size > MAX_OUTPUT_SIZE and not offset and not limit:
        raise ValueError(
            f"File content ({file_size // 1024}KB) exceeds maximum allowed size ({MAX_OUTPUT_SIZE // 1024}KB). Please use offset and limit parameters to read specific portions of the file."
        )

    # Handle text files - use async file operations with anyio
    from ..async_file_utils import async_readlines

    all_lines = await async_readlines(
        full_file_path, encoding="utf-8", errors="replace"
    )

    # Get total line count
    total_lines = len(all_lines)

    # Handle offset (convert from 1-indexed to 0-indexed)
    line_offset = 0 if offset is None else (offset - 1 if offset > 0 else 0)

    # Apply offset and limit
    if line_offset >= total_lines:
        raise IndexError(
            f"Offset {offset} is beyond the end of the file (total lines: {total_lines})"
        )

    max_lines = MAX_LINES_TO_READ if limit is None else limit
    selected_lines = all_lines[line_offset : line_offset + max_lines]

    # Process lines (truncate long lines)
    processed_lines: List[str] = []
    for line in selected_lines:
        if len(line) > MAX_LINE_LENGTH:
            processed_lines.append(
                line[:MAX_LINE_LENGTH] + "... (line truncated)",
            )
        else:
            processed_lines.append(line)

    # Add line numbers (1-indexed)
    numbered_lines: List[str] = []
    for i, line in enumerate(processed_lines):
        line_number = line_offset + i + 1  # 1-indexed line number
        numbered_lines.append(f"{line_number:6}\t{line.rstrip()}")

    content = "\n".join(numbered_lines)

    # Add a message if we truncated the file
    if line_offset + len(processed_lines) < total_lines:
        content += f"\n... (file truncated, showing {len(processed_lines)} of {total_lines} lines)"

    # Apply relevant cursor rules
    # Find git repository root
    repo_root = find_git_root(os.path.dirname(full_file_path))

    if repo_root:
        # Add applicable rules content
        content += get_applicable_rules_content(repo_root, full_file_path)

    return content


@mcp.tool()
async def read_file(
    ctx: Context, file_path: str, offset: int | None = None, limit: int | None = None
) -> str:
    """Reads a file from the local filesystem. The path parameter must be an absolute path, not a relative path.
    By default, it reads up to 1000 lines starting from the beginning of the file. You can optionally specify a
    line offset and limit (especially handy for long files), but it's recommended to read the whole file by not
    providing these parameters. Any lines longer than 1000 characters will be truncated. For image files, the tool
    will display the image for you.
    """
    # Get chat ID from context
    chat_id = get_chat_id_from_context(ctx)
    return await read_file_content(file_path, offset, limit, chat_id)
