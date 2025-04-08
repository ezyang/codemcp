#!/usr/bin/env python3

import logging
import os
import subprocess
from typing import Any, Dict, List, Optional, cast

import tomli

from .common import normalize_file_path, truncate_output_content
from .git import commit_changes, get_repository_root, is_git_repository
from .shell import run_command

__all__ = [
    "get_command_from_config",
    "check_for_changes",
    "run_code_command",
]


def get_command_from_config(project_dir: str, command_name: str) -> Optional[List[str]]:
    """Get a command from the codemcp.toml file.

    Args:
        project_dir: The directory path containing the codemcp.toml file
        command_name: The name of the command to retrieve (e.g., "lint", "format")

    Returns:
        A list of command parts if configured, None otherwise
    """
    try:
        full_dir_path = normalize_file_path(project_dir)
        config_path = os.path.join(full_dir_path, "codemcp.toml")

        if not os.path.exists(config_path):
            logging.warning(f"Config file not found: {config_path}")
            return None

        with open(config_path, "rb") as f:
            config: Dict[str, Any] = tomli.load(f)

        if "commands" in config and command_name in config["commands"]:
            cmd_config = config["commands"][command_name]
            # Handle both direct command lists and dictionaries with 'command' field
            if isinstance(cmd_config, list):
                return cast(List[str], cmd_config)
            elif isinstance(cmd_config, dict) and "command" in cmd_config:
                return cast(List[str], cmd_config["command"])

        return None
    except Exception as e:
        logging.error(f"Error loading {command_name} command: {e}")
        return None


async def check_for_changes(project_dir: str) -> bool:
    """Check if an operation made any changes to the code.

    Args:
        project_dir: The directory path to check

    Returns:
        True if changes were detected, False otherwise
    """
    try:
        # Get the git repository root for reliable status checking
        try:
            git_cwd = await get_repository_root(project_dir)
        except (subprocess.SubprocessError, OSError, ValueError) as e:
            logging.error(f"Error getting git repository root: {e}")
            # Fall back to the project directory
            git_cwd = project_dir

        # Check if working directory has uncommitted changes
        status_result = await run_command(
            ["git", "status", "--porcelain"],
            cwd=git_cwd,
            check=True,
            capture_output=True,
            text=True,
        )

        # If status output is not empty, there are changes
        return bool(status_result.stdout.strip())
    except Exception as e:
        logging.error(f"Error checking for git changes: {e}")
        return False


async def run_code_command(
    project_dir: str,
    command_name: str,
    command: List[str],
    commit_message: str,
    chat_id: Optional[str] = None,
) -> str:
    """Run a code command (lint, format, etc.) and handle git operations using commutable commits.

    This function implements a sophisticated auto-commit mechanism that:
    1. Creates a PRE_COMMIT with all pending changes
    2. Resets HEAD/index to the state before making this commit (working tree keeps changes)
    3. Runs the intended command
    4. Assesses the impact of the command:
       a. If no changes were made, it does nothing and ignores PRE_COMMIT
       b. If changes were made, it creates POST_COMMIT and tries to commute changes:
          - If the cherry-pick succeeds, uses the commuted POST_COMMIT
          - If the cherry-pick fails, uses the original uncommuted POST_COMMIT

    Args:
        project_dir: The directory path containing the code to process
        command_name: The name of the command for logging and messages (e.g., "lint", "format")
        command: The command to run
        commit_message: The commit message to use if changes are made
        chat_id: The unique ID of the current chat session

    Returns:
        A string containing the result of the operation
    """
    try:
        full_dir_path = normalize_file_path(project_dir)

        if not os.path.exists(full_dir_path):
            raise FileNotFoundError(f"Directory does not exist: {project_dir}")

        if not os.path.isdir(full_dir_path):
            raise NotADirectoryError(f"Path is not a directory: {project_dir}")

        if not command:
            # Map the command_name to keep backward compatibility with existing tests
            command_key = command_name
            if command_name == "linting":
                command_key = "lint"
            elif command_name == "formatting":
                command_key = "format"

            raise ValueError(f"No {command_key} command configured in codemcp.toml")

        # Check if directory is in a git repository
        is_git_repo = await is_git_repository(full_dir_path)

        # If it's a git repo, handle the commutable auto-commit mechanism
        pre_commit_hash = None
        original_head_hash = None
        if is_git_repo:
            try:
                git_cwd = await get_repository_root(full_dir_path)

                # Get the current HEAD hash
                head_hash_result = await run_command(
                    ["git", "rev-parse", "HEAD"],
                    cwd=git_cwd,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if head_hash_result.returncode == 0:
                    original_head_hash = head_hash_result.stdout.strip()

                # Check if there are any changes to commit
                has_initial_changes = await check_for_changes(full_dir_path)

                if has_initial_changes:
                    logging.info(f"Creating PRE_COMMIT before running {command_name}")
                    chat_id_str = str(chat_id) if chat_id is not None else ""

                    # Create the PRE_COMMIT with all changes
                    await run_command(
                        ["git", "add", "."],
                        cwd=git_cwd,
                        capture_output=True,
                        text=True,
                        check=True,
                    )

                    # Commit all changes (including untracked files)
                    await run_command(
                        [
                            "git",
                            "commit",
                            "--no-gpg-sign",
                            "-m",
                            f"PRE_COMMIT: Snapshot before auto-{command_name}",
                        ],
                        cwd=git_cwd,
                        capture_output=True,
                        text=True,
                        check=True,
                    )

                    # Get the hash of our PRE_COMMIT
                    pre_commit_hash_result = await run_command(
                        ["git", "rev-parse", "HEAD"],
                        cwd=git_cwd,
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    pre_commit_hash = pre_commit_hash_result.stdout.strip()

                    logging.info(f"Created PRE_COMMIT: {pre_commit_hash}")

                    # Reset HEAD to the previous commit, but keep working tree changes (mixed mode)
                    # This effectively "uncommits" without losing the changes in the working tree
                    if original_head_hash:
                        await run_command(
                            ["git", "reset", original_head_hash],
                            cwd=git_cwd,
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                        logging.info(
                            f"Reset HEAD to {original_head_hash}, keeping changes in working tree"
                        )
            except Exception as e:
                logging.warning(f"Failed to set up PRE_COMMIT: {e}")
                # Continue with command execution even if PRE_COMMIT setup fails

        # Run the command
        try:
            result = await run_command(
                command,
                cwd=full_dir_path,
                check=True,
                capture_output=True,
                text=True,
            )

            # Truncate the output if needed, prioritizing the end content
            truncated_stdout = truncate_output_content(result.stdout, prefer_end=True)

            # If it's a git repo and PRE_COMMIT was created, handle commutation of changes
            if is_git_repo and pre_commit_hash:
                git_cwd = await get_repository_root(full_dir_path)

                # Check if command made any changes
                has_command_changes = await check_for_changes(full_dir_path)

                if not has_command_changes:
                    logging.info(
                        f"No changes made by {command_name}, ignoring PRE_COMMIT"
                    )
                    return f"Code {command_name} successful (no changes made):\n{truncated_stdout}"

                logging.info(
                    f"Changes detected after {command_name}, creating POST_COMMIT"
                )

                # Create POST_COMMIT with PRE_COMMIT as parent
                # First, stage all changes (including untracked files)
                await run_command(
                    ["git", "add", "."],
                    cwd=git_cwd,
                    capture_output=True,
                    text=True,
                    check=True,
                )

                # Create the POST_COMMIT on top of PRE_COMMIT
                chat_id_str = str(chat_id) if chat_id is not None else ""

                # Temporarily set HEAD to PRE_COMMIT
                await run_command(
                    ["git", "update-ref", "HEAD", pre_commit_hash],
                    cwd=git_cwd,
                    capture_output=True,
                    text=True,
                    check=True,
                )

                # Create POST_COMMIT
                await run_command(
                    [
                        "git",
                        "commit",
                        "--no-gpg-sign",
                        "-m",
                        f"POST_COMMIT: {commit_message}",
                    ],
                    cwd=git_cwd,
                    capture_output=True,
                    text=True,
                    check=True,
                )

                # Get the POST_COMMIT hash
                post_commit_hash_result = await run_command(
                    ["git", "rev-parse", "HEAD"],
                    cwd=git_cwd,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                post_commit_hash = post_commit_hash_result.stdout.strip()
                logging.info(f"Created POST_COMMIT: {post_commit_hash}")

                # Now try to commute the changes
                # Reset to original HEAD
                await run_command(
                    ["git", "reset", "--hard", original_head_hash],
                    cwd=git_cwd,
                    capture_output=True,
                    text=True,
                    check=True,
                )

                # Try to cherry-pick PRE_COMMIT onto original HEAD
                try:
                    await run_command(
                        ["git", "cherry-pick", "--no-gpg-sign", pre_commit_hash],
                        cwd=git_cwd,
                        capture_output=True,
                        text=True,
                        check=True,
                    )

                    # If we get here, PRE_COMMIT applied cleanly
                    commuted_pre_commit_hash_result = await run_command(
                        ["git", "rev-parse", "HEAD"],
                        cwd=git_cwd,
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    commuted_pre_commit_hash = (
                        commuted_pre_commit_hash_result.stdout.strip()
                    )

                    # Now try to cherry-pick POST_COMMIT
                    await run_command(
                        ["git", "cherry-pick", "--no-gpg-sign", post_commit_hash],
                        cwd=git_cwd,
                        capture_output=True,
                        text=True,
                        check=True,
                    )

                    # Get the commuted POST_COMMIT hash
                    commuted_post_commit_hash_result = await run_command(
                        ["git", "rev-parse", "HEAD"],
                        cwd=git_cwd,
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    commuted_post_commit_hash = (
                        commuted_post_commit_hash_result.stdout.strip()
                    )

                    # Verify that the final tree is the same
                    original_tree_result = await run_command(
                        ["git", "rev-parse", f"{post_commit_hash}^{{tree}}"],
                        cwd=git_cwd,
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    original_tree = original_tree_result.stdout.strip()

                    commuted_tree_result = await run_command(
                        ["git", "rev-parse", f"{commuted_post_commit_hash}^{{tree}}"],
                        cwd=git_cwd,
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    commuted_tree = commuted_tree_result.stdout.strip()

                    if original_tree == commuted_tree:
                        # Commutation successful and trees match!
                        # Make sure we have the same changes uncommitted
                        await run_command(
                            ["git", "reset", commuted_pre_commit_hash],
                            cwd=git_cwd,
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                        logging.info(
                            f"Commutation successful! Set HEAD to commuted POST_COMMIT and reset to commuted PRE_COMMIT"
                        )
                        return f"Code {command_name} successful (changes commuted successfully):\n{truncated_stdout}"
                    else:
                        # Trees don't match, go back to unconmuted version
                        logging.info(
                            f"Commutation resulted in different trees, using original POST_COMMIT"
                        )
                        await run_command(
                            ["git", "reset", "--hard", post_commit_hash],
                            cwd=git_cwd,
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                        return f"Code {command_name} successful (changes don't commute, using original order):\n{truncated_stdout}"

                except subprocess.CalledProcessError:
                    # Cherry-pick failed, go back to unconmuted version
                    logging.info(f"Cherry-pick failed, using original POST_COMMIT")
                    await run_command(
                        ["git", "cherry-pick", "--abort"],
                        cwd=git_cwd,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    await run_command(
                        ["git", "reset", "--hard", post_commit_hash],
                        cwd=git_cwd,
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    return f"Code {command_name} successful (changes don't commute, using original order):\n{truncated_stdout}"

            # If no PRE_COMMIT was created or not a git repo, handle normally
            elif is_git_repo:
                has_changes = await check_for_changes(full_dir_path)
                if has_changes:
                    logging.info(f"Changes detected after {command_name}, committing")
                    chat_id_str = str(chat_id) if chat_id is not None else ""
                    success, commit_result_message = await commit_changes(
                        full_dir_path, commit_message, chat_id_str, commit_all=True
                    )

                    if success:
                        return f"Code {command_name} successful and changes committed:\n{truncated_stdout}"
                    else:
                        logging.warning(
                            f"Failed to commit {command_name} changes: {commit_result_message}"
                        )
                        return f"Code {command_name} successful but failed to commit changes:\n{truncated_stdout}\nCommit error: {commit_result_message}"

            return f"Code {command_name} successful:\n{truncated_stdout}"
        except subprocess.CalledProcessError as e:
            # If we were in the middle of the commutation process, try to restore the original state
            if is_git_repo and pre_commit_hash and original_head_hash:
                try:
                    git_cwd = await get_repository_root(full_dir_path)

                    # Abort any in-progress cherry-pick
                    await run_command(
                        ["git", "cherry-pick", "--abort"],
                        cwd=git_cwd,
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                    # Reset to original head
                    await run_command(
                        ["git", "reset", "--hard", original_head_hash],
                        cwd=git_cwd,
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    logging.info(f"Restored original state after command failure")
                except Exception as restore_error:
                    logging.error(f"Failed to restore original state: {restore_error}")

            # Map the command_name to keep backward compatibility with existing tests
            command_key = command_name.title()
            if command_name == "linting":
                command_key = "Lint"
            elif command_name == "formatting":
                command_key = "Format"

            # Truncate stdout and stderr if needed, prioritizing the end content
            truncated_stdout = truncate_output_content(
                e.output if e.output else "", prefer_end=True
            )
            truncated_stderr = truncate_output_content(
                e.stderr if e.stderr else "", prefer_end=True
            )

            # Include both stdout and stderr in the error message
            stdout_info = (
                f"STDOUT:\n{truncated_stdout}"
                if truncated_stdout
                else "STDOUT: <empty>"
            )
            stderr_info = (
                f"STDERR:\n{truncated_stderr}"
                if truncated_stderr
                else "STDERR: <empty>"
            )
            error_msg = f"{command_key} command failed with exit code {e.returncode}:\n{stdout_info}\n{stderr_info}"

            # Note: run_command already logs the command and stderr at debug level
            # We just need to log the error summary at error level
            logging.error(
                f"{command_name.title()} command failed with exit code {e.returncode}"
            )
            return f"Error: {error_msg}"

    except Exception as e:
        # If we were in the middle of the commutation process, try to restore the original state
        if is_git_repo and pre_commit_hash and original_head_hash:
            try:
                git_cwd = await get_repository_root(full_dir_path)

                # Abort any in-progress cherry-pick
                await run_command(
                    ["git", "cherry-pick", "--abort"],
                    cwd=git_cwd,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                # Reset to original head
                await run_command(
                    ["git", "reset", "--hard", original_head_hash],
                    cwd=git_cwd,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                logging.info(f"Restored original state after exception")
            except Exception as restore_error:
                logging.error(f"Failed to restore original state: {restore_error}")

        error_msg = f"Error during {command_name}: {e}"
        logging.error(error_msg)
        return f"Error: {error_msg}"
