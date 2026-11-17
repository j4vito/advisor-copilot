"""CONTRACTS section 11 (round 2)."""
from app.rules import analyze, check_draft


def rows(a):
    return {r["key"]: r for r in a["rows"]}


def good(make, **over):
    """A client that fits on every rule unless overridden."""
    values = dict(
        zona="Valencia", plazo={"text": "en verano", "weeks": 30}, compradores=2, edad=[35],
        empleo=["indefinido"], ingresos={"min": 3000, "max": 3000}, deudas=0, ahorro=30000,
    )
    values.update(over)
    net = values.pop("net", "no")
    return make(net=net, **values)


def test_pablo_straddling_income_asks_first(make, config):
    """11.1: 2.100 to 2.500 € straddles the minimum, so no offer."""
    ext = good(make, ingresos=({"min": 2100, "max": 2500}, "doubtful"), empleo=None, net="unknown")
    a = analyze(ext, config)
    assert rows(a)["net_income"]["status"] == "doubtful"
    assert (a["fit"], a["reply_kind"]) == ("needs_data", "ask_info")
    assert a["ask_for"][0] == "ingresos"
    assert a["ask_for"] == ["ingresos", "empleo"]
    assert a["client_reasons"] == []
    assert "Marca el límite de precio" not in [r["note"] for r in a["rows"]]


def test_carmen_gross_income(make, config):
    """11.3: income doubtful with no value."""
    ext = good(make, ingresos=(None, "doubtful"), net="unknown")
    ext["fields"]["ingresos"] = {"value": None, "status": "doubtful", "quotes": [], "note": "Bruto anual"}
    a = analyze(ext, config)
    r = rows(a)
    assert r["ingresos"]["status"] == "doubtful"
    assert r["net_income"]["status"] == "doubtful"
    assert r["net_income"]["display"] == "? − 0 = "
    assert r["net_income"]["note"] == "Falta el neto mensual"
    assert (a["fit"], a["reply_kind"]) == ("needs_data", "ask_info")
    assert a["ask_for"] == ["ingresos"]
    assert a["simulation"] is None


def test_elena_near_miss_savings(make, config):
    """11.2: 14.900 € is within near_miss_pct of 15.000 €: doubtful, full review."""
    ext = good(make, ahorro=14900)
    a = analyze(ext, config)
    r = rows(a)["ahorro"]
    assert r["status"] == "doubtful"
    assert r["note"] == "Casi llega: mínimo 15.000 €"
    assert a["counts"]["fails"] == 0
    assert a["fit"] == "fits"
    assert a["review"] == "full"


def test_near_miss_income_is_doubtful_not_offer(make, config):
    m = config["qualification"]["min_net_income"]
    ext = good(make, ingresos={"min": m - 50, "max": m - 50})
    a = analyze(ext, config)
    r = rows(a)["net_income"]
    assert r["status"] == "doubtful" and r["note"].startswith("Casi llega")
    assert a["fit"] == "needs_data" and a["review"] == "full"


def test_near_miss_weeks(make, deep, config):
    cfg = deep(config)
    cfg["qualification"]["near_miss_pct"] = 0.3
    w = cfg["qualification"]["min_weeks_to_move"]
    a = analyze(good(make, plazo={"text": "ya", "weeks": w - 1}), cfg)
    assert rows(a)["plazo"]["status"] == "doubtful"
    assert rows(a)["plazo"]["note"].startswith("Casi llega")
    assert a["review"] == "full"


def test_far_below_still_fails(make, config):
    a = analyze(good(make, ahorro=10000), config)
    assert rows(a)["ahorro"]["status"] == "fails"
    assert rows(a)["ahorro"]["note"] == "Mínimo: 15.000 €"


def test_marta7_failing_income_note_and_no_simulation(make, config):
    """11.4 and 11.5."""
    ext = good(make, ingresos={"min": 1800, "max": 1800}, edad=[62], ahorro=29500, net="unknown")
    a = analyze(ext, config)
    r = rows(a)["net_income"]
    assert r["status"] == "fails"
    assert r["note"] == "Mínimo: 2.200 €"
    assert a["fit"] == "no_fit"
    assert a["simulation"] is None
    assert not any(k.startswith("sim.") for k in a["facts"])
    assert "Marca el límite de precio" not in [x["note"] for x in a["rows"]]


def test_rosa_failing_row_has_note(make, config):
    ext = make(ingresos={"min": 1400, "max": 1400}, ahorro=0, plazo={"text": "en dos semanas", "weeks": 2})
    a = analyze(ext, config)
    assert rows(a)["net_income"]["note"] == "Mínimo: 2.200 €"


def test_age_62_with_good_income_fits_with_full_review(make, config):
    a = analyze(good(make, edad=[62]), config)
    assert rows(a)["edad"]["status"] == "doubtful"
    assert (a["fit"], a["reply_kind"], a["review"]) == ("fits", "offer", "full")


def test_income_net_yes_ignores_missing_debts(make, config):
    a = analyze(good(make, deudas=None, net="yes"), config)
    r = rows(a)["net_income"]
    assert r["status"] == "ok"
    assert r["display"] == "3.000 € (deudas ya descontadas)"
    assert a["fit"] == "fits"
    assert "deudas" not in a["ask_for"]


def test_ask_for_order_and_cut(make, config):
    a = analyze(make(), config)                   # everything missing
    prio = [k for k in config["draft"]["ask_priority"] if k not in config["draft"]["hidden_fields"]]
    assert a["ask_for"] == prio[: config["draft"]["max_questions"]]
    assert "edad" not in a["ask_for"]


def test_ask_for_follows_config(make, deep, config):
    cfg = deep(config)
    cfg["draft"]["max_questions"] = 1
    cfg["draft"]["ask_priority"] = ["ahorro", "ingresos", "deudas", "zona", "plazo", "compradores", "empleo", "edad"]
    assert analyze(make(), cfg)["ask_for"] == ["ahorro"]


def test_ask_for_empty_for_offer_and_decline(sample, make, config):
    assert analyze(sample["extraction"], config)["ask_for"] == []
    assert analyze(good(make, ahorro=0), config)["ask_for"] == []


def test_client_reasons_only_failing_rows(make, config):
    ext = good(make, ahorro=0, edad=[70], empleo=None, plazo={"text": "ya", "weeks": 1})
    a = analyze(ext, config)
    assert a["fit"] == "no_fit"
    assert [c["key"] for c in a["client_reasons"]] == ["plazo", "ahorro"]
    ahorro = a["client_reasons"][1]
    assert ahorro == {"key": "ahorro", "text": "Ahorro de 0 €, mínimo 15.000 €",
                      "refs": ["field.ahorro", "rule.min_savings"]}
    for c in a["client_reasons"]:
        assert all(ref in a["facts"] for ref in c["refs"])
        assert "edad" not in c["text"].lower()


def test_client_reasons_numbers_pass_number_check(make, config):
    ext = good(make, ingresos={"min": 1200, "max": 1600}, deudas=100, ahorro=0)
    a = analyze(ext, config)
    text = " ".join(c["text"] for c in a["client_reasons"])
    draft = {"reply_kind": "decline", "blocks": [{"label": "x", "text": text}], "key_spans": []}
    checks = {c["name"]: c for c in check_draft(draft, a, config)}
    assert checks["numbers_in_facts"]["ok"], checks["numbers_in_facts"]["detail"]


def test_client_reasons_empty_unless_decline(sample, config):
    assert analyze(sample["extraction"], config)["client_reasons"] == []
