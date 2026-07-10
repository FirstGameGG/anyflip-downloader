# Contributing

Contributions, bug reports, and feature suggestions are welcome.

## Local setup

Use Python 3.12 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

Run the application locally:

```bash
python -m streamlit run app.py
```

## Before submitting a pull request

Compile the Python modules and run the complete test suite:

```bash
python -m py_compile app.py anyflip_downloader.py ui_components.py tests/test_app.py tests/test_anyflip_downloader.py
python -m unittest discover -s tests -v
```

Keep changes focused, follow PEP 8, preserve type hints where practical, and add or update tests for changed behavior. Tests should not depend on live AnyFlip requests.

## Issues and pull requests

Search existing issues before opening a new one and use the provided issue templates. Include reproduction steps, expected behavior, actual behavior, Python version, Streamlit version, browser, and operating system for bug reports.

Describe the purpose and user-visible impact of each pull request. Only test downloads with documents you are authorized to download.
