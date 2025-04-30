#!/usr/bin/env python3

import asyncio
import logging
import subprocess
from typing import Dict, List, Optional, Union

__all__ = [
    "run_command",
    "get_subprocess_env",
]


def get_subprocess_env() -> Optional[Dict[str, str]]:
    """
    Get the environment variables to be used for subprocess execution.
    This function can be mocked in tests to control the environment.

    Returns:
        Optional dictionary of environment variables, or None to use the current environment.
    """
    return None


async def run_command(
    cmd: List[str],
    cwd: Optional[str] = None,
    check: bool = True,
    capture_output: bool = True,
    text: bool = True,
    wait_time: Optional[float] = None,  # Renamed from timeout to avoid ASYNC109
    shell: bool = False,
    input: Optional[str] = None,
) -> subprocess.CompletedProcess[Union[str, bytes]]:
    """
    Run a subprocess command with consistent logging asynchronously.

    Args:
        cmd: Command to run as a list of strings
        cwd: Current working directory for the command
        check: If True, raise RuntimeError if the command returns non-zero exit code
        capture_output: If True, capture stdout and stderr
        text: If True, decode stdout and stderr as text
        wait_time: Timeout in seconds
        shell: If True, run command in a shell
        input: Input to pass to the subprocess's stdin

    Returns:
        CompletedProcess instance with attributes args, returncode, stdout, stderr

    Raises:
        RuntimeError: If check=True and process returns non-zero exit code
        subprocess.TimeoutExpired: If the process times out

    Notes:
        Environment variables are obtained from get_subprocess_env() function.
    """
    # Log the command being run at INFO level
    log_cmd = " ".join(str(c) for c in cmd)
    logging.info(f"Running cVALDLLDommand!!!!!!!: {log_cmd}")

    # Prepare stdout and stderr pipes
    stdout_pipe = asyncio.subprocess.PIPE if capture_output else None
    stderr_pipe = asyncio.subprocess.PIPE if capture_output else None
    stdin_pipe = asyncio.subprocess.PIPE if input is not None else None

    # Convert input to bytes if provided
    input_bytes = None
    if input is not None:
        input_bytes = input.encode()

    # Run the subprocess asynchronously
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        env=get_subprocess_env(),
        stdout=stdout_pipe,
        stderr=stderr_pipe,
        stdin=stdin_pipe,
    )

    try:
        # Wait for the process to complete with optional timeout
        stdout_data, stderr_data = await asyncio.wait_for(
            process.communicate(input=input_bytes), timeout=wait_time
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise subprocess.TimeoutExpired(
            cmd, float(wait_time) if wait_time is not None else 0.0
        )

    # Handle text conversion
    stdout = ""
    stderr = ""
    if capture_output:
        if text and stdout_data:
            stdout = stdout_data.decode()
            logging.info(f"Command stdout: {stdout}")
        elif stdout_data:
            stdout = stdout_data
            logging.info(f"Command stdout: {len(stdout_data)} bytes")

        if text and stderr_data:
            stderr = stderr_data.decode()
            logging.info(f"Command stderr: {stderr}")
        elif stderr_data:
            stderr = stderr_data
            logging.info(f"Command stderr: {len(stderr_data)} bytes")

    # Log the return code
    returncode = process.returncode
    logging.info(f"Command return code: {returncode}")

    # Create a CompletedProcess object to maintain compatibility
    result = subprocess.CompletedProcess[Union[str, bytes]](
        args=cmd,
        returncode=0 if returncode is None else returncode,
        stdout=stdout,
        stderr=stderr,
    )

    # Raise RuntimeError if check is True and command failed
    if check and result.returncode != 0:
        error_message = f"Command failed with exit code {result.returncode}: {' '.join(str(c) for c in cmd)}"
        if result.stdout:
            error_message += f"\nStdout: {result.stdout}"
        if result.stderr:
            error_message += f"\nStderr: {result.stderr}"
        raise RuntimeError(error_message)

    return result
