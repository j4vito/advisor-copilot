"""HTTP server: wires the pieces together. No business logic lives here.

Routes (CONTRACTS section 8):
    GET  /                        the page
    GET  /api/inbox               chats, already sorted by inbox_sort
    GET  /api/chats/{id}          {chat, extraction, analysis, draft, checks}
    POST /api/chats/{id}/approve  appends a libeen message and one log line

Sample mode (LIBEEN_SAMPLE=1, or when app.chats / app.rules / app.llm are not
importable yet) serves samples/laura.json behind the same routes.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
CHAT_ID = re.compile(r"^[a-z0-9_-]+$")
SENT_TEXT_CHECKS = ("banned_words", "numbers_in_facts", "internal_terms", "max_chars")  # the checks that apply to any text


def to_jsonable(obj: Any) -> Any:
    """Turn dataclasses, pydantic models and nested containers into plain JSON."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return to_jsonable(dataclasses.asdict(obj))
    if hasattr(obj, "model_dump"):
        return to_jsonable(obj.model_dump())
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, datetime):
        return obj.isoformat(timespec="minutes")
    return obj


# --- Pipelines -------------------------------------------------------------
# A pipeline is the set of functions from CONTRACTS plus the loaded config.
# The server only calls these, so the real and the sample one are swappable.


def real_pipeline() -> SimpleNamespace:
    from app.chats import append_message, parse_chat
    from app.llm import draft, extract
    from app.rules import analyze, check_draft, inbox_sort, load_config

    # Without app/llm/__init__.py these names would be submodules, not functions.
    if not (callable(extract) and callable(draft)):
        raise ImportError("app.llm does not export extract() and draft() yet")
    return SimpleNamespace(
        name="real",
        chats_dir=ROOT / "data" / "chats",
        config=load_config(ROOT / "config" / "rules.yaml"),
        parse_chat=parse_chat,
        append_message=append_message,
        extract=extract,
        analyze=analyze,
        draft=draft,
        check_draft=check_draft,
        inbox_sort=inbox_sort,
    )


# Sample fallback: only for building the page before the other parts exist.
_LINE = re.compile(r"^\[(cliente|libeen)\]\[([^\]]+)\]\[(.*)\]$")


def _sample_parse_chat(path: Path) -> dict:
    path = Path(path)
    messages = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        m = _LINE.match(line)
        if not m:
            raise ValueError(f"{path.name}: línea {i} con formato incorrecto")
        messages.append({"index": i, "sender": m[1], "ts": m[2], "text": m[3].replace("\\n", "\n")})
    return {"chat_id": path.stem, "name": path.stem.capitalize(), "messages": messages}


def _sample_append_message(path: Path, sender: str, text: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M")
    with Path(path).open("a", encoding="utf-8") as f:
        f.write(f"[{sender}][{ts}][{text.replace(chr(10), chr(92) + 'n')}]\n")


def sample_pipeline(data_dir: Path | None = None) -> SimpleNamespace:
    sample = json.loads((ROOT / "samples" / "laura.json").read_text(encoding="utf-8"))
    chats_dir = Path(data_dir or ROOT / "data") / "sample_chats"
    chats_dir.mkdir(parents=True, exist_ok=True)
    chat_file = chats_dir / "laura.txt"
    if not chat_file.exists():
        chat_file.write_text("\n".join(sample["chat_file"]) + "\n", encoding="utf-8")
    fit_order = {"fits": 0, "needs_data": 1, "no_fit": 2}

    return SimpleNamespace(
        name="sample",
        chats_dir=chats_dir,
        config={},
        parse_chat=_sample_parse_chat,
        append_message=_sample_append_message,
        extract=lambda chat: sample["extraction"],
        analyze=lambda extraction, config: sample["analysis"],
        draft=lambda chat, analysis, config: sample["draft"],
        check_draft=lambda draft, analysis, config: sample["checks"],
        inbox_sort=lambda items: sorted(
            items,
            key=lambda x: (x["last_sender"] != "cliente", fit_order.get(x["fit"], 9), -x["waiting_minutes"]),
        ),
    )


def default_pipeline() -> SimpleNamespace:
    if os.getenv("LIBEEN_SAMPLE") == "1":
        return sample_pipeline()
    try:
        return real_pipeline()
    except ImportError as e:
        print(f"[server] Modo muestra: falta una pieza ({e}). Sirviendo samples/laura.json.")
        return sample_pipeline()


# --- App -------------------------------------------------------------------


class Approval(BaseModel):
    text: str
    edited: bool = False


def create_app(pipeline: SimpleNamespace | None = None, log_path: Path | None = None) -> FastAPI:
    p = pipeline or default_pipeline()
    log_file = Path(log_path or ROOT / "data" / "log.jsonl")
    app = FastAPI(title="Libeen advisor copilot")
    app.state.pipeline = p

    def chat_path(chat_id: str) -> Path:
        path = Path(p.chats_dir) / f"{chat_id}.txt"
        if not CHAT_ID.match(chat_id) or not path.is_file():
            raise HTTPException(404, f"No existe el chat '{chat_id}'")
        return path

    def analyzed(path: Path) -> tuple[Any, dict, dict]:
        chat = p.parse_chat(path)
        extraction = to_jsonable(p.extract(chat))
        analysis = to_jsonable(p.analyze(extraction, p.config))
        return chat, extraction, analysis

    def full(chat_id: str) -> dict:
        path = chat_path(chat_id)
        try:
            chat, extraction, analysis = analyzed(path)
            messages = to_jsonable(chat)["messages"]
            if messages and messages[-1]["sender"] == "libeen":
                draft, checks = None, []  # nothing to answer: no draft call is spent (CONTRACTS 11.9)
            else:
                draft = to_jsonable(p.draft(chat, analysis, p.config))
                checks = p.check_draft(draft, analysis, p.config)
        except Exception as e:  # say it on the page instead of a blank 500
            raise HTTPException(500, f"No se pudo preparar el chat: {e}") from e
        return to_jsonable({"chat": chat, "extraction": extraction, "analysis": analysis, "draft": draft, "checks": checks})

    def list_item(path: Path, now: datetime) -> dict:
        """Inbox fields that only need the chat file: cheap, no model call."""
        chat = to_jsonable(p.parse_chat(path))
        last = chat["messages"][-1] if chat["messages"] else None
        waiting = 0
        if last:
            waiting = max(0, int((now - datetime.fromisoformat(str(last["ts"]))).total_seconds() // 60))
        return {"chat_id": chat["chat_id"], "name": chat["name"], "fit": None, "reasons": [],
                "waiting_minutes": waiting, "last_sender": last["sender"] if last else None}

    def inbox_item(path: Path, now: datetime) -> dict:
        """One full inbox row: runs extract and analyze (never draft)."""
        try:
            item = list_item(path, now)
            _, _, analysis = analyzed(path)
        except Exception as e:  # one broken chat must not hide the others
            return {"chat_id": path.stem, "name": path.stem.capitalize(), "fit": "error",
                    "reasons": [f"Error: {e}"], "waiting_minutes": 0, "last_sender": None}
        return item | {"fit": analysis["fit"], "reasons": analysis.get("reasons", [])}

    def chat_files() -> list[Path]:
        return sorted(Path(p.chats_dir).glob("*.txt"))

    @app.get("/")
    def page():
        return FileResponse(ROOT / "web" / "index.html")

    @app.get("/api/mode")
    def mode():
        # Not in CONTRACTS: lets the page say when it shows sample data.
        return {"mode": p.name}

    @app.get("/api/inbox")
    def inbox():
        now = datetime.now()
        return to_jsonable(p.inbox_sort([inbox_item(path, now) for path in chat_files()]))

    # Not in CONTRACTS: the page loads the list first, then one row at a time,
    # so a cold cache does not block it for minutes.
    @app.get("/api/inbox-list")
    def inbox_list():
        now = datetime.now()
        items = []
        for path in chat_files():
            try:
                items.append(list_item(path, now))
            except Exception as e:
                items.append({"chat_id": path.stem, "name": path.stem.capitalize(), "fit": "error",
                              "reasons": [f"Error: {e}"], "waiting_minutes": 0, "last_sender": None})
        return to_jsonable(p.inbox_sort(items))

    @app.get("/api/inbox/{chat_id}")
    def inbox_row(chat_id: str):
        return to_jsonable(inbox_item(chat_path(chat_id), datetime.now()))

    @app.get("/api/chats/{chat_id}")
    def chat_detail(chat_id: str):
        return full(chat_id)

    @app.post("/api/chats/{chat_id}/approve")
    def approve(chat_id: str, body: Approval):
        text = body.text.strip()
        if not text:
            raise HTTPException(400, "El texto está vacío")
        current = full(chat_id)  # read the decision before the chat file changes
        analysis = current["analysis"]
        checks_failed = sent_text_checks_failed(text, current["draft"], current["checks"], analysis)
        p.append_message(chat_path(chat_id), "libeen", text)  # failed checks warn, never block
        line = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "chat_id": chat_id,
            "reply_kind": analysis["reply_kind"],
            "edited": body.edited,
            "checks_failed": checks_failed,
            "text": text,
        }
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        return {"ok": True, "checks_failed": checks_failed}

    def sent_text_checks_failed(text: str, draft: dict, draft_checks: list, analysis: dict) -> list[str]:
        """Names of the failed checks on the text actually sent.

        The sent text is wrapped as one block with no key spans, so only the
        text checks apply. When it is the proposal unchanged, the proposal's
        own span and disclaimer results still count.
        """
        sent = {"reply_kind": analysis["reply_kind"], "blocks": [{"label": "Enviado", "text": text}], "key_spans": []}
        failed = [c["name"] for c in to_jsonable(p.check_draft(sent, analysis, p.config))
                  if c["name"] in SENT_TEXT_CHECKS and not c["ok"]]
        proposal = "\n\n".join(b["text"] for b in (draft or {}).get("blocks") or []).strip()
        if text == proposal:
            failed += [c["name"] for c in draft_checks if c["name"] not in SENT_TEXT_CHECKS and not c["ok"]]
        return failed

    return app


app = create_app()
