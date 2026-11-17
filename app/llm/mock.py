"""MOCK MODE: what `extract` and `draft` return when there is no ANTHROPIC_API_KEY.

This is the one place where the model is faked. With a key, these answers are never used:
the real calls live in `extract.py` and `draft.py` (through `client.call_model`).

Fixed answers exist for the three chats of the test (laura, javier, rosa). Any other chat
gets a placeholder clearly marked "Modo simulado".
Mock extractions go through the same quote check as real ones.
"""

MOCK_NOTE = "Modo simulado"


def _f(value, status, quotes=(), note=""):
    return {"value": value, "status": status, "quotes": [{"msg": m, "text": t} for m, t in quotes], "note": note}


_MISSING = _f(None, "missing")

EXTRACTIONS = {
    "laura": {
        "fields": {
            "zona": _f("Valencia", "ok", [(0, "Valencia")]),
            "plazo": _f({"text": "antes del verano", "weeks": 30}, "ok", [(0, "antes del verano")]),
            "compradores": _f(2, "ok", [(0, "mi pareja y yo")]),
            "edad": _f([31, 34], "ok", [(2, "31"), (2, "34")]),
            "empleo": _MISSING,
            "ingresos": _f({"min": 3800, "max": 3800}, "ok", [(2, "3.800 € netos")]),
            "deudas": _f(250, "ok", [(3, "préstamo del coche de 250 € al mes")]),
            "ahorro": _f(18000, "ok", [(2, "18.000")]),
        },
        "income_net_of_debts": "unknown",
        "open_questions": [{"msg": 3, "text": "no sé si cuenta"}],
        "special_requests": [],
    },
    "javier": {
        "fields": {
            "zona": _f("Madrid o alrededores", "ok", [(0, "madrid o alrededores")]),
            "plazo": _MISSING,
            "compradores": _f(1, "ok", [(2, "solo")]),
            "edad": _MISSING,
            "empleo": _f(["autónomo"], "ok", [(2, "autonomo")]),
            "ingresos": _f({"min": 2000, "max": 3000}, "doubtful", [(2, "entre 2000 y 3000")], "Varía según el mes"),
            "deudas": _MISSING,
            "ahorro": _MISSING,
        },
        "income_net_of_debts": "unknown",
        "open_questions": [{"msg": 4, "text": "y esto es fiable? no sera una estafa no"}],
        "special_requests": [],
    },
    "rosa": {
        "fields": {
            "zona": _MISSING,
            "plazo": _f({"text": "en dos semanas", "weeks": 2}, "ok", [(0, "en dos semanas")]),
            "compradores": _f(2, "ok", [(0, "mi marido y yo")]),
            "edad": _f([67], "doubtful", [(0, "67 años")], "Falta una edad"),
            "empleo": _f(["jubilado", "media jornada"], "ok", [(0, "jubilado"), (0, "media jornada")]),
            "ingresos": _f({"min": 1400, "max": 1400}, "ok", [(0, "1.400 €")]),
            "deudas": _MISSING,
            "ahorro": _f(0, "ok", [(0, "Ahorros no tenemos")]),
        },
        "income_net_of_debts": "unknown",
        "open_questions": [{"msg": 1, "text": "¿nos alquiláis algo solo de alquiler?"}],
        "special_requests": [
            {"msg": 1, "kind": "rent_only", "text": "nos alquiláis algo solo de alquiler"},
            {"msg": 2, "kind": "written_approval", "text": "os pida por escrito que estamos aprobados"},
        ],
    },
}

DRAFTS = {
    "laura": {
        "reply_kind": "offer",
        "blocks": [
            {"label": "Responde a su pregunta", "text": "¡Hola, Laura! Gracias por los datos. El préstamo del coche sí cuenta, pero en vuestro caso no cambia el resultado."},
            {"label": "Oferta con simulación", "text": "Con lo que nos contáis, podríais optar a una casa de hasta unos 204.500 € en Valencia. La cuota sería de unos 1.317 € al mes y, de ahí, unos 395 € irían a vuestra entrada. Son números orientativos, no una oferta."},
            {"label": "Siguiente paso", "text": "¿Os va bien una llamada esta semana para verlo con calma?"},
        ],
        "key_spans": [
            {"block": 0, "text": "no cambia el resultado", "ref": "decision"},
            {"block": 1, "text": "204.500 €", "ref": "sim.max_price"},
            {"block": 1, "text": "1.317 €", "ref": "sim.monthly_payment"},
            {"block": 1, "text": "395 €", "ref": "sim.monthly_savings"},
        ],
    },
    "javier": {
        "reply_kind": "ask_info",
        "blocks": [
            {"label": "Responde a su pregunta", "text": "¡Hola, Javier! Es normal preguntarlo. Libeen compra la casa que tú eliges y te la alquila con opción a compra, con el precio fijado por contrato desde el primer día. Operamos a través de una SOCIMI regulada por la CNMV."},
            {"label": "Pide lo que falta", "text": "Para decirte hasta qué precio podrías llegar nos falta saber cuánto tienes ahorrado para la entrada y si pagas alguna deuda al mes (préstamos, tarjetas)."},
            {"label": "Siguiente paso", "text": "Con esos datos te preparamos una simulación orientativa. ¿Cuándo te gustaría mudarte?"},
        ],
        "key_spans": [
            {"block": 1, "text": "nos falta saber", "ref": "decision"},
        ],
    },
    "rosa": {
        "reply_kind": "decline",
        "blocks": [
            {"label": "Responde a sus peticiones", "text": "Buenos días, Rosa. Gracias por contarnos vuestra situación. No ofrecemos alquiler sin opción a compra, y no podemos confirmar nada por escrito antes del análisis completo."},
            {"label": "Explica por qué no encaja", "text": "Ahora mismo no podemos ofreceros una casa: necesitamos unas 4 semanas para hacer la compra, unos ingresos de al menos 2.200 € al mes y unos ahorros de 15.000 € para la entrada."},
            {"label": "Siguiente paso", "text": "Si más adelante cambian vuestro plazo, vuestros ingresos o vuestros ahorros, escribidnos y lo volvemos a mirar con gusto."},
        ],
        "key_spans": [
            {"block": 1, "text": "no podemos ofreceros una casa", "ref": "decision"},
            {"block": 1, "text": "2.200 €", "ref": "rule.min_income"},
            {"block": 1, "text": "15.000 €", "ref": "rule.min_savings"},
            {"block": 1, "text": "4 semanas", "ref": "rule.min_weeks"},
        ],
    },
}


def extraction(chat_id: str) -> dict:
    if chat_id in EXTRACTIONS:
        return EXTRACTIONS[chat_id]
    note_field = _f(None, "missing", note=MOCK_NOTE)
    return {
        "fields": {k: note_field for k in ["zona", "plazo", "compradores", "edad", "empleo", "ingresos", "deudas", "ahorro"]},
        "income_net_of_debts": "unknown",
        "open_questions": [],
        "special_requests": [],
        "mock_placeholder": True,
    }


def draft(chat_id: str, reply_kind: str) -> dict:
    fixed = DRAFTS.get(chat_id)
    if fixed and fixed["reply_kind"] == reply_kind:
        return fixed
    return {
        "reply_kind": reply_kind,
        "blocks": [{"label": MOCK_NOTE, "text": "Modo simulado: sin ANTHROPIC_API_KEY no se genera respuesta para este chat."}],
        "key_spans": [],
        "mock_placeholder": True,
    }
