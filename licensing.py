"""LexiCore commercial desktop offline licensing.

Desktop licensing is intentionally standalone: no runtime license server is
required. A signed Ed25519 license envelope is issued offline by the license
authority and is bound to exactly one device fingerprint hash. The desktop
contains only the public verification key.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
except Exception:  # pragma: no cover - deployment dependency guard
    InvalidSignature = Exception
    serialization = None
    Ed25519PublicKey = None

PRODUCT = "LexiCore"
LICENSE_FILENAME = "license.json"
INSTALLATION_ID_PREFIX = "LEXICORE-DEVICE-V1-"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    try:
        text = str(value).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _norm_component(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip()).upper()
    if text in {"", "NONE", "UNKNOWN", "DEFAULT STRING", "TO BE FILLED BY O.E.M."}:
        return ""
    return text


def _windows_machine_guid() -> str:
    if not sys.platform.startswith("win"):
        return ""
    try:
        import winreg
        access = winreg.KEY_READ
        if hasattr(winreg, "KEY_WOW64_64KEY"):
            access |= winreg.KEY_WOW64_64KEY
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0, access) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return _norm_component(value)
    except Exception:
        return ""


def _windows_bios_uuid() -> str:
    if not sys.platform.startswith("win"):
        return ""
    command = [
        "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
        "(Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID",
    ]
    try:
        cp = subprocess.run(
            command, capture_output=True, text=True, timeout=4, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        lines = (cp.stdout or "").splitlines()
        return _norm_component(lines[0] if lines else "")
    except Exception:
        return ""


def device_fingerprint_hash(extra_components: Optional[list[str]] = None) -> str:
    """Return a stable SHA-256 device fingerprint; raw identifiers are never persisted."""
    stable = [_windows_machine_guid(), _windows_bios_uuid()]
    stable = [x for x in stable if x]
    if stable:
        components = stable + [_norm_component(platform.system()), _norm_component(platform.machine())]
    else:
        machine_id = ""
        if not sys.platform.startswith("win"):
            try:
                machine_id = _norm_component(Path("/etc/machine-id").read_text(encoding="utf-8"))
            except Exception:
                machine_id = ""
        components = [
            machine_id, _norm_component(platform.system()), _norm_component(platform.machine()),
            _norm_component(platform.node()), _norm_component(uuid.getnode()),
        ]
    if extra_components:
        components.extend(_norm_component(x) for x in extra_components)
    useful = sorted({x for x in components if x})
    if not useful:
        raise RuntimeError("DEVICE_FINGERPRINT_UNAVAILABLE")
    material = "LEXICORE-DEVICE-V1|" + "|".join(useful)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def installation_id(fingerprint: Optional[str] = None) -> str:
    fp = (fingerprint or device_fingerprint_hash()).strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", fp):
        raise ValueError("INVALID_DEVICE_FINGERPRINT")
    return INSTALLATION_ID_PREFIX + fp


def installation_id_to_fingerprint(value: str) -> str:
    text = str(value or "").strip()
    if text.upper().startswith(INSTALLATION_ID_PREFIX):
        text = text[len(INSTALLATION_ID_PREFIX):]
    text = text.lower()
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise ValueError("INVALID_INSTALLATION_ID")
    return text


def _canonical_payload(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _bundle_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def _default_data_dir() -> Path:
    configured = os.environ.get("LEXICORE_DATA_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return (Path(base) / PRODUCT).resolve()
    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Application Support" / PRODUCT).resolve()
    return (Path.home() / ".lexicore").resolve()


def _public_key_bytes() -> bytes:
    inline = os.environ.get("LEXICORE_LICENSE_PUBLIC_KEY", "").strip()
    if inline:
        return inline.replace("\\n", "\n").encode("utf-8")
    path = os.environ.get("LEXICORE_LICENSE_PUBLIC_KEY_FILE", "").strip()
    candidates = [Path(path)] if path else []
    candidates.extend([_bundle_root() / "license_public_key.pem", Path(__file__).resolve().parent / "license_public_key.pem"])
    for candidate in candidates:
        try:
            if candidate and candidate.is_file():
                return candidate.read_bytes()
        except Exception:
            continue
    raise RuntimeError("LICENSE_PUBLIC_KEY_MISSING")


def verify_signed_envelope(envelope: dict, public_key_pem: Optional[bytes] = None) -> dict:
    if Ed25519PublicKey is None or serialization is None:
        raise RuntimeError("CRYPTOGRAPHY_DEPENDENCY_MISSING")
    if not isinstance(envelope, dict) or not isinstance(envelope.get("payload"), dict) or not envelope.get("signature"):
        raise ValueError("INVALID_LICENSE_ENVELOPE")
    payload = envelope["payload"]
    try:
        signature = base64.b64decode(envelope["signature"], validate=True)
    except Exception as exc:
        raise ValueError("INVALID_LICENSE_SIGNATURE_ENCODING") from exc
    key_data = public_key_pem or _public_key_bytes()
    key = serialization.load_pem_public_key(key_data)
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("LICENSE_PUBLIC_KEY_NOT_ED25519")
    try:
        key.verify(signature, _canonical_payload(payload))
    except InvalidSignature as exc:
        raise ValueError("INVALID_LICENSE_SIGNATURE") from exc
    return payload


@dataclass
class LicenseState:
    status: str
    allowed: bool
    message: str
    license_id: str = ""
    plan: str = ""
    expires_at: str = ""
    device_fingerprint_hash: str = ""
    installation_id: str = ""
    needs_activation: bool = False

    def as_dict(self) -> dict:
        return self.__dict__.copy()


class LicenseManager:
    def __init__(
        self,
        *,
        data_dir: Optional[Path] = None,
        public_key_pem: Optional[bytes] = None,
        now: Callable[[], datetime] = _utcnow,
        fingerprint: Callable[[], str] = device_fingerprint_hash,
    ):
        self.data_dir = (data_dir or _default_data_dir()).resolve()
        self.license_path = self.data_dir / LICENSE_FILENAME
        self.public_key_pem = public_key_pem
        self.now = now
        self.fingerprint = fingerprint

    def current_installation_id(self) -> str:
        return installation_id(self.fingerprint())

    def _load_envelope(self) -> Optional[dict]:
        try:
            if not self.license_path.is_file():
                return None
            return json.loads(self.license_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _save_envelope(self, envelope: dict) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.license_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except Exception:
            pass
        os.replace(tmp, self.license_path)
        try:
            os.chmod(self.license_path, 0o600)
        except Exception:
            pass

    def _verified_payload(self, envelope: Optional[dict] = None) -> tuple[Optional[dict], Optional[str]]:
        envelope = envelope if envelope is not None else self._load_envelope()
        if not envelope:
            return None, "LICENSE_NOT_FOUND"
        try:
            payload = verify_signed_envelope(envelope, self.public_key_pem)
        except Exception as exc:
            return None, str(exc)
        try:
            current_fp = self.fingerprint()
        except Exception as exc:
            return None, str(exc)
        if payload.get("device_fingerprint_hash") != current_fp:
            return None, "DEVICE_MISMATCH"
        if payload.get("product") not in (None, "", PRODUCT):
            return None, "PRODUCT_MISMATCH"
        if str(payload.get("status") or "").upper() != "ACTIVE":
            return None, "LICENSE_INACTIVE"
        return payload, None

    def _state_from_payload(self, payload: dict, status: str, message: str, *, allowed: bool) -> LicenseState:
        fp = str(payload.get("device_fingerprint_hash") or "")
        return LicenseState(
            status=status,
            allowed=allowed,
            message=message,
            license_id=str(payload.get("license_id") or ""),
            plan=str(payload.get("plan") or ""),
            expires_at=str(payload.get("expires_at") or ""),
            device_fingerprint_hash=fp,
            installation_id=installation_id(fp) if re.fullmatch(r"[0-9a-f]{64}", fp or "") else "",
            needs_activation=not allowed,
        )

    def local_status(self) -> LicenseState:
        try:
            iid = self.current_installation_id()
        except Exception:
            iid = ""
        payload, error = self._verified_payload()
        if not payload:
            return LicenseState(
                status="ACTIVATION_REQUIRED" if error == "LICENSE_NOT_FOUND" else "BLOCKED",
                allowed=False,
                message=error or "LICENSE_INVALID",
                installation_id=iid,
                needs_activation=True,
            )
        expires = _parse_time(payload.get("expires_at"))
        if expires and self.now() > expires:
            return self._state_from_payload(payload, "EXPIRED", "LICENSE_EXPIRED", allowed=False)
        return self._state_from_payload(payload, "ACTIVE", "LICENSE_ACTIVE_OFFLINE", allowed=True)

    def status(self) -> LicenseState:
        return self.local_status()

    def install_license(self, envelope: dict) -> LicenseState:
        payload, error = self._verified_payload(envelope)
        if not payload:
            return LicenseState(
                status="BLOCKED", allowed=False, message=error or "LICENSE_INVALID",
                installation_id=self.current_installation_id(), needs_activation=True,
            )
        expires = _parse_time(payload.get("expires_at"))
        if expires and self.now() > expires:
            return self._state_from_payload(payload, "EXPIRED", "LICENSE_EXPIRED", allowed=False)
        self._save_envelope(envelope)
        return self.local_status()

    def remove_local_license(self) -> LicenseState:
        try:
            self.license_path.unlink(missing_ok=True)
        except Exception:
            pass
        return LicenseState(
            status="ACTIVATION_REQUIRED", allowed=False, message="LOCAL_LICENSE_REMOVED",
            installation_id=self.current_installation_id(), needs_activation=True,
        )


_default_manager: Optional[LicenseManager] = None


def get_license_manager() -> LicenseManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = LicenseManager()
    return _default_manager


def licensing_required() -> bool:
    return os.environ.get("LEXICORE_LICENSE_REQUIRED", "0").strip().lower() in {"1", "true", "yes", "on"}
