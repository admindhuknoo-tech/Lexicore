"""Compatibility runner for the v1.3.4 regression suite.

Canonical pytest tests live in tests/test_smoke.py.
Run either:
    py -m pytest -q
or:
    py test_smoke.py
"""
if __name__ == '__main__':
    import pytest
    raise SystemExit(pytest.main(['tests', '-v']))
