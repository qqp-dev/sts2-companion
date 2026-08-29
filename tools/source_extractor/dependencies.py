"""Optional development dependency check without importing game data."""

from importlib import metadata

from .errors import SourceExtractionError

REQUIRED = {"dnfile": "0.18.0", "dncil": "1.0.2"}
INSTALL_HELP = (
    "create a development venv and install the pins: "
    "python3 -m venv .venv-source && "
    ".venv-source/bin/python -m pip install -r requirements-source.txt"
)


def require_metadata_dependencies() -> None:
    problems: list[str] = []
    for package, expected in REQUIRED.items():
        try:
            actual = metadata.version(package)
        except metadata.PackageNotFoundError:
            problems.append(f"{package} is not installed (need {expected})")
            continue
        if actual != expected:
            problems.append(f"{package}=={actual} is installed (need {expected})")
    if problems:
        raise SourceExtractionError("; ".join(problems) + "; " + INSTALL_HELP)
