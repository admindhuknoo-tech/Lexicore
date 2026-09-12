"""Minimal LexiCore activation server reference implementation.

Deploy this service separately from the desktop app. Keep LEXICORE_LICENSE_PRIVATE_KEY
and LEXICORE_LICENSE_ADMIN_KEY on the server only. Never package them with LexiCore Desktop.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, jsonify, request
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

DB_PATH = Path(os.environ.get("LEXICORE_LICENSE_DB", "license_server.db")).resolve()
PRODUCT = "LexiCore"
REVALIDATE_HOURS = int(os.environ.get("LEXICORE_LICENSE_REVALIDATE_HOURS", "72"))
OFFLINE_GRACE_DAYS = int(os.environ.get("LEXICORE_LICENSE_OFFLINE_GRACE_DAYS", "14"))
app = Flask(__name__)


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _conn():
    c = sqlite3.connect(str(DB_PATH), timeout=10)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS licenses(
            id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, plan TEXT DEFAULT 'desktop',
            status TEXT DEFAULT 'ACTIVE', device_fingerprint_hash TEXT,
            expires_at TEXT, activated_at TEXT, last_validated_at TEXT, created_at TEXT NOT NULL)""")
        c.commit()


def _token_hash(token: str) -> str:
    pepper = os.environ.get("LEXICORE_LICENSE_TOKEN_PEPPER", "")
    if not pepper:
        raise RuntimeError("LEXICORE_LICENSE_TOKEN_PEPPER_REQUIRED")
    return hashlib.sha256((pepper + "|" + token).encode("utf-8")).hexdigest()


def _private_key():
    raw = os.environ.get("LEXICORE_LICENSE_PRIVATE_KEY", "").replace("\\n", "\n").encode("utf-8")
    path = os.environ.get("LEXICORE_LICENSE_PRIVATE_KEY_FILE", "")
    if not raw and path:
        raw = Path(path).read_bytes()
    if not raw:
        raise RuntimeError("LEXICORE_LICENSE_PRIVATE_KEY_REQUIRED")
    key = serialization.load_pem_private_key(raw, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise RuntimeError("LICENSE_PRIVATE_KEY_NOT_ED25519")
    return key


def _signed_license(row, device_hash: str):
    now = _now()
    exp = row["expires_at"] or _iso(now + timedelta(days=3650))
    payload = {
        "product": PRODUCT,
        "license_id": row["id"],
        "plan": row["plan"] or "desktop",
        "status": row["status"],
        "device_fingerprint_hash": device_hash,
        "issued_at": _iso(now),
        "expires_at": exp,
        "next_check_at": _iso(now + timedelta(hours=REVALIDATE_HOURS)),
        "offline_until": _iso(now + timedelta(days=OFFLINE_GRACE_DAYS)),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    sig = _private_key().sign(canonical)
    return {"payload": payload, "signature": base64.b64encode(sig).decode("ascii")}


def _bad(error, status=400):
    return jsonify(success=False, error=error), status


def _payload():
    return request.get_json(silent=True) or {}


@app.post('/v1/activate')
def activate():
    data = _payload()
    if data.get("product") != PRODUCT:
        return _bad("PRODUCT_MISMATCH")
    token = str(data.get("activation_token") or "").strip()
    device = str(data.get("device_fingerprint_hash") or "").strip()
    if len(token) < 12 or len(device) != 64:
        return _bad("INVALID_ACTIVATION_REQUEST")
    try:
        th = _token_hash(token)
    except RuntimeError as exc:
        return _bad(str(exc), 500)
    with _conn() as c:
        row = c.execute("SELECT * FROM licenses WHERE token_hash=?", (th,)).fetchone()
        if not row:
            return _bad("INVALID_ACTIVATION_TOKEN", 403)
        if row["status"] != "ACTIVE":
            return _bad("LICENSE_INACTIVE", 403)
        if row["device_fingerprint_hash"] and row["device_fingerprint_hash"] != device:
            return _bad("LICENSE_ALREADY_BOUND_TO_OTHER_DEVICE", 409)
        now = _iso(_now())
        c.execute("UPDATE licenses SET device_fingerprint_hash=?, activated_at=COALESCE(activated_at,?), last_validated_at=? WHERE id=?", (device, now, now, row["id"]))
        c.commit()
        row = c.execute("SELECT * FROM licenses WHERE id=?", (row["id"],)).fetchone()
    return jsonify(success=True, license=_signed_license(row, device))


@app.post('/v1/validate')
def validate():
    data = _payload()
    license_id = str(data.get("license_id") or "")
    device = str(data.get("device_fingerprint_hash") or "")
    with _conn() as c:
        row = c.execute("SELECT * FROM licenses WHERE id=?", (license_id,)).fetchone()
        if not row:
            return _bad("LICENSE_NOT_FOUND", 404)
        if row["status"] != "ACTIVE":
            return _bad("LICENSE_REVOKED" if row["status"] == "REVOKED" else "LICENSE_INACTIVE", 403)
        if row["device_fingerprint_hash"] != device:
            return _bad("DEVICE_MISMATCH", 403)
        if row["expires_at"]:
            try:
                if _now() > datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00")):
                    return _bad("LICENSE_EXPIRED", 403)
            except Exception:
                return _bad("LICENSE_EXPIRY_INVALID", 500)
        c.execute("UPDATE licenses SET last_validated_at=? WHERE id=?", (_iso(_now()), license_id)); c.commit()
    return jsonify(success=True, license=_signed_license(row, device))


@app.post('/v1/deactivate')
def deactivate():
    data = _payload()
    license_id = str(data.get("license_id") or "")
    device = str(data.get("device_fingerprint_hash") or "")
    with _conn() as c:
        row = c.execute("SELECT * FROM licenses WHERE id=?", (license_id,)).fetchone()
        if not row or row["device_fingerprint_hash"] != device:
            return _bad("LICENSE_OR_DEVICE_NOT_FOUND", 404)
        c.execute("UPDATE licenses SET device_fingerprint_hash=NULL, activated_at=NULL, last_validated_at=NULL WHERE id=?", (license_id,)); c.commit()
    return jsonify(success=True)


def _admin_ok():
    expected = os.environ.get("LEXICORE_LICENSE_ADMIN_KEY", "")
    supplied = request.headers.get("X-LexiCore-Admin-Key", "")
    return bool(expected) and secrets.compare_digest(expected, supplied)


@app.post('/admin/licenses')
def admin_create_license():
    if not _admin_ok(): return _bad("ADMIN_UNAUTHORIZED", 401)
    data = _payload(); token = str(data.get("activation_token") or "").strip() or secrets.token_urlsafe(24)
    license_id = "LC-" + secrets.token_hex(8).upper()
    expires_at = data.get("expires_at")
    plan = str(data.get("plan") or "desktop")[:64]
    with _conn() as c:
        c.execute("INSERT INTO licenses(id,token_hash,plan,status,expires_at,created_at) VALUES(?,?,?,?,?,?)", (license_id,_token_hash(token),plan,"ACTIVE",expires_at,_iso(_now()))); c.commit()
    return jsonify(success=True, license_id=license_id, activation_token=token)


@app.post('/admin/licenses/<license_id>/reset')
def admin_reset_license(license_id):
    if not _admin_ok(): return _bad("ADMIN_UNAUTHORIZED", 401)
    with _conn() as c:
        cur=c.execute("UPDATE licenses SET device_fingerprint_hash=NULL, activated_at=NULL, last_validated_at=NULL WHERE id=?", (license_id,)); c.commit()
    return jsonify(success=bool(cur.rowcount))


@app.post('/admin/licenses/<license_id>/revoke')
def admin_revoke_license(license_id):
    if not _admin_ok(): return _bad("ADMIN_UNAUTHORIZED", 401)
    with _conn() as c:
        cur=c.execute("UPDATE licenses SET status='REVOKED' WHERE id=?", (license_id,)); c.commit()
    return jsonify(success=bool(cur.rowcount))


if __name__ == '__main__':
    init_db()
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT','8443')), debug=False)
