"""Console-log detector (Linux): tail Dota's console.log for the ready-up message.

With launch options ``-condebug -conclearlog``, Dota writes ``console.log`` and —
on Linux — updates it in real time. When a match is found, the Game Coordinator
logs ``k_EMsgGCReadyUpStatus`` repeatedly during the ready-check; the first such
line lands the instant the Accept popup appears (verified ~11s before the user
accepts, and independent of whether they accept at all).

We tail the file and fire on the first new trigger line. A ``_fired`` latch
ignores the repeated status lines; it resets on truncation (``-conclearlog``
wipes the log when Dota relaunches) so a later real match still fires. No thread
is needed — each ``poll()`` reads only the bytes appended since the last call.

This backend is Linux-only: on Windows ``console.log`` is buffered until the
client exits, so there's nothing to tail in real time.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .base import Detector, MatchEvent

# Known Steam locations (native + Flatpak). Expanded at resolve time.
_CANDIDATES = [
    "~/.local/share/Steam/steamapps/common/dota 2 beta/game/dota/console.log",
    "~/.var/app/com.valvesoftware.Steam/.local/share/Steam/"
    "steamapps/common/dota 2 beta/game/dota/console.log",
]

DEFAULT_TRIGGERS = ["k_EMsgGCReadyUpStatus"]


def candidate_paths() -> list[Path]:
    return [Path(p).expanduser() for p in _CANDIDATES]


def resolve_console_log(configured: str = "auto") -> Path | None:
    """Resolve ``configured`` to a console.log path.

    "auto" -> the first existing candidate; an explicit path -> itself if it
    exists. Returns None if nothing is found.
    """
    if configured and configured != "auto":
        path = Path(configured).expanduser()
        return path if path.exists() else None
    return next((p for p in candidate_paths() if p.exists()), None)


class ConsoleLogDetector(Detector):
    def __init__(self, log_path: str = "auto", triggers: list[str] | None = None) -> None:
        self._configured = log_path
        self._triggers = list(triggers) if triggers else list(DEFAULT_TRIGGERS)
        self._path: Path | None = None
        self._fp = None
        self._inode: int | None = None
        self._pos = 0
        self._fired = False  # latch: only notify once per ready-check

    # -- readiness ---------------------------------------------------------

    def preflight(self) -> str | None:
        if sys.platform != "linux":
            return (
                "Console detection only works on Linux (Dota's console.log isn't "
                "real-time on Windows). Use the screen detector there."
            )
        path = resolve_console_log(self._configured)
        if path is None:
            searched = "\n  ".join(str(p) for p in candidate_paths())
            return (
                "Couldn't find Dota's console.log.\n"
                "In Steam set Dota's Launch Options to  -condebug -conclearlog  "
                "and start Dota once.\nLooked in:\n  " + searched
            )
        if not os.access(path, os.R_OK):
            return f"Found console.log but can't read it: {path}"
        return None

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        self._path = resolve_console_log(self._configured)
        self._fp = None
        self._inode = None
        self._pos = 0
        self._fired = False
        # Begin watching from the log's current end now, so a match that happens
        # right after start() isn't missed (and pre-existing history is skipped).
        self._ensure_open()

    def _ensure_open(self) -> bool:
        """Open/reopen the log; on first open seek to the end so we only react to
        NEW lines (a fresh ready-check), not pre-existing history. Returns False
        if the log isn't available yet."""
        if self._path is None:
            self._path = resolve_console_log(self._configured)
            if self._path is None:
                return False
        try:
            st = os.stat(self._path)
        except FileNotFoundError:
            if self._fp is not None:
                self._fp.close()
                self._fp = None
            self._inode = None
            return False

        if self._fp is None or st.st_ino != self._inode:  # first open or rotation
            first_open = self._inode is None
            if self._fp is not None:
                self._fp.close()
            self._fp = open(self._path, encoding="utf-8", errors="replace")  # noqa: SIM115
            self._inode = st.st_ino
            if first_open:
                self._fp.seek(0, os.SEEK_END)  # skip existing history
                self._pos = self._fp.tell()
            else:
                self._pos = 0  # rotated -> read the new file from the top

        if st.st_size < self._pos:  # truncated (e.g. -conclearlog on relaunch)
            self._pos = 0
            self._fired = False  # new session -> allow firing again

        return True

    def poll(self) -> MatchEvent | None:
        if not self._ensure_open():
            return None
        self._fp.seek(self._pos)
        chunk = self._fp.read()
        self._pos = self._fp.tell()
        if not chunk:
            return None
        for line in chunk.splitlines():
            if any(t in line for t in self._triggers):
                if self._fired:
                    return None
                self._fired = True
                return MatchEvent(kind="match_found", confidence=1.0)
        return None

    def stop(self) -> None:
        if self._fp is not None:
            self._fp.close()
            self._fp = None
