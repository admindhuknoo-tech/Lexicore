"""Pytest bootstrap: guarantee the test suite never touches the real database.

Bug fix (v1.3.5.4 audit): `database.py` resolves `DB_PATH` from the
LEXICORE_DB_PATH environment variable exactly once, at first module import,
because it is a module-level constant. `tests/test_smoke.py` set that env
var before importing `app`/`database` — but that only works if
`test_smoke.py` is the *first* test module pytest imports.

pytest collects test files alphabetically by default, and
`tests/test_migrations.py` sorts before `tests/test_smoke.py`. That file
imports `database` directly (`from database import ...`) without setting
LEXICORE_DB_PATH first. So `database.DB_PATH` was locked to its default,
relative "lexicore.db" — i.e. the real production database in the current
working directory — the moment pytest collected test_migrations.py, before
test_smoke.py's env var ever took effect. Because Python caches imported
modules, `database`'s module-level state was never re-evaluated afterward,
so `app.py`'s `init_database()` call (which runs schema checks/migrations at
import time) then ran against the real lexicore.db, and every test in
test_smoke.py that used the `client` fixture wrote real rows to it too.

This is exactly the kind of thing this suite's own docstring promised would
never happen ("It never touches the firm's real lexicore.db"), on an app
that stores confidential client/case data. A `conftest.py` is the fix
because pytest always imports it before collecting *any* test module in
this directory, regardless of filename ordering — so the env vars below are
guaranteed to be set before `database` (or anything importing it) is ever
imported by the test run.
"""
import os
import tempfile

_TMP_DIR = tempfile.mkdtemp(prefix="lexicore_test_")
# Test isolation must override the operator's real shell/.env configuration.
# `setdefault` is intentionally NOT used here: if the workstation already has
# GEMINI_API_KEY or LEXICORE_AI_PROVIDER=gemini, the smoke suite would make real
# network/API calls, incur cost, and become nondeterministic.
os.environ["LEXICORE_DB_PATH"] = os.path.join(_TMP_DIR, "test_lexicore.db")
os.environ["LEXICORE_DISABLE_AUTO_BACKUP"] = "1"
# Destructive-operation backups intentionally ignore the auto-backup switch.
# Redirect every test backup into the isolated temp tree so pytest can never
# write pre-delete/pre-migration snapshots into the real project backups/.
os.environ["LEXICORE_BACKUP_DIR"] = os.path.join(_TMP_DIR, "backups")
os.environ["LEXICORE_AI_PROVIDER"] = "local"
os.environ["LEXICORE_AI_MODEL"] = ""
os.environ["LEXICORE_AI_MODE"] = "local"
os.environ["GEMINI_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
# Commercial licensing is a runtime/deployment concern, not a prerequisite for
# deterministic API regression tests. Force the default test process into
# development mode so a desktop-launcher test cannot leak
# LEXICORE_LICENSE_REQUIRED=1 into subsequently collected/executed smoke tests.
# Dedicated licensing tests explicitly enable the gate when they need it.
os.environ["LEXICORE_LICENSE_REQUIRED"] = "0"
