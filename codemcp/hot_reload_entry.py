#!/usr/bin/env python3

import contextlib
import functools
import logging
import os
import sys

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


_CONTEXT = None

async def aexit():
    """Clear the hot reload context, if it exists"""
    global _CONTEXT
    if _CONTEXT is not None:
        mgr, _, _, _ = _CONTEXT
        await mgr.__aexit__(None, None, None)
        _CONTEXT = None


@mcp.tool()
@functools.wraps(original_codemcp)  # This copies the signature and docstring
async def codemcp(**kwargs) -> str:
    """This is a wrapper that forwards all tool calls to the codemcp/main.py process.
    This allows for hot-reloading as main.py will be reloaded on each call.

    Arguments are the same as in main.py's codemcp tool.
    """
    configure_logging()
    try:
        global _CONTEXT

        if _CONTEXT is None:
            # Create server parameters for stdio connection to main.py
            server_params = StdioServerParameters(
                command=sys.executable,  # Use the same Python interpreter
                args=[
                    os.path.join(os.path.dirname(__file__), "__main__.py")
                ],  # Use __main__
                env=os.environ.copy(),  # Pass current environment variables
            )
            mgr = contextlib.AsyncExitStack()
            await mgr.__aenter__()
            read, write = await mgr.enter_async_context(stdio_client(server_params))
            session = await mgr.enter_async_context(ClientSession(read, write))
            _CONTEXT = (mgr, read, write, session)
            await session.initialize()
        else:
            mgr, read, write, session = _CONTEXT

        # Call the codemcp tool in the subprocess
        # TODO: This loses the isError-ness
        return await session.call_tool("codemcp", arguments=kwargs)

    except Exception as e:
        logging.error("Exception in hot_reload_entry.py", exc_info=True)
        raise


def configure_logging():
    """Import and use the same logging configuration from main module"""
    main_configure_logging("codemcp_hot_reload.log")


def run():
    """Run the MCP server with hot reload capability."""
    configure_logging()
    logging.info("Starting codemcp with hot reload capability")
    mcp.run()


if __name__ == "__main__":
    run()
