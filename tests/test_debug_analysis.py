"""Tests for explicitly approved debugging requests."""

import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import Mock, patch

from jarvis.debug_analysis import MAX_DEBUG_CHARS, debug_selected_file
from jarvis.ollama_client import OllamaClient, OllamaError
from jarvis.project_files import ProjectFileError, ProjectFileReader
from jarvis.debug_revision import DebugRevisionResult
from jarvis.patch_validation import PatchCheck


class DebugAnalysisTests(unittest.TestCase):
    """Verify input validation, approval, and model submission."""

    def setUp(self):
        self.reader = Mock(spec=ProjectFileReader)
        self.reader.read.return_value = (
            "def divide(a, b):\n"
            "    return a / b\n\n"
            "divide(10, 0)\n"
        )

        self.client = Mock(spec=OllamaClient)
        self.client.chat.return_value = "Diagnosi di test."

        self.read_multiline = Mock(
            return_value="ZeroDivisionError: division by zero"
        )

    def run_debug(self, inputs):
        output = StringIO()

        with patch("builtins.input", side_effect=inputs):
            with redirect_stdout(output):
                result = debug_selected_file(
                    self.reader,
                    self.client,
                    self.read_multiline,
                )

        return result, output.getvalue()

    def test_confirmed_request_includes_source_and_log(self):
        result, output = self.run_debug(
            ["examples/division.py", "s"]
        )

        self.reader.read.assert_called_once_with("examples/division.py")
        self.read_multiline.assert_called_once_with()
        self.client.chat.assert_called_once()

        prompt = self.client.chat.call_args.args[0]
        self.assertIn(self.reader.read.return_value, prompt)
        self.assertIn(self.read_multiline.return_value, prompt)
        self.assertIn("## Diagnosis", prompt)
        self.assertIn("## Proposed patch", prompt)
        self.assertIn("## Suggested tests", prompt)

        self.assertIn(self.reader.read.return_value, output)
        self.assertIn(self.read_multiline.return_value, output)
        self.assertIn("Diagnosi di test.", result)
        self.assertIn("Patch check: NO_PATCH", result) 

    def test_default_confirmation_cancels_submission(self):
        result, _ = self.run_debug(
            ["examples/division.py", ""]
        )

        self.client.chat.assert_not_called()
        self.assertIn("annullato", result)

    def test_reader_error_does_not_collect_log_or_call_model(self):
        self.reader.read.side_effect = ProjectFileError(
            "Tipo di file non consentito."
        )

        result, _ = self.run_debug([".env"])

        self.read_multiline.assert_not_called()
        self.client.chat.assert_not_called()
        self.assertIn("Tipo di file non consentito.", result)

    def test_empty_source_does_not_collect_log(self):
        self.reader.read.return_value = " \n"

        result, _ = self.run_debug(["empty.py"])

        self.read_multiline.assert_not_called()
        self.client.chat.assert_not_called()
        self.assertIn("vuoto", result)

    def test_empty_log_cancels_submission(self):
        self.read_multiline.return_value = ""

        result, _ = self.run_debug(["examples/division.py"])

        self.client.chat.assert_not_called()
        self.assertIn("nessun errore", result)

    def test_oversized_source_is_rejected_before_log_collection(self):
        self.reader.read.return_value = "x" * (MAX_DEBUG_CHARS + 1)

        result, _ = self.run_debug(["large.py"])

        self.read_multiline.assert_not_called()
        self.client.chat.assert_not_called()
        self.assertIn("troppo lungo", result)

    def test_combined_size_limit_is_enforced(self):
        self.read_multiline.return_value = "x" * MAX_DEBUG_CHARS

        result, _ = self.run_debug(["examples/division.py"])

        self.client.chat.assert_not_called()
        self.assertIn("limite complessivo", result)

    def test_model_error_returns_readable_message(self):
        self.client.chat.side_effect = OllamaError(
            "Servizio non disponibile."
        )

        result, _ = self.run_debug(
            ["examples/division.py", "s"]
        )

        self.assertEqual(
            result,
            "Errore: Servizio non disponibile.",
        )

    def test_revision_result_is_presented_with_both_checks(self):
        revision_result = DebugRevisionResult(
            first_response="Prima proposta.",
            first_check=PatchCheck(
                "REJECTED",
                "Conteggi del diff non validi.",
            ),
            second_response="Proposta revisionata.",
            second_check=PatchCheck(
                "APPLICABLE",
                "Diff applicabile allo snapshot.",
            ),
        )

        with patch(
            "jarvis.debug_analysis.run_debug_revision",
            return_value=revision_result,
        ) as run_revision:
            result, _ = self.run_debug(
                ["examples/division.py", "s"]
            )

        run_revision.assert_called_once()
        arguments = run_revision.call_args.kwargs

        self.assertIs(arguments["client"], self.client)
        self.assertEqual(
            arguments["selected_path"],
            "examples/division.py",
        )
        self.assertEqual(
            arguments["source"],
            self.reader.read.return_value,
        )
        self.assertEqual(
            arguments["error_log"],
            self.read_multiline.return_value,
        )
        self.assertIn(
            self.reader.read.return_value,
            arguments["initial_prompt"],
        )
        self.assertIn(
            self.read_multiline.return_value,
            arguments["initial_prompt"],
        )

        self.client.chat.assert_not_called()
        self.assertIn("Prima proposta.", result)
        self.assertIn("Proposta revisionata.", result)
        self.assertIn("Patch check: REJECTED", result)
        self.assertIn("Patch check: APPLICABLE", result)
        self.assertIn("tentativo 2 di 2", result)
        self.assertIn(
            "Nessun file del progetto è stato modificato.",
            result,
        )
        self.assertIn(
            "Il codice non è stato eseguito.",
            result,
        )
        self.assertEqual(
            result.count(
                "--- Revisione automatica: tentativo 2 di 2 ---"
            ),
            1,
        )
        self.assertEqual(
            result.count("Proposta revisionata."),
            1,
        )
        self.assertEqual(
            result.count("--- Validazione locale: tentativo 2 ---"),
            1,
        )

    def test_confirmation_mentions_revision_and_cancel_skips_orchestration(self):
        output = StringIO()

        with patch(
            "jarvis.debug_analysis.run_debug_revision"
        ) as run_revision:
            with patch(
                "builtins.input",
                side_effect=["examples/division.py", ""],
            ) as input_mock:
                with redirect_stdout(output):
                    result = debug_selected_file(
                        self.reader,
                        self.client,
                        self.read_multiline,
                    )

        confirmation_prompt = input_mock.call_args_list[1].args[0]

        self.assertIn(
            "un solo secondo invio",
            confirmation_prompt,
        )
        run_revision.assert_not_called()
        self.client.chat.assert_not_called()
        self.assertIn("annullato", result)
    
if __name__ == "__main__":
    unittest.main()