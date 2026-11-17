"""extract(chat) -> Extraction (CONTRACTS section 4)."""

import re

from app.llm import cache, client, mock, prompts, schemas, settings

NO_QUOTE_NOTE = "Sin cita en el chat"

_ATTACHMENT = re.compile(r"\[(audio|imagen|documento)(?:\s+([\d:]+))?\]", re.IGNORECASE)
_ATTACHMENT_KIND = {"audio": "audio", "imagen": "image", "documento": "document"}
_ATTACHMENT_LABEL = {"audio": "Audio", "imagen": "Imagen", "documento": "Documento"}


def extract(chat) -> dict:
    chat_id, name, messages = cache.chat_parts(chat)
    chat_hash = cache.chat_hash(messages)

    if settings.live():
        key = cache.digest(settings.model(), prompts.EXTRACT_SYSTEM, messages)
        raw = cache.load(chat_id, "extraction", key)
        if raw is None:
            raw = client.call_model(
                prompts.EXTRACT_SYSTEM, prompts.extract_user(name, messages), schemas.EXTRACTION, max_tokens=16000
            )
            cache.save(chat_id, "extraction", key, raw, chat=chat_hash)
        return finish(chat_id, raw, messages)

    # No model call possible: a recorded real answer for this exact chat, else the mock.
    raw = cache.load_recorded(chat_id, "extraction", chat_hash)
    if raw is not None:
        return dict(finish(chat_id, raw, messages), recorded=True)
    return finish(chat_id, mock.extraction(chat_id), messages)


def finish(chat_id: str, raw: dict, messages: list[dict]) -> dict:
    """Turn a model (or mock) answer into a contract Extraction, checking every quote against the chat."""
    raw = schemas.to_contract(raw)
    fields = {key: check_field(raw["fields"][key], messages) for key in schemas.FIELD_KEYS}

    result = {
        "chat_id": chat_id,
        "fields": fields,
        "income_net_of_debts": raw.get("income_net_of_debts", "unknown"),
        "open_questions": [q for q in raw.get("open_questions", []) if _valid_msg(q.get("msg"), messages)],
        "attachments": find_attachments(messages),
        "special_requests": [r for r in raw.get("special_requests", []) if _valid_msg(r.get("msg"), messages)],
    }
    if raw.get("mock_placeholder"):
        result["mock_placeholder"] = True
    return result


def check_field(field: dict, messages: list[dict]) -> dict:
    """Quote check from CONTRACTS section 4, plus value/status consistency."""
    value = field.get("value")
    status = field.get("status", "missing")
    note = field.get("note", "") or ""
    quotes = [q for q in field.get("quotes", []) if quote_is_valid(q, messages)]

    if value is None:
        # Said but not usable as a value (e.g. gross yearly income): doubtful with its quote.
        if status == "doubtful" and quotes:
            return {"value": None, "status": "doubtful", "quotes": quotes, "note": note}
        return {"value": None, "status": "missing", "quotes": [], "note": note if status == "missing" else ""}
    if status == "missing":
        status = "doubtful"
    if not quotes:
        status, note = "doubtful", NO_QUOTE_NOTE
    if status == "ok":
        note = ""
    return {"value": value, "status": status, "quotes": quotes, "note": note}


def quote_is_valid(quote: dict, messages: list[dict]) -> bool:
    """A quote counts only if it is a non-empty exact substring of a client message."""
    msg, text = quote.get("msg"), quote.get("text") or ""
    if not text.strip() or not _valid_msg(msg, messages):
        return False
    message = messages[msg]
    return message["sender"] == "cliente" and text in message["text"]


def find_attachments(messages: list[dict]) -> list[dict]:
    """Attachments are in the chat text, so code finds them; no model needed."""
    found = []
    for m in messages:
        for match in _ATTACHMENT.finditer(m["text"]):
            word, length = match.group(1).lower(), match.group(2)
            label = _ATTACHMENT_LABEL[word] + (f" de {length}" if length else "")
            found.append({"msg": m["index"], "kind": _ATTACHMENT_KIND[word], "label": label})
    return found


def _valid_msg(msg, messages) -> bool:
    return isinstance(msg, int) and 0 <= msg < len(messages)
