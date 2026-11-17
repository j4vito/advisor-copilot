"""JSON schemas the model is forced to answer with (structured outputs).

The extraction schema is looser than the contract on purpose. A schema with a typed value
per field was rejected by the API ("compiled grammar is too large"), so all eight fields
share one definition whose `value` is a string, a number or a list. `to_contract` then
checks and converts each value to the type in CONTRACTS section 4, in code.
`plazo` and `ingresos` hold a scalar; their second part goes in `plazo_weeks` / `ingresos_max`.
"""

FIELD_KEYS = ["zona", "plazo", "compradores", "edad", "empleo", "ingresos", "deudas", "ahorro"]


def _obj(properties: dict) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


EXTRACTION = _obj({
    "fields": _obj({key: {"$ref": "#/$defs/field"} for key in FIELD_KEYS}),
    "plazo_weeks": {"type": ["integer", "null"]},
    "ingresos_max": {"type": ["number", "null"]},
    "income_net_of_debts": {"type": "string", "enum": ["yes", "no", "unknown"]},
    "open_questions": {"type": "array", "items": {"$ref": "#/$defs/quote"}},
    "special_requests": {
        "type": "array",
        "items": _obj({
            "msg": {"type": "integer"},
            "kind": {"type": "string", "enum": ["rent_only", "written_approval", "other"]},
            "text": {"type": "string"},
        }),
    },
})
EXTRACTION["$defs"] = {
    "quote": _obj({"msg": {"type": "integer"}, "text": {"type": "string"}}),
    "field": _obj({
        "value": {"type": ["string", "number", "array", "null"], "items": {"type": ["string", "number"]}},
        "status": {"type": "string", "enum": ["ok", "doubtful", "missing"]},
        "quotes": {"type": "array", "items": {"$ref": "#/$defs/quote"}},
        "note": {"type": "string"},
    }),
}

DRAFT = _obj({
    "blocks": {"type": "array", "items": _obj({"label": {"type": "string"}, "text": {"type": "string"}})},
    "key_spans": {
        "type": "array",
        "items": _obj({"block": {"type": "integer"}, "text": {"type": "string"}, "ref": {"type": "string"}}),
    },
})


def _number(v):
    """A number, or None. Accepts Spanish-style strings like "18.000"."""
    if isinstance(v, bool):
        return None
    if isinstance(v, str):
        v = v.replace("€", "").replace(".", "").replace(",", ".").strip()
        try:
            v = float(v)
        except ValueError:
            return None
    if isinstance(v, (int, float)):
        return int(v) if float(v).is_integer() else v
    return None


def _as_list(v):
    return v if isinstance(v, list) else [v]


def coerce(key: str, value, raw: dict):
    """Model value -> contract value for one field. None when it cannot be read."""
    if value is None or value == "" or value == []:
        return None
    if key == "zona":
        return value if isinstance(value, str) else None
    if key == "plazo":
        if isinstance(value, dict):  # already contract shape (mock)
            return value
        return {"text": str(value), "weeks": _number(raw.get("plazo_weeks"))} if isinstance(value, str) else None
    if key == "compradores":
        n = _number(value)
        return n if isinstance(n, int) and n > 0 else None
    if key == "edad":
        ages = [_number(a) for a in _as_list(value)]
        return ages if all(isinstance(a, int) for a in ages) else None
    if key == "empleo":
        jobs = _as_list(value)
        return jobs if all(isinstance(j, str) and j for j in jobs) else None
    if key == "ingresos":
        if isinstance(value, dict):  # already contract shape (mock)
            return value
        low = _number(value)
        if low is None:
            return None
        high = _number(raw.get("ingresos_max"))
        high = low if high is None else high
        return {"min": min(low, high), "max": max(low, high)}
    return _number(value)  # deudas, ahorro


def to_contract(raw: dict) -> dict:
    """Model answer -> contract shape. Mock answers are already in contract shape and pass through."""
    fields = {}
    for key in FIELD_KEYS:
        field = dict(raw["fields"][key])
        field["value"] = coerce(key, field.get("value"), raw)
        fields[key] = field
    return dict(raw, fields=fields)
