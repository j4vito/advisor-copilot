"""analyze(extraction, config) -> Analysis. CONTRACTS sections 5 and 11. Pure and deterministic."""

from decimal import Decimal, ROUND_FLOOR

from .fmt import capitalize, eur, join_es, num, num_range, to_int

_STATUS_ORDER = ["ok", "doubtful", "missing", "fails"]
_FIT_FOR_KIND = {"no_fit": "decline", "fits": "offer", "needs_data": "ask_info"}
_PLAIN_KEYS = ["zona", "plazo", "compradores", "edad", "empleo", "ingresos", "deudas", "ahorro"]

NOTE_LIMIT = "Marca el límite de precio"
NOTE_AGE = "Lo decide el asesor"
NOTE_NO_NET = "Falta el neto mensual"


def _d(value) -> Decimal:
    return Decimal(str(value))


def _floor_to(value: Decimal, step) -> int:
    step = _d(step)
    return int((value / step).to_integral_value(rounding=ROUND_FLOOR) * step)


def _raise_to_doubtful(status: str) -> str:
    return "doubtful" if status == "ok" else status


def _field(extraction, key) -> dict:
    """Value and status as the model gave them. A doubtful field may have no value (11.3)."""
    f = (extraction.get("fields") or {}).get(key) or {}
    value = f.get("value")
    status = f.get("status") or "missing"
    if status == "missing" or (value is None and status == "ok"):
        return {"value": None, "status": "missing", "note": f.get("note") or ""}
    # Tolerate loose shapes: a bare number for income, a bare string for plazo.
    if key == "ingresos" and isinstance(value, (int, float)) and not isinstance(value, bool):
        value = {"min": value, "max": value}
    if key == "plazo" and isinstance(value, str):
        value = {"text": value, "weeks": None}
    return {"value": value, "status": status, "note": f.get("note") or ""}


def _near_miss(value, minimum, config) -> bool:
    """Below the minimum but within near_miss_pct of it (11.2)."""
    pct = _d(config["qualification"]["near_miss_pct"])
    return _d(minimum) * (1 - pct) <= _d(value) < _d(minimum)


def _classify(lo, hi, minimum, config) -> str:
    """ok / doubtful / near / fails for a range against a minimum."""
    if hi < minimum:
        return "near" if _near_miss(hi, minimum, config) else "fails"
    if lo >= minimum:
        return "ok"
    return "doubtful"


def _min_check(value, minimum, minimum_txt, config):
    """(status, note) for a single value with a minimum, or None when it passes."""
    if value >= minimum:
        return None
    if _near_miss(value, minimum, config):
        return "doubtful", f"Casi llega: mínimo {minimum_txt}"
    return "fails", f"Mínimo: {minimum_txt}"


# ---------- display of the plain rows ----------

def _display(key, value) -> str:
    if value is None:
        return ""
    if key == "plazo":
        text = (value or {}).get("text") or ""
        weeks = (value or {}).get("weeks")
        if text:
            return capitalize(text)
        return f"{weeks} semanas" if weeks is not None else ""
    if key == "edad":
        return join_es(value if isinstance(value, list) else [value])
    if key == "empleo":
        return capitalize(join_es(value if isinstance(value, list) else [value]))
    if key == "ingresos":
        return f"{num_range(value['min'], value['max'])} € al mes"
    if key == "deudas":
        return f"{eur(value)} al mes"
    if key == "ahorro":
        return eur(value)
    return str(value)


# ---------- the computed net income row ----------

def _net_income(extraction, ingresos, deudas, config) -> dict:
    """Returns {status, display, note, lo, hi, near}; lo/hi are None when unknown."""
    minimum = config["qualification"]["min_net_income"]
    min_note = f"Mínimo: {eur(minimum)}"
    mode = extraction.get("income_net_of_debts") or "unknown"
    out = {"status": "missing", "display": "", "note": "", "lo": None, "hi": None, "near": False}
    debts_txt = "?" if deudas["value"] is None else num(deudas["value"])

    if ingresos["value"] is None:
        if ingresos["status"] == "doubtful":          # 11.3: gross or unusable income
            out.update(status="doubtful", display=f"? − {debts_txt} = ", note=NOTE_NO_NET)
        return out

    i_min, i_max = ingresos["value"]["min"], ingresos["value"]["max"]
    income_txt = num_range(i_min, i_max)

    if mode == "yes":                                 # income already net: debts do not matter
        lo, hi = i_min, i_max
        out["display"] = f"{income_txt} € (deudas ya descontadas)"
        d = 0
    elif deudas["value"] is None:
        out["display"] = f"{income_txt} − ? = "
        if i_max < minimum:
            out.update(status="fails", note=min_note)
        return out
    else:
        d = deudas["value"]
        lo = i_min - d
        hi = i_max - d if mode == "no" else i_max
        out["display"] = f"{income_txt} − {num(d)} = {num_range(i_min - d, i_max - d)} €"
    out["lo"], out["hi"] = lo, hi

    status = _classify(lo, hi, minimum, config)
    if status == "fails":
        out.update(status="fails", note=min_note)
        return out
    if status == "near":
        out.update(status="doubtful", note=f"Casi llega: mínimo {eur(minimum)}", near=True)
        return out

    if "doubtful" in (ingresos["status"], deudas["status"] if mode != "yes" else "ok"):
        status = _raise_to_doubtful(status)
    if mode == "unknown" and d > 0:
        status = _raise_to_doubtful(status)
        with_debts = _classify(i_min - d, i_max - d, minimum, config)
        without = _classify(i_min, i_max, minimum, config)
        if with_debts != without:
            outcome = "Cambia el resultado"
        else:
            outcome = {"ok": "Encaja igual", "doubtful": "Sigue en duda"}.get(without, "No llega igual")
        out["note"] = f"Si ya lo descontó: {income_txt}. {outcome}"
    out["status"] = status
    return out


# ---------- simulation ----------

def _simulate(net_low, savings, config):
    s = config["simulation"]
    by_savings = _d(savings) / _d(s["savings_to_price"])
    by_income = _d(s["effort_max"]) * _d(net_low) * 12 / _d(s["annual_payment_ratio"])
    by_income = max(by_income, Decimal(0))
    limited_by = "savings" if by_savings <= by_income else "income"
    max_price = _floor_to(min(by_savings, by_income), s["round_to"])
    monthly_payment = _d(max_price) * _d(s["annual_payment_ratio"]) / 12
    monthly_savings = monthly_payment * _d(s["savings_share"])
    price_end = _floor_to(_d(max_price) * (1 + _d(s["price_growth"])) ** int(s["years"]), s["round_to"])
    return {
        "max_price": max_price,
        "limited_by": limited_by,
        "monthly_payment": to_int(monthly_payment),
        "monthly_savings": to_int(monthly_savings),
        "price_end": price_end,
    }


# ---------- main ----------

def analyze(extraction: dict, config: dict) -> dict:
    q = config["qualification"]
    fields = {key: _field(extraction, key) for key in _PLAIN_KEYS}
    state = {key: {"status": f["status"], "note": f["note"], "display": _display(key, f["value"])}
             for key, f in fields.items()}
    near_rows = []

    plazo = fields["plazo"]
    weeks = plazo["value"].get("weeks") if isinstance(plazo["value"], dict) else None
    if weeks is not None:
        hit = _min_check(weeks, q["min_weeks_to_move"], f"{num(q['min_weeks_to_move'])} semanas", config)
        if hit:
            state["plazo"].update(status=hit[0], note=hit[1])
            if hit[0] == "doubtful":
                near_rows.append("plazo")

    edad = fields["edad"]
    old_age = False
    if edad["value"] is not None:
        ages = edad["value"] if isinstance(edad["value"], list) else [edad["value"]]
        if any(a > q["advisor_review_age"] for a in ages):
            old_age = True
            state["edad"].update(status=_raise_to_doubtful(state["edad"]["status"]), note=NOTE_AGE)

    ahorro = fields["ahorro"]
    if ahorro["value"] is not None:
        hit = _min_check(ahorro["value"], q["min_savings"], eur(q["min_savings"]), config)
        if hit:
            state["ahorro"].update(status=hit[0], note=hit[1])
            if hit[0] == "doubtful":
                near_rows.append("ahorro")

    net = _net_income(extraction, fields["ingresos"], fields["deudas"], config)
    state["net_income"] = {"status": net["status"], "note": net["note"], "display": net["display"]}
    if net["near"]:
        near_rows.append("net_income")

    # Decision (11.1: an offer needs the low end of net income at or above the minimum).
    failing = [spec["key"] for spec in config["fields"] if state[spec["key"]]["status"] == "fails"]
    income_clear = net["lo"] is not None and net["lo"] >= q["min_net_income"]
    savings_known = ahorro["value"] is not None and state["ahorro"]["status"] in ("ok", "doubtful")
    if failing:
        fit = "no_fit"
    elif income_clear and savings_known:
        fit = "fits"
    else:
        fit = "needs_data"
    reply_kind = _FIT_FOR_KIND[fit]

    # Simulation: needs net income and savings values, never for no_fit (11.5).
    simulation = None
    if fit != "no_fit" and net["lo"] is not None and ahorro["value"] is not None:
        simulation = _simulate(net["lo"], ahorro["value"], config)
        if fit == "fits":                               # 11.4
            limit_row = "ahorro" if simulation["limited_by"] == "savings" else "net_income"
            if not state[limit_row]["note"]:
                state[limit_row]["note"] = NOTE_LIMIT

    rows, n = [], 0
    for spec in config["fields"]:
        key = spec["key"]
        computed = bool(spec.get("computed"))
        if not computed:
            n += 1
        st = state[key]
        rows.append({
            "key": key, "n": None if computed else n, "label": spec["label"],
            "display": st["display"], "status": st["status"], "note": st["note"],
            "group": spec.get("group"),
        })
    counts = {s: sum(1 for r in rows if r["status"] == s) for s in _STATUS_ORDER}

    alerts = {
        "open_questions": list(extraction.get("open_questions") or []),
        "attachments": list(extraction.get("attachments") or []),
        "special_requests": list(extraction.get("special_requests") or []),
    }
    review = "full" if (fit == "no_fit" or alerts["special_requests"] or alerts["attachments"]
                        or near_rows or old_age) else "normal"

    facts = _facts(fields, net, simulation, failing, config)
    ask_for = _ask_for(fields, state, net, extraction, config) if fit == "needs_data" else []
    client_reasons = _client_reasons(failing, fields, net, facts, config) if fit == "no_fit" else []

    return {
        "rows": rows,
        "counts": counts,
        "alerts": alerts,
        "simulation": simulation,
        "fit": fit,
        "reply_kind": reply_kind,
        "review": review,
        "reasons": _reasons(fit, failing, near_rows, ask_for, state, fields, config),
        "facts": facts,
        "ask_for": ask_for,
        "client_reasons": client_reasons,
    }


def _ask_for(fields, state, net, extraction, config) -> list:
    """11.7: missing fields, or doubtful ones that block the decision, in ask_priority order."""
    blocking = {k for k in _PLAIN_KEYS if state[k]["status"] == "missing"}
    if net["lo"] is None or net["lo"] < config["qualification"]["min_net_income"]:
        if fields["ingresos"]["status"] == "doubtful" or net["status"] == "doubtful":
            blocking.add("ingresos")
    if fields["deudas"]["status"] == "doubtful" and fields["deudas"]["value"] is None:
        blocking.add("deudas")
    if fields["ahorro"]["status"] == "doubtful" and fields["ahorro"]["value"] is None:
        blocking.add("ahorro")
    if (extraction.get("income_net_of_debts") == "yes"):
        blocking.discard("deudas")
    hidden = set(config["draft"]["hidden_fields"])
    ordered = [k for k in config["draft"]["ask_priority"] if k in blocking and k not in hidden]
    return ordered[: int(config["draft"]["max_questions"])]


def _client_reasons(failing, fields, net, facts, config) -> list:
    """11.7: one entry per failing row, numbers only from facts."""
    q = config["qualification"]
    out = []
    for key in failing:
        if key == "ahorro":
            out.append({"key": key,
                        "text": f"Ahorro de {facts['field.ahorro']}, mínimo {facts['rule.min_savings']}",
                        "refs": ["field.ahorro", "rule.min_savings"]})
        elif key == "plazo":
            out.append({"key": key,
                        "text": f"Plazo de {facts['field.plazo_weeks']} semanas, mínimo {facts['rule.min_weeks']} semanas",
                        "refs": ["field.plazo_weeks", "rule.min_weeks"]})
        elif key == "net_income":
            if net["lo"] is not None:
                refs = ["field.net_income"] + (["field.net_income_max"] if "field.net_income_max" in facts else [])
                amount = num_range(net["lo"], net["hi"]) + " €"
                text = f"Ingresos tras deudas de {amount}, mínimo {facts['rule.min_income']}"
            else:                                      # debts unknown, income alone is too low
                refs = ["field.ingresos"] if "field.ingresos" in facts else ["field.ingresos_min", "field.ingresos_max"]
                ing = fields["ingresos"]["value"]
                text = f"Ingresos de {num_range(ing['min'], ing['max'])} €, mínimo {facts['rule.min_income']}"
            out.append({"key": key, "text": text, "refs": refs + ["rule.min_income"]})
    return out


def _reasons(fit, failing, near_rows, ask_for, state, fields, config) -> list:
    labels = {spec["key"]: spec["label"] for spec in config["fields"]}
    reasons = []
    if fit == "fits":
        if not near_rows:
            reasons.append("Cumple ingresos y ahorro")
    elif fit == "no_fit":
        texts = {
            "net_income": "Ingresos por debajo del mínimo",
            "ahorro": "Ahorro por debajo del mínimo",
            "plazo": "Plazo demasiado corto",
        }
        reasons.extend(texts.get(k, "No cumple un requisito") for k in failing)
    else:
        if ask_for:
            reasons.append("Falta aclarar " + join_es(labels[k].lower() for k in ask_for))
        else:
            reasons.append("Faltan datos para decidir")
    for key in near_rows:
        reasons.append(f"{labels[key]}: casi llega al mínimo")
    if state["edad"]["note"] == NOTE_AGE:
        reasons.append("Edad: lo decide el asesor")
    plazo = fields["plazo"]
    if (isinstance(plazo["value"], dict) and state["plazo"]["status"] != "fails"
            and plazo["value"].get("text")):
        reasons.append(f"Quiere mudarse {plazo['value']['text']}")
    return reasons


def _facts(fields, net, simulation, failing, config) -> dict:
    q, s = config["qualification"], config["simulation"]
    facts = {}
    ing = fields["ingresos"]["value"]
    if ing is not None:
        if to_int(ing["min"]) == to_int(ing["max"]):
            facts["field.ingresos"] = eur(ing["min"])
        else:
            facts["field.ingresos_min"] = eur(ing["min"])
            facts["field.ingresos_max"] = eur(ing["max"])
    if fields["deudas"]["value"] is not None:
        facts["field.deudas"] = eur(fields["deudas"]["value"])
    if net["lo"] is not None:
        facts["field.net_income"] = eur(net["lo"])
        if "net_income" in failing and to_int(net["hi"]) != to_int(net["lo"]):
            facts["field.net_income_max"] = eur(net["hi"])
    if fields["ahorro"]["value"] is not None:
        facts["field.ahorro"] = eur(fields["ahorro"]["value"])
    if "plazo" in failing:
        facts["field.plazo_weeks"] = num(fields["plazo"]["value"]["weeks"])
    if simulation is not None:
        for key in ("max_price", "monthly_payment", "monthly_savings", "price_end"):
            facts[f"sim.{key}"] = eur(simulation[key])
        facts["sim.years"] = num(s["years"])
    facts["rule.min_income"] = eur(q["min_net_income"])
    facts["rule.min_savings"] = eur(q["min_savings"])
    facts["rule.min_weeks"] = num(q["min_weeks_to_move"])
    return facts
