from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from anyflip_downloader import (
    AnyFlipDownloadError,
    DownloadOptions,
    _build_pdf_bytes,
    build_page_urls,
    clean_download_url,
    normalize_anyflip_url,
    parse_book_title,
    parse_page_count,
    parse_page_file_names,
    prepare_book,
    safe_pdf_filename,
)


CONFIG_JS = """
var bookConfig = {};
bookConfig.bookTitle = "Rice Market Report";
bookConfig.totalPageCount = "3";
var pages = [{"n":["page-1.webp"]},{"n":["page-2.webp"]},{"n":["page-3.webp"]}];
"""


class AnyFlipDownloaderTest(unittest.TestCase):
    def test_normalize_anyflip_url_keeps_owner_and_book(self) -> None:
        normalized = normalize_anyflip_url("https://online.anyflip.com/abcd/efgh/mobile/index.html")
        self.assertEqual(normalized, "https://online.anyflip.com/abcd/efgh")

    def test_normalize_anyflip_url_rejects_other_domains(self) -> None:
        with self.assertRaises(AnyFlipDownloadError):
            normalize_anyflip_url("https://example.com/abcd/efgh")
        with self.assertRaises(AnyFlipDownloadError):
            normalize_anyflip_url("https://notanyflip.com/abcd/efgh")

    def test_parse_config_values(self) -> None:
        self.assertEqual(parse_book_title(CONFIG_JS), "Rice Market Report")
        self.assertEqual(parse_page_count(CONFIG_JS), 3)
        self.assertEqual(parse_page_file_names(CONFIG_JS), ["page-1.webp", "page-2.webp", "page-3.webp"])

    def test_build_page_urls_uses_large_files_when_names_exist(self) -> None:
        urls = build_page_urls(
            "https://online.anyflip.com/abcd/efgh",
            2,
            ["p1.webp", "p2.webp"],
        )
        self.assertEqual(
            urls,
            (
                "https://online.anyflip.com/abcd/efgh/files/large/p1.webp",
                "https://online.anyflip.com/abcd/efgh/files/large/p2.webp",
            ),
        )

    def test_build_page_urls_falls_back_to_mobile_images(self) -> None:
        urls = build_page_urls("https://online.anyflip.com/abcd/efgh", 2, [])
        self.assertEqual(
            urls,
            (
                "https://online.anyflip.com/abcd/efgh/files/mobile/1.jpg",
                "https://online.anyflip.com/abcd/efgh/files/mobile/2.jpg",
            ),
        )

    def test_prepare_book_uses_title_override_and_safe_filename(self) -> None:
        with patch("anyflip_downloader.fetch_config_js", return_value=CONFIG_JS):
            metadata = prepare_book(
                "https://online.anyflip.com/abcd/efgh/",
                "Q1/Rice:Report",
                DownloadOptions(),
            )

        self.assertEqual(metadata.title, "Q1/Rice:Report")
        self.assertEqual(metadata.file_name, "Q1_Rice_Report.pdf")
        self.assertEqual(metadata.page_count, 3)

    def test_safe_pdf_filename_falls_back_for_invalid_titles(self) -> None:
        self.assertEqual(safe_pdf_filename("///"), "anyflip-download.pdf")

    def test_clean_download_url_resolves_path_segments_and_duplicates(self) -> None:
        self.assertEqual(
            clean_download_url("https://online.anyflip.com/a/b/files/large/../files/mobile/1.jpg"),
            "https://online.anyflip.com/a/b/files/mobile/1.jpg",
        )

    def test_build_pdf_bytes_returns_pdf(self) -> None:
        try:
            from PIL import Image
            import reportlab  # noqa: F401
        except Exception as exc:
            self.skipTest(f"PDF dependencies are not installed: {exc}")

        messages: list[str] = []

        def log(stage: str, completed: int, total: int, message: str) -> None:
            messages.append(f"{stage}:{completed}/{total}:{message}")

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = []
            for index in range(2):
                path = Path(temp_dir) / f"{index:04d}.jpg"
                Image.new("RGB", (20, 30), color=(255, 255, 255)).save(path)
                paths.append(path)

            pdf_bytes = _build_pdf_bytes(paths, batch_size=1, log=log)

        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertTrue(messages)


if __name__ == "__main__":
    unittest.main()
