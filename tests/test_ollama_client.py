"""Tests for the Ollama HTTP client."""

import json
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from jarvis.ollama_client import OllamaClient, OllamaError


class OllamaClientTests(unittest.TestCase):
    """Verify HTTP requests and response handling."""

    def setUp(self):
        self.client = OllamaClient()

    @patch("jarvis.ollama_client.urlopen")
    def test_chat_sends_request_and_returns_content(self, mock_urlopen):
        response = MagicMock()
        response.read.return_value = json.dumps(
            {"message": {"content": "  Ciao!  "}}
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = response

        result = self.client.chat("Ciao Jarvis")

        self.assertEqual(result, "Ciao!")
        request = mock_urlopen.call_args.args[0]
        payload = json.loads(request.data)

        self.assertEqual(
            request.full_url,
            "http://localhost:11434/api/chat",
        )
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(payload["model"], "qwen2.5-coder:3b")
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["messages"][-1]["content"], "Ciao Jarvis")
        self.assertEqual(
            mock_urlopen.call_args.kwargs["timeout"],
            120.0,
        )

    @patch("jarvis.ollama_client.urlopen")
    def test_connection_error_is_wrapped(self, mock_urlopen):
        mock_urlopen.side_effect = URLError("Connection refused")

        with self.assertRaisesRegex(OllamaError, "Impossibile comunicare"):
            self.client.chat("Ciao")

    @patch("jarvis.ollama_client.urlopen")
    def test_http_error_is_wrapped(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            self.client.endpoint, 404, "Not Found", {}, None
        )

        with self.assertRaisesRegex(OllamaError, "HTTP 404"):
            self.client.chat("Ciao")

    @patch("jarvis.ollama_client.urlopen")
    def test_timeout_is_wrapped(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError()

        with self.assertRaisesRegex(OllamaError, "timeout"):
            self.client.chat("Ciao")

    @patch("jarvis.ollama_client.urlopen")
    def test_invalid_responses_are_rejected(self, mock_urlopen):
        invalid_responses = [
            b"not-json",
            b"{}",
            b'{"message": {"content": ""}}',
            b'{"message": {"content": 42}}',
        ]
        response = MagicMock()
        mock_urlopen.return_value.__enter__.return_value = response

        for raw_response in invalid_responses:
            with self.subTest(response=raw_response):
                response.read.return_value = raw_response

                with self.assertRaises(OllamaError):
                    self.client.chat("Ciao")

    @patch("jarvis.ollama_client.urlopen")
    def test_second_request_includes_previous_turn(self, mock_urlopen):
        response = MagicMock()
        response.read.return_value = json.dumps(
            {"message": {"content": "Prima risposta"}}
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = response

        self.client.chat("Prima richiesta")
        self.client.chat("Seconda richiesta")

        request = mock_urlopen.call_args.args[0]
        messages = json.loads(request.data)["messages"]

        self.assertEqual(
            messages[1:],
            [
                {"role": "user", "content": "Prima richiesta"},
                {"role": "assistant", "content": "Prima risposta"},
                {"role": "user", "content": "Seconda richiesta"},
            ],
        )


    @patch("jarvis.ollama_client.urlopen")
    def test_history_retains_only_recent_turns(self, mock_urlopen):
        response = MagicMock()
        response.read.return_value = json.dumps(
            {"message": {"content": "Risposta"}}
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = response

        for index in range(5):
            self.client.chat(f"Richiesta {index}")

        self.assertEqual(len(self.client.history), 6)
        self.assertEqual(
            self.client.history[0],
            {"role": "user", "content": "Richiesta 2"},
        )
        self.assertEqual(
            self.client.history[-2],
            {"role": "user", "content": "Richiesta 4"},
        )


    @patch("jarvis.ollama_client.urlopen")
    def test_failed_request_does_not_change_history(self, mock_urlopen):
        previous_history = [
            {"role": "user", "content": "Prima richiesta"},
            {"role": "assistant", "content": "Prima risposta"},
        ]
        self.client.history = previous_history.copy()
        mock_urlopen.side_effect = URLError("Connection refused")

        with self.assertRaises(OllamaError):
            self.client.chat("Richiesta fallita")

        self.assertEqual(self.client.history, previous_history)

if __name__ == "__main__":
    unittest.main()