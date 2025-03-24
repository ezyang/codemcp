#!/usr/bin/env python3

import os
from typing import List

import anyio

from .line_endings import detect_line_endings


async def async_open_text(
    file_path: str,
    mode: str = "r",
    encoding: str = "utf-8",
    errors: str = "replace",
) -> str:
    """Asynchronously open and read a text file.

    Args:
        file_path: The path to the file
        mode: The file open mode (default: 'r')
        encoding: The text encoding (default: 'utf-8')
        errors: How to handle encoding errors (default: 'replace')

    Returns:
        The file content as a string
    """
    async with await anyio.open_file(
        file_path, mode, encoding=encoding, errors=errors
    ) as f:
        return await f.read()


async def async_open_binary(file_path: str, mode: str = "rb") -> bytes:
    """Asynchronously open and read a binary file.

    Args:
        file_path: The path to the file
        mode: The file open mode (default: 'rb')

    Returns:
        The file content as bytes
    """
    async with await anyio.open_file(file_path, mode) as f:
        return await f.read()


async def async_readlines(
    file_path: str, encoding: str = "utf-8", errors: str = "replace"
) -> List[str]:
    """Asynchronously read lines from a text file.

    Args:
        file_path: The path to the file
        encoding: The text encoding (default: 'utf-8')
        errors: How to handle encoding errors (default: 'replace')

    Returns:
        A list of lines from the file
    """
    async with await anyio.open_file(
        file_path, "r", encoding=encoding, errors=errors
    ) as f:
        return await f.readlines()


async def async_write_text(
    file_path: str,
    content: str,
    mode: str = "w",
    encoding: str = "utf-8",
) -> None:
    """Asynchronously write text to a file.

    Args:
        file_path: The path to the file
        content: The text content to write
        mode: The file open mode (default: 'w')
        encoding: The text encoding (default: 'utf-8')
    """
    async with await anyio.open_file(file_path, mode, encoding=encoding) as f:
        await f.write(content)


async def async_write_binary(file_path: str, content: bytes, mode: str = "wb") -> None:
    """Asynchronously write binary data to a file.

    Args:
        file_path: The path to the file
        content: The binary content to write
        mode: The file open mode (default: 'wb')
    """
    async with await anyio.open_file(file_path, mode) as f:
        await f.write(content)


async def async_detect_encoding(file_path: str) -> str:
    """Asynchronously detect the encoding of a file.

    Args:
        file_path: The path to the file

    Returns:
        The detected encoding, defaulting to 'utf-8'
    """
    if not os.path.exists(file_path):
        return "utf-8"

    try:
        # Try to read with utf-8 first
        await async_open_text(file_path, encoding="utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        # If utf-8 fails, default to a more permissive encoding
        return "latin-1"


async def async_detect_line_endings(file_path: str) -> str:
    """Asynchronously detect the line endings of a file.

    Args:
        file_path: The path to the file

    Returns:
        'CRLF' or 'LF'
    """
    return await detect_line_endings(file_path, return_format="format")
