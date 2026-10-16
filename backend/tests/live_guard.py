"""Live suites drive the real router and model, and open real apps, websites and files.

They only run when asked for explicitly, so an ordinary test run can never act on the
computer:  HARIKA_LIVE_TESTS=1 python -m unittest tests.test_cap4_desktop_tools
"""
import os
import unittest

LIVE = os.environ.get("HARIKA_LIVE_TESTS") == "1"
REASON = "live suite: opens real apps and websites; set HARIKA_LIVE_TESTS=1 to run it"


def live_only(loader, tests, pattern):
    """unittest's load_tests hook: the module's tests when live, else one skipped placeholder."""
    if LIVE:
        return tests

    class LiveSuiteSkipped(unittest.TestCase):
        @unittest.skip(REASON)
        def test_live_suite(self):
            pass

    return loader.loadTestsFromTestCase(LiveSuiteSkipped)
