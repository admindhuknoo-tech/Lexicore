"""LexiCore release identity.

Product identity and technical release identity are intentionally separated.
UI/product labels are stable and must not change for every corrective build.
Technical versioning is used only for diagnostics, health, audit, and packaging.
"""
from __future__ import annotations
import os

PRODUCT_NAME = "LexiCore"
PRODUCT_LABEL = "LexiCore Assistant"
INITIATIVE = "Evidence-to-Action Legal Intelligence"
FIRM_NAME = "ELF - Erfan's Law Firm"

# Public release line. Increment only for a deliberate release milestone.
PUBLIC_VERSION = "1.3.14"
RELEASE_CHANNEL = "RC"
RELEASE_SEQUENCE = 18

# Backward-compatible technical version used by health/API/user-agent.
LEXICORE_VERSION = f"{PUBLIC_VERSION}-rc{RELEASE_SEQUENCE}"

# Build identity is operational metadata, not part of the product label.
# CI/deployment may override it without changing source code or tests.
BUILD_ID = os.getenv("LEXICORE_BUILD_ID", "local")
RELEASE_ID = f"{LEXICORE_VERSION}+{BUILD_ID}" if BUILD_ID else LEXICORE_VERSION
TECHNICAL_LABEL = f"{PRODUCT_NAME} {LEXICORE_VERSION}"


def release_metadata() -> dict:
    return {
        "product_name": PRODUCT_NAME,
        "product_label": PRODUCT_LABEL,
        "initiative": INITIATIVE,
        "firm_name": FIRM_NAME,
        "public_version": PUBLIC_VERSION,
        "release_channel": RELEASE_CHANNEL,
        "release_sequence": RELEASE_SEQUENCE,
        "version": LEXICORE_VERSION,
        "build_id": BUILD_ID,
        "release_id": RELEASE_ID,
    }
