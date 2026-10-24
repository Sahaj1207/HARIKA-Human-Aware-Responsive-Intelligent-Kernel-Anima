"""Only HARIKA's own windows can change things; web pages on the same computer can't (no network)."""
import unittest

from fastapi.testclient import TestClient

from app.main import app, _host_name


class FrontDoorTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, client=("127.0.0.1", 50000))  # requests from this computer

    def test_a_web_page_cannot_send_commands(self):
        for path in ("/api/v1/memory/forget-everything", "/api/v1/speech/listen", "/api/v1/speech/stop"):
            reply = self.client.post(path, headers={"Origin": "https://evil.example"})
            self.assertEqual(reply.status_code, 403, path)
            self.assertEqual(reply.json()["detail"], "Only HARIKA's own windows can do that.")
        self.assertEqual(self.client.post("/api/v1/speech/stop", headers={"Origin": "null"}).status_code, 403)

    def test_harikas_own_windows_and_local_programs_can(self):
        for origin in ("http://tauri.localhost", "http://localhost:5173"):
            self.assertEqual(self.client.post("/api/v1/speech/stop", headers={"Origin": origin}).status_code, 200, origin)
        self.assertEqual(self.client.post("/api/v1/speech/stop").status_code, 200)  # no Origin: not a browser

    def test_reading_is_not_blocked(self):
        self.assertEqual(self.client.get("/api/v1/health", headers={"Origin": "https://evil.example"}).status_code, 200)

    def test_only_requests_addressed_to_this_computer(self):
        reply = self.client.get("/api/v1/health", headers={"Host": "attacker.example:47801"})
        self.assertEqual(reply.status_code, 403)
        for host in ("127.0.0.1:47801", "localhost:8000", "[::1]:47801"):
            self.assertEqual(self.client.get("/api/v1/health", headers={"Host": host}).status_code, 200, host)

    def test_host_names(self):
        self.assertEqual(_host_name("127.0.0.1:47801"), "127.0.0.1")
        self.assertEqual(_host_name("[::1]:47801"), "[::1]")
        self.assertEqual(_host_name("localhost"), "localhost")


if __name__ == "__main__":
    unittest.main()
