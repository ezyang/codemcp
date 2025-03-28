#!/usr/bin/env python3

import logging
import os
import re
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
    arguments: str | None = None,
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
        def normalize_newlines(s: object) -> object:
            """Normalize string to use \n for all newlines."""
            return s.replace("\r\n", "\n") if isinstance(s, str) else s

        # Normalize content, old_string, and new_string to use consistent \n newlines
        content_norm = normalize_newlines(content)
        old_string_norm = normalize_newlines(old_string)
        new_string_norm = normalize_newlines(new_string)
        # Also normalize backward compatibility parameters
        old_str_norm = normalize_newlines(old_str)
        new_str_norm = normalize_newlines(new_str)
        # And user prompt which might contain code blocks
        user_prompt_norm = normalize_newlines(user_prompt)

        # Get all provided non-None parameters
        provided_params = {
            param: value
            for param, value in {
                "path": path,
                "content": content_norm,
                "old_string": old_string_norm,
                "new_string": new_string_norm,
                "offset": offset,
                "limit": limit,
                "description": description,
                "pattern": pattern,
                "include": include,
                "command": command,
                "arguments": arguments,
                # Include backward compatibility parameters
                "old_str": old_str_norm,
                "new_str": new_str_norm,
                # Chat ID for session identification
                "chat_id": chat_id,
                # InitProject commit message parameters
                "user_prompt": user_prompt_norm,
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

            if chat_id is None:
                raise ValueError("chat_id is required for WriteFile subtool")
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
            if chat_id is None:
                raise ValueError("chat_id is required for EditFile subtool")
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

            # Ensure chat_id is provided
            if chat_id is None:
                raise ValueError("chat_id is required for RunCommand subtool")

            # Ensure arguments is a string for run_command
            args_str = (
                arguments
                if isinstance(arguments, str) or arguments is None
                else " ".join(arguments)
            )
            return await run_command(
                path,
                command,
                args_str,
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

            if chat_id is None:
                raise ValueError("chat_id is required for RM subtool")
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

            if chat_id is None:
                raise ValueError("chat_id is required for Chmod subtool")

            # Ensure mode is one of the valid literals
            if mode not in ["a+x", "a-x"]:
                raise ValueError("mode must be either 'a+x' or 'a-x' for Chmod subtool")

            from typing import Literal, cast

            chmod_mode = cast(Literal["a+x", "a-x"], mode)
            result = await chmod(path, chmod_mode, chat_id)
            return result.get("resultForAssistant", "Chmod operation completed")
    except Exception:
        logging.error("Exception", exc_info=True)
        raise

    # This should never be reached, but adding for type safety
    return "Unknown subtool or operation"


def configure_logging(log_file: str = "codemcp.log") -> None:
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
        def filter(self, record: logging.LogRecord) -> bool:
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


def init_codemcp_project(path: str, python: bool = False) -> str:
    """Initialize a new codemcp project.

    Args:
        path: Path to initialize the project in
        python: Whether to create Python project files

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

        # Select the appropriate template directory
        template_name = "python" if python else "blank"
        templates_dir = Path(__file__).parent / "templates" / template_name

        # Derive project name from directory name (for replacing placeholders)
        project_name = project_path.name
        package_name = re.sub(r"[^a-z0-9_]", "_", project_name.lower())

        # Create a mapping for placeholder replacements
        replacements = {
            "__PROJECT_NAME__": project_name,
            "__PACKAGE_NAME__": package_name,
        }

        # Track which files we need to add to git
        files_to_add = []

        # Function to replace placeholders in a string
        def replace_placeholders(text):
            for placeholder, value in replacements.items():
                text = text.replace(placeholder, value)
            return text

        # Function to process a file from template directory to output directory
        def process_file(template_file, template_root, output_root):
            # Get the relative path from template root
            rel_path = template_file.relative_to(template_root)

            # Replace placeholders in the path components
            path_parts = []
            for part in rel_path.parts:
                path_parts.append(replace_placeholders(part))

            # Create the output path with replaced placeholders
            output_path = output_root.joinpath(*path_parts)

            # Create parent directories if they don't exist
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Skip if the file already exists
            if output_path.exists():
                print(f"File already exists, skipping: {output_path}")
                return None

            # Read the template content
            with open(template_file, "r") as f:
                content = f.read()

            # Replace placeholders in content
            content = replace_placeholders(content)

            # Write to the output file
            with open(output_path, "w") as f:
                f.write(content)

            # Return the relative path for git tracking
            rel_path = output_path.relative_to(project_path)
            print(f"Created file: {rel_path}")
            return rel_path

        # Recursively process template directory
        for template_file in templates_dir.glob("**/*"):
            if template_file.is_file() and template_file.name != ".gitkeep":
                # Process template file
                rel_path = process_file(template_file, templates_dir, project_path)
                if rel_path:
                    files_to_add.append(str(rel_path))

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

            if result.returncode != 0 and files_to_add:
                # No commits yet, add files and make initial commit
                for file in files_to_add:
                    subprocess.run(["git", "add", file], cwd=project_path, check=True)
                commit_msg = "chore: initialize codemcp project"
                if python:
                    commit_msg += " with Python template"
                subprocess.run(
                    ["git", "commit", "-m", commit_msg],
                    cwd=project_path,
                    check=True,
                )
                print(f"Created initial commit with {', '.join(files_to_add)}")
            else:
                print("Repository already has commits, not creating initial commit")
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to create initial commit: {e}")

        success_msg = f"Successfully initialized codemcp project in {project_path}"
        if python:
            success_msg += " with Python project structure"
        return success_msg
    except Exception as e:
        return f"Error initializing project: {e}"


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """CodeMCP: Command-line interface for MCP server and project management."""
    # If no subcommand is provided, run the MCP server (for backwards compatibility)
    if ctx.invoked_subcommand is None:
        run()


@cli.command()
@click.argument("path", type=click.Path(), default=".")
@click.option("--python", is_flag=True, help="Initialize with Python project structure")
def init(path: str, python: bool) -> None:
    """Initialize a new codemcp project with an empty codemcp.toml file and git repository.

    Use --python flag to create Python project files including pyproject.toml and package structure.
    """
    result = init_codemcp_project(path, python)
    click.echo(result)


def run() -> None:
    """Run the MCP server."""
    configure_logging()
    mcp.run()
