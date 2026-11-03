"""FastAPI application bootstrap."""

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Create the non-business Ledgerly API placeholder."""
    return FastAPI(title="Ledgerly API")


app = create_app()
