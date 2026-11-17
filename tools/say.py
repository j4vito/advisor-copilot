"""Append one message to a chat, to simulate either side in the demo.

Usage: python tools/say.py laura cliente "Vale, ¿cuándo hablamos?"
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.chats import SENDERS, append_message, parse_chat  # noqa: E402


def main(argv):
    if len(argv) != 3 or argv[1] not in SENDERS:
        print(__doc__.strip().splitlines()[-1].replace("Usage: ", "usage: "), file=sys.stderr)
        print(f"sender must be one of: {', '.join(SENDERS)}", file=sys.stderr)
        return 2
    chat_id, sender, text = argv
    path = ROOT / "data" / "chats" / f"{chat_id}.txt"
    if not path.exists():
        print(f"no chat {chat_id!r} in {path.parent}", file=sys.stderr)
        return 1
    append_message(path, sender, text)
    last = parse_chat(path).messages[-1]
    print(f"{chat_id} #{last['index']} [{last['sender']}][{last['ts']}] {last['text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
