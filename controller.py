"""Test lifecycle controller running on a worker thread."""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from typing import Callable, Optional

from actions import ActionContext, log_action
from config import AppConfig
from input_engine import InputEngine
from logger import EventLogger
from safety import SafetyManager
from window_manager import (
    TargetWindow,
    activate_target_window,
    assert_windows_platform,
    find_target_windows,
    get_foreground_target,
    is_runner_title,
    is_target_window_active,
    pick_initial_window,
    refresh_window,
)
from workload import WorkloadEngine

logger = logging.getLogger(__name__)


class ControllerStatus(str, Enum):
    IDLE = "Idle"
    RUNNING = "Running"
    PAUSED = "Paused"
    FOCUS_LOST = "FocusLost"
    STOPPING = "Stopping"
    COMPLETED = "Completed"
    ERROR = "Error"


class TestController:
    def __init__(
        self,
        cfg: AppConfig,
        event_logger: Optional[EventLogger] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.cfg = cfg
        self.logger = event_logger or EventLogger()
        self.safety = SafetyManager()
        self.input = InputEngine(self.safety)
        self.on_status = on_status

        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # not paused
        self._thread: Optional[threading.Thread] = None
        self._status = ControllerStatus.IDLE
        self._status_lock = threading.Lock()
        self._error_message: Optional[str] = None

        self._start_monotonic: Optional[float] = None
        self._duration_sec: float = 0.0
        self._pause_started: Optional[float] = None
        self._paused_total: float = 0.0

        self._window: Optional[TargetWindow] = None
        self._pending_undos: list = []
        self._hotkey_thread: Optional[threading.Thread] = None
        self._hotkey_stop = threading.Event()

        self.input.set_stop_check(self.should_stop)

    # --- status helpers ---

    def _set_status(self, status: ControllerStatus) -> None:
        with self._status_lock:
            self._status = status
        if self.on_status:
            try:
                self.on_status(status.value)
            except Exception:
                pass

    def get_status(self) -> str:
        with self._status_lock:
            return self._status.value

    def get_error(self) -> Optional[str]:
        return self._error_message

    def should_stop(self) -> bool:
        return self._stop_event.is_set() or self._duration_expired()

    def _duration_expired(self) -> bool:
        if self._start_monotonic is None:
            return False
        return self.elapsed_time() >= self._duration_sec

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def elapsed_time(self) -> float:
        if self._start_monotonic is None:
            return 0.0
        paused = self._paused_total
        if self._pause_started is not None:
            paused += time.monotonic() - self._pause_started
        return max(0.0, time.monotonic() - self._start_monotonic - paused)

    def remaining_time(self) -> float:
        return max(0.0, self._duration_sec - self.elapsed_time())

    # --- lifecycle ---

    def start(self, cfg: Optional[AppConfig] = None) -> None:
        if self.is_running():
            raise RuntimeError("Test is already running")
        if cfg is not None:
            self.cfg = cfg

        assert_windows_platform()

        windows = find_target_windows(self.cfg.target)
        if not windows:
            raise RuntimeError(
                "No VS Code or Cursor window found. "
                "Open the IDE with several files, then try again."
            )

        self._window = pick_initial_window(self.cfg.target) or windows[0]
        if is_runner_title(self._window.title):
            raise RuntimeError("Refusing to target QuirkCode. Open VS Code or Cursor first.")
        self._stop_event.clear()
        self._pause_event.set()
        self._error_message = None
        self._pending_undos = []
        self._paused_total = 0.0
        self._pause_started = None
        self._duration_sec = float(self.cfg.duration_minutes) * 60.0
        self._start_monotonic = time.monotonic()

        self.logger = EventLogger()
        self.logger.start_run(self._window.kind)

        self._set_status(ControllerStatus.RUNNING)
        self._start_emergency_hotkey()

        self._thread = threading.Thread(target=self.run, name="QuirkCodeWorker", daemon=True)
        self._thread.start()

    def pause(self) -> None:
        if not self.is_running():
            return
        if not self._pause_event.is_set():
            return
        self._pause_event.clear()
        self._pause_started = time.monotonic()
        self._set_status(ControllerStatus.PAUSED)
        self.logger.record("pause", {})

    def resume(self) -> None:
        if not self.is_running():
            return
        if self._pause_event.is_set():
            return
        if self._pause_started is not None:
            self._paused_total += time.monotonic() - self._pause_started
            self._pause_started = None
        self._pause_event.set()
        self._set_status(ControllerStatus.RUNNING)
        self.logger.record("resume", {})

    def stop(self) -> None:
        self._set_status(ControllerStatus.STOPPING)
        self._stop_event.set()
        self._pause_event.set()  # unblock pause waits
        self.safety.emergency_release()

    def wait_until_done(self, timeout: Optional[float] = None) -> None:
        if self._thread:
            self._thread.join(timeout=timeout)

    # --- worker ---

    def run(self) -> None:
        end_reason = "completed"
        try:
            if not self._window:
                raise RuntimeError("No target window")
            ok = activate_target_window(self._window)
            if not ok:
                self.logger.record("activate_failed", {"title": self._window.title})

            workload = WorkloadEngine(self.cfg, seed=self.cfg.random_seed)
            flags = self.cfg.to_dict()

            while not self.should_stop():
                self._wait_if_paused()
                if self.should_stop():
                    break

                if not self._ensure_focus():
                    if self.should_stop():
                        break
                    continue

                seq_name, actions = workload.build_sequence()
                seq_id = self.logger.next_sequence_id()
                self.logger.record(
                    "sequence_start",
                    {"name": seq_name, "action_count": len(actions)},
                    sequence=seq_id,
                )

                for action in actions:
                    if self.should_stop():
                        break
                    self._wait_if_paused()
                    if self.should_stop():
                        break
                    if not self._ensure_focus():
                        break

                    ctx = ActionContext(
                        input=self.input,
                        logger=self.logger,
                        window=self._window,
                        rng=workload.rng,
                        sequence_id=seq_id,
                        stop_check=self.should_stop,
                        profile=workload.profile,
                        flags=flags,
                        pending_undos=self._pending_undos,
                    )
                    try:
                        details = action.execute(ctx)
                        if ctx.window:
                            self._window = ctx.window
                        log_action(ctx, action, details)
                    except PermissionError as exc:
                        self.logger.record(
                            "blocked",
                            {"reason": str(exc), "action": action.name},
                            sequence=seq_id,
                        )
                    except Exception as exc:
                        logger.exception("action failed: %s", action.name)
                        self.logger.record(
                            "error",
                            {"action": action.name, "error": str(exc)},
                            sequence=seq_id,
                        )

                self.logger.record(
                    "sequence_end",
                    {"name": seq_name},
                    sequence=seq_id,
                )

            if self._stop_event.is_set() and not self._duration_expired():
                end_reason = "stopped"
            elif self._duration_expired():
                end_reason = "duration_elapsed"
            else:
                end_reason = "completed"

        except Exception as exc:
            logger.exception("controller run failed")
            self._error_message = str(exc)
            end_reason = "error"
            self.logger.record("fatal", {"error": str(exc)})
        finally:
            self._cleanup_after_run(end_reason)

    def _cleanup_after_run(self, end_reason: str) -> None:
        self._set_status(ControllerStatus.STOPPING)
        self.safety.emergency_release()

        # Best-effort workspace restore: undo + dismiss UI
        try:
            if self._window and self.cfg.preserve_workspace:
                activate_target_window(self._window)
                undos = max(5, len(self._pending_undos) + 2)
                done = self.safety.undo_pending_edits(
                    count=undos, stop_check=lambda: False
                )
                self.logger.record(
                    "workspace_restore",
                    {"undo_count": done, "pending_markers": len(self._pending_undos)},
                )
        except Exception as exc:
            self.logger.record("workspace_restore_failed", {"error": str(exc)})

        self.safety.emergency_release()
        self._stop_emergency_hotkey()

        report = self.logger.finish_run(
            status=end_reason,
            extra={
                "duration_seconds": round(self.elapsed_time(), 2),
                "configured_duration_seconds": self._duration_sec,
            },
        )
        self.logger.record("report_written", {"path": str(report)})

        if self._error_message:
            self._set_status(ControllerStatus.ERROR)
        else:
            self._set_status(ControllerStatus.COMPLETED)

    def _wait_if_paused(self) -> None:
        while not self._pause_event.is_set():
            if self._stop_event.is_set():
                return
            time.sleep(0.1)

    def _ensure_focus(self) -> bool:
        """Return True if an IDE target is active. Never send input to QuirkCode."""
        if not self._window:
            return False

        # If QuirkCode (or anything non-IDE) is foreground, pull focus back to IDE
        fg = get_foreground_target(self.cfg.target)
        if fg is None:
            # Foreground is QuirkCode or unrelated app
            import sys

            if sys.platform == "win32":
                try:
                    import win32gui

                    title = win32gui.GetWindowText(win32gui.GetForegroundWindow()) or ""
                    if is_runner_title(title):
                        self.logger.record(
                            "focus_skip_runner",
                            {"title": title},
                        )
                        # Re-activate current IDE — do not stay on QuirkCode
                        if activate_target_window(self._window):
                            self._set_status(ControllerStatus.RUNNING)
                            return True
                        self._set_status(ControllerStatus.FOCUS_LOST)
                        self._poll_until_focus_or_stop()
                        return bool(
                            self._window and is_target_window_active(self._window)
                        )
                except Exception:
                    pass

        refreshed = refresh_window(self._window)
        if refreshed is None:
            windows = find_target_windows(self.cfg.target)
            if not windows:
                self._set_status(ControllerStatus.FOCUS_LOST)
                self.logger.record("focus_lost", {"reason": "window_missing"})
                self._poll_until_focus_or_stop()
                return self._window is not None and is_target_window_active(self._window)
            self._window = windows[0]
        else:
            self._window = refreshed

        if is_target_window_active(self._window):
            if self.get_status() == ControllerStatus.FOCUS_LOST.value:
                self._set_status(ControllerStatus.RUNNING)
            return True

        self._set_status(ControllerStatus.FOCUS_LOST)
        self.logger.record("focus_lost", {"title": self._window.title})
        if activate_target_window(self._window) and is_target_window_active(self._window):
            self._set_status(ControllerStatus.RUNNING)
            return True

        self._poll_until_focus_or_stop()
        return bool(self._window and is_target_window_active(self._window))

    def _poll_until_focus_or_stop(self) -> None:
        """Pause until an IDE is foreground again (ignore QuirkCode)."""
        while not self.should_stop():
            time.sleep(0.4)
            fg = get_foreground_target(self.cfg.target)
            if fg is not None:
                self._window = fg
                self._set_status(ControllerStatus.RUNNING)
                self.logger.record("focus_restored", {"title": fg.title})
                return
            # If only QuirkCode is focused, try bringing IDE forward once in a while
            windows = find_target_windows(self.cfg.target)
            if windows and activate_target_window(windows[0]):
                self._window = windows[0]
                self._set_status(ControllerStatus.RUNNING)
                self.logger.record("focus_restored", {"title": windows[0].title})
                return
        return

    # --- emergency hotkey (Windows RegisterHotKey) ---

    def _start_emergency_hotkey(self) -> None:
        self._hotkey_stop.clear()
        self._hotkey_thread = threading.Thread(
            target=self._hotkey_loop, name="QAEmergencyHotkey", daemon=True
        )
        self._hotkey_thread.start()

    def _stop_emergency_hotkey(self) -> None:
        self._hotkey_stop.set()

    def _hotkey_loop(self) -> None:
        """Ctrl+Shift+F12 emergency stop via RegisterHotKey (Windows only)."""
        import sys

        if sys.platform != "win32":
            return
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            MOD_CONTROL = 0x0002
            MOD_SHIFT = 0x0004
            VK_F12 = 0x7B
            WM_HOTKEY = 0x0312
            HOTKEY_ID = 0x0A01

            if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_SHIFT, VK_F12):
                logger.warning("RegisterHotKey failed for Ctrl+Shift+F12")
                return

            msg = wintypes.MSG()
            while not self._hotkey_stop.is_set() and not self._stop_event.is_set():
                # PeekMessage non-blocking
                has = user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1)
                if has and msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    self.logger.record("emergency_hotkey", {"keys": "ctrl+shift+f12"})
                    self.stop()
                    break
                time.sleep(0.05)

            user32.UnregisterHotKey(None, HOTKEY_ID)
        except Exception as exc:
            logger.warning("emergency hotkey loop error: %s", exc)
