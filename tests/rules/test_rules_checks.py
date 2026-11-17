from app.rules import analyze, check_draft


def by_name(checks):
    return {c["name"]: c for c in checks}


def test_unknown_number_fails(sample, config, deep):
    a = analyze(sample["extraction"], config)
    d = deep(sample["draft"])
    d["blocks"][1]["text"] += " Y el precio final sería 250.000 €."
    c = by_name(check_draft(d, a, config))
    assert c["numbers_in_facts"]["ok"] is False
    assert "250.000" in c["numbers_in_facts"]["detail"]
    assert c["banned_words"]["ok"] is True


def test_number_formats_tolerated(sample, config, deep):
    a = analyze(sample["extraction"], config)
    d = deep(sample["draft"])
    d["blocks"][1]["text"] = "Hasta unos 204.500 euros, en 3 años. Es orientativo."
    assert by_name(check_draft(d, a, config))["numbers_in_facts"]["ok"] is True


def test_banned_word_fails(sample, config, deep):
    a = analyze(sample["extraction"], config)
    d = deep(sample["draft"])
    d["blocks"][2]["text"] = "¡Estáis Aprobados!"
    c = by_name(check_draft(d, a, config))
    assert c["banned_words"]["ok"] is False
    assert "aprobados" in c["banned_words"]["detail"]


def test_bad_key_spans(sample, config, deep):
    a = analyze(sample["extraction"], config)
    d = deep(sample["draft"])
    d["key_spans"].append({"block": 0, "text": "no está aquí", "ref": "decision"})
    d["key_spans"].append({"block": 1, "text": "204.500 €", "ref": "sim.inventado"})
    d["key_spans"].append({"block": 9, "text": "x", "ref": "decision"})
    c = by_name(check_draft(d, a, config))["key_spans_valid"]
    assert c["ok"] is False
    assert "inventado" in c["detail"] and "bloque 9" in c["detail"]


def test_offer_needs_disclaimer(sample, config, deep):
    a = analyze(sample["extraction"], config)
    d = deep(sample["draft"])
    d["blocks"][1]["text"] = d["blocks"][1]["text"].replace("orientativos", "aproximados")
    assert by_name(check_draft(d, a, config))["offer_disclaimer"]["ok"] is False
    d["reply_kind"] = "ask_info"
    assert by_name(check_draft(d, a, config))["offer_disclaimer"]["ok"] is True


def test_draft_mentioning_age_fails(sample, config, deep):
    a = analyze(sample["extraction"], config)
    d = deep(sample["draft"])
    d["blocks"][0]["text"] += " Por vuestra Edad no hay problema."
    c = by_name(check_draft(d, a, config))
    assert c["internal_terms"]["ok"] is False
    assert "edad" in c["internal_terms"]["detail"]


def test_draft_too_long_fails(sample, config, deep):
    a = analyze(sample["extraction"], config)
    d = deep(sample["draft"])
    d["blocks"][2]["text"] = "a" * config["draft"]["max_chars"]
    c = by_name(check_draft(d, a, config))
    assert c["max_chars"]["ok"] is False


def test_six_checks_in_order(sample, config):
    a = analyze(sample["extraction"], config)
    names = [c["name"] for c in check_draft(sample["draft"], a, config)]
    assert names == ["banned_words", "numbers_in_facts", "key_spans_valid", "offer_disclaimer",
                     "internal_terms", "max_chars"]
