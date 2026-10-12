"""Tests for restricted project file reading."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.project_files import ProjectFileError, ProjectFileReader


class ProjectFileReaderTests(unittest.TestCase):
    """Verify allowed reads and rejected paths."""

    def setUp(self):
        self.temp_directory = TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)

        self.base = Path(self.temp_directory.name)
        self.root = self.base / "project"
        self.root.mkdir()

        self.reader = ProjectFileReader(self.root)

    def create_file(self, relative_path, content=b"example"):
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_reads_utf8_source_without_modifying_it(self):
        content = b"def square(number):\n    return number * number\n"
        path = self.create_file("src/example.py", content)

        result = self.reader.read("src/example.py")

        self.assertEqual(result, content.decode("utf-8"))
        self.assertEqual(path.read_bytes(), content)

    def test_rejects_empty_path(self):
        with self.assertRaises(ProjectFileError):
            self.reader.read("")

    def test_rejects_absolute_path(self):
        path = self.create_file("example.py")

        with self.assertRaises(ProjectFileError):
            self.reader.read(str(path))

    def test_rejects_path_outside_project(self):
        outside = self.base / "outside.py"
        outside.write_text("print('outside')", encoding="utf-8")

        with self.assertRaisesRegex(ProjectFileError, "esce"):
            self.reader.read("../outside.py")

    def test_rejects_symlink_outside_project(self):
        outside = self.base / "outside.py"
        outside.write_text("print('outside')", encoding="utf-8")

        link = self.root / "linked.py"
        link.symlink_to(outside)

        with self.assertRaisesRegex(ProjectFileError, "esce"):
            self.reader.read("linked.py")

    def test_rejects_excluded_directory(self):
        self.create_file("secrets/config.py")

        with self.assertRaisesRegex(ProjectFileError, "esclusa"):
            self.reader.read("secrets/config.py")

    def test_rejects_symlink_to_excluded_directory(self):
        target = self.create_file("secrets/config.py")
        (self.root / "linked.py").symlink_to(target)

        with self.assertRaisesRegex(ProjectFileError, "esclusa"):
            self.reader.read("linked.py")

    def test_rejects_unsupported_extension(self):
        self.create_file(".env", b"API_KEY=private")

        with self.assertRaisesRegex(ProjectFileError, "Tipo"):
            self.reader.read(".env")

    def test_rejects_missing_file(self):
        with self.assertRaises(ProjectFileError):
            self.reader.read("missing.py")

    def test_rejects_directory(self):
        (self.root / "folder.py").mkdir()

        with self.assertRaisesRegex(ProjectFileError, "non indica"):
            self.reader.read("folder.py")

    def test_rejects_oversized_file(self):
        reader = ProjectFileReader(self.root, max_bytes=10)
        self.create_file("large.py", b"x" * 11)

        with self.assertRaisesRegex(ProjectFileError, "limite"):
            reader.read("large.py")

    def test_rejects_invalid_utf8(self):
        self.create_file("invalid.py", b"\xff")

        with self.assertRaisesRegex(ProjectFileError, "UTF-8"):
            self.reader.read("invalid.py")

    def test_rejects_binary_content(self):
        self.create_file("binary.py", b"abc\x00def")

        with self.assertRaisesRegex(ProjectFileError, "binari"):
            self.reader.read("binary.py")


if __name__ == "__main__":
    unittest.main()