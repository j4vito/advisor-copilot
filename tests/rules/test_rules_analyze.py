from app.rules import analyze

ORDER = ["zona", "plazo", "compradores", "edad", "empleo", "ingresos", "deudas", "net_income", "ahorro"]


def rows(a):
    return {r["key"]: r for r in a["rows"]}


def test_nine_rows_in_order_even_when_empty(make, config):
    a = analyze(make(), config)
    assert [r["key"] for r in a["rows"]] == ORDER
    assert [r["n"] for r in a["rows"]] == [1, 2, 3, 4, 5, 6, 7, None, 8]
    assert all(r["status"] == "missing" for r in a["rows"])
    assert a["fit"] == "needs_data" and a["simulation"] is None


def test_rosa_declines(make, config):
    ext = make(
        zona="Madrid",
        plazo={"text": "en dos semanas", "weeks": 2},
        compradores=1,
        edad=[67],
        ingresos={"min": 1400, "max": 1400},
        ahorro=0,
    )
    a = analyze(ext, config)
    r = rows(a)
    assert {k for k, v in r.items() if v["status"] == "fails"} == {"plazo", "net_income", "ahorro"}
    assert r["edad"]["status"] == "doubtful"
    assert r["edad"]["note"] == "Lo decide el asesor"
    assert r["net_income"]["display"] == "1.400 − ? = "
    assert r["ahorro"]["note"] == "Mínimo: 15.000 €"
    assert r["deudas"]["status"] == "missing"
    assert a["simulation"] is None
    assert (a["fit"], a["reply_kind"], a["review"]) == ("no_fit", "decline", "full")
    assert a["counts"]["fails"] == 3


def test_age_never_fails(make, config):
    ext = make(edad=[95], ingresos={"min": 4000, "max": 4000}, deudas=0, ahorro=30000)
    a = analyze(ext, config)
    assert rows(a)["edad"]["status"] == "doubtful"
    assert a["fit"] == "fits"


def test_javier_needs_data(make, config):
    ext = make(
        ingresos=({"min": 2000, "max": 3000}, "doubtful"),
        attachments=[{"msg": 3, "kind": "audio", "label": "Audio de 1:12"}],
    )
    a = analyze(ext, config)
    r = rows(a)
    assert r["net_income"]["status"] == "missing"
    assert r["net_income"]["display"] == "2.000 a 3.000 − ? = "
    assert r["ahorro"]["status"] == "missing"
    assert (a["fit"], a["reply_kind"], a["review"]) == ("needs_data", "ask_info", "full")
    assert a["simulation"] is None


def test_income_exactly_at_minimum_is_ok(make, config):
    m = config["qualification"]["min_net_income"]
    ext = make(ingresos={"min": m, "max": m}, deudas=0, ahorro=config["qualification"]["min_savings"], net="no")
    a = analyze(ext, config)
    assert rows(a)["net_income"]["status"] == "ok"
    assert rows(a)["ahorro"]["status"] == "ok"
    assert a["fit"] == "fits"


def test_net_income_straddling_is_doubtful(make, config):
    m = config["qualification"]["min_net_income"]
    ext = make(ingresos={"min": m - 500, "max": m + 500}, deudas=0, ahorro=20000, net="no")
    assert rows(analyze(ext, config))["net_income"]["status"] == "doubtful"


def test_debt_doubt_that_changes_outcome(make, config):
    m = config["qualification"]["min_net_income"]
    ext = make(ingresos={"min": m + 100, "max": m + 100}, deudas=300, ahorro=20000)
    r = rows(analyze(ext, config))["net_income"]
    assert r["status"] == "doubtful"
    assert r["note"].endswith("Cambia el resultado")


def test_known_net_income_has_no_debt_note(make, config):
    ext = make(ingresos={"min": 3800, "max": 3800}, deudas=250, ahorro=18000, net="no")
    r = rows(analyze(ext, config))["net_income"]
    assert r["status"] == "ok"
    assert r["display"] == "3.800 − 250 = 3.550 €"


def test_rules_never_touch_missing(make, config):
    a = analyze(make(ingresos={"min": 100, "max": 100}, deudas=0, net="no"), config)
    assert rows(a)["ahorro"]["status"] == "missing"
    assert rows(a)["plazo"]["status"] == "missing"


def test_plazo_short_fails(make, config):
    w = config["qualification"]["min_weeks_to_move"]
    a = analyze(make(plazo={"text": "ya", "weeks": w - 1}), config)
    assert rows(a)["plazo"]["status"] == "fails"
    a = analyze(make(plazo={"text": "pronto", "weeks": w}), config)
    assert rows(a)["plazo"]["status"] == "ok"


def test_special_request_forces_full_review(make, config):
    ext = make(ingresos={"min": 4000, "max": 4000}, deudas=0, ahorro=30000, net="no",
               special=[{"msg": 1, "kind": "rent_only", "text": "solo alquiler"}])
    a = analyze(ext, config)
    assert a["fit"] == "fits" and a["review"] == "full"


def test_simulation_limited_by_income(make, config):
    ext = make(ingresos={"min": 2500, "max": 2500}, deudas=0, ahorro=100000, net="no")
    a = analyze(ext, config)
    assert a["simulation"]["limited_by"] == "income"
    assert a["simulation"]["max_price"] % config["simulation"]["round_to"] == 0
    assert rows(a)["net_income"]["note"] == "Marca el límite de precio"


def test_config_change_changes_result(sample, config, deep):
    ext = sample["extraction"]
    assert analyze(ext, config)["fit"] == "fits"

    stricter = deep(config)
    stricter["qualification"]["min_net_income"] = 4000
    a = analyze(ext, stricter)
    assert a["fit"] == "no_fit"
    assert a["facts"]["rule.min_income"] == "4.000 €"

    cheaper = deep(config)
    cheaper["simulation"]["savings_to_price"] = 0.1
    assert analyze(ext, cheaper)["simulation"]["max_price"] == 180000
