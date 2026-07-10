# AnyFlip PDF Downloader

[![CI](https://github.com/FirstGameGG/anyflip-downloader/actions/workflows/build.yml/badge.svg)](https://github.com/FirstGameGG/anyflip-downloader/actions/workflows/build.yml)

<p align="center">
  <img src="assets/anyflip.jpg" alt="AnyFlip" width="180">
</p>

A Thai-language Streamlit application that downloads permitted AnyFlip page images and combines them into a PDF.

## Disclaimer

Use this application only for documents whose owner explicitly permits PDF downloading. You are responsible for complying with copyright law, the publisher's terms, and AnyFlip's terms of service.

This project does not determine whether you have permission, bypass authentication or access controls, or have any affiliation with AnyFlip. AnyFlip and its logo are the property of their respective owner.

## Features

- Accepts standard and mobile `anyflip.com` book URLs
- Uses the AnyFlip book title or an optional custom PDF filename
- Downloads pages concurrently with configurable retries and delay
- Displays progress, result metrics, and an execution log
- Preserves page order and original image dimensions
- Generates PDFs without permanent server-side file storage
- Provides a responsive Thai interface built with Streamlit

## Local setup

Python 3.12 is recommended.

```bash
git clone https://github.com/FirstGameGG/anyflip-downloader.git
cd anyflip-downloader

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python -m streamlit run app.py
```

On Windows, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

Then open [http://localhost:8501](http://localhost:8501).

## Usage

1. Paste a permitted AnyFlip URL, such as `https://online.anyflip.com/owner/book/`.
2. Optionally enter a custom PDF filename.
3. Adjust the advanced options when needed.
4. Confirm that the document is permitted for PDF download.
5. Select **เริ่มดาวน์โหลดและสร้าง PDF**.
6. Review the result and download the generated PDF.

## Advanced options

| Option | Default | Purpose |
| --- | ---: | --- |
| Concurrent downloads | 4 | Number of pages downloaded simultaneously |
| PDF batch size | 10 pages | Number of images processed in each PDF batch |
| Retries per page | 1 | Additional attempts after a failed page request |
| Retry delay | 1 second | Wait time before another attempt |
| TLS verification | Enabled | Verifies HTTPS certificates and should normally remain enabled |

Lower concurrency can help on unstable networks. Smaller PDF batches reduce peak processing load but may take longer.

## How it works

1. The application normalizes the submitted URL to its AnyFlip owner and book identifiers.
2. It reads the public viewer's `config.js` to determine the title, page count, and available page assets.
3. Page images are downloaded concurrently into a temporary directory, with retries when configured.
4. The images are combined in order into an image-based PDF, then the temporary files are removed.
5. The PDF bytes remain only in the active Streamlit session until the session ends or a new job starts.

## Project structure

```text
.
├── app.py                    # Streamlit UI, validation, progress, and results
├── anyflip_downloader.py     # URL parsing, downloads, retries, and PDF generation
├── ui_components.py          # Shared header, footer, and stylesheet loading
├── assets/anyflip.jpg        # Header and README logo
├── .streamlit/               # Theme and responsive application styling
├── tests/                    # Downloader unit tests and Streamlit UI tests
├── requirements.txt          # Python dependencies
└── Dockerfile                # Containerized Streamlit application
```

The main Python interface is `download_book()`. It accepts `DownloadOptions`, returns `DownloadResult`, and raises `AnyFlipDownloadError` for expected failures.

## Testing

```bash
python -m py_compile app.py anyflip_downloader.py ui_components.py tests/test_app.py tests/test_anyflip_downloader.py
python -m unittest discover -s tests -v
```

The tests cover URL validation, metadata parsing, page URL generation, safe filenames, PDF creation, initial UI rendering, and form validation without live AnyFlip requests.

## Docker

```bash
docker build -t anyflip-downloader .
docker run --rm -p 8501:8501 anyflip-downloader
```

Open [http://localhost:8501](http://localhost:8501).

## Deployment

For Streamlit Community Cloud, select `app.py` as the entrypoint. Dependencies are declared in `requirements.txt`; no application secrets are required.

The deployment environment must allow outbound HTTPS requests to public AnyFlip assets. Large books may exceed the memory or execution limits of hosted environments.

## Limitations

- Supports only AnyFlip URLs containing an owner and book identifier
- Requires publicly accessible viewer metadata and page assets
- Does not support private, authenticated, or access-controlled books
- Produces image-based PDFs without selectable text, links, or document structure
- Very large books may require substantial memory and processing time
- Changes to AnyFlip's viewer format may require parser updates
- Provides no queue, history, persistent storage, REST API, or command-line interface

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and validation guidance.

## License

Licensed under the [GNU General Public License v3.0](LICENSE).
