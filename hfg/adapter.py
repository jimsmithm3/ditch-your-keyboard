"""The boundary between the base app and one game.

The base app calls only these methods. Everything GSPro-specific (its window title, its screens, its clicks, its
keys and its course database) belongs behind one adapter. Another game is another adapter.

Positions are fractions of the game window (0.0 to 1.0), so a layout works at any window size.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Command:
    """One thing the user can say. Keys and clicks are sent by the adapter, not by the base app."""

    phrases: tuple[str, ...]  # the words heard; the first is the name the table shows
    description: str
    area: str = ""  # which grammar or screen it belongs to, for the commands page


class GameAdapter(Protocol):
    """Everything the base app needs from one game. Each method is called on the thread the listener uses."""

    name: str  # shown in the app, for example "GSPro"
    process_title: str  # the window title used to find the game

    def find_window(self) -> int | None:
        """The game's window handle, or None if the game is not running."""

    def focus(self, window: int) -> bool:
        """Bring the game to the front. False if it could not be done, in which case nothing is sent to it."""

    def click(self, window: int, point: tuple[float, float], label: str) -> None:
        """Click a point given as window fractions."""

    def press(self, keys: str | tuple[str, ...], label: str) -> None:
        """Press a key, or a modifier with a key, in the game."""

    def current_screen(self) -> str | None:
        """The screen key the game is on as far as the adapter knows, or None when it is not known."""

    def commands(self) -> Sequence[Command]:
        """Every command the game offers, for the commands page and the grammar."""

    def grammars(self) -> Mapping[str, tuple[str, ...]]:
        """The phrases that listen on each screen or panel, keyed by the grammar name."""

    def layout(self) -> Mapping[str, object]:
        """Boxes and where each command goes on each screen. The data the layout tool draws and edits."""

    def handle(self, phrase: str, on_done: Callable[[str], None]) -> str | None:
        """Run a phrase the adapter owns. Return a note for the log and the status line, or None if this adapter does
        not handle the phrase (the base app then tries the next one)."""


_adapters: list[GameAdapter] = []


def register(adapter: GameAdapter) -> None:
    """Add a game. The base app asks each registered adapter in order, so the first one that handles a phrase wins."""
    _adapters.append(adapter)


def adapters() -> tuple[GameAdapter, ...]:
    return tuple(_adapters)
