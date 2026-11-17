import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.rules import load_config  # noqa: E402


@pytest.fixture
def config():
    return load_config(ROOT / "config" / "rules.yaml")


@pytest.fixture
def sample():
    return json.loads((ROOT / "samples" / "laura.json").read_text(encoding="utf-8"))


def field(value, status="ok", quotes=None, note=""):
    if value is None:
        return {"value": None, "status": "missing", "quotes": [], "note": ""}
    return {"value": value, "status": status, "quotes": quotes or [{"msg": 0, "text": "x"}], "note": note}


def make_extraction(chat_id="test", net="unknown", attachments=None, special=None, **values):
    """Small extraction: every field missing unless given. Values may be (value, status) tuples."""
    keys = ["zona", "plazo", "compradores", "edad", "empleo", "ingresos", "deudas", "ahorro"]
    fields = {}
    for k in keys:
        v = values.get(k)
        fields[k] = field(*v) if isinstance(v, tuple) else field(v)
    return {
        "chat_id": chat_id,
        "fields": fields,
        "income_net_of_debts": net,
        "open_questions": [],
        "attachments": attachments or [],
        "special_requests": special or [],
    }


@pytest.fixture
def make():
    return make_extraction


@pytest.fixture
def deep():
    return copy.deepcopy
