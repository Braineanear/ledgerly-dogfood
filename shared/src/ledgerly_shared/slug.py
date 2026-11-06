"""Name slug helper.

Empty or whitespace-only input returns "". Punctuation and non-ASCII
characters are kept as is.
"""


def slugify(name: str) -> str:
    """Lowercase a name and join its words with hyphens."""
    return "-".join(name.lower().split())
