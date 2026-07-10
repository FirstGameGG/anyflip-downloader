from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
ASSETS_DIR = APP_PATH.parent / "assets"


def by_label(elements, label: str):
    return next(element for element in elements if element.label == label)


class AnyFlipAppTest(unittest.TestCase):
    def render(self) -> AppTest:
        return AppTest.from_file(APP_PATH, default_timeout=10).run()

    def test_initial_render(self) -> None:
        with patch("anyflip_downloader.download_book") as download_book:
            app = self.render()

        self.assertEqual(app.exception.len, 0)
        self.assertEqual(app.title.values, ["ระบบดาวน์โหลด AnyFlip เป็น PDF"])
        self.assertEqual(app.header.values, ["แปลงหนังสือออนไลน์เป็นไฟล์ PDF"])
        self.assertIn(
            "ขั้นตอน: (1) วางลิงก์ AnyFlip → (2) ระบุชื่อไฟล์หรือใช้ชื่อหนังสือ → "
            "(3) ยืนยันสิทธิ์ → (4) สร้างและดาวน์โหลด PDF",
            app.caption.values,
        )
        self.assertEqual(
            [element.label for element in app.text_input],
            ["ลิงก์ AnyFlip", "ชื่อไฟล์ PDF"],
        )
        self.assertEqual(
            by_label(app.button, "เริ่มดาวน์โหลดและสร้าง PDF").proto.type,
            "primary",
        )
        self.assertTrue((ASSETS_DIR / "anyflip.jpg").is_file())
        image_count = max(len(app.get("imgs")), len(app.get("image")))
        self.assertEqual(image_count, 1)
        download_book.assert_not_called()

    def test_empty_url_validation(self) -> None:
        with patch("anyflip_downloader.download_book") as download_book:
            app = self.render()
            by_label(app.button, "เริ่มดาวน์โหลดและสร้าง PDF").click().run()

        self.assertEqual(app.error.values, ["กรุณาระบุลิงก์ AnyFlip ก่อนเริ่มทำงาน"])
        self.assertEqual(app.exception.len, 0)
        download_book.assert_not_called()

    def test_permission_validation(self) -> None:
        with patch("anyflip_downloader.download_book") as download_book:
            app = self.render()
            by_label(app.text_input, "ลิงก์ AnyFlip").set_value(
                "https://online.anyflip.com/abcd/efgh"
            )
            by_label(app.button, "เริ่มดาวน์โหลดและสร้าง PDF").click().run()

        self.assertEqual(
            app.error.values,
            ["กรุณายืนยันสิทธิ์การดาวน์โหลดก่อนเริ่มทำงาน"],
        )
        self.assertEqual(app.exception.len, 0)
        download_book.assert_not_called()


if __name__ == "__main__":
    unittest.main()
