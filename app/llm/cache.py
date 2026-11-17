"""Results cached in `data/cache/<chat_id>.json`, keyed by a hash of the chat.

Only real-model answers are cached; mock answers are free to recompute.
"""

import hashlib
import json

from app.llm import settings


def chat_parts(chat) -> tuple[str, str, list[dict]]:
    """(chat_id, name, messages) from a Chat object or a plain dict."""
    get = (lambda k: chat[k]) if isinstance(chat, dict) else (lambda k: getattr(chat, k))
    messages = []
    for m in get("messages"):
        mget = (lambda k: m[k]) if isinstance(m, dict) else (lambda k: getattr(m, k))
        messages.append({"index": mget("index"), "sender": mget("sender"), "ts": str(mget("ts")), "text": mget("text")})
    return get("chat_id"), get("name"), messages


def digest(*parts) -> str:
    """Stable hash of JSON-able parts. The chat hash is over its parsed messages,
    which change exactly when the chat file changes."""
    raw = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _path(chat_id: str):
    return settings.CACHE_DIR / f"{chat_id}.json"


def load(chat_id: str, slot: str, key: str):
    path = _path(chat_id)
    if not path.exists():
        return None
    try:
        entry = json.loads(path.read_text(encoding="utf-8")).get(slot)
    except (json.JSONDecodeError, AttributeError):
        return None
    if entry and entry.get("key") == key:
        return entry["value"]
    return None


def save(chat_id: str, slot: str, key: str, value) -> None:
    path = _path(chat_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    data[slot] = {"key": key, "value": value}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
