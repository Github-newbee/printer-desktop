from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from desktop_app import count_pdf_pages, pages_in_range


class DesktopHelperTests(unittest.TestCase):
    def test_page_count_handles_pdf_page_markers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.pdf"
            path.write_bytes(b"%PDF-1.7\n/Type /Page\n/Type /Page\n%%EOF")
            self.assertEqual(count_pdf_pages(path), 2)

    def test_page_count_handles_marker_split_across_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "split.pdf"
            marker = b"/Type /Page"
            header = b"%PDF-1.7\n"
            path.write_bytes(header + b"x" * (1024 * 1024 - len(header) - 4) + marker + b"\n%%EOF")
            self.assertEqual(count_pdf_pages(path), 1)

    def test_page_range_summary_is_limited_to_document_pages(self) -> None:
        self.assertEqual(pages_in_range("1-2,4", 3), 3)
        self.assertEqual(pages_in_range("", 5), 5)


if __name__ == "__main__":
    unittest.main()
