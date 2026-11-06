"""Tests for read-only validation of model-generated patches."""

import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from jarvis.patch_validation import validate_model_patch


SOURCE = "value = 1\n"

VALID_PATCH = (
    "```diff\n"
    "--- a/example.py\n"
    "+++ b/example.py\n"
    "@@ -1 +1 @@\n"
    "-value = 1\n"
    "+value = 2\n"
    "```\n"
)


class PatchValidationTests(unittest.TestCase):
    """Verify rejection rules and Git applicability checks."""

    def test_response_without_diff_returns_no_patch(self):
        result = validate_model_patch(
            "Non propongo modifiche.",
            "example.py",
            SOURCE,
        )

        self.assertEqual(result.status, "NO_PATCH")

    def test_multiple_diff_blocks_are_rejected(self):
        with patch("jarvis.patch_validation.subprocess.run") as run:
            result = validate_model_patch(
                VALID_PATCH + VALID_PATCH,
                "example.py",
                SOURCE,
            )

        self.assertEqual(result.status, "REJECTED")
        run.assert_not_called()

    def test_different_file_is_rejected_before_git(self):
        with patch("jarvis.patch_validation.subprocess.run") as run:
            result = validate_model_patch(
                VALID_PATCH.replace("example.py", "other.py"),
                "example.py",
                SOURCE,
            )

        self.assertEqual(result.status, "REJECTED")
        run.assert_not_called()

    def test_path_traversal_is_rejected(self):
        with patch("jarvis.patch_validation.subprocess.run") as run:
            result = validate_model_patch(
                VALID_PATCH,
                "../example.py",
                SOURCE,
            )

        self.assertEqual(result.status, "REJECTED")
        run.assert_not_called()

    def test_second_file_inside_block_is_rejected(self):
        response = VALID_PATCH.replace(
            "```\n",
            "--- a/other.py\n"
            "+++ b/other.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
            "```\n",
        )

        result = validate_model_patch(
            response,
            "example.py",
            SOURCE,
        )

        self.assertEqual(result.status, "REJECTED")
        
    @unittest.skipUnless(shutil.which("git"), "Git is required")
    def test_git_style_patch_header_is_supported(self):
        response = VALID_PATCH.replace(
            "```diff\n",
            "```diff\n"
            "diff --git a/example.py b/example.py\n"
            "index 1234567..89abcdef 100644\n",
            1,
        )

        result = validate_model_patch(
            response,
            "example.py",
            SOURCE,
        )

        self.assertEqual(result.status, "APPLICABLE")

    @unittest.skipUnless(shutil.which("git"), "Git is required")
    def test_valid_patch_is_applicable_without_modifying_project(self):
        with TemporaryDirectory() as directory:
            original = Path(directory) / "example.py"
            original.write_bytes(SOURCE.encode("utf-8"))

            result = validate_model_patch(
                VALID_PATCH,
                "example.py",
                original.read_text(encoding="utf-8"),
            )

            self.assertEqual(result.status, "APPLICABLE")
            self.assertEqual(
                original.read_bytes(),
                SOURCE.encode("utf-8"),
            )

    @unittest.skipUnless(shutil.which("git"), "Git is required")
    def test_corrupt_hunk_counts_are_rejected(self):
        response = VALID_PATCH.replace(
            "@@ -1 +1 @@",
            "@@ -1,6 +1,10 @@",
        )

        result = validate_model_patch(
            response,
            "example.py",
            SOURCE,
        )

        self.assertEqual(result.status, "REJECTED")

    @unittest.skipUnless(shutil.which("git"), "Git is required")
    def test_source_mismatch_is_rejected(self):
        result = validate_model_patch(
            VALID_PATCH,
            "example.py",
            "value = 99\n",
        )

        self.assertEqual(result.status, "REJECTED")

    @patch("jarvis.patch_validation.subprocess.run")
    def test_missing_git_returns_check_error(self, run):
        run.side_effect = FileNotFoundError()

        result = validate_model_patch(
            VALID_PATCH,
            "example.py",
            SOURCE,
        )

        self.assertEqual(result.status, "CHECK_ERROR")

    @patch("jarvis.patch_validation.subprocess.run")
    def test_timeout_returns_check_error(self, run):
        run.side_effect = subprocess.TimeoutExpired(
            cmd=["git", "apply"],
            timeout=5,
        )

        result = validate_model_patch(
            VALID_PATCH,
            "example.py",
            SOURCE,
        )

        self.assertEqual(result.status, "CHECK_ERROR")


if __name__ == "__main__":
    unittest.main()