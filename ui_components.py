from __future__ import annotations

from pathlib import Path

import streamlit as st


def load_custom_css(base_dir: Path) -> None:
    style_path = base_dir / ".streamlit" / "style.css"
    if style_path.exists():
        st.markdown(f"<style>{style_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def render_header(base_dir: Path) -> None:
    header_col, logo_col = st.columns([6, 1], vertical_alignment="center")
    with header_col:
        st.title("ระบบดาวน์โหลด AnyFlip เป็น PDF")
        st.header("แปลงหนังสือออนไลน์เป็นไฟล์ PDF")
        st.markdown(
            "วางลิงก์ AnyFlip ที่ต้องการ ระบบจะอ่านข้อมูลหนังสือ ดาวน์โหลดหน้าที่อนุญาต "
            "และรวมเป็นไฟล์ PDF พร้อมดาวน์โหลดในหน้าเดียว"
        )

    logo_path = base_dir / "assets" / "anyflip.jpg"
    with logo_col:
        if logo_path.exists():
            st.image(str(logo_path), width="stretch")

    st.divider()


def format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value):,} {unit}"
            return f"{value:,.1f} {unit}"
        value /= 1024
    return f"{value:,.1f} GB"


def render_footer() -> None:
    st.markdown("---")
    st.markdown(
        "<div class='app-footer'>ใช้งานเฉพาะเอกสารที่เจ้าของอนุญาตให้ดาวน์โหลดเป็น PDF เท่านั้น</div>",
        unsafe_allow_html=True,
    )
