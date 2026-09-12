"""R36 bounded diagnostic helper for provision-location failures.

Usage:
    py tools/audit_provision_location.py "Pasal 3" path/to/extracted_text.txt

This utility does not fetch the network and does not change verification state.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

from services.positive_law_verification import locate_provisions, verify_provisions


def audit_text(provision: str, text: str) -> dict:
    located=locate_provisions([provision], text, None)
    verified=verify_provisions([provision], text, None)
    return {
        'provision': provision,
        'text_length': len(text or ''),
        'location': located,
        'verification': verified,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print('Usage: py tools/audit_provision_location.py "Pasal 3" extracted_text.txt')
        return 2
    provision=argv[1]
    text=Path(argv[2]).read_text(encoding='utf-8', errors='ignore')
    print(json.dumps(audit_text(provision, text), ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
