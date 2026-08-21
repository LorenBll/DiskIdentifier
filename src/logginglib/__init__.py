"""Shared JSON logging library implementing the project logging standard.

Logs are stored as JSON files containing a list of logged events. Each event
has a `timestamp`, `type` (ERROR/WARN/INFO/DEBUG), `title`, `data`, and a
`hash` (sha256) computed over the canonical serialization of `timestamp`,
`title`, and `data`, so an entry can be referenced by the couple
(projectName, hash).

Log files are named `DD-MM-YYYY_HH.MM.SS.json` under a log directory that
defaults to `<project root>/logs`. On init, log files older than 14 days
(compared by date only) are pruned.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import date, datetime
from pathlib import Path

_RETENTION_DAYS = 14
_VALID_TYPES = ("ERROR", "WARN", "INFO", "DEBUG")

_LOCK = threading.Lock()

_project_name = "unknown"
_debug = False
_log_dir: Path | None = None
_current_file: Path | None = None
_events: list[dict] = []


def _hash_entry(timestamp: str, title: str, data) -> str:
    """Compute the sha256 hash over the canonical entry fields."""
    canonical = json.dumps(
        [timestamp, title, data],
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _parse_log_date(filename: str) -> date | None:
    """Parse the DD-MM-YYYY date prefix from a log filename."""
    try:
        return date(
            year=int(filename[6:10]),
            month=int(filename[3:5]),
            day=int(filename[0:2]),
        )
    except (ValueError, IndexError):
        return None


def _prune_expired_logs() -> None:
    """Remove log files older than the retention period (date-only comparison)."""
    if _log_dir is None or not _log_dir.exists():
        return

    today = date.today()
    for log_file in _log_dir.glob("*.json"):
        file_date = _parse_log_date(log_file.name)
        if file_date is None:
            try:
                file_date = date.fromtimestamp(log_file.stat().st_mtime)
            except OSError:
                continue
        if (today - file_date).days > _RETENTION_DAYS:
            try:
                log_file.unlink()
            except OSError:
                pass


def init_logging(
    project_name: str,
    debug: bool = False,
    log_dir: Path | None = None,
) -> None:
    """Initialize logging: set project/debug/log dir, prune, open run file."""
    global _project_name, _debug, _log_dir, _current_file, _events

    _project_name = project_name
    _debug = bool(debug)

    if log_dir is not None:
        _log_dir = Path(log_dir)
    else:
        _log_dir = Path(__file__).resolve().parent.parent.parent / "logs"

    _log_dir.mkdir(parents=True, exist_ok=True)
    _prune_expired_logs()

    with _LOCK:
        _current_file = _log_dir / f"{datetime.now().strftime('%d-%m-%Y_%H.%M.%S')}.json"
        _events = []


def _log(level: str, title: str, data) -> None:
    """Write a single event to the current run's log file."""
    if _current_file is None:
        return

    timestamp = datetime.now().isoformat()
    entry = {
        "timestamp": timestamp,
        "type": level,
        "title": title,
        "data": data,
        "hash": _hash_entry(timestamp, title, data),
    }

    try:
        with _LOCK:
            _events.append(entry)
            with _current_file.open("w", encoding="utf-8") as handle:
                json.dump(
                    _events,
                    handle,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
    except OSError:
        pass


def log_error(title: str, data=None) -> None:
    """Log an ERROR event."""
    _log("ERROR", title, data)


def log_warn(title: str, data=None) -> None:
    """Log a WARN event."""
    _log("WARN", title, data)


def log_info(title: str, data=None) -> None:
    """Log an INFO event."""
    _log("INFO", title, data)


def log_debug(title: str, data=None) -> None:
    """Log a DEBUG event (no-op unless debug mode is enabled)."""
    if _debug:
        _log("DEBUG", title, data)
