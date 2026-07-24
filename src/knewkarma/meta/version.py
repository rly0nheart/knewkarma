"""Package version, read from the installed distribution metadata."""

from importlib.metadata import PackageNotFoundError, version


class Version:
    """The package version, read from the installed distribution so it never drifts from pyproject."""

    try:
        full_version: str = version("knewkarma")
    except PackageNotFoundError:  # a source tree with nothing installed yet
        full_version = "0.0.0"

    release: str = ".".join(full_version.split(".")[:2])
