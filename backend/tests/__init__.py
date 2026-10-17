"""HARIKA's tests.

Every test run gets its own empty data folder, so tests never read or change the
memories, goals, reminders, people or settings in backend/data (or anyone's real
HARIKA data). This runs before any app module is imported.
"""
import atexit
import os
import shutil
import tempfile

if "HARIKA_DATA_DIR" not in os.environ:
    _folder = tempfile.mkdtemp(prefix="harika-tests-")
    os.environ["HARIKA_DATA_DIR"] = _folder
    atexit.register(shutil.rmtree, _folder, True)
