from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from desktop_app import count_pdf_pages, pages_in_range
from services.print_options import get_sumatra_paper_setting
from workers.print_worker import PrintWorker


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


    def test_sumatra_settings_use_selected_paper_and_orientation(self) -> None:
        worker = PrintWorker.__new__(PrintWorker)

        portrait = worker._print_settings({"paper_size": "A5", "orientation": "portrait"})
        landscape = worker._print_settings({"paper_size": "A5", "orientation": "landscape"})

        self.assertEqual(get_sumatra_paper_setting("A5"), "paper=A5")
        self.assertEqual(portrait, "portrait,disable-auto-rotation,paper=A5")
        self.assertEqual(landscape, "landscape,disable-auto-rotation,paper=A5")

if __name__ == "__main__":
    unittest.main()
