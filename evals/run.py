"""python -m evals.run [--mock] [--fresh] [chat_id ...]

Runs `extract` on every chat and compares with its expected file. If `app.rules` exists,
also runs `analyze`, `draft` and `check_draft`. Exit code 1 if anything fails.
"""

import argparse
import shutil
import sys
import unicodedata
from collections import Counter

from evals import samples


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def matches(expected, got) -> bool:
    """Lenient where the wording may differ, exact for numbers.
    Dicts: only the keys the expected file gives. Strings: expected contained in got,
    ignoring case and accents. Lists of numbers: same items in any order."""
    if isinstance(expected, dict):
        return isinstance(got, dict) and all(matches(v, got.get(k)) for k, v in expected.items())
    if isinstance(expected, str):
        return isinstance(got, str) and _norm(expected) in _norm(got)
    if isinstance(expected, list):
        if not isinstance(got, list) or len(expected) != len(got):
            return False
        if all(isinstance(x, (int, float)) for x in expected + got):
            return sorted(expected) == sorted(got)
        return all(matches(e, g) for e, g in zip(expected, got))
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return isinstance(got, (int, float)) and not isinstance(got, bool) and float(expected) == float(got)
    return expected == got


class Case:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.tally = Counter()  # category -> passed
        self.total = Counter()  # category -> checked
        self.failures = []
        self.skipped = ""

    def check(self, category, label, expected, got, ok=None):
        self.total[category] += 1
        ok = matches(expected, got) if ok is None else ok
        if ok:
            self.tally[category] += 1
        else:
            self.failures.append(f"{label}: expected {expected!r}, got {got!r}")


CATEGORIES = [
    ("status", "Field status"),
    ("value", "Field value"),
    ("net_of_debts", "income_net_of_debts"),
    ("net_income", "net_income_status"),
    ("fit", "fit"),
    ("reply_kind", "reply_kind"),
    ("review", "review"),
    ("checks", "Draft checks"),
]


def run_case(chat, expected, rules) -> Case:
    from app.llm import draft, extract

    extraction = extract(chat)
    case = Case(extraction["chat_id"])
    if extraction.get("mock_placeholder"):
        case.skipped = "modo simulado, sin respuesta fija para este chat"
        return case
    if expected is None:
        case.failures.append("no expected file")
        return case

    for key, exp in expected.get("fields", {}).items():
        got = extraction["fields"][key]
        case.check("status", f"{key}.status", exp["status"], got["status"])
        if "value" in exp:
            case.check("value", f"{key}.value", exp["value"], got["value"])
    if "income_net_of_debts" in expected:
        case.check("net_of_debts", "income_net_of_debts", expected["income_net_of_debts"], extraction["income_net_of_debts"])

    if rules is None:
        return case
    load_config, analyze, check_draft = rules
    config = load_config()
    analysis = analyze(extraction, config)
    net_row = next(r for r in analysis["rows"] if r["key"] == "net_income")
    for category, label, got in [
        ("net_income", "net_income_status", net_row["status"]),
        ("fit", "fit", analysis["fit"]),
        ("reply_kind", "reply_kind", analysis["reply_kind"]),
        ("review", "review", analysis["review"]),
    ]:
        if label in expected:
            case.check(category, label, expected[label], got)

    reply = draft(chat, analysis, config)
    if reply.get("mock_placeholder"):
        return case
    for check in check_draft(reply, analysis, config):
        case.check("checks", f"check {check['name']}", "ok", check.get("detail") or "failed", ok=check["ok"])
    return case


def load_rules():
    try:
        from app.rules import analyze, check_draft, load_config
    except ImportError:
        return None
    return load_config, analyze, check_draft


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("chat_ids", nargs="*", help="only these chats")
    parser.add_argument("--mock", action="store_true", help="force mock mode even with a key")
    parser.add_argument("--fresh", action="store_true", help="delete data/cache first")
    args = parser.parse_args(argv)

    import os

    from app.llm import settings

    if args.mock:
        os.environ["LIBEEN_MOCK"] = "1"
    if args.fresh and settings.CACHE_DIR.exists():
        shutil.rmtree(settings.CACHE_DIR)

    mode = f"modelo {settings.model()}" if settings.api_key() else "modo simulado (sin API key)"
    source, cases = samples.cases()
    rules = load_rules()
    print(f"Evals: {source}, {mode}, reglas {'sí' if rules else 'no (app.rules no existe)'}\n")

    results = []
    for chat, expected in cases:
        chat_id = chat["chat_id"] if isinstance(chat, dict) else chat.chat_id
        if args.chat_ids and chat_id not in args.chat_ids:
            continue
        try:
            case = run_case(chat, expected, rules)
        except Exception as exc:  # one broken chat must not hide the others
            case = Case(chat_id)
            case.failures.append(f"error: {type(exc).__name__}: {exc}")
        results.append(case)

        if case.skipped:
            print(f"SKIP {case.chat_id:<14} {case.skipped}")
            continue
        passed, total = sum(case.tally.values()), sum(case.total.values())
        print(f"{'PASS' if not case.failures else 'FAIL'} {case.chat_id:<14} {passed}/{total}")
        for failure in case.failures:
            print(f"       - {failure}")

    print("\nResumen")
    print(f"  {'check':<22}{'ok':>6}{'total':>7}")
    for category, label in CATEGORIES:
        total = sum(c.total[category] for c in results)
        if total:
            print(f"  {label:<22}{sum(c.tally[category] for c in results):>6}{total:>7}")
    failed = [c.chat_id for c in results if c.failures]
    skipped = [c.chat_id for c in results if c.skipped]
    ran = len(results) - len(skipped)
    print(f"\n  Chats: {ran - len(failed)}/{ran} pasan" + (f", {len(skipped)} saltados (modo simulado)" if skipped else ""))
    if failed:
        print(f"  Fallan: {', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
