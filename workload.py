"""Workload sequence selection and construction."""

from __future__ import annotations

import random
from typing import Callable, List, Optional

from actions import (
    Action,
    Click,
    CloseTerminal,
    DoubleClick,
    Drag,
    KeyboardBurst,
    MoveMouse,
    NavigateLine,
    OpenTerminal,
    PressKey,
    RunSafeTerminalCommand,
    Scroll,
    SearchText,
    SelectText,
    SwitchIdeApp,
    SwitchTab,
    TemporaryEdit,
    Wait,
)
from config import INTENSITY_PROFILES, AppConfig


SequenceBuilder = Callable[[random.Random, dict, AppConfig], List[Action]]


def _pause(rng: random.Random, profile: dict) -> Wait:
    lo, hi = profile["pause_sec"]
    return Wait(seconds=rng.uniform(lo, hi))


def _action_pause(rng: random.Random, profile: dict) -> Wait:
    lo, hi = profile["action_pause_sec"]
    return Wait(seconds=rng.uniform(lo, hi))


def _core_keyboard_and_tabs(rng: random.Random, profile: dict, cfg: AppConfig) -> List[Action]:
    """Every sequence should exercise tabs + keyboard when those flags are on."""
    actions: List[Action] = []
    if cfg.enable_tab_switching:
        actions.append(SwitchTab())
        actions.append(_action_pause(rng, profile))
    if cfg.enable_keyboard:
        actions.append(KeyboardBurst())
        actions.append(_action_pause(rng, profile))
    return actions


def sequence_a(rng: random.Random, profile: dict, cfg: AppConfig) -> List[Action]:
    """Tabs + keyboard + scroll + temp edit."""
    actions: List[Action] = [
        Click(region="editor"),
        _action_pause(rng, profile),
    ]
    actions.extend(_core_keyboard_and_tabs(rng, profile, cfg))
    if cfg.enable_mouse:
        actions.append(Click(region="editor"))
    if cfg.enable_scrolling:
        actions.append(Scroll())
        actions.append(_action_pause(rng, profile))
    if cfg.enable_keyboard:
        actions.append(NavigateLine())
        actions.append(TemporaryEdit())
    actions.append(_pause(rng, profile))
    return actions


def sequence_b(rng: random.Random, profile: dict, cfg: AppConfig) -> List[Action]:
    """Tabs + search + keyboard + scroll."""
    actions: List[Action] = []
    actions.extend(_core_keyboard_and_tabs(rng, profile, cfg))
    if cfg.enable_keyboard:
        actions.append(SearchText())
        actions.append(_action_pause(rng, profile))
        actions.append(SelectText())
    if cfg.enable_scrolling:
        actions.append(Scroll())
    if cfg.enable_mouse:
        actions.append(MoveMouse(region="editor"))
        actions.append(Click(region="editor"))
    actions.append(_pause(rng, profile))
    return actions


def sequence_c(rng: random.Random, profile: dict, cfg: AppConfig) -> List[Action]:
    """Tabs + keyboard nav + temp edit."""
    actions: List[Action] = []
    if cfg.enable_mouse:
        actions.append(Click(region="editor"))
        actions.append(_action_pause(rng, profile))
        if rng.random() < 0.35:
            actions.append(DoubleClick(region="editor"))
            actions.append(_action_pause(rng, profile))
        if rng.random() < 0.25:
            actions.append(Drag())
            actions.append(_action_pause(rng, profile))
    actions.extend(_core_keyboard_and_tabs(rng, profile, cfg))
    if cfg.enable_keyboard:
        actions.append(PressKey(key="pagedown"))
        actions.append(PressKey(key="pagedown"))
        actions.append(PressKey(key="home"))
        actions.append(NavigateLine())
        actions.append(TemporaryEdit())
    actions.append(_pause(rng, profile))
    return actions


def sequence_d(rng: random.Random, profile: dict, cfg: AppConfig) -> List[Action]:
    """Terminal (optional) then return to editor tabs + keyboard."""
    actions: List[Action] = [
        OpenTerminal(),
        _action_pause(rng, profile),
        RunSafeTerminalCommand(),
        _action_pause(rng, profile),
        CloseTerminal(),
        Click(region="editor"),
    ]
    actions.extend(_core_keyboard_and_tabs(rng, profile, cfg))
    if cfg.enable_scrolling:
        actions.append(Scroll())
    actions.append(_pause(rng, profile))
    return actions


SEQUENCE_BUILDERS: dict[str, SequenceBuilder] = {
    "A": sequence_a,
    "B": sequence_b,
    "C": sequence_c,
    "D": sequence_d,
}


class WorkloadEngine:
    def __init__(self, cfg: AppConfig, seed: Optional[int] = None) -> None:
        self.cfg = cfg
        self.profile = INTENSITY_PROFILES[cfg.intensity]
        self.rng = random.Random(seed if seed is not None else cfg.random_seed)
        self._sequences_since_ide_switch = 0

    def available_sequences(self) -> List[str]:
        names = ["A", "B", "C"]
        if self.cfg.enable_terminal:
            names.append("D")
        return names

    def choose_sequence_name(self) -> str:
        names = self.available_sequences()
        weights = self.profile["sequence_weights"]
        w = [float(weights.get(n, 1.0)) for n in names]
        return self.rng.choices(names, weights=w, k=1)[0]

    def build_sequence(self, name: Optional[str] = None) -> tuple[str, List[Action]]:
        name = name or self.choose_sequence_name()
        builder = SEQUENCE_BUILDERS[name]
        actions = builder(self.rng, self.profile, self.cfg)

        # Auto mode: occasionally switch Cursor <-> VS Code (never QuirkCode)
        self._sequences_since_ide_switch += 1
        if self.cfg.target == "auto" and self._sequences_since_ide_switch >= self.rng.randint(2, 4):
            actions.insert(0, SwitchIdeApp())
            actions.insert(1, _action_pause(self.rng, self.profile))
            self._sequences_since_ide_switch = 0

        actions = [a for a in actions if self._allowed(a)]
        if not actions:
            # Hard fallback so keyboard always happens when enabled
            if self.cfg.enable_keyboard:
                actions = [KeyboardBurst()]
            elif self.cfg.enable_tab_switching:
                actions = [SwitchTab()]
            else:
                actions = [Wait(seconds=0.5)]
        return name, actions

    def _allowed(self, action: Action) -> bool:
        cfg = self.cfg
        n = action.name
        if n in ("move_mouse", "click", "double_click", "drag") and not cfg.enable_mouse:
            return False
        if n == "scroll" and not cfg.enable_scrolling:
            return False
        if n == "switch_tab" and not cfg.enable_tab_switching:
            return False
        if n == "switch_ide" and cfg.target != "auto":
            return False
        if n in (
            "open_terminal",
            "close_terminal",
            "terminal_command",
        ) and not cfg.enable_terminal:
            return False
        if n in (
            "press_key",
            "hotkey",
            "type_text",
            "select_text",
            "navigate_line",
            "search_text",
            "temporary_edit",
            "undo_edit",
            "keyboard_burst",
        ) and not cfg.enable_keyboard:
            return False
        return True
