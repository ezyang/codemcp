#!/usr/bin/env python3


import asyncio
import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import asynccontextmanager
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    List,
    Optional,
    Protocol,
    TypeVar,
    Union,
    cast,
)


# Define a local ExceptionGroup class for type checking purposes
# In Python 3.11+, this would be available as a built-in
class ExceptionGroup(Exception):
    """Simple ExceptionGroup implementation for type checking."""

    def __init__(self, message: str, exceptions: List[Exception]) -> None:
        self.exceptions: List[Exception] = exceptions
        super().__init__(message, exceptions)


from unittest import mock

from expecttest import TestCase
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Define types for objects used in the testing module
T = TypeVar("T")


class TextContent(Protocol):
    """Protocol for objects with a text attribute."""

    text: str


class CallToolResult(Protocol):
    """Protocol for objects returned by call_tool."""

    isError: bool
    content: Union[str, List[TextContent], Any]


class MCPEndToEndTestCase(TestCase, unittest.IsolatedAsyncioTestCase):
    """Base class for end-to-end tests of codemcp using MCP client."""

    in_process: bool = True

    async def asyncSetUp(self):
        """Async setup method to prepare the test environment."""
        # Create a temporary directory for testing
        self.temp_dir = tempfile.TemporaryDirectory()
        self.testing_time = "1112911993"  # Fixed timestamp for git

        # Initialize environment variables for git
        self.env = os.environ.copy()
        # Set environment variables for reproducible git behavior
        self.env.setdefault("GIT_TERMINAL_PROMPT", "0")
        self.env.setdefault("EDITOR", ":")
        self.env.setdefault("GIT_MERGE_AUTOEDIT", "no")
        self.env.setdefault("LANG", "C")
        self.env.setdefault("LC_ALL", "C")
        self.env.setdefault("PAGER", "cat")
        self.env.setdefault("TZ", "UTC")
        self.env.setdefault("TERM", "dumb")
        # For deterministic commit times
        self.env.setdefault("GIT_AUTHOR_EMAIL", "author@example.com")
        self.env.setdefault("GIT_AUTHOR_NAME", "A U Thor")
        self.env.setdefault("GIT_COMMITTER_EMAIL", "committer@example.com")
        self.env.setdefault("GIT_COMMITTER_NAME", "C O Mitter")
        self.env.setdefault("GIT_COMMITTER_DATE", f"{self.testing_time} -0700")
        self.env.setdefault("GIT_AUTHOR_DATE", f"{self.testing_time} -0700")

        # Patch get_subprocess_env to use the test environment
        self.env_patcher = mock.patch(
            "codemcp.shell.get_subprocess_env", return_value=self.env
        )
        self.env_patcher.start()

        # Initialize a git repository in the temp directory
        await self.setup_repository()

    async def asyncTearDown(self):
        """Async teardown to clean up after the test."""
        # Stop the environment patcher
        self.env_patcher.stop()
        self.temp_dir.cleanup()

    async def setup_repository(self):
        """Setup a git repository for testing with an initial commit.

        This method can be overridden by subclasses to customize the repository setup.
        By default, it initializes a git repository and creates an initial commit.
        """
        # Initialize and configure git
        try:
            await self.git_run(["init", "-b", "main"])
        except subprocess.CalledProcessError:
            self.fail(
                "git version is too old for tests! Please install a newer version of git."
            )
        await self.git_run(["config", "user.email", "test@example.com"])
        await self.git_run(["config", "user.name", "Test User"])

        # Create initial commit
        readme_path = os.path.join(self.temp_dir.name, "README.md")
        with open(readme_path, "w") as f:  # noqa: ASYNC230
            f.write("# Test Repository\n")

        # Create a codemcp.toml file in the repo root (required for permission checks)
        codemcp_toml_path = os.path.join(self.temp_dir.name, "codemcp.toml")
        with open(codemcp_toml_path, "w") as f:  # noqa: ASYNC230
            f.write("")

        await self.git_run(["add", "README.md", "codemcp.toml"])
        await self.git_run(["commit", "-m", "Initial commit"])

    def normalize_path(self, text: Any) -> Union[str, List[object], Any]:
        """Normalize temporary directory paths in output text."""
        if self.temp_dir and self.temp_dir.name:
            # Handle CallToolResult objects by converting to string first
            if hasattr(text, "content"):
                # This is a CallToolResult object, extract the content
                text = cast(CallToolResult, text).content

            # Handle lists where items might have a 'text' attribute
            if isinstance(text, list):
                # Return lists as-is - we only normalize string content
                return text  # type: ignore

            # Replace the actual temp dir path with a fixed placeholder
            if isinstance(text, str):
                return text.replace(self.temp_dir.name, "/tmp/test_dir")
        # Return anything else as-is
        return text

    def extract_text_from_result(self, result: Any) -> str:
        """Extract text content from various result formats for assertions.

        Args:
            result: The result object (could be string, list of TextContent, etc.)

        Returns:
            str: The extracted text content
        """
        # Handle strings directly
        if isinstance(result, str):
            return result

        # Handle lists - most common case after strings
        if isinstance(result, list):
            # Empty list case
            if not result:
                return "[]"

            # For non-empty lists with elements that have a text attribute
            # Type checkers struggle with this dynamic access pattern
            # so we use a try-except to make the code more robust
            try:
                obj = result[0]  # type: ignore
                if hasattr(obj, "text"):  # type: ignore
                    text_attr = getattr(obj, "text")  # type: ignore
                    if isinstance(text_attr, str):
                        return text_attr
            except (IndexError, AttributeError):
                pass

            # Fallback for other list types - convert to string
            return str(result)  # type: ignore

        # For anything else, convert to string
        return str(result)

    def extract_chat_id_from_text(self, text: str) -> str:
        """Extract chat_id from init_result_text.

        Args:
            text: The text output from InitProject tool

        Returns:
            str: The extracted chat_id

        Raises:
            AssertionError: If chat_id cannot be found in text
        """
        chat_id_match = re.search(r"chat ID: ([a-zA-Z0-9-]+)", text)
        assert chat_id_match is not None, "Could not find chat ID in text"
        return chat_id_match.group(1)

    async def _dispatch_to_subtool(self, subtool: str, kwargs: Dict[str, Any]) -> Any:
        """Dispatch to the appropriate subtool function based on the subtool name.

        This is a helper method that both call_tool_assert_success and call_tool_assert_error
        use to route the call to the appropriate function in the tools module.

        Args:
            subtool: The name of the subtool to call
            kwargs: Dictionary of parameters to pass to the subtool

        Returns:
            The result from the subtool function

        Raises:
            ValueError: If the subtool is unknown
        """
        # Directly call the appropriate tool function
        if subtool == "ReadFile":
            from codemcp.tools.read_file import read_file

            return await read_file(**kwargs)

        elif subtool == "WriteFile":
            from codemcp.tools.write_file import write_file

            return await write_file(**kwargs)

        elif subtool == "EditFile":
            from codemcp.tools.edit_file import edit_file

            return await edit_file(**kwargs)

        elif subtool == "LS":
            from codemcp.tools.ls import ls

            return await ls(**kwargs)

        elif subtool == "InitProject":
            from codemcp.tools.init_project import init_project

            # No need for parameter conversion anymore - init_project accepts both path and directory
            return await init_project(**kwargs)

        elif subtool == "RunCommand":
            from codemcp.tools.run_command import run_command

            # No need for parameter conversion anymore - run_command accepts both path and project_dir
            return await run_command(**kwargs)

        elif subtool == "Grep":
            from codemcp.tools.grep import grep

            return await grep(**kwargs)

        elif subtool == "Glob":
            from codemcp.tools.glob import glob

            return await glob(**kwargs)

        elif subtool == "RM":
            from codemcp.tools.rm import rm

            return await rm(**kwargs)

        elif subtool == "MV":
            from codemcp.tools.mv import mv

            return await mv(**kwargs)

        elif subtool == "Think":
            from codemcp.tools.think import think

            return await think(**kwargs)

        elif subtool == "Chmod":
            from codemcp.tools.chmod import chmod

            return await chmod(**kwargs)

        elif subtool == "GitLog":
            from codemcp.tools.git_log import git_log

            return await git_log(**kwargs)

        elif subtool == "GitDiff":
            from codemcp.tools.git_diff import git_diff

            return await git_diff(**kwargs)

        elif subtool == "GitShow":
            from codemcp.tools.git_show import git_show

            return await git_show(**kwargs)

        elif subtool == "GitBlame":
            from codemcp.tools.git_blame import git_blame

            return await git_blame(**kwargs)

        else:
            raise ValueError(f"Unknown subtool: {subtool}")

    async def call_tool_assert_error(
        self,
        session: Optional[ClientSession],
        tool_name: str,
        tool_params: Dict[str, Any],
    ) -> str:
        """Call a tool and assert that it fails (isError=True).

        This is a helper method for the error path of tool calls, which:
        1. Calls the specified tool function directly based on subtool parameter
        2. Asserts that the call raises an exception
        3. Returns the exception string

        Args:
            session: The client session to use (kept for backward compatibility but unused)
            tool_name: The name of the tool to call (must be 'codemcp')
            tool_params: Dictionary of parameters to pass to the tool

        Returns:
            str: The extracted error message

        Raises:
            AssertionError: If the tool call does not result in an error
        """
        # Only codemcp tool is supported
        assert tool_name == "codemcp", (
            f"Only 'codemcp' tool is supported, got '{tool_name}'"
        )

        # Extract the parameters to pass to the direct function
        subtool = tool_params.get("subtool")
        assert subtool is not None, "subtool parameter is required"
        kwargs = {k: v for k, v in tool_params.items() if k != "subtool"}

        try:
            if self.in_process:
                # Use the dispatcher to call the appropriate function
                await self._dispatch_to_subtool(subtool, kwargs)

                # If we get here, the call succeeded - but we expected it to fail
                self.fail(f"Tool call to {tool_name} succeeded, expected to fail")
            else:
                assert session is not None, (
                    "Session cannot be None when in_process=False"
                )
                # Convert subtool name to lowercase snake case (e.g., ReadFile -> read_file)
                subtool_snake_case = "".join(
                    ["_" + c.lower() if c.isupper() else c for c in subtool]
                ).lstrip("_")
                # Call the subtool directly instead of calling the codemcp tool
                result = await session.call_tool(subtool_snake_case, kwargs)  # type: ignore
                self.assertTrue(result.isError, result)
                error_message = self.extract_text_from_result(result.content)
                return cast(str, self.normalize_path(error_message))
        except Exception as e:
            # The call failed as expected - return the error message
            error_message = f"Error executing tool {tool_name}: {str(e)}"
            normalized_result = self.normalize_path(error_message)
            return cast(str, normalized_result)

    async def call_tool_assert_success(
        self,
        session: Optional[ClientSession],
        tool_name: str,
        tool_params: Dict[str, Any],
    ) -> str:
        """Call a tool and assert that it succeeds (isError=False).

        This is a helper method for the happy path of tool calls, which:
        1. Calls the specified tool function directly based on subtool parameter
        2. Asserts that the call succeeds (no exception)
        3. Returns the result text

        Args:
            session: The client session to use (kept for backward compatibility but unused)
            tool_name: The name of the tool to call (must be 'codemcp')
            tool_params: Dictionary of parameters to pass to the tool

        Returns:
            str: The extracted text content from the result

        Raises:
            AssertionError: If the tool call results in an error
        """
        # Only codemcp tool is supported
        assert tool_name == "codemcp", (
            f"Only 'codemcp' tool is supported, got '{tool_name}'"
        )

        # Extract the parameters to pass to the direct function
        subtool = tool_params.get("subtool")
        assert subtool is not None, "subtool parameter is required"
        kwargs = {k: v for k, v in tool_params.items() if k != "subtool"}

        if self.in_process:
            # Use the dispatcher to call the appropriate function
            result = await self._dispatch_to_subtool(subtool, kwargs)

            # Return the normalized, extracted text result
            normalized_result = self.normalize_path(result)
            return self.extract_text_from_result(normalized_result)
        else:
            assert session is not None, "Session cannot be None when in_process=False"
            # Convert subtool name to lowercase snake case (e.g., ReadFile -> read_file)
            subtool_snake_case = "".join(
                ["_" + c.lower() if c.isupper() else c for c in subtool]
            ).lstrip("_")
            # Call the subtool directly instead of calling the codemcp tool
            result = await session.call_tool(subtool_snake_case, kwargs)  # type: ignore
            self.assertFalse(result.isError, result)
            normalized_result = self.normalize_path(result.content)
            return self.extract_text_from_result(normalized_result)

    async def get_chat_id(self, session: Optional[ClientSession]) -> str:
        """Initialize project and get chat_id.

        Args:
            session: The client session to use (kept for backward compatibility but unused)

        Returns:
            str: The chat_id
        """
        # Use the _dispatch_to_subtool for consistency with other test methods
        init_result_text = await self._dispatch_to_subtool(
            "InitProject",
            {
                "path": self.temp_dir.name,
                "user_prompt": "Test initialization for get_chat_id",
                "subject_line": "test: initialize for e2e testing",
                "reuse_head_chat_id": False,
            },
        )

        # Extract chat_id from the init result
        chat_id_match = re.search(r"chat ID: ([a-zA-Z0-9-]+)", str(init_result_text))
        assert chat_id_match is not None, (
            "Could not find chat ID in initialization result"
        )
        chat_id = chat_id_match.group(1)

        return chat_id

    @asynccontextmanager
    async def _unwrap_exception_groups(self) -> AsyncGenerator[None, None]:
        """Context manager that unwraps ExceptionGroups with single exceptions.
        Only unwraps if there's exactly one exception at each level.
        """
        try:
            yield
        except ExceptionGroup as eg:
            # Since we're using our own ExceptionGroup implementation,
            # we know exceptions is a List[Exception]
            if len(eg.exceptions) == 1:
                exc: Exception = eg.exceptions[0]
                # Recursively unwrap if it's another ExceptionGroup with a single exception
                while isinstance(exc, ExceptionGroup):
                    if len(exc.exceptions) == 1:
                        exc = exc.exceptions[0]
                    else:
                        break
                raise exc from None
            else:
                # Multiple exceptions - don't unwrap
                raise

    @asynccontextmanager
    async def create_client_session(
        self,
    ) -> AsyncGenerator[Optional[ClientSession], None]:
        """Create an MCP client session connected to codemcp server."""
        if self.in_process:
            yield None
            return

        # Set up server parameters for the codemcp MCP server
        server_params = StdioServerParameters(
            command=sys.executable,  # Current Python executable
            args=["-m", "codemcp"],  # Module path to codemcp
            env=self.env,
            # Working directory is specified directly with kwargs in stdio_client
        )

        async with self._unwrap_exception_groups():
            async with stdio_client(server_params) as (read, write):
                async with self._unwrap_exception_groups():
                    async with ClientSession(read, write) as session:
                        # Initialize the connection
                        await session.initialize()
                        yield session

    async def git_run(
        self,
        args: List[str],
        check: bool = True,
        capture_output: bool = False,
        text: bool = False,
        **kwargs: Any,
    ) -> Union[subprocess.CompletedProcess[bytes], str]:
        """Run git command asynchronously with appropriate temp_dir and env settings.

        This helper method simplifies git subprocess calls in e2e tests by:
        1. Automatically using the test's temp_dir as the working directory
        2. Using the test's pre-configured env variables
        3. Supporting async execution and various output capture options

        Args:
            args: List of git command arguments (without 'git' prefix)
            check: If True, raises if the command returns a non-zero exit code
            capture_output: If True, captures stdout and stderr
            text: If True, decodes stdout and stderr using the preferred encoding
            **kwargs: Additional keyword arguments to pass to subprocess.run

        Returns:
            If capture_output is False: subprocess.CompletedProcess instance
            If capture_output is True and text is True: The stdout content as string

        Example:
            # Run git add command
            await self.git_run(["add", "file.txt"])

            # Get commit log as string
            log_output = await self.git_run(["log", "--oneline"], capture_output=True, text=True)
        """
        # Always include 'git' as the command
        cmd = ["git"] + args

        # Set defaults for working directory and environment
        kwargs.setdefault("cwd", self.temp_dir.name)
        kwargs.setdefault("env", self.env)

        # Capture output if requested
        if capture_output:
            kwargs.setdefault("stdout", subprocess.PIPE)
            kwargs.setdefault("stderr", subprocess.PIPE)

        # Run the command asynchronously
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            **kwargs,
        )

        stdout, stderr = await proc.communicate()

        # Build a CompletedProcess-like result
        result = subprocess.CompletedProcess[bytes](
            args=cmd,
            returncode=proc.returncode or 0,  # Use 0 if returncode is None
            stdout=stdout,
            stderr=stderr,
        )

        # Check for error if requested
        if check and proc.returncode and proc.returncode != 0:
            cmd_str = " ".join(cmd)
            raise subprocess.CalledProcessError(
                proc.returncode, cmd_str, output=stdout, stderr=stderr
            )

        # Return the appropriate result type
        if capture_output and text:
            # Always decode to string when text=True even if stdout is empty
            return stdout.decode().strip() if stdout else ""
        return result
