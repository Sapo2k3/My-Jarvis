"""Tests for explicit file analysis and submission approval."""

import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import Mock, patch

from jarvis.file_analysis import (
    MAX_ANALYSIS_CHARS,
    analyze_selected_file,
)
from jarvis.ollama_client import OllamaClient, OllamaError
from jarvis.project_files import ProjectFileError, ProjectFileReader


class FileAnalysisTests(unittest.TestCase):
    """Verify preview, confirmation, and model submission."""

    def setUp(self):
        self.reader = Mock(spec=ProjectFileReader)
        self.reader.read.return_value = (
            "def square(number):\n"
            "    return number * number\n"
        )
        self.client = Mock(spec=OllamaClient)
        self.client.chat.return_value = "Analisi completata."

    def run_analysis(self, inputs):
        output = StringIO()

        with patch("builtins.input", side_effect=inputs):
            with redirect_stdout(output):
                result = analyze_selected_file(
                    self.reader,
                    self.client,
                )

        return result, output.getvalue()

    def test_confirmed_file_is_sent_to_model(self):
        result, output = self.run_analysis(
            ["src/example.py", "Cerca possibili bug.", "s"]
        )

        self.reader.read.assert_called_once_with("src/example.py")
        self.client.chat.assert_called_once()

        prompt = self.client.chat.call_args.args[0]
        self.assertIn("Cerca possibili bug.", prompt)
        self.assertIn(self.reader.read.return_value, prompt)
        self.assertIn("untrusted data", prompt)
        self.assertIn(self.reader.read.return_value, output)
        self.assertEqual(result, "Analisi completata.")

    def test_default_confirmation_cancels_submission(self):
        result, _ = self.run_analysis(
            ["src/example.py", "", ""]
        )

        self.client.chat.assert_not_called()
        self.assertIn("annullata", result)

    def test_reader_error_does_not_call_model(self):
        self.reader.read.side_effect = ProjectFileError(
            "Tipo di file non consentito."
        )

        result, _ = self.run_analysis([".env"])

        self.client.chat.assert_not_called()
        self.assertIn("Tipo di file non consentito.", result)

    def test_empty_file_does_not_call_model(self):
        self.reader.read.return_value = " \n"

        result, _ = self.run_analysis(["empty.py"])

        self.client.chat.assert_not_called()
        self.assertIn("vuoto", result)

    def test_large_file_does_not_call_model(self):
        self.reader.read.return_value = "x" * (
            MAX_ANALYSIS_CHARS + 1
        )

        result, _ = self.run_analysis(["large.py"])

        self.client.chat.assert_not_called()
        self.assertIn("limite", result)

    def test_model_error_returns_readable_message(self):
        self.client.chat.side_effect = OllamaError(
            "Servizio non disponibile."
        )

        result, _ = self.run_analysis(
            ["src/example.py", "", "s"]
        )

        self.assertEqual(
            result,
            "Errore: Servizio non disponibile.",
        )


if __name__ == "__main__":
    unittest.main()