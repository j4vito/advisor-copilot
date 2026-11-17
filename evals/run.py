"""python -m evals.run [--mock] [--fresh] [--jobs N] [chat_id ...]

Runs `extract` on every chat and compares with its expected file. If `app.rules` exists,
also runs `analyze`, `draft` and `check_draft`, checks `must_not_contain` against the reply,
and makes no draft when the expected file says `no_draft`. Exit code 1 if anything fails.

With a key it calls the model (answers cached in data/cache/). Without one it uses the
recorded real answers in data/cache/, then the mock.
"""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
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
        self.recorded = False
        self.note = ""

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
    ("max_chars", "max_chars"),
    ("must_not_contain", "must_not_contain"),
    ("no_draft", "no_draft"),
]


def run_case(chat, expected, rules) -> Case:
    from app.llm import draft, extract

    extraction = extract(chat)
    case = Case(extraction["chat_id"])
    case.recorded = bool(extraction.get("recorded"))
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

    messages = chat["messages"] if isinstance(chat, dict) else chat.messages
    last = messages[-1] if messages else None
    last_sender = (last["sender"] if isinstance(last, dict) else getattr(last, "sender", None)) if last else None
    if expected.get("no_draft"):
        # CONTRACTS 11.9: libeen wrote last, nothing to answer, no draft call is spent.
        case.check("no_draft", "no_draft (último mensaje de libeen)", "libeen", last_sender)
        case.note = "sin borrador"
        return case

    reply = draft(chat, analysis, config)
    if reply.get("mock_placeholder"):
        return case
    for check in check_draft(reply, analysis, config):
        category = "max_chars" if check["name"] == "max_chars" else "checks"
        case.check(category, f"check {check['name']}", "ok", check.get("detail") or "failed", ok=check["ok"])
    text = "\n\n".join(b["text"] for b in reply["blocks"])
    for word in expected.get("must_not_contain", []):
        case.check("must_not_contain", f"must_not_contain «{word}»", "ausente", "aparece en el borrador",
                   ok=word.lower() not in text.lower())
    case.note = f"{reply['reply_kind']}, {len(text)} car."
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
    parser.add_argument("--mock", action="store_true", help="no model calls even with a key: recorded answers, then mock")
    parser.add_argument("--fresh", action="store_true", help="with a key: ignore stored answers and call the model again")
    parser.add_argument("--jobs", type=int, default=4, help="chats in parallel (default 4)")
    args = parser.parse_args(argv)

    import os

    from app.llm import cache, settings

    if args.mock:
        os.environ["LIBEEN_MOCK"] = "1"
    live = settings.live()
    if args.fresh and not live:
        print("--fresh necesita API key: sin ella se borrarían las respuestas grabadas.", file=sys.stderr)
        return 2

    mode = f"modelo {settings.model()}" if live else "sin API key: respuestas grabadas, si no modo simulado"
    source, cases = samples.cases()
    rules = load_rules()
    print(f"Evals: {source}, {mode}, reglas {'sí' if rules else 'no (app.rules no existe)'}\n")

    def chat_id_of(chat):
        return chat["chat_id"] if isinstance(chat, dict) else chat.chat_id

    selected = [(c, e) for c, e in cases if not args.chat_ids or chat_id_of(c) in args.chat_ids]

    def one(item):
        chat, expected = item
        if args.fresh:
            cache.drop(chat_id_of(chat), "extraction")
            cache.drop(chat_id_of(chat), "draft")
        try:
            return run_case(chat, expected, rules)
        except Exception as exc:  # one broken chat must not hide the others
            case = Case(chat_id_of(chat))
            case.failures.append(f"error: {type(exc).__name__}: {exc}")
            return case

    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        results = list(pool.map(one, selected))

    for case in results:
        if case.skipped:
            print(f"SKIP {case.chat_id:<14} {case.skipped}")
            continue
        passed, total = sum(case.tally.values()), sum(case.total.values())
        extra = ", ".join(x for x in [case.note, "grabada" if case.recorded else ""] if x)
        print(f"{'PASS' if not case.failures else 'FAIL'} {case.chat_id:<14} {passed}/{total}" + (f"  ({extra})" if extra else ""))
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
