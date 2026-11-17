"""python -m app.llm.warm [--fresh] [--jobs N] [chat_id ...]

Refreshes the recorded real answers in data/cache/ before committing: runs extract and
draft with the real model for every chat in data/chats. Chats that end with a libeen
message get no draft (CONTRACTS 11.9). Needs ANTHROPIC_API_KEY.
"""

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from app.llm import cache, settings
from app.llm.draft import draft
from app.llm.extract import extract

CHATS_DIR = settings.ROOT / "data" / "chats"


def warm_one(path: Path, fresh: bool) -> str:
    from app.chats import parse_chat
    from app.rules import analyze, load_config

    chat = parse_chat(path)
    chat_id, _, messages = cache.chat_parts(chat)
    if fresh:
        cache.drop(chat_id, "extraction")
        cache.drop(chat_id, "draft")
    start = time.monotonic()
    extraction = extract(chat)
    config = load_config()
    analysis = analyze(extraction, config)
    if messages and messages[-1]["sender"] == "libeen":
        cache.drop(chat_id, "draft")
        what = "sin borrador (último mensaje de libeen)"
    else:
        draft(chat, analysis, config)
        what = f"borrador {analysis['reply_kind']}"
    return f"{chat_id:<12} extracción + {what} ({time.monotonic() - start:.0f} s)"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("chat_ids", nargs="*", help="only these chats")
    parser.add_argument("--fresh", action="store_true", help="ignore stored answers and call the model again")
    parser.add_argument("--jobs", type=int, default=4, help="chats in parallel (default 4)")
    args = parser.parse_args(argv)

    if not settings.live():
        print("Hace falta ANTHROPIC_API_KEY (y el paquete anthropic) para grabar respuestas reales.", file=sys.stderr)
        return 2

    paths = sorted(CHATS_DIR.glob("*.txt"))
    if args.chat_ids:
        paths = [p for p in paths if p.stem in args.chat_ids]
    print(f"Grabando {len(paths)} chats con {settings.model()} en {settings.CACHE_DIR}")

    failed = 0
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = {pool.submit(warm_one, p, args.fresh): p.stem for p in paths}
        for done, future in enumerate(as_completed(futures), 1):
            try:
                line = future.result()
            except Exception as exc:  # one broken chat must not stop the others
                failed += 1
                line = f"{futures[future]:<12} ERROR {type(exc).__name__}: {exc}"
            print(f"[{done:>2}/{len(paths)}] {line}", flush=True)

    print("Listo." if not failed else f"{failed} chats fallaron.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
