# Advisor copilot: shared contracts

Read this first. Every agent builds against this file and `samples/laura.json`.
If something here blocks you, do not change it on your own: write the problem in your log and pick the closest reading.

## 1. What we are building

A local prototype for the Libeen technical test (AI Product Engineer).
A sales advisor opens one page and sees, for each WhatsApp chat:

1. The chat, with highlights showing where each extracted value comes from.
2. A fixed table (the "ficha") with the same rows in the same order for every chat.
3. A simulation, when there is enough data.
4. One proposed reply. The advisor approves it. Nothing is sent without approval.

Principles, in order:

- The advisor only decides. Save typing and reading.
- The model reads and writes text. Rules decide. Rules live in `config/rules.yaml`, never in code.
- When the model is wrong or data is missing, the system says so. It never guesses.
- Small and working beats big and half done. Total budget for the whole project is about 4 hours.

Test rules that bind everyone: invented data only, no secrets in the repo, code in Python that starts from the README at the first try.

## 2. Stack and layout

Python 3.11+, FastAPI, one plain HTML page with vanilla JS. No build step, no database, no frontend framework.
Code and identifiers in English. Everything the advisor reads is in Spanish.

```
config/rules.yaml        shared, do not edit without asking
samples/laura.json       shared sample of every object in this file
data/chats/*.txt         agent 1
data/expected/*.json     agent 1
tools/                   agent 1
app/chats.py             agent 1 (parser, used by everyone)
app/rules/               agent 2
tests/rules/             agent 2
app/llm/                 agent 3
evals/                   agent 3
app/server.py, web/      agent 4
data/cache/, data/log.jsonl   written at runtime, git-ignored
logs/agent-N.md          each agent, see section 10
.env.example             agent 3
```

Only touch your own paths.

## 3. Chat file

One file per conversation: `data/chats/<chat_id>.txt`. The display name is the file name with a capital letter (`laura.txt` is "Laura").

One message per line:

```
[sender][timestamp][message]
```

- `sender`: `cliente` or `libeen`.
- `timestamp`: ISO local time to the minute, `2026-11-14T10:02`.
- `message`: everything between the third `[` and the last `]` of the line. Brackets inside the message are fine.
- A line break inside a message is the two characters `\n`. The parser turns them into real line breaks.
- Attachments are written inside the message as `[audio 1:12]`, `[imagen]`, `[documento]`.
- The message index is the line number, starting at 0.

Regex: `^\[(cliente|libeen)\]\[([^\]]+)\]\[(.*)\]$`

Example:

```
[cliente][2026-11-14T10:11][Unos 3.800 € netos entre los dos. Ahorrado tenemos 18.000 más o menos. Yo tengo 31 y él 34.]
[cliente][2026-11-14T10:33][[audio 1:12]]
```

`app/chats.py` exposes:

```python
parse_chat(path) -> Chat            # chat_id, name, messages[{index, sender, ts, text}]
append_message(path, sender, text)  # adds one line with the current time
```

## 4. Extraction (model output, agent 3)

`extract(chat) -> Extraction`

```json
{
  "chat_id": "laura",
  "fields": {
    "<key>": {"value": <typed or null>, "status": "ok|doubtful|missing", "quotes": [{"msg": 2, "text": "3.800 € netos"}], "note": ""}
  },
  "income_net_of_debts": "yes|no|unknown",
  "open_questions": [{"msg": 3, "text": "no sé si cuenta"}],
  "attachments": [{"msg": 3, "kind": "audio", "label": "Audio de 1:12"}],
  "special_requests": [{"msg": 1, "kind": "rent_only|written_approval|other", "text": "..."}]
}
```

The eight fields, always all present, always in this order:

| key | label (UI) | value type |
|---|---|---|
| `zona` | Zona | string |
| `plazo` | Plazo | `{"text": "antes del verano", "weeks": 30}`, `weeks` null if unclear |
| `compradores` | Compradores | int |
| `edad` | Edad | list of int |
| `empleo` | Empleo | list of string |
| `ingresos` | Ingresos declarados | `{"min": 2000, "max": 3000}` euros per month, min = max for one number |
| `deudas` | Deudas | number, euros per month |
| `ahorro` | Ahorro | number, euros |

Status set by the model, about what was said and nothing else:

- `ok`: the client stated it clearly.
- `doubtful`: stated but vague, a range, or contradictory.
- `missing`: not stated. `value` is null and `quotes` is empty.

The model never judges whether a value is good enough. That is the rules' job.

Quote check, in code, after the model answers: each quote `text` must be an exact substring of message `msg`. If it is not, drop the quote. If a field with a value ends up with no valid quote, set its status to `doubtful` and its note to "Sin cita en el chat".

`income_net_of_debts`: whether the declared income already subtracts the debts. `unknown` when the client does not make it clear.

## 5. Analysis (rules output, agent 2)

`analyze(extraction, config) -> Analysis`. Pure code, no model, deterministic.

```json
{
  "rows": [{"key": "zona", "n": 1, "label": "Zona", "display": "Valencia", "status": "ok", "note": "", "group": null}],
  "counts": {"ok": 6, "doubtful": 1, "missing": 1, "fails": 0},
  "alerts": {"open_questions": [...], "attachments": [...], "special_requests": [...]},
  "simulation": {"max_price": 204500, "limited_by": "savings", "monthly_payment": 1317, "monthly_savings": 395, "price_end": 236700} ,
  "fit": "fits|needs_data|no_fit",
  "reply_kind": "offer|ask_info|decline",
  "review": "normal|full",
  "reasons": ["Cumple ingresos y ahorro", "..."],
  "facts": {"sim.max_price": "204.500 €", "rule.min_income": "2.200 €", "...": "..."}
}
```

Rows: the eight fields plus one computed row, nine in total, always in this order:
zona, plazo, compradores, edad, empleo, ingresos, deudas, **net_income**, ahorro.

Row statuses: `ok`, `doubtful`, `missing` come from the extraction. Rules can add `fails`, and can raise `ok` to `doubtful`. Rules never turn `missing` into anything else.

The `net_income` row ("Ingresos tras deudas"):

- `display` is the visible sum: `"3.800 − 250 = 3.550 €"`. With unknown debts: `"1.400 − ? = "` and no result.
- `group: "calc"` on the rows `ingresos`, `deudas` and `net_income`, so the page can draw them as one joined block.
- Net income is a range. Low end: income min minus debts (when `income_net_of_debts` is `no` or `unknown`). High end: income max (minus debts only when `no`).
- Compare with `min_net_income`: whole range below is `fails`, whole range at or above is `ok`, straddling is `doubtful`.
- Debts missing: if income max is below the minimum the row `fails` (it fails even before debts), otherwise it is `missing`.
- `income_net_of_debts` unknown and debts above 0: status is at least `doubtful`, and the note says whether the doubt changes the outcome.

Other rules:

- `ahorro` below `min_savings`: `fails`, note "Mínimo: 15.000 €".
- `plazo.weeks` below `min_weeks_to_move`: `fails`.
- Any age above `advisor_review_age`: `doubtful`, note "Lo decide el asesor". Age never produces `fails`.
- Notes are short, six words or so, in Spanish.

Simulation: only when net income and savings have values. Uses the low end of net income. Formulas, with ratios from config:

```
by_savings = savings / savings_to_price
by_income  = effort_max * net_income * 12 / annual_payment_ratio
max_price  = floor_to_100(min(by_savings, by_income)); limited_by says which one won
monthly_payment = max_price * annual_payment_ratio / 12
monthly_savings = monthly_payment * savings_share
price_end = floor_to_100(max_price * (1 + price_growth) ** years)
```

Decision:

- `fit`: `no_fit` if any row fails. `fits` if net income and savings are both `ok` or `doubtful` with a value and nothing fails. Otherwise `needs_data`.
- `reply_kind`: `no_fit` gives `decline`, `fits` gives `offer`, `needs_data` gives `ask_info`.
- `review`: `full` if `no_fit`, or there is any special request, or any attachment. Otherwise `normal`.

`facts`: every number the draft is allowed to mention, already formatted in Spanish style (`204.500 €`), keyed by where it comes from (`field.ahorro`, `sim.max_price`, `rule.min_income`, and so on).

Inbox order, `inbox_sort(items)`: chats whose last message is from `cliente` first. Among them, best fit first (`fits`, `needs_data`, `no_fit`), then longest waiting first.

## 6. Draft (model output, agent 3)

`draft(chat, analysis, config) -> Draft`

```json
{
  "reply_kind": "offer",
  "blocks": [{"label": "Responde a su pregunta", "text": "..."}],
  "key_spans": [{"block": 1, "text": "204.500 €", "ref": "sim.max_price"}]
}
```

- The model does not choose `reply_kind`. It receives it from the analysis.
- Blocks, in order: answer every open question first, then the main message for the kind, then the next step.
- `key_spans` mark the strings that matter in the reply: every number and the actual decision (for example "no podemos ofreceros una casa"). Each `text` must be an exact substring of its block. `ref` is a key of `facts`, or `"decision"`. The page draws a rounded dotted box around each one.
- The text sent to the client is the blocks joined by blank lines.

`check_draft(draft, analysis, config) -> [{"name", "ok", "detail"}]` (agent 2, pure code):

1. No banned word from config (`aprobado`, `aprobados`, `garantizado`...).
2. Every number in the text equals a value in `facts`.
3. Every key span is a substring of its block and its `ref` exists.
4. `offer` drafts contain the "orientativo" disclaimer.

A failed check does not block the page. It shows a warning next to the draft.

## 7. Model

- Anthropic API, Claude Haiku. Model id from the env var `ANTHROPIC_MODEL`, default `claude-haiku-5-5`. Key from `ANTHROPIC_API_KEY` in `.env`. Check the current Anthropic docs for the exact call for structured output.
- Two calls per chat: extract, then draft (after the rules decided).
- No key in the env: mock mode. `extract` and `draft` return fixed answers for the sample chats and a clear "modo simulado" marker for the rest. The mock sits in one obvious place.
- Results are cached in `data/cache/<chat_id>.json`, keyed by a hash of the chat file. Recompute only when the file changes.

## 8. HTTP (agent 4)

```
GET  /                         the page
GET  /api/inbox                [{chat_id, name, fit, reasons, waiting_minutes, last_sender}] already sorted
GET  /api/chats/{id}           {chat, extraction, analysis, draft, checks}
POST /api/chats/{id}/approve   {text, edited}  appends a libeen message to the chat file and one line to data/log.jsonl
```

Log line: `{ts, chat_id, reply_kind, edited, checks_failed, text}`.

## 9. Out of this version

Tone buttons ("más corta", "más cercana"), a second reply option, correcting a field from the page, audio transcription, real WhatsApp. Do not build them. If you finish early, improve tests.

## 10. Your log

Keep `logs/agent-N.md` as you work. Short entries, honest, one per decision or problem:

```
## 20:15 Parser regex
Asked: parser for the chat format.
Did: regex from CONTRACTS section 3.
Changed after review: messages ending in "]" were cut. Fixed with a greedy match, added a test.
Open doubt: none.
```

The log is part of the delivery. The test asks how the work with AI was done.

## 11. Round 2 changes (2026-11-16)

These come from reading the real model output for the 13 chats. Where this section and an earlier one disagree, this one wins. New config keys are already in `config/rules.yaml`, and `samples/laura.json` already has the two new analysis keys.

**11.1 An offer needs a clear income.** `fits` now requires the low end of net income to be at or above the minimum. If the net income range straddles the minimum, `fit` is `needs_data` and the reply asks for the income first. (Pablo was offered a simulation on 2.100 €, which is below the minimum.)

**11.2 Near miss.** A value below a minimum but within `near_miss_pct` of it is `doubtful`, not `fails`, with the note "Casi llega: mínimo 15.000 €". It sets `review` to `full`. The advisor decides. (Elena was declined for 100 €.)

**11.3 Gross or unusable income.** `ingresos` doubtful with no value: the net income row is `doubtful`, display `"? − 0 = "`, note "Falta el neto mensual". `fit` is `needs_data`.

**11.4 Notes on the net income row.** A failing row always carries "Mínimo: 2.200 €". "Marca el límite de precio" appears only when `fit` is `fits`.

**11.5 No simulation for `no_fit`.** `simulation` is null and no `sim.*` facts exist.

**11.6 Age.** Any age above `advisor_review_age` sets `review` to `full`. Age is for the advisor only: the `edad` row is never sent to the draft model (`draft.hidden_fields`) and a reply never mentions it (`draft.internal_terms`, a fifth check named `internal_terms`).

**11.7 Two new analysis keys.**
- `ask_for`: ordered list of field keys the reply should ask for. Only for `ask_info`. Fields that are missing, or doubtful in a way that blocks the decision, in `draft.ask_priority` order, cut to `draft.max_questions`. Empty for `offer` and `decline`.
- `client_reasons`: only for `decline`. One entry per failing row: `{"key": "ahorro", "text": "Ahorro de 0 €, mínimo 15.000 €", "refs": ["field.ahorro", "rule.min_savings"]}`. Empty otherwise.

**11.8 Draft rules.**
- `ask_info`: asks only for the fields in `ask_for`.
- `decline`: gives only the reasons in `client_reasons`. No invented reasons. It does not ask the client for more data.
- `offer`: mentions only the facts in `draft.offer_facts`. The next step is to propose a short call. Other missing fields wait for the call.
- A snippet is used only when the client asked that question or made that request.
- A doubtful value is not stated as a fact.
- Stay under `draft.max_chars`.

**11.9 Nothing to answer.** When the last message is from `libeen`, no draft is made and no draft call is spent. `GET /api/chats/{id}` returns `"draft": null, "checks": []`. The panel shows "Esperando respuesta del cliente" in the reply block.

**11.10 Recorded answers.** With no API key, `extract` and `draft` first look for a recorded real answer for that exact chat content in `data/cache/`, and use it, marked `"recorded": true`. Only when there is none do they fall back to the mock. `data/cache/` is committed to the repo, so someone with no key sees the real output for all 13 chats.

**11.11 Expected files** may carry `"must_not_contain": ["edad"]` (strings that must not appear in the draft) and `"no_draft": true`.
