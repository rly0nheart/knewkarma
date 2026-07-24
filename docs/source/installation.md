# Install

Knew Karma needs Python 3.11 or newer.

## From PyPI

```console
pip install knewkarma
knewkarma --help
```

## For local work

```console
uv sync
uv run knewkarma --help
```

## Docker

Build the image:

```console
docker build -t knewkarma .
```

Run the command:

```console
docker run --rm knewkarma --help
```
