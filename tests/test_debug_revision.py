"""Tests for bounded, read-only debugging revision orchestration."""

import json
import shutil
import unittest
from unittest.mock import Mock, call, patch
from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.debug_revision import run_debug_revision
from jarvis.ollama_client import OllamaClient, OllamaError
from jarvis.patch_validation import PatchCheck
from jarvis.project_files import ProjectFileReader


class DebugRevisionTests(unittest.TestCase):
    """Verify validation, retry limits, and history isolation."""

    def setUp(self):
        self.client = Mock(spec=OllamaClient)
        self.client.chat.side_effect = [
            "First model response.",
            "Revised model response.",
        ]

        self.initial_prompt = "Analyze the selected source and error log."
        self.selected_path = "examples/division.py"
        self.source = (
            "def divide(a, b):\n"
            "    return a / b\n"
            "\n"
            "print(divide(10, 0))\n"
        )
        self.error_log = "ZeroDivisionError: division by zero"

        self.applicable = PatchCheck(
            "APPLICABLE",
            "The patch applies to the source snapshot.",
        )
        self.rejected = PatchCheck(
            "REJECTED",
            "error: corrupt patch at line 10",
        )

        self.validator_patcher = patch(
            "jarvis.debug_revision.validate_model_patch"
        )
        self.validator = self.validator_patcher.start()
        self.addCleanup(self.validator_patcher.stop)
        self.validator.return_value = self.applicable

    def run_revision(self):
        return run_debug_revision(
            client=self.client,
            initial_prompt=self.initial_prompt,
            selected_path=self.selected_path,
            source=self.source,
            error_log=self.error_log,
        )

    def test_applicable_first_patch_stops_after_one_model_call(self):
        result = self.run_revision()

        self.client.chat.assert_called_once_with(self.initial_prompt)
        self.client.reset_history.assert_not_called()
        self.validator.assert_called_once_with(
            response="First model response.",
            selected_path=self.selected_path,
            source=self.source,
        )

        self.assertEqual(result.first_response, "First model response.")
        self.assertEqual(result.first_check, self.applicable)
        self.assertIsNone(result.second_response)
        self.assertIsNone(result.second_check)
        self.assertIsNone(result.revision_error)
        self.assertIsNone(result.revision_skipped_reason)

    def test_rejected_first_patch_gets_one_successful_revision(self):
        self.validator.side_effect = [
            self.rejected,
            self.applicable,
        ]

        result = self.run_revision()

        self.assertEqual(self.client.chat.call_count, 2)
        self.assertEqual(self.validator.call_count, 2)
        self.assertEqual(result.first_check, self.rejected)
        self.assertEqual(
            result.second_response,
            "Revised model response.",
        )
        self.assertEqual(result.second_check, self.applicable)
        self.assertIsNone(result.revision_error)
        self.assertIsNone(result.revision_skipped_reason)

    def test_two_rejected_patches_stop_without_a_third_attempt(self):
        self.validator.return_value = self.rejected

        result = self.run_revision()

        self.assertEqual(self.client.chat.call_count, 2)
        self.assertEqual(self.validator.call_count, 2)
        self.assertEqual(result.first_check, self.rejected)
        self.assertEqual(result.second_check, self.rejected)

    def test_no_patch_does_not_trigger_revision(self):
        check = PatchCheck(
            "NO_PATCH",
            "No recognized Markdown diff block.",
        )
        self.validator.return_value = check

        result = self.run_revision()

        self.client.chat.assert_called_once_with(self.initial_prompt)
        self.client.reset_history.assert_not_called()
        self.validator.assert_called_once()
        self.assertEqual(result.first_check, check)
        self.assertIsNone(result.second_response)
        self.assertIsNone(result.second_check)

    def test_check_error_does_not_trigger_revision(self):
        check = PatchCheck(
            "CHECK_ERROR",
            "Git is not available.",
        )
        self.validator.return_value = check

        result = self.run_revision()

        self.client.chat.assert_called_once_with(self.initial_prompt)
        self.client.reset_history.assert_not_called()
        self.validator.assert_called_once()
        self.assertEqual(result.first_check, check)
        self.assertIsNone(result.second_response)
        self.assertIsNone(result.second_check)

    def test_second_model_error_preserves_the_first_result(self):
        self.validator.return_value = self.rejected
        self.client.chat.side_effect = [
            "First model response.",
            OllamaError("Servizio non disponibile."),
        ]

        result = self.run_revision()

        self.assertEqual(self.client.chat.call_count, 2)
        self.validator.assert_called_once()
        self.assertEqual(result.first_response, "First model response.")
        self.assertEqual(result.first_check, self.rejected)
        self.assertIsNone(result.second_response)
        self.assertIsNone(result.second_check)
        self.assertIn(
            "Servizio non disponibile.",
            result.revision_error,
        )
        self.assertIsNone(result.revision_skipped_reason)

    def test_first_model_error_is_propagated_to_the_caller(self):
        self.client.chat.side_effect = OllamaError(
            "Servizio non disponibile."
        )

        with self.assertRaisesRegex(
            OllamaError,
            "Servizio non disponibile",
        ):
            self.run_revision()

        self.client.chat.assert_called_once_with(self.initial_prompt)
        self.client.reset_history.assert_not_called()
        self.validator.assert_not_called()

    def test_revision_prompt_contains_original_evidence_and_rejection(self):
        self.validator.side_effect = [
            self.rejected,
            self.applicable,
        ]

        self.run_revision()

        revision_prompt = self.client.chat.call_args_list[1].args[0]
        start_marker = "BEGIN UNTRUSTED JSON EVIDENCE\n"
        end_marker = "\nEND UNTRUSTED JSON EVIDENCE"

        self.assertIn(start_marker, revision_prompt)
        self.assertIn(end_marker, revision_prompt)

        evidence_text = revision_prompt.split(
            start_marker,
            1,
        )[1].rsplit(end_marker, 1)[0]
        evidence = json.loads(evidence_text)

        self.assertEqual(evidence["selected_path"], self.selected_path)
        self.assertEqual(evidence["original_source"], self.source)
        self.assertEqual(evidence["original_error_log"], self.error_log)
        self.assertEqual(
            evidence["previous_response"],
            "First model response.",
        )
        self.assertEqual(
            evidence["validator_rejection"],
            self.rejected.detail,
        )

    def test_both_responses_use_the_same_validator_and_source_snapshot(self):
        self.validator.side_effect = [
            self.rejected,
            self.applicable,
        ]

        self.run_revision()

        self.assertEqual(
            self.validator.call_args_list,
            [
                call(
                    response="First model response.",
                    selected_path=self.selected_path,
                    source=self.source,
                ),
                call(
                    response="Revised model response.",
                    selected_path=self.selected_path,
                    source=self.source,
                ),
            ],
        )

    def test_history_is_reset_between_model_calls(self):
        self.validator.side_effect = [
            self.rejected,
            self.applicable,
        ]

        self.run_revision()

        revision_prompt = self.client.chat.call_args_list[1].args[0]

        self.assertEqual(
            self.client.method_calls,
            [
                call.chat(self.initial_prompt),
                call.reset_history(),
                call.chat(revision_prompt),
            ],
        )

    def test_oversized_revision_prompt_is_not_sent(self):
        self.validator.return_value = self.rejected

        with patch(
            "jarvis.debug_revision.MAX_REVISION_PROMPT_CHARS",
            1,
        ):
            result = self.run_revision()

        self.client.chat.assert_called_once_with(self.initial_prompt)
        self.client.reset_history.assert_not_called()
        self.validator.assert_called_once()
        self.assertEqual(result.first_response, "First model response.")
        self.assertEqual(result.first_check, self.rejected)
        self.assertIsNone(result.second_response)
        self.assertIsNone(result.second_check)
        self.assertIsNone(result.revision_error)
        self.assertIsInstance(result.revision_skipped_reason, str)
        self.assertTrue(result.revision_skipped_reason.strip())

@unittest.skipUnless(shutil.which("git"), "Git is required")
class DebugRevisionIntegrationTests(unittest.TestCase):
    """Verify real patch validation preserves the selected source file."""

    def test_rejected_then_applicable_patch_preserves_original_file(self):
        original_bytes = (
            b"def divide(a, b):\n"
            b"    return a / b\n"
            b"\n"
            b"print(divide(10, 0))\n"
        )

        rejected_response = (
            "```diff\n"
            "--- a/examples/division.py\n"
            "+++ b/examples/division.py\n"
            "@@ -1,4 +1,7 @@\n"
            " def divide(a, b):\n"
            "     return a / b\n"
            " \n"
            "-print(divide(10, 0))\n"
            "+try:\n"
            "+    print(divide(10, 0))\n"
            "+except ZeroDivisionError:\n"
            "```"
        )

        applicable_response = (
            "```diff\n"
            "--- a/examples/division.py\n"
            "+++ b/examples/division.py\n"
            "@@ -1,4 +1,7 @@\n"
            " def divide(a, b):\n"
            "     return a / b\n"
            " \n"
            "-print(divide(10, 0))\n"
            "+try:\n"
            "+    print(divide(10, 0))\n"
            "+except ZeroDivisionError:\n"
            "+    print(\"Cannot divide by zero.\")\n"
            "```"
        )

        client = Mock(spec=OllamaClient)
        client.chat.side_effect = [
            rejected_response,
            applicable_response,
        ]

        with TemporaryDirectory(prefix="jarvis-revision-test-") as directory:
            root = Path(directory)
            source_path = root / "examples" / "division.py"
            source_path.parent.mkdir()
            source_path.write_bytes(original_bytes)

            reader = ProjectFileReader(root)
            source = reader.read("examples/division.py")

            result = run_debug_revision(
                client=client,
                initial_prompt=(
                    "Analyze the selected source and ZeroDivisionError. "
                    "Propose a minimal unified diff."
                ),
                selected_path="examples/division.py",
                source=source,
                error_log="ZeroDivisionError: division by zero",
            )

            self.assertEqual(
                result.first_check.status,
                "REJECTED",
                result.first_check.detail,
            )
            self.assertIsNotNone(result.second_check)
            self.assertEqual(
                result.second_check.status,
                "APPLICABLE",
                result.second_check.detail,
            )
            self.assertEqual(
                result.first_response,
                rejected_response,
            )
            self.assertEqual(
                result.second_response,
                applicable_response,
            )
            self.assertIsNone(result.revision_error)
            self.assertIsNone(result.revision_skipped_reason)

            self.assertEqual(client.chat.call_count, 2)
            client.reset_history.assert_called_once_with()

            self.assertEqual(
                source_path.read_bytes(),
                original_bytes,
                "Patch validation must not modify the original source file.",
            )

if __name__ == "__main__":
    unittest.main()