"""Dynamic user/firm identity provider for commercial LexiCore deployments.

Product identity (LexiCore) is stable. Professional/firm identity is installation/user
specific and is stored locally in SQLite. Exporters and client-facing generators read
from this module as the single source of truth.
"""
from __future__ import annotations

from database import AppProfileManager


def get_identity_profile() -> dict:
    p = AppProfileManager.get()
    professional = (p.get("professional_name") or "").strip()
    firm = (p.get("firm_name") or "").strip()
    credentials = (p.get("credentials") or "").strip()
    display = firm or professional or "Pengguna LexiCore"
    signatory = professional or firm or "Pengguna LexiCore"
    if credentials and professional and credentials.casefold() not in professional.casefold():
        signatory = f"{professional}, {credentials}"
    watermark = (p.get("watermark_text") or "").strip() or display
    configured = bool(professional or firm)
    onboarding_seen = bool((p.get("onboarding_seen_at") or "").strip())
    return {
        **p,
        "display_name": display,
        "signatory_name": signatory,
        "watermark_text": watermark,
        "configured": configured,
        "onboarding_seen": onboarding_seen,
        "first_run_required": (not configured) and (not onboarding_seen),
    }


def identity_brand_line(prefix: str = "LexiCore") -> str:
    p = get_identity_profile()
    return f"{prefix} | {p['display_name']}"


def working_paper_line() -> str:
    p = get_identity_profile()
    return f"Dokumen kerja LexiCore untuk {p['display_name']} dan wajib diverifikasi profesional hukum sebelum digunakan."
