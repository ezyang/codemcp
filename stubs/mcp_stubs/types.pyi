"""Type stubs for the mcp.types module.

This module provides type definitions for the mcp.types module.
"""

from typing import Any, Dict, List, Optional, Protocol, TypeVar, Union

class TextContent:
    """A class representing text content."""
    
    text: str
    
    def __init__(self, text: str) -> None:
        """Initialize a new TextContent instance.
        
        Args:
            text: The text content
        """
        ...
