import pytest
import yaml

from app.rules import ConfigError, eur, inbox_sort, load_config, num


def test_spanish_format():
    assert eur(204500) == "204.500 €"
    assert num(3) == "3"
    assert num(1317.36) == "1.317"
    assert eur(1000000) == "1.000.000 €"


def test_inbox_order():
    items = [
        {"chat_id": "a", "fit": "no_fit", "last_sender": "cliente", "waiting_minutes": 500},
        {"chat_id": "b", "fit": "fits", "last_sender": "libeen", "waiting_minutes": 900},
        {"chat_id": "c", "fit": "fits", "last_sender": "cliente", "waiting_minutes": 10},
        {"chat_id": "d", "fit": "fits", "last_sender": "cliente", "waiting_minutes": 60},
        {"chat_id": "e", "fit": "needs_data", "last_sender": "cliente", "waiting_minutes": 5},
    ]
    assert [i["chat_id"] for i in inbox_sort(items)] == ["d", "c", "e", "a", "b"]


def test_missing_key_fails_clearly(tmp_path, config):
    del config["qualification"]["min_savings"]
    p = tmp_path / "rules.yaml"
    p.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ConfigError, match="qualification.min_savings"):
        load_config(p)


def test_wrong_type_fails_clearly(tmp_path, config):
    config["simulation"]["effort_max"] = "mucho"
    p = tmp_path / "rules.yaml"
    p.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ConfigError, match="effort_max"):
        load_config(p)


def test_missing_file_fails_clearly(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")


@pytest.mark.parametrize("section,key,bad", [
    ("qualification", "near_miss_pct", 2),
    ("draft", "max_questions", "tres"),
    ("draft", "ask_priority", ["ingresos", "sueldo"]),
    ("draft", "hidden_fields", "edad"),
    ("draft", "internal_terms", [1]),
    ("draft", "offer_facts", None),
])
def test_round2_keys_validated(tmp_path, config, section, key, bad):
    config[section][key] = bad
    p = tmp_path / "rules.yaml"
    p.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ConfigError, match=key):
        load_config(p)


def test_round2_key_missing(tmp_path, config):
    del config["draft"]["offer_facts"]
    p = tmp_path / "rules.yaml"
    p.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ConfigError, match="draft.offer_facts"):
        load_config(p)
