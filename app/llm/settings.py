"""Where the model layer reads its settings from: the environment and `.env`.

The API key is only ever read here and handed to the Anthropic client.
It is never logged, cached or put in a prompt.

`live()` says whether a real model call may be made. When it is False, `extract` and
`draft` use the recorded real answer for that chat (data/cache/), then the mock.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "data" / "cache"

DEFAULT_MODEL = "claude-haiku-5-5"  # CONTRACTS section 7; ANTHROPIC_MODEL overrides it

_env_loaded = False


def _load_env_file() -> None:
    """Read `KEY=VALUE` lines from `.env` without overriding the real environment."""
    global _env_loaded
    if _env_loaded:
        return
    _env_loaded = True
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def api_key() -> str | None:
    """The key, or None for mock mode. `CLAUDE_API_KEY` is accepted as an alias."""
    _load_env_file()
    if os.environ.get("LIBEEN_MOCK") == "1":
        return None
    return os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY") or None


def model() -> str:
    _load_env_file()
    return os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL


_warned_no_package = False


def _package_available() -> bool:
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def live() -> bool:
    """True when a real model call can be made: a key, no LIBEEN_MOCK, and the `anthropic` package.
    A key without the package behaves like no key, and says so once on stderr."""
    global _warned_no_package
    if api_key() is None:
        return False
    if not _package_available():
        if not _warned_no_package:
            _warned_no_package = True
            print(
                "Aviso: hay API key pero el paquete `anthropic` no está instalado. "
                "Se usan las respuestas grabadas (data/cache/) o el modo simulado.",
                file=sys.stderr,
            )
        return False
    return True
