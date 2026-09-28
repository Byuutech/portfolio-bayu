import os
import re
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("CHAT_OPERATOR_USERNAME", "test-operator")
os.environ.setdefault("CHAT_OPERATOR_PASSWORD", "test-password")
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key")

from app import app
from chat import init_chat, socketio


class LiveChatTests(unittest.TestCase):
    def setUp(self):
        self.database = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        self.database.close()
        self.addCleanup(lambda: os.path.exists(self.database.name) and os.unlink(self.database.name))
        self.previous_database = app.config["CHAT_DATABASE"]
        app.config.update(TESTING=True, CHAT_DATABASE=self.database.name)
        self.addCleanup(self.restore_database)
        init_chat(app)
        self.credentials = patch.dict(
            os.environ,
            {
                "CHAT_OPERATOR_USERNAME": "test-operator",
                "CHAT_OPERATOR_PASSWORD": "test-password",
            },
        )
        self.credentials.start()
        self.addCleanup(self.credentials.stop)

    def restore_database(self):
        app.config["CHAT_DATABASE"] = self.previous_database

    def test_visitor_messages_are_persisted_and_private_to_their_session(self):
        visitor = app.test_client()
        visitor.get("/")
        visitor_socket = socketio.test_client(app, flask_test_client=visitor)

        visitor_socket.emit("chat:send", {"body": "Halo, Bayu!"})
        response = visitor.get("/chat/history")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["messages"][0]["body"], "Halo, Bayu!")

        another_visitor = app.test_client()
        another_visitor.get("/")
        self.assertEqual(another_visitor.get("/chat/history").json["messages"], [])
        visitor_socket.disconnect()

    def test_operator_login_protects_dashboard_and_logout(self):
        client = app.test_client()
        self.assertEqual(client.get("/operator").status_code, 302)

        login_page = client.get("/operator/login")
        csrf_token = re.search(
            rb'name="csrf_token" value="([^"]+)"', login_page.data
        ).group(1).decode()
        response = client.post(
            "/operator/login",
            data={
                "csrf_token": csrf_token,
                "username": "test-operator",
                "password": "test-password",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.get("/operator").status_code, 200)
        self.assertEqual(client.get("/operator/conversations").status_code, 200)
        operator_socket = socketio.test_client(app, flask_test_client=client)

        dashboard = client.get("/operator")
        csrf_token = re.search(
            rb'name="csrf_token" value="([^"]+)"', dashboard.data
        ).group(1).decode()
        self.assertEqual(
            client.post("/operator/logout", data={"csrf_token": csrf_token}).status_code,
            302,
        )
        self.assertEqual(client.get("/operator").status_code, 302)
        self.assertFalse(operator_socket.is_connected())

    def test_visitors_cannot_choose_another_conversation_or_send_invalid_messages(self):
        visitor = app.test_client()
        visitor.get("/")
        visitor_socket = socketio.test_client(app, flask_test_client=visitor)

        visitor_socket.emit(
            "chat:send",
            {"body": "pesan palsu", "conversation_id": "someone-elses-id"},
        )
        visitor_socket.emit("chat:send", {"body": "x" * 1001})
        errors = [
            event for event in visitor_socket.get_received()
            if event["name"] == "chat:error"
        ]
        self.assertEqual(len(errors), 1)
        history = visitor.get("/chat/history").json["messages"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["body"], "pesan palsu")
        visitor_socket.disconnect()

    def test_operator_can_read_and_reply_to_a_visitor(self):
        visitor = app.test_client()
        visitor.get("/")
        visitor_socket = socketio.test_client(app, flask_test_client=visitor)
        visitor_socket.emit("chat:send", {"body": "Bisa bantu?"})

        operator = app.test_client()
        login_page = operator.get("/operator/login")
        csrf_token = re.search(
            rb'name="csrf_token" value="([^"]+)"', login_page.data
        ).group(1).decode()
        operator.post(
            "/operator/login",
            data={
                "csrf_token": csrf_token,
                "username": "test-operator",
                "password": "test-password",
            },
        )
        conversation_id = operator.get("/operator/conversations").json[
            "conversations"
        ][0]["id"]
        operator_socket = socketio.test_client(app, flask_test_client=operator)
        operator_socket.emit("chat:select", {"conversation_id": conversation_id})
        history_events = [
            event for event in operator_socket.get_received()
            if event["name"] == "chat:history"
        ]
        self.assertEqual(history_events[0]["args"][0]["messages"][0]["body"], "Bisa bantu?")

        operator_socket.emit(
            "chat:send",
            {"conversation_id": conversation_id, "body": "Tentu, ada yang bisa saya bantu?"},
        )
        self.assertEqual(
            visitor.get("/chat/history").json["messages"][-1]["sender"], "operator"
        )
        operator_socket.disconnect()
        visitor_socket.disconnect()


if __name__ == "__main__":
    unittest.main()
