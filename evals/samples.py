"""Load eval cases: the real chats from agent 1 when they exist, else `samples/laura.json`."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHATS_DIR = ROOT / "data" / "chats"
EXPECTED_DIR = ROOT / "data" / "expected"
SAMPLE = ROOT / "samples" / "laura.json"

_LINE = re.compile(r"^\[(cliente|libeen)\]\[([^\]]+)\]\[(.*)\]$")


def chat_from_lines(chat_id: str, lines: list[str]) -> dict:
    """Minimal stand-in for `app.chats.parse_chat`, used only for the sample."""
    messages = []
    for i, line in enumerate(lines):
        match = _LINE.match(line)
        if not match:
            raise ValueError(f"{chat_id}: line {i} does not match the chat format")
        sender, ts, text = match.groups()
        messages.append({"index": i, "sender": sender, "ts": ts, "text": text.replace("\\n", "\n")})
    return {"chat_id": chat_id, "name": chat_id.capitalize(), "messages": messages}


def load_sample() -> dict:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def cases() -> tuple[str, list[tuple[object, dict]]]:
    """(source description, [(chat, expected)])."""
    try:
        from app.chats import parse_chat
    except ImportError:
        parse_chat = None

    paths = sorted(CHATS_DIR.glob("*.txt")) if CHATS_DIR.exists() else []
    if parse_chat and paths:
        out = []
        for path in paths:
            exp_path = EXPECTED_DIR / f"{path.stem}.json"
            expected = json.loads(exp_path.read_text(encoding="utf-8")) if exp_path.exists() else None
            out.append((parse_chat(path), expected))
        return "data/chats", out

    sample = load_sample()
    return "samples/laura.json", [(chat_from_lines("laura", sample["chat_file"]), sample["expected"])]
