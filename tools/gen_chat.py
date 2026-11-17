"""Generate a random test chat and its expected answers.

Usage: python tools/gen_chat.py --seed 7 --out data/chats
Writes <out>/<chat_id>.txt and data/expected/<chat_id>.json (next to <out>).
The script picks every value, so it knows the right answers. Rule values are
read from config/rules.yaml (simple "key: number" lines, no YAML library).
"""

import argparse
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAMES = [("lucia", "sola"), ("sergio", "solo"), ("marta", "sola"), ("hugo", "solo"), ("ines", "sola"), ("raul", "solo")]
CITIES = ["Valencia", "Madrid", "Sevilla", "Zaragoza", "Murcia", "Córdoba", "Valladolid"]
JOBS = ["una tienda", "un hospital", "una oficina", "un colegio", "un taller"]
WEEKS = {2: "en dos semanas", 8: "en unos dos meses", 13: "en unos tres meses", 26: "en unos seis meses"}


def euros(n):
    return f"{n:,}".replace(",", ".")


def load_rules(path=ROOT / "config" / "rules.yaml"):
    text = path.read_text(encoding="utf-8")
    return {k: float(text_match) for k, text_match in re.findall(r"^\s*(\w+):\s*([\d.]+)", text, re.M)}


def below(value, minimum, rules):
    """CONTRACTS 11.2: "ok" at or above the minimum, "near" within near_miss_pct below it, else "fails"."""
    if value >= minimum:
        return "ok"
    return "near" if value >= minimum * (1 - rules["near_miss_pct"]) else "fails"


def net_status(income, debts, net_known, rules):
    """Net income row (CONTRACTS 5, 11.1, 11.2). Returns (status, near_miss, clear) where
    clear means the low end of the range is at or above the minimum (needed for "fits")."""
    minimum = rules["min_net_income"]
    if income is None:
        return "missing", False, False
    if debts is None:  # the best case is the declared income, debts can only lower it
        top = below(income, minimum, rules)
        return {"ok": "missing", "near": "doubtful", "fails": "fails"}[top], top == "near", False
    low = income if net_known == "yes" else income - debts
    high = income - debts if net_known == "no" else income
    top = below(high, minimum, rules)
    if top != "ok":  # whole range below the minimum
        return ("doubtful", True, False) if top == "near" else ("fails", False, False)
    if low >= minimum:
        return ("doubtful" if net_known == "unknown" and debts > 0 else "ok"), False, True
    return "doubtful", False, False  # straddles the minimum


def generate(seed, rules):
    rnd = random.Random(seed)
    name, alone = rnd.choice(NAMES)
    chat_id = f"{name}{seed}"
    buyers = rnd.choice([1, 2])
    pick = lambda: rnd.random() < 0.75  # each field is stated 3 times out of 4
    f = {}
    s = [f"Hola, soy {name.capitalize()}."]
    s.append(f"Compro {alone}." if buyers == 1 else "Somos mi pareja y yo.")
    f["compradores"] = {"status": "ok", "value": buyers}
    zona = rnd.choice(CITIES) if pick() else None
    weeks = rnd.choice([2, 8, 13, 13, 26, 26]) if pick() else None
    ages = [rnd.randint(25, 70) for _ in range(buyers)] if pick() else None
    job = rnd.choice(JOBS) if buyers == 1 and pick() else None
    income = rnd.randrange(1600, 4600, 100) if pick() else None
    debts = rnd.choice([0, 0, 150, 300, 450]) if pick() else None
    net_known = rnd.choice(["yes", "unknown"]) if income and debts else "unknown"
    savings = rnd.randrange(12000, 40000, 500) if pick() else None
    audio = rnd.random() < 0.2
    v = (lambda one, many: many if buyers > 1 else one)  # verb for one or two buyers
    if zona:
        s.append(f"{v('Busco', 'Buscamos')} en {zona}.")
    if weeks:
        s.append(f"{v('Querría mudarme', 'Querríamos mudarnos')} {WEEKS[weeks]}.")
    if ages:
        s.append(f"Tengo {ages[0]} años." if buyers == 1 else f"Tenemos {ages[0]} y {ages[1]} años.")
    if job:
        s.append(f"Trabajo en {job}.")
    if income:
        s.append(f"{v('Gano', 'Ganamos')} {euros(income)} € netos al mes" + (", ya descontadas las deudas." if net_known == "yes" else "."))
    if debts is not None:
        s.append(f"No {v('tengo', 'tenemos')} deudas." if debts == 0 else f"{v('Pago', 'Pagamos')} {debts} € al mes de un préstamo.")
    if savings:
        s.append(f"{v('Tengo', 'Tenemos')} {euros(savings)} € ahorrados.")
    f["zona"] = {"status": "ok", "value": zona} if zona else {"status": "missing"}
    f["plazo"] = {"status": "ok"} if weeks else {"status": "missing"}
    f["edad"] = {"status": "ok", "value": ages} if ages else {"status": "missing"}
    f["empleo"] = {"status": "ok"} if job else {"status": "missing"}
    f["ingresos"] = {"status": "ok", "value": {"min": income, "max": income}} if income else {"status": "missing"}
    f["deudas"] = {"status": "ok", "value": debts} if debts is not None else {"status": "missing"}
    f["ahorro"] = {"status": "ok", "value": savings} if savings else {"status": "missing"}
    order = ["zona", "plazo", "compradores", "edad", "empleo", "ingresos", "deudas", "ahorro"]
    net, near, clear = net_status(income, debts, net_known, rules)
    checks = [below(savings, rules["min_savings"], rules) if savings else "ok",
              below(weeks, rules["min_weeks_to_move"], rules) if weeks else "ok"]
    near = near or "near" in checks
    old_age = bool(ages) and max(ages) > rules["advisor_review_age"]
    if net == "fails" or "fails" in checks:
        fit = "no_fit"
    else:
        fit = "fits" if clear and savings else "needs_data"
    expected = {
        "_note": f"Generated by tools/gen_chat.py --seed {seed}",
        "fields": {k: f[k] for k in order},
        "income_net_of_debts": net_known,
        "net_income_status": net,
        "fit": fit,
        "reply_kind": {"fits": "offer", "needs_data": "ask_info", "no_fit": "decline"}[fit],
        "review": "full" if fit == "no_fit" or audio or near or old_age else "normal",
    }
    if old_age:
        expected["must_not_contain"] = ["edad"]
    cut = rnd.randint(1, len(s))  # split the sentences into two client messages
    texts = [" ".join(s[:cut]), " ".join(s[cut:])]
    texts = [t for t in texts if t] + (["[audio 0:45]"] if audio else [])
    hour, minute = rnd.randint(9, 20), rnd.randint(0, 40)
    lines = [f"[cliente][2026-11-14T{hour:02d}:{minute + i * 2:02d}][{t}]" for i, t in enumerate(texts)]
    return chat_id, "\n".join(lines) + "\n", expected


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", default="data/chats")
    args = ap.parse_args()
    chat_id, text, expected = generate(args.seed, load_rules())
    out = Path(args.out)
    exp_dir = out.parent / "expected"
    out.mkdir(parents=True, exist_ok=True)
    exp_dir.mkdir(parents=True, exist_ok=True)
    (out / f"{chat_id}.txt").write_text(text, encoding="utf-8")
    (exp_dir / f"{chat_id}.json").write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{out / chat_id}.txt  fit={expected['fit']} reply={expected['reply_kind']} review={expected['review']}")


if __name__ == "__main__":
    main()
