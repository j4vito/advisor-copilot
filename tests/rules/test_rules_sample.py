from app.rules import analyze, check_draft


def test_laura_analysis_matches_sample(sample, config):
    assert analyze(sample["extraction"], config) == sample["analysis"]


def test_laura_checks_match_sample(sample, config):
    # The sample lists the four original checks; round 2 adds internal_terms and max_chars (11.6).
    analysis = analyze(sample["extraction"], config)
    checks = check_draft(sample["draft"], analysis, config)
    assert checks[:4] == sample["checks"]
    assert checks[4:] == [
        {"name": "internal_terms", "ok": True, "detail": ""},
        {"name": "max_chars", "ok": True, "detail": ""},
    ]


def test_laura_matches_expected_block(sample, config):
    a = analyze(sample["extraction"], config)
    exp = sample["expected"]
    net = next(r for r in a["rows"] if r["key"] == "net_income")
    assert net["status"] == exp["net_income_status"]
    assert (a["fit"], a["reply_kind"], a["review"]) == (exp["fit"], exp["reply_kind"], exp["review"])


def test_same_input_same_output(sample, config):
    assert analyze(sample["extraction"], config) == analyze(sample["extraction"], config)
