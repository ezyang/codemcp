#!/usr/bin/env python3

import asyncio
import functools
import logging
import os
import sys
from asyncio import Queue, Task
from typing import Optional

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


class HotReloadManager:
    """
    Manages the lifecycle of the hot reload context in a dedicated background task.
    This ensures proper cleanup of async resources by having a single task own the
    context manager.
    """

    def __init__(self):
        self._task: Optional[Task] = None
        self._request_queue: Optional[Queue] = None

    async def start(self) -> None:
        """Start the background task if not already running."""
        if self._task is None or self._task.done():
            # Create fresh queue for this run
            self._request_queue = Queue()

            # Create the task with explicit parameters
            self._task = asyncio.create_task(
                self._run_manager_task(self._request_queue)
            )

    async def stop(self) -> None:
        """Stop the background task and clean up resources."""
        if self._task and not self._task.done() and self._request_queue:
            # Create a future for the stop command
            stop_future = asyncio.Future()

            # Get a local reference to the queue and task before clearing
            request_queue = self._request_queue
            task = self._task

            # Clear request_queue BEFORE any awaits to prevent race conditions
            self._request_queue = None

            # Now it's safe to do awaits since new messages can't be added to self._request_queue
            await request_queue.put(("stop", None, stop_future))
            await stop_future
            await task

    async def call_tool(self, **kwargs) -> str:
        """Call the codemcp tool in the subprocess."""
        if self._task is None or self._task.done() or self._request_queue is None:
            await self.start()

        # Create a future for this specific request
        response_future = asyncio.Future()

        # Send the request and its associated future to the manager task
        if self._request_queue:  # Safety check
            await self._request_queue.put(("call", kwargs, response_future))
        else:
            response_future.set_exception(RuntimeError("Request queue not available"))

        # Wait for the response
        return await response_future

    async def _run_manager_task(self, request_queue: Queue) -> None:
        """
        Background task that owns and manages the async context managers lifecycle.

        Parameters:
            request_queue: Queue to receive commands from
        """
        try:
            # Setup stdio connection to main.py
            server_params = StdioServerParameters(
                command=sys.executable,  # Use the same Python interpreter
                args=[
                    os.path.join(os.path.dirname(__file__), "__main__.py")
                ],  # Use __main__
                env=os.environ.copy(),  # Pass current environment variables
            )

            # Use nested async with statements to properly manage context
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    # Initialize the session
                    await session.initialize()

                    # Process commands until told to stop
                    while True:
                        try:
                            command, args, future = await request_queue.get()

                            if command == "stop":
                                future.set_result(True)
                                break

                            if command == "call":
                                try:
                                    result = await session.call_tool(
                                        "codemcp", arguments=args
                                    )
                                    future.set_result(result)
                                except Exception as e:
                                    future.set_exception(e)

                        except Exception as e:
                            logging.error(
                                "Error in hot reload manager task", exc_info=True
                            )
                            if "future" in locals() and not future.done():
                                future.set_exception(e)

        except Exception:
            logging.error("Error initializing hot reload context", exc_info=True)


# Global singleton manager
_MANAGER = HotReloadManager()


async def aexit():
    """Stop the hot reload manager and clean up resources."""
    await _MANAGER.stop()


@mcp.tool()
@functools.wraps(original_codemcp)  # This copies the signature and docstring
async def codemcp(**kwargs) -> str:
    """This is a wrapper that forwards all tool calls to the codemcp/main.py process.
    This allows for hot-reloading as main.py will be reloaded on each call.

    Arguments are the same as in main.py's codemcp tool.
    """
    configure_logging()
    try:
        # Use the HotReloadManager to handle the context and session lifecycle
        return await _MANAGER.call_tool(**kwargs)
    except Exception:
        logging.error("Exception in hot_reload_entry.py", exc_info=True)
        raise


def configure_logging():
    """Import and use the same logging configuration from main module"""
    main_configure_logging("codemcp_hot_reload.log")


def run():
    """Run the MCP server with hot reload capability."""
    configure_logging()
    logging.info("Starting codemcp with hot reload capability")

    try:
        # Run MCP server
        mcp.run()
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        logging.info("Received keyboard interrupt, shutting down...")
        # No need to explicitly run shutdown here - resources will be cleaned up
        # when the program exits


if __name__ == "__main__":
    run()
