"""Chat files: one WhatsApp conversation per file, one message per line.

Format (CONTRACTS.md section 3):  [sender][timestamp][message]
"""

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

SENDERS = ("cliente", "libeen")
TS_FORMAT = "%Y-%m-%dT%H:%M"
LINE_RE = re.compile(r"^\[(cliente|libeen)\]\[([^\]]+)\]\[(.*)\]$")


class ChatFormatError(ValueError):
    """A line in a chat file does not follow the format."""


@dataclass
class Chat:
    chat_id: str
    name: str
    messages: list[dict] = field(default_factory=list)  # {index, sender, ts, text}

    def __getitem__(self, key):  # also readable as chat["messages"]
        return getattr(self, key)

    def to_dict(self) -> dict:
        return asdict(self)


def parse_chat(path) -> Chat:
    path = Path(path)
    lines = path.read_text(encoding="utf-8").split("\n")
    if lines and lines[-1] == "":  # trailing newline at end of file
        lines.pop()
    messages = []
    for index, raw in enumerate(lines):
        line = raw.rstrip("\r")
        match = LINE_RE.match(line)
        if not match:
            raise ChatFormatError(
                f"{path.name}, line {index + 1}: expected [cliente|libeen][YYYY-MM-DDTHH:MM][text], got: {line[:80]!r}"
            )
        sender, ts, text = match.groups()
        try:
            datetime.strptime(ts, TS_FORMAT)
        except ValueError:
            raise ChatFormatError(
                f"{path.name}, line {index + 1}: bad timestamp {ts!r}, expected YYYY-MM-DDTHH:MM"
            ) from None
        messages.append({"index": index, "sender": sender, "ts": ts, "text": text.replace("\\n", "\n")})
    return Chat(chat_id=path.stem, name=path.stem.capitalize(), messages=messages)


def append_message(path, sender, text) -> None:
    if sender not in SENDERS:
        raise ValueError(f"sender must be one of {SENDERS}, got {sender!r}")
    text = text.replace("\r\n", "\n").replace("\n", "\\n")
    line = f"[{sender}][{datetime.now().strftime(TS_FORMAT)}][{text}]"
    if not LINE_RE.match(line):
        raise ValueError(f"message cannot be written as one line: {text!r}")
    path = Path(path)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    prefix = "\n" if existing and not existing.endswith("\n") else ""
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{prefix}{line}\n")
