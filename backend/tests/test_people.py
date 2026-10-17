"""People: remembering who's who, birthdays, and WhatsApp messages that only send after a yes.

Temporary stores and fake WhatsApp windows only: nothing is opened or sent.
"""
import asyncio
import tempfile
import time
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.tools.executor import ToolExecutor
from app.tools.productivity import people_tool as people
from app.tools.productivity.people_tool import (
    MessageDraft, PeopleStore, PeopleTool, birthday_text, clean_phone, next_birthday, parse_birthday, whatsapp_number,
)
from app.tools.schemas import ToolStatusCode
from app.tools.system.screen_reader import WindowInfo

WHATSAPP = WindowInfo(hwnd=1, pid=2, title="WhatsApp", process="whatsapp.root.exe")


class ParsingTests(unittest.TestCase):
    def test_birthdays(self):
        self.assertEqual(parse_birthday("12 March"), "--03-12")
        self.assertEqual(parse_birthday("March 12th 1998"), "1998-03-12")
        self.assertEqual(parse_birthday("--03-12"), "--03-12")
        self.assertEqual(parse_birthday("1998-03-12"), "1998-03-12")
        self.assertEqual(parse_birthday("29 Feb"), "--02-29")
        self.assertEqual(parse_birthday("20-10"), "--10-20")  # day-month when the first can't be a month
        self.assertEqual(parse_birthday("20/10"), "--10-20")
        self.assertIsNone(parse_birthday("31 June"))
        self.assertIsNone(parse_birthday("soon"))

    def test_next_birthday_and_age(self):
        today = date(2026, 10, 17)
        self.assertEqual(next_birthday("1998-03-12", today), (date(2027, 3, 12), 29))
        self.assertEqual(next_birthday("--10-17", today), (date(2026, 10, 17), None))
        self.assertEqual(birthday_text("2000-10-18", today), "18 October, tomorrow, turning 26")

    def test_phone_numbers(self):
        self.assertEqual(clean_phone("+91 98765 43210"), "+919876543210")
        self.assertEqual(clean_phone("0044 20 7946 0958"), "+442079460958")
        self.assertEqual(clean_phone("98765-43210"), "9876543210")
        self.assertIsNone(clean_phone("12345"))
        self.assertEqual(whatsapp_number("+919876543210", "US"), "919876543210")
        self.assertEqual(whatsapp_number("9876543210", "IN"), "919876543210")
        self.assertEqual(whatsapp_number("09876543210", "IN"), "919876543210")
        self.assertIsNone(whatsapp_number("9876543210", "XX"))  # unknown country: ask for the code


class PeopleToolTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.store = PeopleStore(Path(self.folder.name) / "people.json")
        self.tool = PeopleTool(self.store)
        self.country = patch("app.tools.web.weather.locator.country_code", AsyncMock(return_value="IN"))
        self.country.start()

    def tearDown(self):
        self.country.stop()
        self.folder.cleanup()

    def run_tool(self, **args):
        return asyncio.run(self.tool.execute(args))

    def test_remember_merges_what_the_user_says(self):
        self.run_tool(operation="remember_person", target="Mom", phone="98765 43210")
        result = self.run_tool(operation="remember_person", target="mom", full_name="Sunita Sharma", birthday="12 March")
        self.assertEqual(len(self.store.load()), 1)
        self.assertIn("Mom (Sunita Sharma)", result["summary"])
        self.assertIn("phone 9876543210", result["summary"])
        self.assertEqual(self.store.find("my mom")[0]["birthday"], "--03-12")
        self.assertEqual(self.store.find("Sunita")[0]["name"], "Mom")

    def test_bad_details_are_not_saved(self):
        result = self.run_tool(operation="remember_person", target="Priya", phone="123")
        self.assertFalse(result["success"])
        self.assertEqual(self.store.load(), [])

    def test_answers_about_people(self):
        self.run_tool(operation="remember_person", target="Priya", relation="best friend", email="priya@example.com")
        self.assertEqual(self.run_tool(operation="person_info", target="Priya", field="email")["summary"],
                         "Priya's email is priya@example.com.")
        self.assertIn("don't have Priya's number", self.run_tool(operation="person_info", target="Priya", field="phone")["summary"])
        self.assertIn("don't know anyone called Ravi", self.run_tool(operation="person_info", target="Ravi")["error"])

    def test_message_waits_for_approval_and_shows_the_number(self):
        self.run_tool(operation="remember_person", target="Mom", phone="98765 43210")
        with patch("os.startfile", create=True) as start:
            result = self.run_tool(operation="message", target="Mom", text="I'm on my way")
        start.assert_not_called()
        self.assertEqual(result["summary"], "Send “I'm on my way” to Mom (+919876543210) on WhatsApp?")
        self.assertEqual(result["confirmation"]["capability"], "send_message")

    def test_send_opens_that_chat_and_sends_only_the_prefilled_text(self):
        self.run_tool(operation="remember_person", target="Mom", phone="+91 98765 43210")
        self.run_tool(operation="message", target="Mom", text="I'm on my way")
        with patch("os.startfile", create=True) as start, \
             patch("app.tools.system.screen_reader.find_app_window", return_value=WHATSAPP), \
             patch("app.tools.system.screen_reader.send_prefilled", return_value=None) as send, \
             patch("app.tools.system.screen_reader.text_visible", return_value=True), \
             patch("app.tools.productivity.people_tool.asyncio.sleep", AsyncMock()):
            result = self.run_tool(operation="send_message")
        self.assertEqual(start.call_args.args[0], "whatsapp://send?phone=919876543210&text=I%27m%20on%20my%20way")
        send.assert_called_once_with(WHATSAPP, "I'm on my way")
        self.assertTrue(result["verified"])
        self.assertIsNone(self.tool.draft)  # sent once

    def test_nothing_is_sent_when_whatsapp_has_not_prepared_the_chat(self):
        self.tool.draft = MessageDraft({"name": "Mom"}, "919876543210", "hi", time.time())
        refusal = "WhatsApp didn't open the chat with the message ready, so I didn't send anything"
        with patch("os.startfile", create=True), \
             patch("app.tools.system.screen_reader.find_app_window", return_value=WHATSAPP), \
             patch("app.tools.system.screen_reader.send_prefilled", return_value=refusal), \
             patch("app.tools.productivity.people_tool.asyncio.sleep", AsyncMock()):
            result = self.run_tool(operation="send_message")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], refusal)

    def test_number_without_country_code_abroad_is_asked_for(self):
        self.run_tool(operation="remember_person", target="Ravi", phone="9876543210")
        with patch("app.tools.web.weather.locator.country_code", AsyncMock(return_value="XX")):
            result = self.run_tool(operation="message", target="Ravi", text="hi")
        self.assertIn("country code", result["error"])

    def test_change_rewrites_the_waiting_message(self):
        self.run_tool(operation="remember_person", target="Mom", phone="+91 98765 43210")
        self.run_tool(operation="message", target="Mom", text="on my way")
        with patch.object(PeopleTool, "_rewrite", AsyncMock(return_value="On my way, see you soon!")):
            result = self.run_tool(operation="message", target="it", instruction="make it warmer")
        self.assertEqual(self.tool.draft.text, "On my way, see you soon!")
        self.assertIn("to Mom (+919876543210)", result["summary"])

    def test_executor_holds_sending_and_forgetting_for_approval(self):
        self.run_tool(operation="remember_person", target="Mom", phone="+91 98765 43210")
        self.run_tool(operation="message", target="Mom", text="hi")
        self.run_tool(operation="forget_person", target="Mom")
        executor = ToolExecutor()
        executor._save_history = lambda: None
        with patch("os.startfile", create=True) as start:
            for operation in ("send_message", "remove_person"):
                result = asyncio.run(executor.execute_tool(self.tool, {"operation": operation, "target": "Mom"}))
                self.assertEqual(result.status_code, ToolStatusCode.CONFIRMATION_REQUIRED)
        start.assert_not_called()
        self.assertEqual(len(self.store.load()), 1)

    def test_birthdays_in_the_briefing(self):
        from app.tools.utilities.briefing import birthdays_text
        self.store.upsert("Priya", {"birthday": "--10-17"})
        self.store.upsert("Mom", {"birthday": "--10-20"})
        self.store.upsert("Ravi", {"birthday": "--12-01"})
        with patch.object(people, "people_store", self.store):
            self.assertEqual(birthdays_text(datetime(2026, 10, 17, 8)),
                             "It's Priya's birthday today. Coming up: Mom's birthday on Tuesday.")

    def test_email_uses_the_saved_address(self):
        from app.tools.productivity.email_tool import EmailTool
        self.store.upsert("Mom", {"email": "sunita@example.com", "full_name": "Sunita Sharma"})
        mail = AsyncMock()

        async def ask(system_prompt, message):
            return "Subject: Hi\n\nHello"
        with patch.object(people, "people_store", self.store), patch.object(EmailTool, "_ask", staticmethod(ask)):
            result = asyncio.run(EmailTool(mail).execute({"operation": "email", "target": "Mom", "instruction": "hi"}))
        mail.find_addresses.assert_not_called()
        self.assertIn("Sunita Sharma <sunita@example.com>", result["summary"])


class RememberRoutingTests(unittest.TestCase):
    def test_remember_is_confirmed_by_the_interpreter(self):
        from app.cognition.core import CognitiveCore
        from app.router.classifier import intent_classifier
        from app.router.schemas import RequestContext

        core = CognitiveCore(semantic_interpreter_instance=object())
        graph, confidence = intent_classifier.classify_request(RequestContext(message="remember Mom's number is 98765 43210"))
        self.assertTrue(core.needs_deliberation(graph, confidence))


if __name__ == "__main__":
    unittest.main()
