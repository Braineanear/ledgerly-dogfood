"""Test environment: the URL settings must exist before main is imported.

The values are assigned unconditionally so an ambient DATABASE_URL or
REDIS_URL from a developer or CI shell never leaks into the tests.
"""

import os
import tempfile

_DB_DIR = tempfile.mkdtemp(prefix="ledgerly-api-tests-")

os.environ["DATABASE_URL"] = f"sqlite:///{_DB_DIR}/ledgerly-test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
