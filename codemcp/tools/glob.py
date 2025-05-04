#!/usr/bin/env python3

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mcp.server.fastmcp import Context

from ..common import normalize_file_path
from ..main import get_chat_id_from_context, mcp

__all__ = [
    "glob_files",
    "glob",
    "render_result_for_assistant",
    "glob_tool",
]

# Define constants
MAX_RESULTS = 100


async def glob(
    pattern: str,
    path: str,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Find files matching a glob pattern.

    Args:
        pattern: The glob pattern to match files against
        path: The directory to search in
        options: Optional parameters for pagination (limit, offset)

    Returns:
        A dictionary with matched files and metadata
    """
    if options is None:
        options = {}

    limit = options.get("limit", MAX_RESULTS)
    offset = options.get("offset", 0)

    # Normalize the directory path
    absolute_path = normalize_file_path(path)

    # In non-test environment, verify the path exists
    if not os.environ.get("DESKAID_TESTING"):
        # Check if path exists
        if not os.path.exists(absolute_path):
            raise FileNotFoundError(f"Path does not exist: {path}")

        # Check if it's a directory
        if not os.path.isdir(absolute_path):
            raise ValueError(f"Path is not a directory: {path}")

    # Create Path object for the directory
    path_obj = Path(absolute_path)

    try:
        # Use pathlib's glob functionality to find matching files
        if pattern.startswith("/"):
            # Treat as absolute path if it starts with /
            matches = list(Path("/").glob(pattern[1:]))
        else:
            # Use relative path otherwise
            matches = list(path_obj.glob(pattern))

        # Filter out directories if they match the pattern
        matches = [match for match in matches if match.is_file()]

        # Sort matches by modification time (newest first)
        loop = asyncio.get_event_loop()

        # Get file stats asynchronously
        stats: List[Optional[os.stat_result]] = []
        for match in matches:
            file_stat = await loop.run_in_executor(
                None, lambda m=match: os.stat(m) if os.path.exists(m) else None
            )
            stats.append(file_stat)

        matches_with_stats: List[Tuple[Path, Optional[os.stat_result]]] = list(
            zip(matches, stats, strict=False)
        )

        # In tests, sort by filename for deterministic results
        if os.environ.get("NODE_ENV") == "test":
            matches_with_stats.sort(key=lambda x: str(x[0]))
        else:
            # Sort by modification time (newest first), with filename as tiebreaker
            matches_with_stats.sort(
                key=lambda x: (-(x[1].st_mtime if x[1] else 0), str(x[0]))
            )

        matches = [match for match, _ in matches_with_stats]

        # Convert Path objects to strings
        file_paths = [str(match) for match in matches]

        # Apply pagination
        total_files = len(file_paths)
        if offset > 0:
            file_paths = file_paths[offset:]

        truncated = total_files > (offset + limit)

        # Limit the number of results
        file_paths = file_paths[:limit]

        return {
            "files": file_paths,
            "truncated": truncated,
            "total": total_files,
        }
    except Exception as e:
        logging.exception(f"Error executing glob: {e!s}")
        raise


def render_result_for_assistant(output: Dict[str, Any]) -> str:
    """Render the results in a format suitable for the assistant.

    Args:
        output: The glob results dictionary

    Returns:
        A formatted string representation of the results
    """
    filenames = output.get("filenames", [])
    num_files = output.get("numFiles", 0)

    if num_files == 0:
        return "No files found"

    result = os.linesep.join(filenames)

    # Only add truncation message if results were actually truncated
    if output.get("truncated", False):
        result += (
            "\n(Results are truncated. Consider using a more specific path or pattern.)"
        )

    return result


async def glob_files(
    pattern: str,
    path: str | None = None,
    limit: int = MAX_RESULTS,
    offset: int = 0,
    chat_id: str | None = None,
) -> Dict[str, Any]:
    """Search for files matching a glob pattern.

    Args:
        pattern: The glob pattern to match files against
        path: The directory to search in (defaults to current working directory)
        limit: Maximum number of results to return
        offset: Number of results to skip (for pagination)
        chat_id: The unique ID of the current chat session

    Returns:
        A dictionary with matched files
    """
    # Use current working directory if path is not provided
    if path is None:
        path = os.getcwd()

    # Set up options for glob
    options = {
        "limit": limit,
        "offset": offset,
    }

    # Execute glob
    result = await glob(pattern, path, options)

    # Get matching files
    files = result.get("files", [])

    # Prepare output
    output = {
        "filenames": files,
        "numFiles": len(files),
        "truncated": result.get("truncated", False),
    }

    # Add formatted result for assistant
    output["resultForAssistant"] = render_result_for_assistant(output)

    return output


@mcp.tool()
async def glob_tool(ctx: Context, pattern: str, path: str) -> str:
    """Fast file pattern matching tool that works with any codebase size
    Supports glob patterns like "**/*.js" or "src/**/*.ts"
    Returns matching file paths sorted by modification time
    Use this tool when you need to find files by name patterns
    """
    # Get chat ID from context
    chat_id = get_chat_id_from_context(ctx)
    result = await glob_files(pattern, path, MAX_RESULTS, 0, chat_id)
    return result.get(
        "resultForAssistant", f"Found {result.get('numFiles', 0)} file(s)"
    )
