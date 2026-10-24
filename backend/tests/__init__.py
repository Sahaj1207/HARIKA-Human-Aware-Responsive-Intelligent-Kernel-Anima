"""HARIKA's tests.

Every test run gets its own empty data folder, so tests never read or change the
memories, goals, reminders, people or settings in backend/data (or anyone's real
HARIKA data). This runs before any app module is imported.

Keys come from an empty in-memory keychain too, so a test never uses this computer's real
service keys (which would make it call Groq or Gemini for real).
"""
import atexit
import os
import shutil
import tempfile

if "HARIKA_DATA_DIR" not in os.environ:
    _folder = tempfile.mkdtemp(prefix="harika-tests-")
    os.environ["HARIKA_DATA_DIR"] = _folder
    atexit.register(shutil.rmtree, _folder, True)

import keyring
from keyring.backend import KeyringBackend


class _EmptyKeychain(KeyringBackend):
    priority = 1

    def __init__(self):
        super().__init__()
        self.store = {}

    def get_password(self, service, username):
        return self.store.get((service, username))

    def set_password(self, service, username, password):
        self.store[(service, username)] = password

    def delete_password(self, service, username):
        self.store.pop((service, username), None)


keyring.set_keyring(_EmptyKeychain())
