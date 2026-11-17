"""Round 2: draft input (11.6-11.8), recorded answers (11.10), warm-up, offline fallbacks, evals."""

import copy
import json

import pytest

from app.llm import cache, client, draft, extract, mock, prompts, settings, warm
from app.llm.client import LLMError
from app.llm.client import call_model as real_call_model  # the original, before the fixture patches it
from app.rules import analyze, load_config
from evals import run as evals_run
from evals.samples import chat_from_lines, load_sample

SAMPLE = load_sample()
CONFIG = load_config()


def laura():
    return chat_from_lines("laura", SAMPLE["chat_file"])


def laura_analysis(**changes):
    return copy.deepcopy(dict(SAMPLE["analysis"], **changes))


def draft_answer():
    return {k: copy.deepcopy(SAMPLE["draft"][k]) for k in ("blocks", "key_spans")}


# ---- draft input -------------------------------------------------------------

def test_hidden_rows_and_advisor_reasons_never_reach_the_draft_model():
    analysis = laura_analysis(reasons=["Edad: lo decide el asesor"])
    analysis["facts"]["field.edad"] = "34"
    ctx = prompts.draft_context("Laura", analysis, CONFIG)
    assert "Edad" not in [r["label"] for r in ctx["ficha"]]
    assert "field.edad" not in ctx["facts"]
    assert "reasons" not in ctx
    user = prompts.draft_user("Laura", laura()["messages"], analysis, CONFIG)
    assert "Lo decide el asesor" not in user and "31 y 34" not in user


def test_offer_gets_only_offer_facts_and_facts_of_clear_fields():
    ctx = prompts.draft_context("Laura", laura_analysis(), CONFIG)
    # net income is doubtful in the sample, so its number is not passed as a fact
    assert set(ctx["facts"]) == {
        "sim.max_price", "sim.monthly_payment", "sim.monthly_savings",
        "field.ingresos", "field.deudas", "field.ahorro",
    }
    assert "ask_for" not in ctx and "client_reasons" not in ctx


def test_decline_gets_client_reasons_and_only_their_facts_and_no_ficha():
    analysis = laura_analysis(
        reply_kind="decline", simulation=None,
        client_reasons=[{"key": "ahorro", "text": "Ahorro de 0 €, mínimo 15.000 €", "refs": ["field.ahorro", "rule.min_savings"]}],
    )
    ctx = prompts.draft_context("Laura", analysis, CONFIG)
    assert ctx["client_reasons"] == ["Ahorro de 0 €, mínimo 15.000 €"]
    assert set(ctx["facts"]) == {"field.ahorro", "rule.min_savings"}
    assert "ficha" not in ctx


def test_ask_info_gets_ask_for_in_order_and_no_simulation_numbers():
    analysis = laura_analysis(reply_kind="ask_info", ask_for=["empleo", "zona"])
    ctx = prompts.draft_context("Laura", analysis, CONFIG)
    assert [a["label"] for a in ctx["ask_for"]] == ["Empleo", "Zona"]
    assert not any(k.startswith("sim.") for k in ctx["facts"])


def test_ask_for_never_includes_a_hidden_field():
    analysis = laura_analysis(reply_kind="ask_info", ask_for=["edad", "empleo"])
    assert [a["label"] for a in prompts.draft_context("Laura", analysis, CONFIG)["ask_for"]] == ["Empleo"]


def test_draft_system_prompt_carries_config_limits_and_internal_terms():
    system = prompts.draft_system(CONFIG)
    assert f"under {CONFIG['draft']['max_chars']} characters" in system
    for word in CONFIG["draft"]["internal_terms"] + CONFIG["draft"]["banned_words"]:
        assert f'"{word}"' in system


# ---- recorded answers ----------------------------------------------------------

def record_laura(fake_model):
    fake_model.answers["extraction"] = copy.deepcopy(mock.EXTRACTIONS["laura"])
    fake_model.answers["draft"] = draft_answer()
    real_extraction = extract(laura())
    real_draft = draft(laura(), SAMPLE["analysis"], CONFIG)
    return real_extraction, real_draft


def go_offline(monkeypatch):
    monkeypatch.setenv("LIBEEN_MOCK", "1")


def test_offline_uses_recorded_answer_for_the_same_chat(fake_model, monkeypatch):
    real_extraction, real_draft = record_laura(fake_model)
    go_offline(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_MODEL", "some-other-model")  # model id is ignored for the lookup
    calls = len(fake_model.calls)
    assert extract(laura()) == dict(real_extraction, recorded=True)
    assert draft(laura(), SAMPLE["analysis"], CONFIG) == dict(real_draft, recorded=True)
    assert len(fake_model.calls) == calls


def test_recorded_answer_is_not_used_when_the_chat_changed(fake_model, monkeypatch):
    record_laura(fake_model)
    go_offline(monkeypatch)
    chat = laura()
    chat["messages"][3]["text"] += " Gracias."
    out = extract(chat)
    assert "recorded" not in out  # falls back to the fixed mock answer for laura
    assert out["fields"]["ahorro"]["value"] == 18000


def test_recorded_draft_must_match_the_reply_kind(fake_model, monkeypatch):
    record_laura(fake_model)
    go_offline(monkeypatch)
    out = draft(laura(), laura_analysis(reply_kind="decline"), CONFIG)
    assert out.get("mock_placeholder") and "recorded" not in out


def test_cache_entry_has_chat_hash_and_no_secret(fake_model):
    record_laura(fake_model)
    data = json.loads((settings.CACHE_DIR / "laura.json").read_text())
    assert data["draft"]["reply_kind"] == "offer"
    assert data["extraction"]["chat"] == data["draft"]["chat"] == cache.chat_hash(laura()["messages"])
    assert "sk-test" not in json.dumps(data)


def test_committed_cache_has_no_secrets():
    for path in (settings.ROOT / "data" / "cache").glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "sk-ant" not in text and "api_key" not in text.lower(), path.name


# ---- missing package, bad key ---------------------------------------------------

def test_key_without_package_behaves_like_no_key_and_warns_once(monkeypatch, capsys):
    monkeypatch.delenv("LIBEEN_MOCK", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-secret-key")
    monkeypatch.setattr(settings, "_package_available", lambda: False)
    monkeypatch.setattr(settings, "_warned_no_package", False)
    assert settings.live() is False
    assert settings.live() is False
    err = capsys.readouterr().err
    assert err.count("anthropic") == 1 and "sk-test" not in err
    assert extract(laura())["fields"]["ahorro"]["value"] == 18000  # mock answer, no call


def test_failed_api_call_raises_a_clear_error(monkeypatch):
    anthropic = pytest.importorskip("anthropic")
    import httpx

    class FakeMessages:
        def create(self, **kwargs):
            response = httpx.Response(401, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
            raise anthropic.AuthenticationError("invalid x-api-key", response=response, body=None)

    class FakeClient:
        def __init__(self, api_key):
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic, "Anthropic", FakeClient)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-secret-key")
    with pytest.raises(LLMError, match="API key no es válida") as info:
        real_call_model("s", "u", {}, 10)
    assert "sk-test" not in str(info.value)


# ---- warm-up ---------------------------------------------------------------------

def test_warm_records_every_chat_and_no_draft_when_libeen_wrote_last(fake_model, monkeypatch, tmp_path, capsys):
    chats = tmp_path / "chats"
    chats.mkdir()
    lines = SAMPLE["chat_file"]
    (chats / "laura.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (chats / "lauritas.txt").write_text(
        "\n".join(lines + ["[libeen][2026-11-14T10:20][Gracias, os escribimos mañana.]"]) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(warm, "CHATS_DIR", chats)
    fake_model.answers["extraction"] = copy.deepcopy(mock.EXTRACTIONS["laura"])
    fake_model.answers["draft"] = draft_answer()

    assert warm.main(["--jobs", "1"]) == 0
    assert set(json.loads((settings.CACHE_DIR / "laura.json").read_text())) == {"extraction", "draft"}
    assert set(json.loads((settings.CACHE_DIR / "lauritas.json").read_text())) == {"extraction"}
    assert "2/2]" in capsys.readouterr().out


def test_warm_refuses_without_a_key():
    assert warm.main([]) == 2


# ---- evals -------------------------------------------------------------------------

def test_evals_check_must_not_contain_case_insensitive():
    expected = dict(SAMPLE["expected"], must_not_contain=["VALENCIA", "hipoteca"])
    case = evals_run.run_case(laura(), expected, evals_run.load_rules())
    assert case.total["must_not_contain"] == 2 and case.tally["must_not_contain"] == 1
    assert any("VALENCIA" in f for f in case.failures)
    assert case.total["max_chars"] == 1 and case.tally["max_chars"] == 1


def test_evals_make_no_draft_when_expected_says_so(monkeypatch):
    called = []
    monkeypatch.setattr("app.llm.draft", lambda *a: called.append(a))
    chat = laura()
    chat["messages"].append({"index": 4, "sender": "libeen", "ts": "2026-11-14T10:20", "text": "Gracias."})
    case = evals_run.run_case(chat, dict(SAMPLE["expected"], no_draft=True), evals_run.load_rules())
    assert not called and not case.failures and case.total["no_draft"] == 1


def test_evals_fresh_refuses_without_a_key():
    assert evals_run.main(["--fresh"]) == 2


def test_analysis_of_recorded_extraction_still_works(fake_model, monkeypatch):
    record_laura(fake_model)
    go_offline(monkeypatch)
    assert analyze(extract(laura()), CONFIG)["fit"] == "fits"
