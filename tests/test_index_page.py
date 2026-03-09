import unittest

from fastapi.testclient import TestClient

from src.webapp.assistant_app import app


class IndexPageTestCase(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_index_page_contains_static_assets_and_socketio_hooks(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("cdn.socket.io", response.text)
        self.assertIn("static/css/index.css", response.text)
        self.assertIn("static/js/index.js", response.text)
        self.assertIn("showDepartmentAppointmentModal", response.text)
        self.assertIn("showPatientReportModal", response.text)
        self.assertIn("showQueueModal", response.text)
        self.assertIn("debug-panel", response.text)
        self.assertIn("debugPayloadInput", response.text)
        self.assertIn("sendDebugMessageButton", response.text)
        self.assertIn("currentSessionLabel", response.text)
        self.assertNotIn("conversationIdInput", response.text)
        self.assertNotIn("<style>", response.text)
        self.assertNotIn("??", response.text)


if __name__ == "__main__":
    unittest.main()
