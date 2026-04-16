"""
Thread-safe snapshot + stop request for the web dashboard (same process as the bot).
"""
import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

_lock = threading.RLock()
_snapshot: Dict[str, Any] = {"status": "initializing"}
_stop_requested = False
_session_start: float = 0.0


def set_session_start(ts: float) -> None:
    global _session_start
    with _lock:
        _session_start = ts


def set_snapshot(data: Dict[str, Any]) -> None:
    """Called from main trading loop (every ~0.1s)."""
    global _snapshot
    with _lock:
        data = dict(data)
        data["updated_at"] = time.time()
        _snapshot = data


def get_snapshot() -> Dict[str, Any]:
    with _lock:
        return dict(_snapshot)


def request_stop() -> None:
    global _stop_requested
    with _lock:
        _stop_requested = True


def consume_stop_request() -> bool:
    """Main loop: if True, set stop_flag and clear request."""
    global _stop_requested
    with _lock:
        if _stop_requested:
            _stop_requested = False
            return True
        return False


def write_state_file(project_root: Path, data: Dict[str, Any]) -> None:
    """Optional: write logs/bot_state.json for read-only monitoring without shared memory."""
    path = project_root / "logs" / "bot_state.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        payload = dict(data)
        payload["updated_at"] = time.time()
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp.replace(path)
    except OSError:
        pass


def read_state_file(project_root: Path) -> Optional[Dict[str, Any]]:
    path = project_root / "logs" / "bot_state.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
