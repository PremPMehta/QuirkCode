"""Mouse movement, clicks, drag, and scroll relative to the IDE window."""

from __future__ import annotations

import logging
import time
from typing import Optional, Tuple

from window_manager import TargetWindow, UI_REGIONS, get_client_point

logger = logging.getLogger(__name__)


class MouseEngine:
    def __init__(self, stop_check=None) -> None:
        self.stop_check = stop_check or (lambda: False)

    def _pyautogui(self):
        import pyautogui

        return pyautogui

    def move_to(
        self,
        x: int,
        y: int,
        duration: float = 0.25,
    ) -> Tuple[int, int]:
        if self.stop_check():
            return (x, y)
        pag = self._pyautogui()
        pag.moveTo(x, y, duration=max(0.05, duration))
        return (x, y)

    def move_to_region(
        self,
        window: TargetWindow,
        region: str,
        jitter: float = 0.03,
        duration: float = 0.25,
        rng=None,
    ) -> Tuple[int, int]:
        fx, fy = UI_REGIONS.get(region, UI_REGIONS["editor"])
        if rng is not None and jitter:
            fx = min(1.0, max(0.0, fx + rng.uniform(-jitter, jitter)))
            fy = min(1.0, max(0.0, fy + rng.uniform(-jitter, jitter)))
        x, y = get_client_point(window, fx, fy)
        return self.move_to(x, y, duration=duration)

    def click(
        self,
        button: str = "left",
        clicks: int = 1,
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> None:
        if self.stop_check():
            return
        pag = self._pyautogui()
        if x is not None and y is not None:
            pag.click(x=x, y=y, clicks=clicks, button=button)
        else:
            pag.click(clicks=clicks, button=button)

    def double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> None:
        self.click(clicks=2, x=x, y=y)

    def drag(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        duration: float = 0.35,
    ) -> None:
        if self.stop_check():
            return
        pag = self._pyautogui()
        pag.moveTo(start[0], start[1], duration=0.15)
        pag.dragTo(end[0], end[1], duration=duration, button="left")

    def scroll(self, amount: int) -> None:
        if self.stop_check():
            return
        pag = self._pyautogui()
        # PyAutoGUI: positive = up, negative = down
        pag.scroll(int(amount))
        time.sleep(0.05)
