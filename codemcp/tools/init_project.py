#!/usr/bin/env python3

import asyncio
import logging
import os
import re
from typing import Any, Dict, List, Optional

import tomli

from ..common import normalize_file_path
from ..git import get_repository_root, is_git_repository
from ..mcp import mcp

__all__ = [
    "init_project",
]


def _slugify(text: str) -> str:
    """Convert a string to an alphanumeric + hyphen identifier.

    Args:
        text: The string to convert

    Returns:
        A string containing only alphanumeric characters and hyphens
    """
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and non-alphanumeric characters with hyphens
    text = re.sub(r"[^a-z0-9]+", "-", text)
    # Remove leading and trailing hyphens
    text = text.strip("-")
    # If empty after processing, return a default value
    if not text:
        return "untitled"
    # Limit length to avoid excessively long identifiers
    return text[:50]


# pyright: reportUnusedFunction=false
def _generate_command_docs(command_docs: Dict[str, str]) -> str:  # noqa: F811
    """Generate documentation for commands from the command_docs dictionary.

    Args:
        command_docs: A dictionary of command names to their documentation

    Returns:
        A formatted string with command documentation
    """
    if not command_docs:
        return ""

    docs: List[str] = []
    for cmd_name, doc in command_docs.items():
        docs.append(f"\n- {cmd_name}: {doc}")

    return "\n\nCommand documentation:" + "".join(docs)


async def _generate_chat_id(directory: str, description: Optional[str] = None) -> str:
    """Generate a unique chat ID based on a counter stored in the git repository.

    Args:
        directory: The directory path within the git repository
        description: Optional description to use for the human-readable part of the ID

    Returns:
        A string containing the unique chat ID, e.g., "23-feat-use-description"
    """
    # Generate a human-readable short identifier from the description if provided
    human_readable_part = _slugify(description) if description else "untitled"

    try:
        # Check if we're in a git repository
        if not await is_git_repository(directory):
            logging.warning(f"Not in a git repository: {directory}")
            # Return a fallback ID if not in a git repository
            return f"0-{human_readable_part}"

        # Get the repository root
        repo_root = await get_repository_root(directory)

        # Create .git/codemcp directory if it doesn't exist
        codemcp_dir = os.path.join(repo_root, ".git", "codemcp")
        os.makedirs(codemcp_dir, exist_ok=True)

        # Path to the counter file
        counter_file = os.path.join(codemcp_dir, "counter")

        # Read the current counter value or initialize to 0
        counter_value = 0
        asyncio.get_event_loop()

        if os.path.exists(counter_file):
            try:
                from ..async_file_utils import async_open_text

                read_counter = await async_open_text(counter_file)
                counter_value = int(read_counter.strip())
            except (ValueError, IOError) as e:
                logging.warning(f"Error reading counter file: {e}")

        # Increment the counter
        counter_value += 1

        # Write the new counter value
        try:
            from ..async_file_utils import async_write_text

            await async_write_text(counter_file, str(counter_value))
        except IOError as e:
            logging.warning(f"Error writing to counter file: {e}")

        # Return the chat ID in the format "number-human-readable-part"
        return f"{counter_value}-{human_readable_part}"

    except Exception as e:
        logging.warning(f"Exception generating chat ID: {e!s}", exc_info=True)
        # Return a fallback ID in case of errors
        return f"0-{human_readable_part}"


@mcp.tool()
async def init_project(
    directory: Optional[str] = None,
    user_prompt: str = "",
    subject_line: str = "",
    reuse_head_chat_id: bool = False,
    path: Optional[str] = None,
) -> str:
    """If and only if the user explicitly asks you to initialize codemcp with
    path, you should invoke this tool. This will return instructions which you should
    IMMEDIATELY follow before continuing, in particular, it will explain other ways
    you can invoke this tool.

    If the user indicates they want to "amend" or "continue working" on a PR,
    you should set reuse_head_chat_id=True to continue using the same chat ID.

    Args:
        directory: The directory path containing the codemcp.toml file
        user_prompt: The user's original prompt verbatim, starting AFTER instructions to initialize codemcp (e.g., you should exclude "Initialize codemcp for PATH")
        subject_line: A short subject line in Git conventional commit format
        reuse_head_chat_id: Whether to reuse the chat ID from the HEAD commit
        path: Alias for directory parameter (for backward compatibility)

    Returns:
        A string containing the system prompt plus any project_prompt from the config,
        or an error message if validation fails

    """
    try:
        # Use path as an alias for directory if directory is not provided
        effective_directory = directory if directory is not None else path
        if effective_directory is None:
            raise ValueError("Either directory or path must be provided")

        # Normalize the directory path
        full_dir_path = normalize_file_path(effective_directory)

        # Validate the directory path
        if not os.path.exists(full_dir_path):
            raise FileNotFoundError(f"Directory does not exist: {effective_directory}")

        if not os.path.isdir(full_dir_path):
            raise NotADirectoryError(f"Path is not a directory: {effective_directory}")

        # Check if the directory is a Git repository
        is_git_repo = await is_git_repository(full_dir_path)

        # Build path to codemcp.toml file
        rules_file_path = os.path.join(full_dir_path, "codemcp.toml")
        has_codemcp_toml = os.path.exists(rules_file_path)

        # If validation fails, return appropriate error messages
        if not is_git_repo and not has_codemcp_toml:
            raise ValueError(
                f"The directory is not a valid codemcp project. Please initialize a Git repository with 'git init' and create a codemcp.toml file with 'touch codemcp.toml'."
            )
        elif not is_git_repo:
            raise ValueError(
                f"The directory is not a Git repository. Please initialize it with 'git init'."
            )
        elif not has_codemcp_toml:
            raise ValueError(
                f"The directory does not contain a codemcp.toml file. Please create one with 'touch codemcp.toml'."
            )

        # If reuse_head_chat_id is True, try to get the chat ID from the HEAD commit
        chat_id = None
        if reuse_head_chat_id:
            from ..git import get_head_commit_chat_id

            # We already validated that we're in a git repository
            chat_id = await get_head_commit_chat_id(full_dir_path)
            if not chat_id:
                logging.warning(
                    "reuse_head_chat_id was True but no chat ID found in HEAD commit, generating new chat ID"
                )

        # If not reusing or no chat ID was found in HEAD, generate a new one
        if not chat_id:
            chat_id = await _generate_chat_id(full_dir_path, subject_line)

        # Create an empty commit with user prompt and subject line
        from ..git import create_commit_reference

        # We already validated that we're in a git repository
        # Format the commit message according to the specified format
        commit_body = user_prompt
        commit_msg = f"{subject_line}\n\n{commit_body}\n\ncodemcp-id: {chat_id}"

        # Create a commit reference instead of creating a regular commit
        # This will not advance HEAD but store the commit in refs/codemcp/<chat_id>
        _, _ = await create_commit_reference(
            full_dir_path,
            chat_id=chat_id,
            commit_msg=commit_msg,
        )

        project_prompt = ""
        command_docs: Dict[str, str] = {}
        rules_config: Dict[str, Any] = {}

        # We've already confirmed that codemcp.toml exists
        try:
            from ..async_file_utils import async_open_binary

            rules_data = await async_open_binary(rules_file_path)
            # tomli.loads expects a string, but we have bytes, so use tomli.load with an io.BytesIO object
            import io

            rules_config = tomli.load(io.BytesIO(rules_data))

            # Extract project_prompt if it exists
            if "project_prompt" in rules_config:
                project_prompt = rules_config["project_prompt"]

            # Extract commands and their documentation
            command_list = rules_config.get("commands", {})
            ", ".join(command_list.keys())

            # Process command documentation
            for cmd_name, cmd_config in command_list.items():
                if isinstance(cmd_config, dict) and "doc" in cmd_config:
                    command_docs[cmd_name] = cmd_config["doc"]

        except Exception as e:
            logging.warning(
                f"Exception suppressed when reading codemcp.toml: {e!s}",
                exc_info=True,
            )
            raise ValueError(f"Error reading codemcp.toml file: {e!s}")

        # Default system prompt, cribbed from claude code
        # TODO: Figure out if we want Sonnet to make determinations about what
        # goes in the global prompt.  The current ARCHITECTURE.md rule is
        # mostly to make sure we don't lose important information that was
        # conveyed in chats.
        # TODO: This prompt is pretty long, maybe we want it shorter
        # NB: If you edit this, also edit codemcp/main.py
        system_prompt = f"""\
You are an AI assistant that helps users with software engineering tasks. Use the instructions below and the tools available to you to assist the user.

# Tone and style
IMPORTANT: You should minimize output tokens as much as possible while maintaining helpfulness, quality, and accuracy. Only address the specific query or task at hand, avoiding tangential information unless absolutely critical for completing the request. If you can answer in 1-3 sentences or a short paragraph, please do.
IMPORTANT: You should NOT answer with unnecessary preamble or postamble (such as explaining your code or summarizing your action), unless the user asks you to.

# Proactiveness
You are allowed to be proactive, but only when the user asks you to do something. You should strive to strike a balance between:
1. Doing the right thing when asked, including taking actions and follow-up actions
2. Not surprising the user with actions you take without asking
For example, if the user asks you how to approach something, you should do your best to answer their question first, and not immediately jump into taking actions.
3. Do not add additional code explanation summary unless requested by the user. After working on a file, just stop, rather than providing an explanation of what you did.

# Following conventions
When making changes to files, first understand the file's code conventions. Mimic code style, use existing libraries and utilities, and follow existing patterns.
- NEVER assume that a given library is available, even if it is well known. Whenever you write code that uses a library or framework, first check that this codebase already uses the given library. For example, you might look at neighboring files, or check the package.json (or cargo.toml, and so on depending on the language).
- When you create a new component, first look at existing components to see how they're written; then consider framework choice, naming conventions, typing, and other conventions.
- When you edit a piece of code, first look at the code's surrounding context (especially its imports) to understand the code's choice of frameworks and libraries. Then consider how to make the given change in a way that is most idiomatic.
- Always follow security best practices. Never introduce code that exposes or logs secrets and keys. Never commit secrets or keys to the repository.

# Code style
- Do not add comments to the code you write, unless the user asks you to, or the code is complex and requires additional context.

# Tool usage policy
- If you intend to call multiple tools and there are no dependencies between the calls, make all of the independent calls in the same function_calls block.

# Chat ID and Git tracking
This chat has been assigned a chat ID: {chat_id}
When you use any tool, you MUST always include this chat ID as the chat_id parameter.

# Git Commit Hash
This project uses Git commit hashes to track changes across conversations. After each operation that modifies files, the current Git commit hash will be reported. The commit hash represents the current state of the repository.
"""

        # Combine system prompt, global prompt
        combined_prompt = system_prompt
        if project_prompt:
            combined_prompt += "\n\n" + project_prompt

        return f"""
# Chat ID and Git tracking
This chat has been assigned a chat ID: {chat_id}
When you use any tool, you MUST always include this chat ID as the chat_id parameter.
"""
    except Exception as e:
        logging.warning(
            f"Exception suppressed during project initialization: {e!s}", exc_info=True
        )
        return f"Error initializing project: {e!s}"
