import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.chats import Chat, ChatFormatError, append_message, parse_chat

ROOT = Path(__file__).resolve().parents[2]
CHATS = sorted((ROOT / "data" / "chats").glob("*.txt"))
FIELDS = ["zona", "plazo", "compradores", "edad", "empleo", "ingresos", "deudas", "ahorro"]


def write(tmp_path, *lines, name="ana.txt"):
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_parse_basic(tmp_path):
    path = write(
        tmp_path,
        "[cliente][2026-11-14T10:02][Hola]",
        "[libeen][2026-11-14T10:05][¡Hola! ¿Qué tal?]",
    )
    chat = parse_chat(path)
    assert isinstance(chat, Chat)
    assert chat.chat_id == "ana" and chat.name == "Ana"
    assert chat.messages == [
        {"index": 0, "sender": "cliente", "ts": "2026-11-14T10:02", "text": "Hola"},
        {"index": 1, "sender": "libeen", "ts": "2026-11-14T10:05", "text": "¡Hola! ¿Qué tal?"},
    ]
    assert chat["messages"] is chat.messages
    assert chat.to_dict()["chat_id"] == "ana"


def test_line_break_inside_message(tmp_path):
    chat = parse_chat(write(tmp_path, r"[cliente][2026-11-14T10:02][Hola\nSomos dos]"))
    assert chat.messages[0]["text"] == "Hola\nSomos dos"


def test_brackets_inside_message(tmp_path):
    chat = parse_chat(write(
        tmp_path,
        "[cliente][2026-11-14T10:33][[audio 1:12]]",
        "[cliente][2026-11-14T10:34][Somos 2 [mi hermana y yo] (sin deudas [ninguna])]",
        "[cliente][2026-11-14T10:35][]",
    ))
    assert [m["text"] for m in chat.messages] == [
        "[audio 1:12]",
        "Somos 2 [mi hermana y yo] (sin deudas [ninguna])",
        "",
    ]


def test_no_trailing_newline(tmp_path):
    path = tmp_path / "ana.txt"
    path.write_text("[cliente][2026-11-14T10:02][Hola]", encoding="utf-8")
    assert len(parse_chat(path).messages) == 1


@pytest.mark.parametrize("bad", [
    "[cliente][2026-11-14T10:02]Hola",          # message without brackets
    "[asesor][2026-11-14T10:02][Hola]",         # unknown sender
    "[cliente][2026-11-14T10:02][Hola] ",       # text after the last bracket
    "[cliente][ayer][Hola]",                    # bad timestamp
    "[cliente][2026-11-14 10:02][Hola]",        # space instead of T
    "",                                         # empty line in the middle
])
def test_bad_line_reports_line_number(tmp_path, bad):
    path = write(tmp_path, "[cliente][2026-11-14T10:02][Hola]", bad, "[libeen][2026-11-14T10:05][Adiós]")
    with pytest.raises(ChatFormatError, match="line 2"):
        parse_chat(path)


def test_append_then_parse(tmp_path):
    path = write(tmp_path, "[cliente][2026-11-14T10:02][Hola]")
    append_message(path, "libeen", "Línea uno\nLínea dos [con corchetes]")
    msgs = parse_chat(path).messages
    assert len(msgs) == 2
    assert msgs[1]["index"] == 1 and msgs[1]["sender"] == "libeen"
    assert msgs[1]["text"] == "Línea uno\nLínea dos [con corchetes]"
    assert path.read_text(encoding="utf-8").count("\n") == 2  # one physical line per message


def test_append_to_file_without_trailing_newline(tmp_path):
    path = tmp_path / "ana.txt"
    path.write_text("[cliente][2026-11-14T10:02][Hola]", encoding="utf-8")
    append_message(path, "cliente", "Otra")
    assert [m["text"] for m in parse_chat(path).messages] == ["Hola", "Otra"]


def test_append_rejects_unknown_sender(tmp_path):
    path = write(tmp_path, "[cliente][2026-11-14T10:02][Hola]")
    with pytest.raises(ValueError):
        append_message(path, "asesor", "Hola")


@pytest.mark.parametrize("path", CHATS, ids=lambda p: p.stem)
def test_data_chat_parses_and_has_expected(path):
    chat = parse_chat(path)
    assert chat.messages, "empty chat"
    expected = json.loads((ROOT / "data" / "expected" / f"{chat.chat_id}.json").read_text(encoding="utf-8"))
    assert list(expected["fields"]) == FIELDS
    for key, field in expected["fields"].items():
        assert field["status"] in ("ok", "doubtful", "missing"), key
        if field["status"] == "missing":
            assert "value" not in field, key
    assert expected["income_net_of_debts"] in ("yes", "no", "unknown")
    assert expected["net_income_status"] in ("ok", "doubtful", "missing", "fails")
    kind = {"fits": "offer", "needs_data": "ask_info", "no_fit": "decline"}[expected["fit"]]
    assert expected["reply_kind"] == kind
    assert expected["review"] in ("normal", "full")
    if expected["fit"] == "no_fit":
        assert expected["review"] == "full"
    # 11.6: any age above 60 means full review and no age in the reply
    ages = expected["fields"]["edad"].get("value") or []
    if ages and max(ages) > 60:
        assert expected["review"] == "full"
        assert "edad" in expected["must_not_contain"]
    # 11.1: an offer needs a clear net income; a straddling or near-miss range is not "fits"
    if expected["fit"] == "fits":
        assert expected["net_income_status"] in ("ok", "doubtful")
    # 11.11
    assert all(isinstance(s, str) and s for s in expected.get("must_not_contain", []))
    # 11.9: no draft exactly when Libeen wrote last
    assert expected.get("no_draft", False) == (chat.messages[-1]["sender"] == "libeen")
    assert set(expected) <= {"_note", "fields", "income_net_of_debts", "net_income_status", "fit",
                             "reply_kind", "review", "must_not_contain", "no_draft"}


def test_laura_matches_sample():
    sample = json.loads((ROOT / "samples" / "laura.json").read_text(encoding="utf-8"))
    chat = parse_chat(ROOT / "data" / "chats" / "laura.txt")
    assert [m["text"] for m in chat.messages] == [
        line.split("][", 2)[2][:-1] for line in sample["chat_file"]
    ]
    expected = json.loads((ROOT / "data" / "expected" / "laura.json").read_text(encoding="utf-8"))
    expected.pop("_note", None)
    assert expected == sample["expected"]


def test_gen_chat_is_deterministic(tmp_path):
    out = tmp_path / "chats"
    for _ in range(2):
        subprocess.run([sys.executable, str(ROOT / "tools" / "gen_chat.py"), "--seed", "7", "--out", str(out)], check=True)
    files = list(out.glob("*.txt"))
    assert len(files) == 1
    first = files[0].read_text(encoding="utf-8")
    parse_chat(files[0])
    assert (tmp_path / "expected" / f"{files[0].stem}.json").exists()
    subprocess.run([sys.executable, str(ROOT / "tools" / "gen_chat.py"), "--seed", "7", "--out", str(out)], check=True)
    assert files[0].read_text(encoding="utf-8") == first


def test_gen_chat_many_seeds_parse(tmp_path):
    sys.path.insert(0, str(ROOT / "tools"))
    import gen_chat
    rules = gen_chat.load_rules()
    for seed in range(50):
        chat_id, text, expected = gen_chat.generate(seed, rules)
        path = tmp_path / f"{chat_id}.txt"
        path.write_text(text, encoding="utf-8")
        assert parse_chat(path).messages
        assert list(expected["fields"]) == FIELDS


def test_gen_chat_net_status_rules():
    sys.path.insert(0, str(ROOT / "tools"))
    import gen_chat
    rules = {"min_net_income": 2200, "near_miss_pct": 0.03}
    ns = lambda *a: gen_chat.net_status(*a, rules)
    assert ns(None, 0, "unknown") == ("missing", False, False)
    assert ns(1500, None, "unknown") == ("fails", False, False)
    assert ns(3000, None, "unknown") == ("missing", False, False)
    assert ns(3800, 250, "unknown") == ("doubtful", False, True)    # laura
    assert ns(3800, 0, "unknown") == ("ok", False, True)
    assert ns(2600, 200, "yes") == ("ok", False, True)              # diego
    assert ns(2300, 200, "unknown") == ("doubtful", False, False)   # straddles: not clear (11.1)
    assert ns(2150, 0, "yes") == ("doubtful", True, False)          # near miss (11.2), alberto
    assert ns(2134, 0, "yes") == ("doubtful", True, False)          # 2200 * 0.97 = 2134
    assert ns(2133, 0, "yes") == ("fails", False, False)
    assert ns(2100, 0, "yes") == ("fails", False, False)


def test_gen_chat_below():
    sys.path.insert(0, str(ROOT / "tools"))
    import gen_chat
    rules = {"near_miss_pct": 0.03}
    assert gen_chat.below(15000, 15000, rules) == "ok"
    assert gen_chat.below(14900, 15000, rules) == "near"   # elena
    assert gen_chat.below(14550, 15000, rules) == "near"
    assert gen_chat.below(14500, 15000, rules) == "fails"


def test_gen_chat_reads_near_miss_from_config():
    sys.path.insert(0, str(ROOT / "tools"))
    import gen_chat
    rules = gen_chat.load_rules()
    assert {"near_miss_pct", "advisor_review_age", "min_net_income", "min_savings", "min_weeks_to_move"} <= set(rules)


def test_gen_chat_old_age_gives_full_review_and_must_not_contain():
    sys.path.insert(0, str(ROOT / "tools"))
    import gen_chat
    rules = gen_chat.load_rules()
    seen = 0
    for seed in range(200):
        _, _, expected = gen_chat.generate(seed, rules)
        ages = expected["fields"]["edad"].get("value") or []
        if ages and max(ages) > rules["advisor_review_age"]:
            seen += 1
            assert expected["review"] == "full"
            assert expected["must_not_contain"] == ["edad"]
        else:
            assert "must_not_contain" not in expected
    assert seen


def test_say_appends(tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT / "tools"))
    import say
    (tmp_path / "data" / "chats").mkdir(parents=True)
    path = write(tmp_path / "data" / "chats", "[cliente][2026-11-14T10:02][Hola]", name="ana.txt")
    monkeypatch.setattr(say, "ROOT", tmp_path)
    assert say.main(["ana", "cliente", "Vale, ¿cuándo hablamos?"]) == 0
    assert parse_chat(path).messages[-1]["text"] == "Vale, ¿cuándo hablamos?"
    assert say.main(["ana", "asesor", "x"]) == 2
    assert say.main(["nadie", "cliente", "x"]) == 1
