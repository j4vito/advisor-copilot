"""check_draft(draft, analysis, config) -> list of checks. CONTRACTS sections 6 and 11.6."""

import re

# Spanish numbers: 204.500 / 1.317 / 395 / 3,5. Dots group thousands, comma is decimal.
_NUMBER = re.compile(r"(?<![\d.,])\d{1,3}(?:\.\d{3})+(?:,\d+)?|(?<![\d.,])\d+(?:,\d+)?")


def _parse(token: str) -> float:
    return float(token.replace(".", "").replace(",", "."))


def numbers_in(text: str) -> list:
    return [(m.group(0), _parse(m.group(0))) for m in _NUMBER.finditer(text)]


def draft_text(draft: dict) -> str:
    return "\n\n".join(b.get("text", "") for b in draft.get("blocks") or [])


def _check(name, problems):
    return {"name": name, "ok": not problems, "detail": "; ".join(problems)}


def check_draft(draft: dict, analysis: dict, config: dict) -> list:
    text = draft_text(draft)
    facts = analysis.get("facts") or {}
    blocks = draft.get("blocks") or []

    banned = []
    for word in config["draft"]["banned_words"]:
        if re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text, flags=re.IGNORECASE):
            banned.append(f"Palabra no permitida: «{word}»")

    allowed = {value for fact in facts.values() for _, value in numbers_in(str(fact))}
    unknown = []
    for token, value in numbers_in(text):
        if value not in allowed and f"Número sin fuente: {token}" not in unknown:
            unknown.append(f"Número sin fuente: {token}")

    spans = []
    for i, span in enumerate(draft.get("key_spans") or []):
        b, span_text, ref = span.get("block"), span.get("text") or "", span.get("ref")
        if not isinstance(b, int) or not 0 <= b < len(blocks):
            spans.append(f"Marca {i}: bloque {b} no existe")
        elif not span_text or span_text not in (blocks[b].get("text") or ""):
            spans.append(f"Marca {i}: «{span_text}» no está en el bloque {b}")
        if ref != "decision" and ref not in facts:
            spans.append(f"Marca {i}: referencia «{ref}» desconocida")

    disclaimer = []
    word = config["draft"]["offer_disclaimer"]
    if draft.get("reply_kind") == "offer" and word.lower() not in text.lower():
        disclaimer.append(f"Falta el aviso «{word}»")

    internal = []
    for term in config["draft"]["internal_terms"]:
        if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, flags=re.IGNORECASE):
            internal.append(f"Término interno: «{term}»")

    too_long = []
    limit = config["draft"]["max_chars"]
    if len(text) > limit:
        too_long.append(f"{len(text)} caracteres, máximo {limit}")

    return [
        _check("banned_words", banned),
        _check("numbers_in_facts", unknown),
        _check("key_spans_valid", spans),
        _check("offer_disclaimer", disclaimer),
        _check("internal_terms", internal),
        _check("max_chars", too_long),
    ]
