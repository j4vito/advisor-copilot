"""draft(chat, analysis, config) -> Draft (CONTRACTS sections 6 and 11.8)."""

from app.llm import cache, client, mock, prompts, schemas, settings


def draft(chat, analysis: dict, config: dict) -> dict:
    chat_id, name, messages = cache.chat_parts(chat)
    reply_kind = analysis["reply_kind"]
    chat_hash = cache.chat_hash(messages)

    if settings.live():
        system = prompts.draft_system(config)
        user = prompts.draft_user(name, messages, analysis, config)
        key = cache.digest(settings.model(), system, user)
        raw = cache.load(chat_id, "draft", key)
        if raw is None:
            raw = client.call_model(system, user, schemas.DRAFT, max_tokens=16000)
            cache.save(chat_id, "draft", key, raw, chat=chat_hash, reply_kind=reply_kind)
        return _finish(raw, reply_kind)

    # No model call possible: a recorded real answer for this chat and kind, else the mock.
    raw = cache.load_recorded(chat_id, "draft", chat_hash, reply_kind)
    if raw is not None:
        return dict(_finish(raw, reply_kind), recorded=True)
    return mock.draft(chat_id, reply_kind)


def _finish(raw: dict, reply_kind: str) -> dict:
    # The kind always comes from the rules, whatever the model wrote.
    blocks = raw["blocks"]
    return {"reply_kind": reply_kind, "blocks": blocks, "key_spans": fix_span_blocks(raw["key_spans"], blocks)}


def fix_span_blocks(spans: list[dict], blocks: list[dict]) -> list[dict]:
    """The model sometimes points a span at the wrong block, or changes the capital letter at
    the start of a sentence. If the text appears in exactly one block (ignoring case), point
    the span there and copy the text exactly from the block. Anything else is left as is,
    for check_draft to report."""
    fixed = []
    for span in spans:
        b, text = span.get("block"), span.get("text") or ""
        in_stated = isinstance(b, int) and 0 <= b < len(blocks) and text in blocks[b]["text"]
        if text and not in_stated:
            hits = [(i, block["text"].lower().find(text.lower())) for i, block in enumerate(blocks)]
            hits = [(i, pos) for i, pos in hits if pos >= 0]
            if len(hits) == 1:
                i, pos = hits[0]
                span = dict(span, block=i, text=blocks[i]["text"][pos:pos + len(text)])
        fixed.append(span)
    return fixed


def reply_text(d: dict) -> str:
    """The text that would be sent: blocks joined by blank lines."""
    return "\n\n".join(b["text"] for b in d["blocks"])
