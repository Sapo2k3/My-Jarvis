"""Tests for the Jarvis text interface."""

import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import Mock, patch

from jarvis.main import handle_request, main
from jarvis.ollama_client import OllamaClient, OllamaError


class HandleRequestTests(unittest.TestCase):
    """Verify validation, delegation, and error handling."""

    def setUp(self):
        self.client = Mock(spec=OllamaClient)

    def test_empty_request_does_not_call_client(self):
        result = handle_request("", self.client)

        self.assertEqual(result, "Scrivi una richiesta per iniziare.")
        self.client.chat.assert_not_called()

    def test_whitespace_request_does_not_call_client(self):
        result = handle_request("   \t\n", self.client)

        self.assertEqual(result, "Scrivi una richiesta per iniziare.")
        self.client.chat.assert_not_called()

    def test_valid_request_returns_model_response(self):
        self.client.chat.return_value = "Ciao Mattia!"

        result = handle_request("  Ciao Jarvis  ", self.client)

        self.assertEqual(result, "Ciao Mattia!")
        self.client.chat.assert_called_once_with("Ciao Jarvis")

    def test_client_error_returns_readable_message(self):
        self.client.chat.side_effect = OllamaError("Servizio non disponibile.")

        result = handle_request("Ciao", self.client)

        self.assertEqual(result, "Errore: Servizio non disponibile.")


class MainTests(unittest.TestCase):
    """Verify interaction without contacting a real model."""

    def setUp(self):
        self.client = Mock(spec=OllamaClient)
        self.client.model = "test-model"
        self.client.chat.return_value = "Risposta di test"

    def run_session(self, inputs):
        output = StringIO()

        with patch("jarvis.main.OllamaClient", return_value=self.client):
            with patch("builtins.input", side_effect=inputs):
                with redirect_stdout(output):
                    main()

        return output.getvalue()

    def test_request_is_processed_before_exit(self):
        output = self.run_session(["Ciao Jarvis", "esci"])

        self.assertIn("Risposta di test", output)
        self.assertIn("Jarvis > A presto!", output)
        self.client.chat.assert_called_once_with("Ciao Jarvis")

    def test_exit_commands_are_case_insensitive(self):
        for command in ("esci", "EXIT", "Quit"):
            with self.subTest(command=command):
                output = self.run_session([command])
                self.assertIn("Jarvis > A presto!", output)

        self.client.chat.assert_not_called()

    def test_input_interruptions_close_session(self):
        for error in (EOFError, KeyboardInterrupt):
            with self.subTest(error=error.__name__):
                output = self.run_session([error()])
                self.assertIn("Jarvis > Sessione terminata.", output)

    def test_reset_clears_history_without_calling_model(self):
        output = self.run_session(["/reset", "esci"])

        self.client.reset_history.assert_called_once_with()
        self.client.chat.assert_not_called()
        self.assertIn("Jarvis > Cronologia cancellata.", output)
        
    def test_multiline_request_is_sent_as_one_message(self):
        output = self.run_session(
            [
                "/paste",
                "Spiega questa funzione:",
                "def square(number):",
                "    return number * number",
                "/send",
                "esci",
            ]
        )

        self.client.chat.assert_called_once_with(
            "Spiega questa funzione:\n"
            "def square(number):\n"
            "    return number * number"
        )
        self.assertIn("Risposta di test", output)


    def test_cancelled_multiline_request_does_not_call_model(self):
        output = self.run_session(
            [
                "/paste",
                "Testo da non inviare",
                "/cancel",
                "esci",
            ]
        )

        self.client.chat.assert_not_called()
        self.assertIn("Inserimento annullato o vuoto.", output)

if __name__ == "__main__":
    unittest.main()