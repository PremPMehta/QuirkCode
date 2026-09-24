"""Structured event logging and live statistics."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config import logs_dir


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


@dataclass
class Stats:
    keyboard_events: int = 0
    mouse_events: int = 0
    scroll_events: int = 0
    tab_switches: int = 0
    temporary_edits: int = 0
    sequences: int = 0
    visited_tabs: int = 0

    def snapshot(self) -> dict[str, int]:
        return {
            "keyboard_events": self.keyboard_events,
            "mouse_events": self.mouse_events,
            "scroll_events": self.scroll_events,
            "tab_switches": self.tab_switches,
            "temporary_edits": self.temporary_edits,
            "sequences": self.sequences,
            "visited_tabs": self.visited_tabs,
        }


class EventLogger:
    """Thread-safe JSONL logger with counters for the GUI."""

    def __init__(self, run_id: Optional[str] = None) -> None:
        self._lock = threading.Lock()
        self.stats = Stats()
        stamp = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_id = stamp
        self.jsonl_path = logs_dir() / f"run_{stamp}.jsonl"
        self.report_path = logs_dir() / f"run_{stamp}_report.json"
        self._sequence_counter = 0
        self.application: str = "unknown"
        self._started_at: Optional[str] = None
        self._ended_at: Optional[str] = None
        self._status: str = "idle"

    def start_run(self, application: str) -> None:
        with self._lock:
            self.application = application
            self._started_at = _now_iso()
            self._status = "running"
            self.stats = Stats()
            self._sequence_counter = 0
            self.jsonl_path.write_text("", encoding="utf-8")
        self.record(
            "run_start",
            {"application": application, "run_id": self.run_id},
        )

    def next_sequence_id(self) -> int:
        with self._lock:
            self._sequence_counter += 1
            return self._sequence_counter

    def record(
        self,
        action: str,
        details: Optional[dict[str, Any]] = None,
        sequence: Optional[int] = None,
    ) -> None:
        entry = {
            "timestamp": _now_iso(),
            "action": action,
            "details": details or {},
            "application": self.application,
            "sequence": sequence,
        }
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with self._lock:
            with self.jsonl_path.open("a", encoding="utf-8") as f:
                f.write(line)
            self._bump_counters(action, details or {})

    def _bump_counters(self, action: str, details: dict[str, Any]) -> None:
        a = action.lower()
        if a in (
            "keyboard",
            "keyboard_burst",
            "press_key",
            "hotkey",
            "type_text",
            "select_text",
            "search_text",
            "navigate_line",
            "undo_edit",
            "open_terminal",
            "close_terminal",
            "temporary_edit",
            "switch_tab",
        ):
            # Count key activity; switch_tab / temporary_edit also bump their own counters
            if a == "keyboard_burst":
                self.stats.keyboard_events += int(details.get("count", 1))
            elif a == "switch_tab":
                self.stats.keyboard_events += int(details.get("count", 1))
            else:
                self.stats.keyboard_events += 1
        if a in (
            "mouse",
            "move_mouse",
            "click",
            "double_click",
            "drag",
        ):
            self.stats.mouse_events += 1
        if a == "scroll":
            self.stats.scroll_events += 1
        if a == "switch_tab":
            self.stats.tab_switches += 1
            self.stats.visited_tabs += int(details.get("count", 1))
        if a == "temporary_edit":
            self.stats.temporary_edits += 1
        if a == "switch_ide":
            pass
        if a == "sequence_start":
            self.stats.sequences += 1

    def get_stats(self) -> dict[str, int]:
        with self._lock:
            return self.stats.snapshot()

    def finish_run(
        self,
        status: str,
        extra: Optional[dict[str, Any]] = None,
    ) -> Path:
        with self._lock:
            self._ended_at = _now_iso()
            self._status = status
            report = {
                "run_id": self.run_id,
                "status": status,
                "application": self.application,
                "started_at": self._started_at,
                "ended_at": self._ended_at,
                "stats": self.stats.snapshot(),
                "jsonl_path": str(self.jsonl_path),
            }
            if extra:
                report.update(extra)
            with self.report_path.open("w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
                f.write("\n")
        self.record("run_end", {"status": status, **(extra or {})})
        return self.report_path
