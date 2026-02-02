"""Load .env variables for HoneyGrid."""

from __future__ import annotations

from pathlib import Path


def load_env() -> bool:
    """
    Load environment variables from a .env file if present.

    Returns:
        True if python-dotenv is available, False otherwise.
    """
    try:
        from dotenv import find_dotenv, load_dotenv
    except Exception:
        return False

    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path:
        load_dotenv(dotenv_path, override=True)
    else:
        # Fallback: check workspace root .env
        candidate = Path.cwd() / ".env"
        if candidate.exists():
            load_dotenv(candidate, override=True)

    return True
