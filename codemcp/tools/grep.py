#!/usr/bin/env python3

import logging
import os
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from mcp.server.fastmcp import Context

from ..common import normalize_file_path
from ..git import is_git_repository
from ..main import get_chat_id_from_context, mcp
from ..shell import run_command

__all__ = [
    "grep_files",
    "git_grep",
    "render_result_for_assistant",
    "TOOL_NAME_FOR_PROMPT",
    "DESCRIPTION",
    "grep",
]

# Define constants
MAX_RESULTS = 100
TOOL_NAME_FOR_PROMPT = "Grep"
DESCRIPTION = f"""
Searches for files containing a specified pattern (regular expression) using git grep.
Files with a match are returned, up to a maximum of {MAX_RESULTS} files.
Note that this tool only works inside git repositories.

Example:
  grep "function.*hello" /path/to/repo  # Find files containing functions with "hello" in their name
  grep "console\\.log" /path/to/repo --include="*.js"  # Find JS files with console.log statements
  grep "pattern" /path/to/file.js  # Search for pattern in a specific file
"""


async def git_grep(
    pattern: str,
    path: str | None = None,
    include: str | None = None,
) -> list[str]:
    """Execute git grep to search for pattern in files.

    Args:
        pattern: The regular expression pattern to search for
        path: The directory or file to search in (must be in a git repository)
        include: Optional file pattern to filter the search

    Returns:
        A list of file paths with matches

    """
    if path is None:
        raise ValueError("Path must be provided for git grep")

    # Normalize the directory path
    absolute_path = normalize_file_path(path)

    # Verify this is a git repository - this check uses the mocked version in tests
    if not await is_git_repository(absolute_path):
        raise ValueError(f"The provided path is not in a git repository: {path}")

    # In non-test environment, verify the path exists
    if not os.environ.get("DESKAID_TESTING"):
        # Check if path exists
        if not os.path.exists(absolute_path):
            raise FileNotFoundError(f"Path does not exist: {path}")

        # If it's a file, adjust the command to use the file's directory
        # and restrict search to the specific file
        is_file = os.path.isfile(absolute_path)
        if not os.path.isdir(absolute_path) and not is_file:
            raise ValueError(f"Path is neither a directory nor a file: {path}")

    # Build git grep command
    # -l: list file names only
    # -i: case insensitive matching
    args = ["git", "grep", "-li", pattern]

    # Check if the path is a file
    is_file = (
        os.path.isfile(absolute_path)
        if not os.environ.get("DESKAID_TESTING")
        else False
    )

    # If it's a file, get the directory and restrict search to the specific file
    if is_file:
        file_dir = os.path.dirname(absolute_path)
        file_name = os.path.basename(absolute_path)

        # Add the specific file to search
        args.extend(["--", file_name])

        # Update absolute_path to the directory containing the file
        absolute_path = file_dir
    # Otherwise, add file pattern if specified
    elif include:
        args.extend(["--", include])

    logging.debug(f"Executing git grep command: {' '.join(args)}")

    try:
        # Execute git grep command asynchronously
        # Use explicit parameters to avoid confusion in mocking
        result = await run_command(
            cmd=args,
            cwd=absolute_path,
            capture_output=True,
            text=True,
            check=False,  # Don't raise exception if git grep doesn't find matches
        )

        # git grep returns exit code 1 when no matches are found, which is normal
        if result.returncode not in [0, 1]:
            logging.error(
                f"git grep failed with exit code {result.returncode}: {result.stderr}",
            )
            raise subprocess.SubprocessError(f"git grep failed: {result.stderr}")

        # Process results - split by newline and filter empty lines
        matches = [line.strip() for line in result.stdout.split() if line.strip()]

        # Convert to absolute paths
        matches = [
            os.path.join(absolute_path, match)
            for match in matches
            if isinstance(match, str)
        ]

        return matches
    except subprocess.SubprocessError as e:
        logging.exception(f"Error executing git grep: {e!s}")
        raise


def render_result_for_assistant(output: Dict[str, Any]) -> str:
    """Render the results in a format suitable for the assistant.

    Args:
        output: The grep results dictionary

    Returns:
        A formatted string representation of the results

    """
    num_files = output.get("numFiles", 0)
    filenames = output.get("filenames", [])

    if num_files == 0:
        return "No files found"

    result = f"Found {num_files} file{'' if num_files == 1 else 's'}\n{os.linesep.join(filenames[:MAX_RESULTS])}"
    if num_files > MAX_RESULTS:
        result += (
            "\n(Results are truncated. Consider using a more specific path or pattern.)"
        )

    return result


async def grep_files(
    pattern: str,
    path: str | None = None,
    include: str | None = None,
    chat_id: str | None = None,
) -> dict[str, Any]:
    """Search for a pattern in files within a directory or in a specific file.

    Args:
        pattern: The regular expression pattern to search for
        path: The directory or file to search in (must be in a git repository)
        include: Optional file pattern to filter the search
        chat_id: The unique ID of the current chat session

    Returns:
        A dictionary with matched files

    """

    # Execute git grep asynchronously
    matches = await git_grep(pattern, path, include)

    # Sort matches
    # Use asyncio for getting file stats
    import asyncio

    loop = asyncio.get_event_loop()

    # Get file stats asynchronously
    stats: List[Optional[os.stat_result]] = []
    for match in matches:
        file_stat = await loop.run_in_executor(
            None, lambda m=match: os.stat(m) if os.path.exists(m) else None
        )
        stats.append(file_stat)

    matches_with_stats: List[Tuple[str, Optional[os.stat_result]]] = list(
        zip(matches, stats, strict=False)
    )

    # In tests, sort by filename for deterministic results
    if os.environ.get("NODE_ENV") == "test":
        matches_with_stats.sort(key=lambda x: x[0])
    else:
        # Sort by modification time (newest first), with filename as tiebreaker
        matches_with_stats.sort(key=lambda x: (-(x[1].st_mtime if x[1] else 0), x[0]))

    matches = [match for match, _ in matches_with_stats]

    # Prepare output
    output: Dict[str, Any] = {
        "filenames": matches[:MAX_RESULTS],
        "numFiles": len(matches),
    }

    # Add formatted result for assistant
    formatted_result = render_result_for_assistant(output)
    output["resultForAssistant"] = formatted_result

    return output


@mcp.tool()
async def grep(
    ctx: Context, pattern: str, path: str, include: str | None = None
) -> str:
    """Searches for files containing a specified pattern (regular expression) using git grep.
    Files with a match are returned, up to a maximum of 100 files.
    Note that this tool only works inside git repositories.

    Example:
      Grep "function.*hello" /path/to/repo  # Find files containing functions with "hello" in their name
      Grep "console\\.log" /path/to/repo --include="*.js"  # Find JS files with console.log statements
    """
    # Get chat ID from context
    chat_id = get_chat_id_from_context(ctx)
    result = await grep_files(pattern, path, include, chat_id)
    return result.get(
        "resultForAssistant", f"Found {result.get('numFiles', 0)} file(s)"
    )
