import json

import pytest
from fastapi.testclient import TestClient

from app.rules import check_draft, load_config
from app.server import ROOT, create_app, sample_pipeline


@pytest.fixture
def env(tmp_path):
    pipeline = sample_pipeline(tmp_path)
    log = tmp_path / "log.jsonl"
    client = TestClient(create_app(pipeline, log_path=log))
    return client, pipeline.chats_dir / "laura.txt", log


def test_page(env):
    client, _, _ = env
    res = client.get("/")
    assert res.status_code == 200
    assert "Aprobar y enviar" in res.text


def test_inbox(env):
    client, _, _ = env
    items = client.get("/api/inbox").json()
    assert len(items) == 1
    item = items[0]
    assert set(item) == {"chat_id", "name", "fit", "reasons", "waiting_minutes", "last_sender"}
    assert item["chat_id"] == "laura"
    assert item["name"] == "Laura"
    assert item["fit"] == "fits"
    assert item["last_sender"] == "cliente"
    assert item["waiting_minutes"] > 0


def test_chat_detail(env):
    client, _, _ = env
    body = client.get("/api/chats/laura").json()
    assert set(body) == {"chat", "extraction", "analysis", "draft", "checks"}
    assert [m["index"] for m in body["chat"]["messages"]] == [0, 1, 2, 3]
    assert len(body["analysis"]["rows"]) == 9


def test_unknown_chat_is_404(env):
    client, _, _ = env
    assert client.get("/api/chats/nadie").status_code == 404
    assert client.get("/api/chats/..%2Fsecret").status_code == 404
    assert client.post("/api/chats/nadie/approve", json={"text": "hola"}).status_code == 404


def test_approve_appends_one_line_to_chat_and_log(env):
    client, chat_file, log = env
    before = chat_file.read_text(encoding="utf-8").splitlines()

    res = client.post("/api/chats/laura/approve", json={"text": "Hola\nLaura", "edited": True})
    assert res.status_code == 200

    after = chat_file.read_text(encoding="utf-8").splitlines()
    assert after[:-1] == before
    assert len(after) == len(before) + 1
    assert after[-1].startswith("[libeen][") and after[-1].endswith("][Hola\\nLaura]")

    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert set(entry) == {"ts", "chat_id", "reply_kind", "edited", "checks_failed", "text"}
    assert entry["chat_id"] == "laura"
    assert entry["reply_kind"] == "offer"
    assert entry["edited"] is True
    assert entry["checks_failed"] == []
    assert entry["text"] == "Hola\nLaura"

    # the chat now ends with libeen: inbox reflects it
    assert client.get("/api/inbox").json()[0]["last_sender"] == "libeen"


def test_approve_rejects_empty_text(env):
    client, chat_file, log = env
    before = chat_file.read_text(encoding="utf-8")
    assert client.post("/api/chats/laura/approve", json={"text": "  "}).status_code == 400
    assert chat_file.read_text(encoding="utf-8") == before
    assert not log.exists()


def test_approve_logs_failed_checks(tmp_path):
    pipeline = sample_pipeline(tmp_path)
    pipeline.check_draft = lambda d, a, c: [
        {"name": "banned_words", "ok": False, "detail": "aprobado"},
        {"name": "offer_disclaimer", "ok": True, "detail": ""},
    ]
    log = tmp_path / "log.jsonl"
    client = TestClient(create_app(pipeline, log_path=log))
    client.post("/api/chats/laura/approve", json={"text": "Hola", "edited": False})
    assert json.loads(log.read_text(encoding="utf-8"))["checks_failed"] == ["banned_words"]


def test_inbox_survives_a_broken_chat(tmp_path):
    pipeline = sample_pipeline(tmp_path)
    (pipeline.chats_dir / "roto.txt").write_text("esto no es un chat\n", encoding="utf-8")
    client = TestClient(create_app(pipeline, log_path=tmp_path / "log.jsonl"))
    items = client.get("/api/inbox").json()
    assert [i["chat_id"] for i in items] == ["laura", "roto"]
    assert items[1]["fit"] == "error"
    assert client.get("/api/chats/roto").status_code == 500


@pytest.fixture
def checked(tmp_path):
    """Sample data, but the real check_draft and config."""
    pipeline = sample_pipeline(tmp_path)
    pipeline.check_draft = check_draft
    pipeline.config = load_config(ROOT / "config" / "rules.yaml")
    log = tmp_path / "log.jsonl"
    return TestClient(create_app(pipeline, log_path=log)), pipeline.chats_dir / "laura.txt", log


def test_edited_text_with_banned_word_is_sent_and_logged(checked):
    client, chat_file, log = checked
    before = len(chat_file.read_text(encoding="utf-8").splitlines())

    res = client.post("/api/chats/laura/approve", json={"text": "¡Estáis aprobados!", "edited": True})

    assert res.status_code == 200
    assert res.json()["checks_failed"] == ["banned_words"]
    lines = chat_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == before + 1 and lines[-1].endswith("][¡Estáis aprobados!]")
    assert json.loads(log.read_text(encoding="utf-8"))["checks_failed"] == ["banned_words"]


def test_edited_text_with_unknown_number_is_logged(checked):
    client, _, log = checked
    res = client.post("/api/chats/laura/approve", json={"text": "Podríais optar a 250.000 €.", "edited": True})
    assert res.json()["checks_failed"] == ["numbers_in_facts"]


def test_unedited_proposal_passes_checks(checked):
    client, _, log = checked
    body = client.get("/api/chats/laura").json()
    text = "\n\n".join(b["text"] for b in body["draft"]["blocks"])
    res = client.post("/api/chats/laura/approve", json={"text": text, "edited": False})
    assert res.json()["checks_failed"] == []
    assert json.loads(log.read_text(encoding="utf-8"))["edited"] is False


# --- Round 2 (CONTRACTS 11) ---

def never(*args, **kwargs):
    raise AssertionError("must not be called")


def test_no_draft_when_libeen_wrote_last(tmp_path):
    pipeline = sample_pipeline(tmp_path)
    pipeline.append_message(pipeline.chats_dir / "laura.txt", "libeen", "Ya os llamamos.")
    pipeline.draft = never
    pipeline.check_draft = never
    client = TestClient(create_app(pipeline, log_path=tmp_path / "log.jsonl"))
    body = client.get("/api/chats/laura").json()
    assert body["draft"] is None
    assert body["checks"] == []
    assert body["analysis"]["fit"] == "fits"


def test_inbox_routes_never_call_draft(tmp_path):
    pipeline = sample_pipeline(tmp_path)
    pipeline.draft = never
    client = TestClient(create_app(pipeline, log_path=tmp_path / "log.jsonl"))
    assert client.get("/api/inbox").json()[0]["fit"] == "fits"
    assert client.get("/api/inbox/laura").json()["fit"] == "fits"


def test_inbox_list_is_cheap(tmp_path):
    pipeline = sample_pipeline(tmp_path)
    pipeline.extract = never
    pipeline.draft = never
    client = TestClient(create_app(pipeline, log_path=tmp_path / "log.jsonl"))
    items = client.get("/api/inbox-list").json()
    assert [(i["chat_id"], i["fit"], i["last_sender"]) for i in items] == [("laura", None, "cliente")]
    assert client.get("/api/inbox/nadie").status_code == 404


def test_markers_pass_through(tmp_path):
    pipeline = sample_pipeline(tmp_path)
    extract, draft = pipeline.extract, pipeline.draft
    pipeline.extract = lambda chat: extract(chat) | {"recorded": True}
    pipeline.draft = lambda chat, a, c: draft(chat, a, c) | {"mock_placeholder": True}
    client = TestClient(create_app(pipeline, log_path=tmp_path / "log.jsonl"))
    body = client.get("/api/chats/laura").json()
    assert body["extraction"]["recorded"] is True
    assert body["draft"]["mock_placeholder"] is True


def test_edited_text_mentioning_age_is_logged(checked):
    client, _, log = checked
    res = client.post("/api/chats/laura/approve", json={"text": "Por vuestra edad no hay problema.", "edited": True})
    assert res.json()["checks_failed"] == ["internal_terms"]
