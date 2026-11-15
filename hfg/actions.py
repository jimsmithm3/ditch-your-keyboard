"""Actions: the things a plug-in can do, and chains that run several of them in order.

A plug-in gets the core actions out of the box (click, slider, text entry, grid). A plug-in that needs something
complicated writes its own action and registers it under a name. A chain is a list of steps: each step names an
action, gives it parameters, and says how long to wait before the next step.

Actions run on the thread the chain is run on. An action raises ActionFailed to stop the chain early.
"""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol


class ActionFailed(Exception):
    """An action could not be done (for example the game is not in front). The chain stops at that step."""


@dataclass(frozen=True)
class Step:
    action: str  # the name of a registered action
    params: Mapping[str, object] = field(default_factory=dict)
    delay_after: float = 0.0  # seconds to wait before the next step; set per chain, so it can be tuned


class Action(Protocol):
    name: str  # the name a Step uses

    def run(self, game: object, params: Mapping[str, object]) -> str | None:
        """Do the action in the game. `game` is the plug-in's GameAdapter. Return a short note, or None."""


_actions: dict[str, Action] = {}


def register_action(action: Action) -> None:
    _actions[action.name] = action


def action(name: str) -> Action:
    return _actions[name]


def run_chain(steps: Sequence[Step], game: object) -> list[str]:
    """Run the steps in order, waiting delay_after between them. Returns each step's note. Raises ActionFailed
    (with the steps before it already done) if a step cannot be done."""
    notes: list[str] = []
    for index, step in enumerate(steps):
        note = action(step.action).run(game, step.params)
        if note:
            notes.append(note)
        if index < len(steps) - 1 and step.delay_after > 0:
            time.sleep(step.delay_after)
    return notes


class Click:
    """Click a point given as window fractions. params: x, y (0.0 to 1.0)."""

    name = "click"

    def run(self, game: object, params: Mapping[str, object]) -> str | None:
        game.click_fraction(float(params["x"]), float(params["y"]), label=str(params.get("label", "click")))
        return None


class Slider:
    """Press a slider's left end, then drag it right until the chain's next step says stop.
    params: left_x, left_y, right_x (window fractions)."""

    name = "slider"

    def run(self, game: object, params: Mapping[str, object]) -> str | None:
        game.drag_fraction(float(params["left_x"]), float(params["left_y"]), float(params["right_x"]))
        return "dragging; a stop step ends it"


class TextEntry:
    """Type text into the box that has focus. params: text."""

    name = "text_entry"

    def run(self, game: object, params: Mapping[str, object]) -> str | None:
        game.type_text(str(params["text"]))
        return None


class Grid:
    """Pick a point with the lettered grid. params: passes (one per level of the grid)."""

    name = "grid"

    def run(self, game: object, params: Mapping[str, object]) -> str | None:
        game.pick_with_grid(int(params.get("passes", 2)))
        return None


for _core in (Click(), Slider(), TextEntry(), Grid()):
    register_action(_core)
