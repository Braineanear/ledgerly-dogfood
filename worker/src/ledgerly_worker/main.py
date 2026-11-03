"""Executable placeholder for the Ledgerly worker."""

from ledgerly_shared import PlaceholderModel


def main() -> int:
    """Start and immediately stop the placeholder worker."""
    PlaceholderModel(identifier="worker")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
