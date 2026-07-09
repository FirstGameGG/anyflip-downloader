from __future__ import annotations

import concurrent.futures
import io
import re
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import unquote, urlparse, urlunparse


ProgressCallback = Callable[[str, int, int, str], None]

CONFIG_TIMEOUT_SECONDS = 30
PAGE_TIMEOUT_SECONDS = 45
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


class AnyFlipDownloadError(Exception):
    """Raised when a book cannot be prepared, downloaded, or converted."""


@dataclass(frozen=True)
class DownloadOptions:
    threads: int = 4
    retries: int = 1
    retry_delay_seconds: float = 1.0
    pdf_batch_size: int = 10
    verify_tls: bool = True

    def normalized(self) -> "DownloadOptions":
        return DownloadOptions(
            threads=max(1, min(int(self.threads), 12)),
            retries=max(0, min(int(self.retries), 10)),
            retry_delay_seconds=max(0.0, float(self.retry_delay_seconds)),
            pdf_batch_size=max(1, min(int(self.pdf_batch_size), 100)),
            verify_tls=bool(self.verify_tls),
        )


@dataclass(frozen=True)
class BookMetadata:
    source_url: str
    normalized_url: str
    title: str
    file_name: str
    page_count: int
    page_urls: tuple[str, ...]


@dataclass(frozen=True)
class PageDownloadRecord:
    page_number: int
    url: str
    path: str


@dataclass(frozen=True)
class DownloadResult:
    title: str
    file_name: str
    normalized_url: str
    page_count: int
    downloaded_pages: int
    pdf_bytes: bytes
    elapsed_seconds: float
    status_log: list[str] = field(default_factory=list)

    @property
    def file_size_bytes(self) -> int:
        return len(self.pdf_bytes)


def emit_progress(
    callback: ProgressCallback | None,
    stage: str,
    completed: int,
    total: int,
    message: str,
) -> None:
    if callback:
        callback(stage, completed, total, message)


def http_get(url: str, **kwargs):
    try:
        import requests
    except ImportError as exc:
        raise AnyFlipDownloadError("ไม่พบแพ็กเกจ requests กรุณาติดตั้ง dependencies จาก requirements.txt") from exc

    return requests.get(url, **kwargs)


def normalize_anyflip_url(raw_url: str) -> str:
    candidate = raw_url.strip()
    if not candidate:
        raise AnyFlipDownloadError("กรุณาระบุ URL ของ AnyFlip")

    if "://" not in candidate:
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    hostname = (parsed.hostname or "").lower()
    if hostname != "anyflip.com" and not hostname.endswith(".anyflip.com"):
        raise AnyFlipDownloadError("รองรับเฉพาะ URL จากโดเมน anyflip.com")

    path_parts = [unquote(part) for part in parsed.path.split("/") if part]
    if len(path_parts) < 2:
        raise AnyFlipDownloadError("รูปแบบ URL ไม่ถูกต้อง ควรมี owner และรหัสหนังสือ")

    normalized_path = f"/{path_parts[0]}/{path_parts[1]}"
    return urlunparse(("https", "online.anyflip.com", normalized_path, "", "", ""))


def safe_pdf_filename(title: str) -> str:
    filename = INVALID_FILENAME_CHARS.sub("_", title).strip().strip(".")
    filename = re.sub(r"\s+", " ", filename)
    if not filename or not filename.strip("._- "):
        filename = "anyflip-download"
    if len(filename) > 140:
        filename = filename[:140].rstrip(" ._")
    if not filename:
        filename = "anyflip-download"
    return f"{filename}.pdf"


def clean_download_url(raw_url: str) -> str:
    decoded = unquote(raw_url).replace("\\", "/")
    parsed = urlparse(decoded)
    if not parsed.scheme or not parsed.netloc:
        return decoded

    cleaned_parts: list[str] = []
    for part in parsed.path.split("/"):
        if part in ("", "."):
            if not cleaned_parts:
                cleaned_parts.append("")
            continue
        if part == "..":
            if len(cleaned_parts) > 1:
                cleaned_parts.pop()
            continue
        if cleaned_parts and cleaned_parts[-1] == part:
            continue
        cleaned_parts.append(part)

    cleaned_path = "/".join(cleaned_parts) or "/"
    return parsed._replace(path=cleaned_path).geturl()


def parse_book_title(config_js: str) -> str | None:
    patterns = (
        r'"?(?:bookConfig\.)?bookTitle"?\s*=\s*"([^"]+)"',
        r'"bookTitle"\s*:\s*"([^"]+)"',
        r'"title"\s*:\s*"([^"]+)"',
    )
    for pattern in patterns:
        match = re.search(pattern, config_js)
        if match:
            title = match.group(1).strip()
            if title:
                return title
    return None


def parse_page_count(config_js: str) -> int:
    pattern = r'"?(?:bookConfig\.)?(?:total)?[Pp]ageCount"?\s*[:=]\s*"?(\d+)"?'
    match = re.search(pattern, config_js)
    if not match:
        raise AnyFlipDownloadError("ไม่พบจำนวนหน้าใน config.js")
    page_count = int(match.group(1))
    if page_count <= 0:
        raise AnyFlipDownloadError("จำนวนหน้าใน config.js ไม่ถูกต้อง")
    return page_count


def parse_page_file_names(config_js: str) -> list[str]:
    file_names: list[str] = []
    for match in re.finditer(r'"n"\s*:\s*\[(.*?)\]', config_js, flags=re.DOTALL):
        file_names.extend(re.findall(r'"([^"]+)"', match.group(1)))
    return file_names


def fetch_config_js(normalized_url: str, options: DownloadOptions) -> str:
    parsed = urlparse(normalized_url)
    config_url = urlunparse(
        (
            "https",
            "online.anyflip.com",
            f"{parsed.path}/mobile/javascript/config.js",
            "",
            "",
            "",
        )
    )
    response = http_get(
        config_url,
        headers={"User-Agent": USER_AGENT},
        timeout=CONFIG_TIMEOUT_SECONDS,
        verify=options.verify_tls,
    )
    if response.status_code != 200:
        raise AnyFlipDownloadError(f"ไม่สามารถโหลด config.js ได้: HTTP {response.status_code}")
    return response.text


def build_page_urls(normalized_url: str, page_count: int, page_file_names: Iterable[str]) -> tuple[str, ...]:
    parsed = urlparse(normalized_url)
    base_path = parsed.path.rstrip("/")
    names = list(page_file_names)

    if len(names) >= page_count:
        return tuple(
            urlunparse(
                (
                    "https",
                    "online.anyflip.com",
                    f"{base_path}/files/large/{names[index]}",
                    "",
                    "",
                    "",
                )
            )
            for index in range(page_count)
        )

    return tuple(
        urlunparse(
            (
                "https",
                "online.anyflip.com",
                f"{base_path}/files/mobile/{page_number}.jpg",
                "",
                "",
                "",
            )
        )
        for page_number in range(1, page_count + 1)
    )


def prepare_book(
    raw_url: str,
    title_override: str | None,
    options: DownloadOptions | None = None,
) -> BookMetadata:
    safe_options = (options or DownloadOptions()).normalized()
    normalized_url = normalize_anyflip_url(raw_url)
    config_js = fetch_config_js(normalized_url, safe_options)

    title = (title_override or "").strip() or parse_book_title(config_js) or Path(urlparse(normalized_url).path).name
    if not title:
        title = "anyflip-download"

    page_count = parse_page_count(config_js)
    page_urls = build_page_urls(normalized_url, page_count, parse_page_file_names(config_js))
    return BookMetadata(
        source_url=raw_url,
        normalized_url=normalized_url,
        title=title,
        file_name=safe_pdf_filename(title),
        page_count=page_count,
        page_urls=page_urls,
    )


def download_book(
    raw_url: str,
    title_override: str | None = None,
    options: DownloadOptions | None = None,
    progress_callback: ProgressCallback | None = None,
) -> DownloadResult:
    start_time = time.perf_counter()
    safe_options = (options or DownloadOptions()).normalized()
    status_log: list[str] = []

    def log(stage: str, completed: int, total: int, message: str) -> None:
        status_log.append(message)
        emit_progress(progress_callback, stage, completed, total, message)

    log("prepare", 0, 1, "กำลังอ่านข้อมูลหนังสือจาก AnyFlip...")
    metadata = prepare_book(raw_url, title_override, safe_options)
    log("prepare", 1, 1, f"พบหนังสือ \"{metadata.title}\" จำนวน {metadata.page_count:,} หน้า")

    with tempfile.TemporaryDirectory(prefix="anyflip-download-") as temp_dir:
        image_dir = Path(temp_dir) / "pages"
        image_dir.mkdir(parents=True, exist_ok=True)

        records = _download_pages(metadata, image_dir, safe_options, log)
        pdf_bytes = _build_pdf_bytes(
            sorted(Path(record.path) for record in records),
            safe_options.pdf_batch_size,
            log,
        )

    elapsed = time.perf_counter() - start_time
    log("done", 1, 1, "สร้างไฟล์ PDF เสร็จสมบูรณ์")
    return DownloadResult(
        title=metadata.title,
        file_name=metadata.file_name,
        normalized_url=metadata.normalized_url,
        page_count=metadata.page_count,
        downloaded_pages=len(records),
        pdf_bytes=pdf_bytes,
        elapsed_seconds=elapsed,
        status_log=status_log,
    )


def _download_pages(
    metadata: BookMetadata,
    image_dir: Path,
    options: DownloadOptions,
    log: ProgressCallback,
) -> list[PageDownloadRecord]:
    log("download", 0, metadata.page_count, "กำลังดาวน์โหลดรูปภาพแต่ละหน้า...")
    records: list[PageDownloadRecord] = []
    errors: list[str] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=options.threads) as executor:
        future_map = {
            executor.submit(
                _download_page,
                page_index,
                page_url,
                metadata.normalized_url,
                image_dir,
                options,
            ): page_index
            for page_index, page_url in enumerate(metadata.page_urls)
        }

        completed = 0
        for future in concurrent.futures.as_completed(future_map):
            page_index = future_map[future]
            try:
                records.append(future.result())
            except Exception as exc:
                errors.append(f"หน้า {page_index + 1}: {exc}")
            completed += 1
            log(
                "download",
                completed,
                metadata.page_count,
                f"ดาวน์โหลดแล้ว {completed:,}/{metadata.page_count:,} หน้า",
            )

    if errors:
        preview = "; ".join(errors[:3])
        if len(errors) > 3:
            preview = f"{preview}; และข้อผิดพลาดอื่นอีก {len(errors) - 3} รายการ"
        raise AnyFlipDownloadError(preview)

    records.sort(key=lambda record: record.page_number)
    return records


def _download_page(
    page_index: int,
    page_url: str,
    referer: str,
    image_dir: Path,
    options: DownloadOptions,
) -> PageDownloadRecord:
    cleaned_url = clean_download_url(page_url)
    last_error: Exception | None = None

    for attempt in range(options.retries + 1):
        try:
            response = http_get(
                cleaned_url,
                headers={"Referer": referer, "User-Agent": USER_AGENT},
                timeout=PAGE_TIMEOUT_SECONDS,
                verify=options.verify_tls,
            )
            if response.status_code != 200:
                raise AnyFlipDownloadError(f"HTTP {response.status_code}")

            extension = Path(urlparse(cleaned_url).path).suffix.lower() or ".jpg"
            if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
                extension = ".jpg"
            path = image_dir / f"{page_index:04d}{extension}"
            path.write_bytes(response.content)
            return PageDownloadRecord(page_index + 1, cleaned_url, str(path))
        except Exception as exc:
            last_error = exc
            if attempt < options.retries and options.retry_delay_seconds > 0:
                time.sleep(options.retry_delay_seconds)

    raise AnyFlipDownloadError(f"ดาวน์โหลดไม่สำเร็จหลังลอง {options.retries + 1} ครั้ง: {last_error}")


def _build_pdf_bytes(
    image_paths: list[Path],
    batch_size: int,
    log: ProgressCallback,
) -> bytes:
    if not image_paths:
        raise AnyFlipDownloadError("ไม่พบรูปภาพสำหรับสร้าง PDF")

    from PIL import Image
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    pdf_buffer = io.BytesIO()
    pdf = canvas.Canvas(pdf_buffer)
    total = len(image_paths)

    for start in range(0, total, batch_size):
        batch = image_paths[start : start + batch_size]
        for image_path in batch:
            with Image.open(image_path) as image:
                image.load()
                if image.mode not in ("RGB", "L"):
                    image = image.convert("RGB")
                width, height = image.size
                pdf.setPageSize((width, height))
                pdf.drawImage(ImageReader(image), 0, 0, width=width, height=height)
                pdf.showPage()

        completed = min(start + len(batch), total)
        log("pdf", completed, total, f"แปลงเป็น PDF แล้ว {completed:,}/{total:,} หน้า")

    pdf.save()
    return pdf_buffer.getvalue()
