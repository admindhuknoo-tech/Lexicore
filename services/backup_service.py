"""Safe SQLite backup utilities for LexiCore.

Backups are created before schema migrations and destructive history cleanup.
The service never mutates the source database while copying it: SQLite's
online backup API is used so the snapshot remains consistent even when the
application has an open connection.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


def _default_backup_dir(db_path: str) -> Path:
    configured = os.environ.get("LEXICORE_BACKUP_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path(db_path).expanduser().resolve().parent / "backups")


def create_database_backup(db_path: str, reason: str = "manual", backup_dir: Optional[str] = None) -> Optional[str]:
    """Create a timestamped SQLite snapshot and return its absolute path.

    Returns None when the source database does not yet exist (first startup).
    The filename contains a sanitized reason to make restore points obvious.
    """
    source = Path(db_path).expanduser().resolve()
    if not source.exists() or source.stat().st_size == 0:
        return None

    target_dir = Path(backup_dir).expanduser().resolve() if backup_dir else _default_backup_dir(str(source))
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_reason = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in (reason or "backup"))[:40]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    target = target_dir / f"{source.stem}_{stamp}_{safe_reason}{source.suffix or '.db'}"

    src_conn = sqlite3.connect(str(source))
    dst_conn = sqlite3.connect(str(target))
    try:
        src_conn.backup(dst_conn)
        dst_conn.commit()
    finally:
        dst_conn.close()
        src_conn.close()
    return str(target)


def prune_backups(db_path: str, keep: int = 30, backup_dir: Optional[str] = None) -> int:
    """Keep only the newest N automatic backups; return number removed."""
    keep = max(1, int(keep or 30))
    source = Path(db_path).expanduser().resolve()
    target_dir = Path(backup_dir).expanduser().resolve() if backup_dir else _default_backup_dir(str(source))
    if not target_dir.exists():
        return 0
    files = sorted(target_dir.glob(f"{source.stem}_*{source.suffix or '.db'}"), key=lambda p: p.stat().st_mtime, reverse=True)
    removed = 0
    for path in files[keep:]:
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def ensure_daily_backup(db_path: str, backup_dir: Optional[str] = None) -> Optional[str]:
    """Create at most one routine backup per calendar day.

    This provides a lightweight periodic safety net without requiring a scheduler.
    It runs at application startup; migration/destructive-operation backups remain
    separate and are always created when needed.
    """
    source = Path(db_path).expanduser().resolve()
    if not source.exists() or source.stat().st_size == 0:
        return None
    target_dir = Path(backup_dir).expanduser().resolve() if backup_dir else _default_backup_dir(str(source))
    target_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    pattern = f"{source.stem}_{today}-*_daily_startup{source.suffix or '.db'}"
    if any(target_dir.glob(pattern)):
        return None
    return create_database_backup(str(source), reason="daily_startup", backup_dir=str(target_dir))
