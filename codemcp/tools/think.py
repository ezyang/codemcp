#!/usr/bin/env python3

import logging

from mcp.server.fastmcp import Context

from ..main import get_chat_id_from_context, mcp

__all__ = [
    "think",
    "think_tool",
]


async def think(thought: str, chat_id: str | None = None) -> str:
    """Use this tool to think about something without obtaining new information or changing the database.

    Args:
        thought: The thought to log
        chat_id: The unique ID of the current chat session

    Returns:
        A confirmation message that the thought was logged
    """
    # Log the thought but don't actually do anything with it
    logging.info(f"[{chat_id}] Thought: {thought}")

    # Return a simple confirmation message
    return f"Thought logged: {thought}"


@mcp.tool()
async def think_tool(ctx: Context, thought: str) -> str:
    """Use the tool to think about something. It will not obtain new information or change the database,
    but just append the thought to the log. Use it when complex reasoning or some cache memory is needed.
    """
    # Get chat ID from context
    chat_id = get_chat_id_from_context(ctx)
    return await think(thought, chat_id)
