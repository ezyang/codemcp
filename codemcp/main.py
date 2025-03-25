#!/usr/bin/env python3

import logging
import os
from pathlib import Path

import click
from mcp.server.fastmcp import FastMCP

from .tools.chmod import chmod
from .tools.edit_file import edit_file_content
from .tools.glob import MAX_RESULTS, glob_files
from .tools.grep import grep_files
from .tools.init_project import init_project
from .tools.ls import ls_directory
from .tools.read_file import read_file_content
from .tools.rm import rm_file
from .tools.run_command import run_command
from .tools.think import think
from .tools.user_prompt import user_prompt as user_prompt_tool
from .tools.write_file import write_file_content

# Initialize FastMCP server
mcp = FastMCP("codemcp")


# NB: If you edit this, also edit codemcp/tools/init_project.py
@mcp.tool()
async def codemcp(
    subtool: str,
    *,
    path: str | None = None,
    content: object = None,  # Allow any type, will be serialized to string if needed
    old_string: str | None = None,
    new_string: str | None = None,
    offset: int | None = None,
    limit: int | None = None,
    description: str | None = None,
    pattern: str | None = None,
    include: str | None = None,
    command: str | None = None,
    arguments: list[str] | str | None = None,
    old_str: str | None = None,  # Added for backward compatibility
    new_str: str | None = None,  # Added for backward compatibility
    chat_id: str | None = None,  # Added for chat identification
    user_prompt: str | None = None,  # Added for InitProject commit message
    subject_line: str | None = None,  # Added for InitProject commit message
    reuse_head_chat_id: bool
    | None = None,  # Whether to reuse the chat ID from the HEAD commit
    thought: str | None = None,  # Added for Think tool
    mode: str | None = None,  # Added for Chmod tool
) -> str:
    """If and only if the user explicitly asks you to initialize codemcp with
    path, you should invoke this tool.  This will return instructions which you should
    IMMEDIATELY follow before continuing.

    If the user indicates they want to "amend" or "continue working" on a PR,
    you should set reuse_head_chat_id=True to continue using the same chat ID.

    In each response after the first one, you must call the UserPrompt tool
    with the user's verbatim message text.

    Arguments:
      subtool: The subtool to run (InitProject, UserPrompt, Think, ...)
      path: The path to the file or directory to operate on
      chat_id: A unique ID to identify the chat session (provided by InitProject and required for all tools EXCEPT InitProject)
      user_prompt: The user's original prompt verbatim, starting AFTER instructions to initialize codemcp (e.g., you should exclude "Initialize codemcp for PATH")
      subject_line: A short subject line in Git conventional commit format (for InitProject)
      reuse_head_chat_id: If True, reuse the chat ID from the HEAD commit instead of generating a new one (for InitProject)
      thought: The thought content for the Think tool (used for complex reasoning or cache memory)
      ... (there are other arguments which are documented later)
    """
    try:
        # Define expected parameters for each subtool
        expected_params = {
            "ReadFile": {"path", "offset", "limit", "chat_id"},
            "WriteFile": {"path", "content", "description", "chat_id"},
            "EditFile": {
                "path",
                "old_string",
                "new_string",
                "description",
                "old_str",
                "new_str",
                "chat_id",
            },
            "LS": {"path", "chat_id"},
            "InitProject": {
                "path",
                "user_prompt",
                "subject_line",
                "reuse_head_chat_id",
            },  # chat_id is not expected for InitProject as it's generated there
            "UserPrompt": {"user_prompt", "chat_id"},
            "RunCommand": {"path", "command", "arguments", "chat_id"},
            "Grep": {"pattern", "path", "include", "chat_id"},
            "Glob": {"pattern", "path", "limit", "offset", "chat_id"},
            "RM": {"path", "description", "chat_id"},
            "Think": {"thought", "chat_id"},
            "Chmod": {"path", "mode", "chat_id"},
        }

        # Check if subtool exists
        if subtool not in expected_params:
            raise ValueError(
                f"Unknown subtool: {subtool}. Available subtools: {', '.join(expected_params.keys())}"
            )

        # We no longer need to convert string arguments to list since run_command now only accepts strings

        # Normalize string inputs to ensure consistent newlines
        def normalize_newlines(s):
            """Normalize string to use \n for all newlines."""
            return s.replace("\r\n", "\n") if isinstance(s, str) else s

        # Normalize content, old_string, and new_string to use consistent \n newlines
        content = normalize_newlines(content)
        old_string = normalize_newlines(old_string)
        new_string = normalize_newlines(new_string)
        # Also normalize backward compatibility parameters
        old_str = normalize_newlines(old_str)
        new_str = normalize_newlines(new_str)
        # And user prompt which might contain code blocks
        user_prompt = normalize_newlines(user_prompt)

        # Get all provided non-None parameters
        provided_params = {
            param: value
            for param, value in {
                "path": path,
                "content": content,
                "old_string": old_string,
                "new_string": new_string,
                "offset": offset,
                "limit": limit,
                "description": description,
                "pattern": pattern,
                "include": include,
                "command": command,
                "arguments": arguments,
                # Include backward compatibility parameters
                "old_str": old_str,
                "new_str": new_str,
                # Chat ID for session identification
                "chat_id": chat_id,
                # InitProject commit message parameters
                "user_prompt": user_prompt,
                "subject_line": subject_line,
                # Whether to reuse the chat ID from the HEAD commit
                "reuse_head_chat_id": reuse_head_chat_id,
                # Think tool parameter
                "thought": thought,
                # Chmod tool parameter
                "mode": mode,
            }.items()
            if value is not None
        }

        # Check for unexpected parameters
        unexpected_params = set(provided_params.keys()) - expected_params[subtool]
        if unexpected_params:
            raise ValueError(
                f"Unexpected parameters for {subtool} subtool: {', '.join(unexpected_params)}"
            )

        # Check for required chat_id for all tools except InitProject
        if subtool != "InitProject" and chat_id is None:
            raise ValueError(f"chat_id is required for {subtool} subtool")

        # Now handle each subtool with its expected parameters
        if subtool == "ReadFile":
            if path is None:
                raise ValueError("path is required for ReadFile subtool")

            return await read_file_content(path, offset, limit, chat_id)

        if subtool == "WriteFile":
            if path is None:
                raise ValueError("path is required for WriteFile subtool")
            if description is None:
                raise ValueError("description is required for WriteFile subtool")

            import json

            # If content is not a string, serialize it to a string using json.dumps
            if content is not None and not isinstance(content, str):
                content_str = json.dumps(content)
            else:
                content_str = content or ""

            return await write_file_content(path, content_str, description, chat_id)

        if subtool == "EditFile":
            if path is None:
                raise ValueError("path is required for EditFile subtool")
            if description is None:
                raise ValueError("description is required for EditFile subtool")
            if old_string is None and old_str is None:
                # TODO: I want telemetry to tell me when this occurs.
                raise ValueError(
                    "Either old_string or old_str is required for EditFile subtool (use empty string for new file creation)"
                )

            # Accept either old_string or old_str (prefer old_string if both are provided)
            old_content = old_string or old_str or ""
            # Accept either new_string or new_str (prefer new_string if both are provided)
            new_content = new_string or new_str or ""
            return await edit_file_content(
                path, old_content, new_content, None, description, chat_id
            )

        if subtool == "LS":
            if path is None:
                raise ValueError("path is required for LS subtool")

            return await ls_directory(path, chat_id)

        if subtool == "InitProject":
            if path is None:
                raise ValueError("path is required for InitProject subtool")
            if user_prompt is None:
                raise ValueError("user_prompt is required for InitProject subtool")
            if subject_line is None:
                raise ValueError("subject_line is required for InitProject subtool")
            if reuse_head_chat_id is None:
                reuse_head_chat_id = (
                    False  # Default value in main.py only, not in the implementation
                )

            return await init_project(
                path, user_prompt, subject_line, reuse_head_chat_id
            )

        if subtool == "RunCommand":
            # When is something a command as opposed to a subtool?  They are
            # basically the same thing, but commands are always USER defined.
            # This means we shove them all in RunCommand so they are guaranteed
            # not to conflict with codemcp's subtools.

            if path is None:
                raise ValueError("path is required for RunCommand subtool")
            if command is None:
                raise ValueError("command is required for RunCommand subtool")

            return await run_command(
                path,
                command,
                arguments,
                chat_id,
            )

        if subtool == "Grep":
            if pattern is None:
                raise ValueError("pattern is required for Grep subtool")

            if path is None:
                raise ValueError("path is required for Grep subtool")

            try:
                result = await grep_files(pattern, path, include, chat_id)
                return result.get(
                    "resultForAssistant",
                    f"Found {result.get('numFiles', 0)} file(s)",
                )
            except Exception as e:
                # Log the error but don't suppress it - let it propagate
                logging.error(f"Exception in grep subtool: {e!s}", exc_info=True)
                raise

        if subtool == "Glob":
            if pattern is None:
                raise ValueError("pattern is required for Glob subtool")

            if path is None:
                raise ValueError("path is required for Glob subtool")

            try:
                result = await glob_files(
                    pattern,
                    path,
                    limit=limit if limit is not None else MAX_RESULTS,
                    offset=offset if offset is not None else 0,
                    chat_id=chat_id,
                )
                return result.get(
                    "resultForAssistant",
                    f"Found {result.get('numFiles', 0)} file(s)",
                )
            except Exception as e:
                # Log the error but don't suppress it - let it propagate
                logging.error(f"Exception in glob subtool: {e!s}", exc_info=True)
                raise

        if subtool == "UserPrompt":
            if user_prompt is None:
                raise ValueError("user_prompt is required for UserPrompt subtool")

            return await user_prompt_tool(user_prompt, chat_id)

        if subtool == "RM":
            if path is None:
                raise ValueError("path is required for RM subtool")
            if description is None:
                raise ValueError("description is required for RM subtool")

            return await rm_file(path, description, chat_id)

        if subtool == "Think":
            if thought is None:
                raise ValueError("thought is required for Think subtool")

            return await think(thought, chat_id)

        if subtool == "Chmod":
            if path is None:
                raise ValueError("path is required for Chmod subtool")
            if mode is None:
                raise ValueError("mode is required for Chmod subtool")

            result = await chmod(path, mode, chat_id)
            return result.get("resultForAssistant", "Chmod operation completed")
    except Exception:
        logging.error("Exception", exc_info=True)
        raise


def configure_logging(log_file="codemcp.log"):
    """Configure logging to write to both a file and the console.

    The log level is determined from the configuration file.
    It can be overridden by setting the DESKAID_DEBUG environment variable.
    Example: DESKAID_DEBUG=1 python -m codemcp

    The log directory is read from the configuration file's logger.path setting.
    By default, logs are written to $HOME/.codemcp.

    By default, logs from the 'mcp' module are filtered out unless in debug mode.
    """
    from .config import get_logger_path, get_logger_verbosity

    log_dir = get_logger_path()
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_file)

    # Get log level from config, with environment variable override
    log_level_str = os.environ.get("DESKAID_DEBUG_LEVEL") or get_logger_verbosity()

    # Map string log level to logging constants
    log_level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    # Convert string to logging level, default to INFO if invalid
    log_level = log_level_map.get(log_level_str.upper(), logging.INFO)

    # Force DEBUG level if DESKAID_DEBUG is set (for backward compatibility)
    debug_mode = False
    if os.environ.get("DESKAID_DEBUG"):
        log_level = logging.DEBUG
        debug_mode = True

    # Create a root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear any existing handlers
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Create file handler
    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(log_level)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)

    # Create formatter and add it to the handlers
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Set up filter to exclude logs from 'mcp' module unless in debug mode
    class ModuleFilter(logging.Filter):
        def filter(self, record):
            # Allow all logs in debug mode, otherwise filter 'mcp' module
            if debug_mode or not record.name.startswith("mcp"):
                return True
            return False

    module_filter = ModuleFilter()
    file_handler.addFilter(module_filter)
    console_handler.addFilter(module_filter)

    # Add the handlers to the root logger
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.info(f"Logging configured. Log file: {log_path}")
    logging.info(f"Log level set to: {logging.getLevelName(log_level)}")
    if not debug_mode:
        logging.info("Logs from 'mcp' module are being filtered")


def init_codemcp_project(path: str) -> str:
    """Initialize a new codemcp project.

    Args:
        path: Path to initialize the project in

    Returns:
        Message indicating success or failure
    """
    import subprocess

    try:
        # Convert to Path object and resolve to absolute path
        project_path = Path(path).resolve()

        # Create directory if it doesn't exist
        project_path.mkdir(parents=True, exist_ok=True)

        # Check if git repository already exists
        git_dir = project_path / ".git"
        if not git_dir.exists():
            # Initialize git repository
            subprocess.run(["git", "init"], cwd=project_path, check=True)
            print(f"Initialized git repository in {project_path}")
        else:
            print(f"Git repository already exists in {project_path}")

        # Create empty codemcp.toml file if it doesn't exist
        config_file = project_path / "codemcp.toml"
        if not config_file.exists():
            with open(config_file, "w") as f:
                f.write("# codemcp configuration file\n\n")
            print(f"Created empty codemcp.toml file in {project_path}")
        else:
            print(f"codemcp.toml file already exists in {project_path}")

        # Make initial commit if there are no commits yet
        try:
            # Check if there are any commits
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=project_path,
                check=False,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                # No commits yet, add codemcp.toml and make initial commit
                subprocess.run(
                    ["git", "add", "codemcp.toml"], cwd=project_path, check=True
                )
                subprocess.run(
                    ["git", "commit", "-m", "chore: initialize codemcp project"],
                    cwd=project_path,
                    check=True,
                )
                print("Created initial commit with codemcp.toml")
            else:
                print("Repository already has commits, not creating initial commit")
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to create initial commit: {e}")

        return f"Successfully initialized codemcp project in {project_path}"
    except Exception as e:
        return f"Error initializing project: {e}"


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """CodeMCP: Command-line interface for MCP server and project management."""
    # If no subcommand is provided, run the MCP server (for backwards compatibility)
    if ctx.invoked_subcommand is None:
        run()


@cli.command()
@click.argument("path", type=click.Path(), default=".")
def init(path):
    """Initialize a new codemcp project with an empty codemcp.toml file and git repository."""
    result = init_codemcp_project(path)
    click.echo(result)


def run():
    """Run the MCP server."""
    configure_logging()
    mcp.run()
