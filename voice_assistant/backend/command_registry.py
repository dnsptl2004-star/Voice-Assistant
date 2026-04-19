"""Utility helpers for fast command lookup."""

from __future__ import annotations

import re
from typing import Any, Callable


Handler = Callable[..., Any]


class CommandRegistry:
    """Register exact and pattern-based command handlers."""

    def __init__(self) -> None:
        self.commands: dict[str, dict[str, Any]] = {}
        self.patterns: dict[str, dict[str, Any]] = {}

    def register(self, keywords: str | list[str], handler: Handler, category: str = "general") -> None:
        """Register one or more keywords for substring matching."""
        if isinstance(keywords, str):
            keywords = [keywords]

        for keyword in keywords:
            normalized = keyword.lower()
            self.commands[normalized] = {
                "handler": handler,
                "category": category,
                "keyword": normalized,
            }

    def register_pattern(self, pattern: str, handler: Handler, category: str = "general") -> None:
        """Register a regex pattern for more complex matches."""
        self.patterns[pattern] = {
            "handler": handler,
            "category": category,
            "compiled": re.compile(pattern, re.IGNORECASE),
        }

    def match(self, text: str) -> Any:
        """Return the first matching handler result for the given text."""
        lowered = text.lower()

        for keyword, command in self.commands.items():
            if keyword in lowered:
                return command["handler"](text, lowered)

        for command in self.patterns.values():
            match = command["compiled"].search(text)
            if match:
                return command["handler"](text, lowered, match)

        return None


registry = CommandRegistry()
