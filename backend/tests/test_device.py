"""Device controls: each change is read back. Radios, theme and windows are simulated here."""
import asyncio
import unittest
from unittest.mock import patch

from app.core.battery import Battery
from app.tools.system.device import DeviceTool
from app.tools.system.screen_reader import WindowInfo

CHROME = WindowInfo(hwnd=5, pid=6, title="Inbox - Google Chrome", process="chrome.exe")


class DeviceTests(unittest.TestCase):
    def setUp(self):
        self.tool = DeviceTool()

    def run_tool(self, **args):
        return asyncio.run(self.tool.execute(args))

    def test_targets(self):
        self.assertEqual(self.tool.match_target("wi-fi", "turn_off")[0], "wifi")
        self.assertEqual(self.tool.match_target("dark theme", "turn_on")[0], "dark mode")

    def test_radio_change_is_verified(self):
        with patch("app.tools.system.device.radio", return_value="Off") as radio:
            result = self.run_tool(operation="turn_off", target="bluetooth")
        radio.assert_called_once_with("bluetooth", "Off")
        self.assertEqual(result["summary"], "Bluetooth is off.")
        with patch("app.tools.system.device.radio", return_value="On"):
            self.assertEqual(self.run_tool(operation="turn_off", target="wifi")["error"], "Wi-Fi is still on")
        with patch("app.tools.system.device.radio", return_value="Disabled"):
            self.assertIn("airplane mode", self.run_tool(operation="turn_on", target="wifi")["error"])

    def test_light_mode_means_dark_off(self):
        with patch("app.tools.system.device.set_dark_mode") as set_dark, \
             patch("app.tools.system.device.dark_mode", return_value=False):
            result = self.run_tool(operation="turn_on", target="light mode")
        set_dark.assert_called_once_with(False)
        self.assertEqual(result["summary"], "Switched to light mode.")

    def test_battery(self):
        with patch("app.core.battery.battery_status", return_value=Battery(77, False, 192)):
            self.assertEqual(self.run_tool(operation="battery")["summary"], "Battery is at 77%, about 3 hours 12 minutes left.")
        with patch("app.core.battery.battery_status", return_value=Battery(90, True)):
            self.assertEqual(self.run_tool(operation="battery")["summary"], "Battery is at 90% and charging.")

    def test_switch_to_an_open_app(self):
        with patch("app.tools.system.device.find_window", return_value=CHROME), \
             patch("app.tools.system.device.bring_forward", return_value=True):
            self.assertEqual(self.run_tool(operation="switch_to", target="chrome")["summary"], "Switched to Google Chrome.")
        with patch("app.tools.system.device.find_window", return_value=None):
            self.assertIn("doesn't seem to be open", self.run_tool(operation="switch_to", target="figma")["error"])


if __name__ == "__main__":
    unittest.main()
