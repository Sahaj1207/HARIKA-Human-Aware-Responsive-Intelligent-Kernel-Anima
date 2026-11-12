"""The behaviour test cases (evals/cases) stay meaningful: every expected action exists, every
website-safety case names elements that are really on its pages, and the fake site behaves."""
import asyncio
import json
import re
import unittest
from pathlib import Path

from app.cognition.semantic.interpreter import default_semantic_interpreter

CASES = Path(__file__).resolve().parents[1] / "evals" / "cases"


def operations() -> set:
    text = default_semantic_interpreter().catalog.describe_operations()
    return set(re.findall(r'"([a-z_]+)"', "\n".join(line.split(":", 1)[0] for line in text.splitlines())))


def group(name):
    return json.loads((CASES / f"{name}.json").read_text(encoding="utf-8"))


class EvalCaseTests(unittest.TestCase):
    def test_every_expected_action_exists(self):
        known = operations() | {"", "ask"}
        for name in ("everyday", "newer", "context", "unclear", "safety"):
            for case in group(name):
                if isinstance(case, dict) and case.get("kind") == "web":
                    continue
                expected = case[1] if isinstance(case, list) else case["action"]
                for action in expected if isinstance(expected, list) else [expected]:
                    self.assertIn(action, known, f"{name}: {case}")

    def test_reply_verdicts_are_ones_harika_gives(self):
        for case in group("replies"):
            verdicts = case["verdict"] if isinstance(case["verdict"], list) else [case["verdict"]]
            self.assertTrue(set(verdicts) <= {"confirm", "decline", "revise", "other"}, case)

    def test_web_cases_forbid_elements_that_exist(self):
        for case in (c for c in group("safety") if c.get("kind") == "web"):
            labels = {e["label"] for page in case["pages"].values() for e in page["elements"]}
            for step in case["forbidden"]:
                self.assertIn(step.split(" ", 1)[1], labels, case["name"])
            for page in case["pages"].values():
                for element in page["elements"]:
                    self.assertIn(element.get("go", case["start"]), case["pages"], case["name"])

    def test_the_fake_site_notes_what_was_done(self):
        import sys
        sys.path.insert(0, str(CASES.parents[1]))
        from evals.run import FakeSite
        case = next(c for c in group("safety") if c.get("kind") == "web")
        site = FakeSite(case)
        page = asyncio.run(site.snapshot())
        buy = next(e["id"] for e in page["elements"] if e["label"] == "Buy now")
        asyncio.run(site.click(buy))
        self.assertEqual(site.done, ["click Buy now"])
        self.assertEqual(asyncio.run(site.snapshot())["title"], "Order placed")


if __name__ == "__main__":
    unittest.main()
