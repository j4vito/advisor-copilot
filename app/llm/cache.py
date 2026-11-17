"""Real model answers, stored in `data/cache/<chat_id>.json` (committed to the repo).

Each file has an `extraction` and a `draft` slot:
    {"key": ..., "chat": ..., "model": ..., "reply_kind": ..., "value": <raw model answer>}

- `key` hashes everything the answer depends on (model id, prompt, chat, and for the draft
  the analysis and config). With a key in the env, a matching `key` means no new call.
- `chat` hashes only the chat content. With no key, a matching `chat` is enough: the answer
  is used as a recorded real answer (CONTRACTS 11.10), whatever model or prompt made it.

Only real-model answers are stored. The API key is never part of any of this.
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


def chat_hash(messages: list[dict]) -> str:
    return digest(messages)


def _path(chat_id: str):
    return settings.CACHE_DIR / f"{chat_id}.json"


def _entry(chat_id: str, slot: str):
    path = _path(chat_id)
    if not path.exists():
        return None
    try:
        entry = json.loads(path.read_text(encoding="utf-8")).get(slot)
    except (json.JSONDecodeError, AttributeError):
        return None
    return entry if isinstance(entry, dict) and "value" in entry else None


def load(chat_id: str, slot: str, key: str):
    """The answer stored under exactly this key, or None."""
    entry = _entry(chat_id, slot)
    return entry["value"] if entry and entry.get("key") == key else None


def load_recorded(chat_id: str, slot: str, chat: str, reply_kind: str | None = None):
    """The recorded answer for this chat content, or None. For a draft, the reply kind
    must match too: a recorded offer is no use when the rules now say decline."""
    entry = _entry(chat_id, slot)
    if not entry or entry.get("chat") != chat:
        return None
    if reply_kind is not None and entry.get("reply_kind") != reply_kind:
        return None
    return entry["value"]


def save(chat_id: str, slot: str, key: str, value, chat: str, reply_kind: str | None = None) -> None:
    path = _path(chat_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    entry = {"key": key, "chat": chat, "model": settings.model()}
    if reply_kind is not None:
        entry["reply_kind"] = reply_kind
    entry["value"] = value
    data[slot] = entry
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def drop(chat_id: str, slot: str) -> None:
    """Remove one slot (used when a chat no longer needs a draft)."""
    path = _path(chat_id)
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if data.pop(slot, None) is not None:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
