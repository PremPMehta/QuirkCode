"""Atomic workload actions."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional, TYPE_CHECKING

from config import SAFE_SEARCH_TERMS, SAFE_TERMINAL_COMMAND, TEMP_EDIT_MARKER
from window_manager import get_client_point, refresh_window

if TYPE_CHECKING:
    from input_engine import InputEngine
    from logger import EventLogger
    from window_manager import TargetWindow


@dataclass
class ActionContext:
    input: "InputEngine"
    logger: "EventLogger"
    window: "TargetWindow"
    rng: Any
    sequence_id: int
    stop_check: Any
    profile: dict
    flags: dict
    pending_undos: list  # mutable list counted by controller


class Action(ABC):
    name: str = "action"

    @abstractmethod
    def execute(self, ctx: ActionContext) -> dict:
        ...

    def describe(self) -> str:
        return self.name

    def _refresh(self, ctx: ActionContext) -> None:
        refreshed = refresh_window(ctx.window)
        if refreshed:
            ctx.window = refreshed


@dataclass
class Wait(Action):
    seconds: float = 0.5
    name: str = "wait"

    def execute(self, ctx: ActionContext) -> dict:
        end = time.monotonic() + max(0.0, self.seconds)
        while time.monotonic() < end:
            if ctx.stop_check():
                break
            time.sleep(min(0.1, end - time.monotonic()))
        return {"seconds": self.seconds}


@dataclass
class MoveMouse(Action):
    region: str = "editor"
    duration: float = 0.25
    name: str = "move_mouse"

    def execute(self, ctx: ActionContext) -> dict:
        self._refresh(ctx)
        x, y = ctx.input.move_to_region(
            ctx.window, self.region, duration=self.duration, rng=ctx.rng
        )
        return {"region": self.region, "x": x, "y": y}


@dataclass
class Click(Action):
    region: Optional[str] = "editor"
    name: str = "click"

    def execute(self, ctx: ActionContext) -> dict:
        self._refresh(ctx)
        pos = None
        if self.region:
            pos = ctx.input.move_to_region(
                ctx.window, self.region, duration=0.2, rng=ctx.rng
            )
            ctx.input.click(x=pos[0], y=pos[1])
        else:
            ctx.input.click()
        return {"region": self.region, "pos": pos}


@dataclass
class DoubleClick(Action):
    region: str = "editor"
    name: str = "double_click"

    def execute(self, ctx: ActionContext) -> dict:
        self._refresh(ctx)
        pos = ctx.input.move_to_region(
            ctx.window, self.region, duration=0.2, rng=ctx.rng
        )
        ctx.input.double_click(x=pos[0], y=pos[1])
        return {"region": self.region, "pos": pos}


@dataclass
class Drag(Action):
    name: str = "drag"

    def execute(self, ctx: ActionContext) -> dict:
        self._refresh(ctx)
        start = get_client_point(ctx.window, 0.40, 0.40)
        end = get_client_point(ctx.window, 0.70, 0.40)
        ctx.input.drag(start, end, duration=0.35)
        # Clear selection with Escape to avoid leaving selected text
        ctx.input.press("escape")
        return {"start": start, "end": end}


@dataclass
class Scroll(Action):
    amount: Optional[int] = None
    name: str = "scroll"

    def execute(self, ctx: ActionContext) -> dict:
        choices = ctx.profile.get("scroll_clicks", (-5, 5))
        amount = self.amount if self.amount is not None else ctx.rng.choice(list(choices))
        ctx.input.scroll(amount)
        return {"amount": amount}


@dataclass
class PressKey(Action):
    key: str = "down"
    name: str = "press_key"

    def execute(self, ctx: ActionContext) -> dict:
        ctx.input.press(self.key)
        return {"key": self.key}


@dataclass
class Hotkey(Action):
    keys: tuple = ("ctrl", "tab")
    name: str = "hotkey"

    def execute(self, ctx: ActionContext) -> dict:
        ctx.input.hotkey(*self.keys)
        return {"key": "+".join(self.keys)}


@dataclass
class TypeText(Action):
    text: str = ""
    name: str = "type_text"

    def execute(self, ctx: ActionContext) -> dict:
        ctx.input.type_text(self.text)
        return {"text": self.text}


@dataclass
class SelectText(Action):
    name: str = "select_text"

    def execute(self, ctx: ActionContext) -> dict:
        # Select current line-ish: Home then Shift+End
        ctx.input.press("home")
        ctx.input.hotkey("shift", "end")
        time.sleep(0.1)
        ctx.input.press("right")  # collapse selection without deleting
        return {"mode": "line"}


@dataclass
class SwitchTab(Action):
    """Cycle open editor tabs/files inside the current IDE (Ctrl+Tab / Ctrl+PageDown)."""

    times: Optional[int] = None
    name: str = "switch_tab"

    def execute(self, ctx: ActionContext) -> dict:
        lo, hi = ctx.profile.get("tab_switches_per_seq", (1, 2))
        count = self.times if self.times is not None else ctx.rng.randint(lo, hi)
        # Click editor first so focus is in the tab strip / editor, not QuirkCode
        self._refresh(ctx)
        ctx.input.move_to_region(ctx.window, "editor", duration=0.15, rng=ctx.rng)
        ctx.input.click()
        time.sleep(0.08)
        used_keys = []
        for i in range(count):
            if ctx.stop_check():
                break
            # Alternate shortcuts — both work in VS Code and Cursor
            if i % 2 == 0:
                ctx.input.hotkey("ctrl", "tab")
                used_keys.append("ctrl+tab")
            else:
                ctx.input.hotkey("ctrl", "pagedown")
                used_keys.append("ctrl+pagedown")
            time.sleep(0.18)
        return {"count": count, "keys": used_keys}


@dataclass
class KeyboardBurst(Action):
    """Guaranteed keyboard activity: arrows, home/end, short navigation chords."""

    name: str = "keyboard_burst"

    def execute(self, ctx: ActionContext) -> dict:
        self._refresh(ctx)
        ctx.input.move_to_region(ctx.window, "editor", duration=0.15, rng=ctx.rng)
        ctx.input.click()
        time.sleep(0.05)

        events = []
        # Burst length scales lightly with intensity typing_burst_sec
        lo, hi = ctx.profile.get("typing_burst_sec", (1.0, 3.0))
        steps = max(4, int(ctx.rng.uniform(lo, hi) * 2))

        keys = ["up", "down", "left", "right", "home", "end", "pageup", "pagedown"]
        for _ in range(steps):
            if ctx.stop_check():
                break
            roll = ctx.rng.random()
            if roll < 0.15:
                ctx.input.hotkey("ctrl", "right")
                events.append("ctrl+right")
            elif roll < 0.25:
                ctx.input.hotkey("ctrl", "left")
                events.append("ctrl+left")
            elif roll < 0.35:
                ctx.input.hotkey("shift", "down")
                events.append("shift+down")
                ctx.input.press("right")  # collapse selection
                events.append("right")
            else:
                key = ctx.rng.choice(keys)
                ctx.input.press(key)
                events.append(key)
            time.sleep(0.04)
        return {"events": events, "count": len(events)}


@dataclass
class SwitchIdeApp(Action):
    """Auto mode only: switch focus between Cursor and VS Code (never QuirkCode)."""

    name: str = "switch_ide"

    def execute(self, ctx: ActionContext) -> dict:
        from window_manager import activate_target_window, pick_other_ide_window

        target = ctx.flags.get("target", "auto")
        if target != "auto":
            return {"switched": False, "reason": "target_not_auto"}

        other = pick_other_ide_window(ctx.window, target="auto")
        if other is None:
            return {"switched": False, "reason": "no_other_ide"}

        ok = activate_target_window(other)
        prev_kind = ctx.window.kind
        prev_title = ctx.window.title
        if ok:
            ctx.window = other
            ctx.logger.application = other.kind
            time.sleep(0.2)
            # Focus editor inside the newly activated IDE
            ctx.input.move_to_region(ctx.window, "editor", duration=0.2, rng=ctx.rng)
            ctx.input.click()
        return {
            "switched": ok,
            "from": prev_kind,
            "to": other.kind,
            "from_title": prev_title[:80],
            "to_title": other.title[:80],
        }


@dataclass
class NavigateLine(Action):
    name: str = "navigate_line"

    def execute(self, ctx: ActionContext) -> dict:
        lo, hi = ctx.profile.get("nav_steps", (2, 6))
        steps = ctx.rng.randint(lo, hi)
        keys = [
            "up",
            "down",
            "left",
            "right",
            "home",
            "end",
            "pageup",
            "pagedown",
        ]
        used = []
        for _ in range(steps):
            if ctx.stop_check():
                break
            choice = ctx.rng.choice(keys)
            if choice in ("pageup", "pagedown") and ctx.rng.random() < 0.3:
                ctx.input.hotkey("ctrl", "home" if choice == "pageup" else "end")
                used.append("ctrl+" + ("home" if choice == "pageup" else "end"))
            else:
                ctx.input.press(choice)
                used.append(choice)
            time.sleep(0.04)
        return {"steps": used}


@dataclass
class SearchText(Action):
    term: Optional[str] = None
    name: str = "search_text"

    def execute(self, ctx: ActionContext) -> dict:
        term = self.term or ctx.rng.choice(SAFE_SEARCH_TERMS)
        ctx.input.hotkey("ctrl", "f")
        time.sleep(0.15)
        ctx.input.type_text(term, interval=0.04)
        time.sleep(0.1)
        ctx.input.press("enter")
        time.sleep(0.1)
        ctx.input.press("escape")
        return {"term": term}


@dataclass
class TemporaryEdit(Action):
    marker: str = TEMP_EDIT_MARKER
    name: str = "temporary_edit"

    def execute(self, ctx: ActionContext) -> dict:
        self._refresh(ctx)
        ctx.input.move_to_region(ctx.window, "editor", duration=0.2, rng=ctx.rng)
        ctx.input.click()
        time.sleep(0.05)
        ctx.input.type_text(self.marker, interval=0.025)
        time.sleep(0.08)
        # Select marker then undo
        for _ in range(len(self.marker)):
            if ctx.stop_check():
                break
            ctx.input.hotkey("shift", "left")
        time.sleep(0.05)
        ctx.input.hotkey("ctrl", "z")
        ctx.pending_undos.append(self.marker)
        return {"inserted": self.marker, "reverted": True}


@dataclass
class UndoEdit(Action):
    name: str = "undo_edit"

    def execute(self, ctx: ActionContext) -> dict:
        ctx.input.hotkey("ctrl", "z")
        return {"key": "ctrl+z"}


@dataclass
class OpenTerminal(Action):
    name: str = "open_terminal"

    def execute(self, ctx: ActionContext) -> dict:
        ctx.input.hotkey("ctrl", "`")
        time.sleep(0.25)
        self._refresh(ctx)
        ctx.input.move_to_region(ctx.window, "terminal", duration=0.2, rng=ctx.rng)
        ctx.input.click()
        return {"key": "ctrl+`"}


@dataclass
class CloseTerminal(Action):
    name: str = "close_terminal"

    def execute(self, ctx: ActionContext) -> dict:
        ctx.input.hotkey("ctrl", "`")
        time.sleep(0.15)
        return {"key": "ctrl+`"}


@dataclass
class RunSafeTerminalCommand(Action):
    command: str = SAFE_TERMINAL_COMMAND
    name: str = "terminal_command"

    def execute(self, ctx: ActionContext) -> dict:
        ctx.input.type_text(self.command, interval=0.04)
        time.sleep(0.05)
        ctx.input.press("enter")
        time.sleep(0.2)
        return {"command": self.command}


def log_action(ctx: ActionContext, action: Action, details: dict) -> None:
    # Map action name to logger category
    name = action.name
    if name == "hotkey" and details.get("key") == "ctrl+tab":
        # switch_tab logs separately
        pass
    ctx.logger.record(name, details, sequence=ctx.sequence_id)
