#!/usr/bin/env python3

import asyncio
import functools
import logging
import os
import sys
from contextlib import AsyncExitStack, asynccontextmanager
from typing import AsyncGenerator, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server.fastmcp import FastMCP

# Import the original codemcp function from main to clone its signature
from codemcp.main import (
    codemcp as original_codemcp,
)
from codemcp.main import (
    configure_logging as main_configure_logging,
)

# Initialize FastMCP server with the same name
mcp = FastMCP("codemcp")

# Global cache for exit stack and session
_exit_stack: Optional[AsyncExitStack] = None
_session: Optional[ClientSession] = None


@asynccontextmanager
async def get_cached_client_session() -> AsyncGenerator[ClientSession, None]:
    """Get a cached ClientSession or create a new one if not available."""
    global _exit_stack, _session

    # Check if we need to initialize a new connection
    if _exit_stack is None or _session is None:
        # Clean up any existing stack before creating a new one
        if _exit_stack is not None:
            try:
                logging.info("Closing previous client session")
                await _exit_stack.aclose()
            except Exception:
                logging.warning("Error closing previous client session", exc_info=True)
            _exit_stack = None
            _session = None

        # Create server parameters for stdio connection to main.py
        server_params = StdioServerParameters(
            command=sys.executable,  # Use the same Python interpreter
            args=[
                os.path.join(os.path.dirname(__file__), "__main__.py")
            ],  # Use __main__
            env=os.environ.copy(),  # Pass current environment variables
        )

        # Create new exit stack and setup context managers
        logging.info("Creating new client session")
        stack = AsyncExitStack()
        _exit_stack = stack

        # Enter the stdio_client context and get read/write streams
        read, write = await stack.enter_async_context(stdio_client(server_params))

        # Enter the ClientSession context
        session = await stack.enter_async_context(ClientSession(read, write))

        # Initialize the session
        await session.initialize()

        # Store the session for reuse
        _session = session

    try:
        # Yield the cached session
        yield _session
    except Exception:
        # Log the exception but don't close the connection on errors
        logging.error("Error using cached client session", exc_info=True)
        raise


@mcp.tool()
@functools.wraps(original_codemcp)  # This copies the signature and docstring
async def codemcp(**kwargs) -> str:
    """This is a wrapper that forwards all tool calls to the codemcp/main.py process.
    This allows for hot-reloading as main.py will be reloaded on each call.

    Arguments are the same as in main.py's codemcp tool.
    """
    configure_logging()
    try:
        async with get_cached_client_session() as session:
            # Call the codemcp tool in the subprocess
            result = await session.call_tool("codemcp", arguments=kwargs)

            # Return the result from the subprocess
            # TODO: This loses the isError-ness
            return result.content

    except Exception as e:
        logging.error("Exception in hot_reload_entry.py", exc_info=True)
        return f"Error in hot_reload_entry.py: {str(e)}"


def configure_logging():
    """Import and use the same logging configuration from main module"""
    main_configure_logging("codemcp_hot_reload.log")


async def cleanup_client_session():
    """Cleanup cached client session when shutting down."""
    global _exit_stack, _session

    if _exit_stack is not None:
        try:
            logging.info("Closing cached client session")
            await _exit_stack.aclose()
        except Exception:
            logging.warning("Error during client session cleanup", exc_info=True)
        _exit_stack = None
        _session = None


def run():
    """Run the MCP server with hot reload capability."""
    configure_logging()
    logging.info("Starting codemcp with hot reload capability")

    try:
        mcp.run()
    finally:
        # Use asyncio to run the cleanup coroutine
        asyncio.run(cleanup_client_session())


if __name__ == "__main__":
    run()
