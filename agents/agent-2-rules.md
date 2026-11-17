# Agent 2: rules core

Read `CONTRACTS.md` first (sections 1, 4, 5, 6 and 10). You own: `app/rules/`, `tests/rules/`.

## Goal

All the deciding in the product, as pure Python. No model, no network, no clock. Same input, same output. Every threshold and ratio comes from `config/rules.yaml`.

## Build

1. `load_config(path="config/rules.yaml")`: loads and validates the file. A missing or wrong key fails at start with a clear message.

2. `analyze(extraction, config) -> Analysis`: exactly as CONTRACTS section 5. In particular:
   - the nine rows, always, in config order
   - the `net_income` row with its visible sum and its range logic
   - statuses: rules may add `fails` and may raise `ok` to `doubtful`, never touch `missing`
   - simulation only with enough data, using the low end of net income
   - `fit`, `reply_kind`, `review`, `reasons`
   - `facts`: every number a reply may mention, formatted Spanish style (`204.500 €`)

3. `check_draft(draft, analysis, config) -> list`: the four checks in CONTRACTS section 6. Number matching should tolerate "unos 204.500 €" and "204.500 euros" but reject a number that is in no fact.

4. `inbox_sort(items)`: order from CONTRACTS section 5 (waiting chats first, best fit first, then longest wait).

5. A small formatter for Spanish numbers and euros, used for every `display` and fact.

## Test targets

`samples/laura.json`: `analyze(extraction)` must equal `analysis`, and `check_draft(draft, analysis)` must equal `checks`.

Also cover, with your own small extractions:
- Rosa: income 1.400, no savings, 2 weeks, ages with 67. Three rows fail, age is `doubtful` and never `fails`, no simulation, `decline`, `review` full.
- Javier: income 2.000 to 3.000, debts and savings missing. `net_income` is `missing` (range straddles, debts unknown), `needs_data`, `ask_info`, `review` full because of the audio.
- Income exactly at the minimum is `ok`.
- A draft with a number that is in no fact fails `numbers_in_facts`.
- A draft with "aprobados" fails `banned_words`.
- Changing a threshold in the config changes the result with no code change.

## Done when

- `pytest tests/rules` passes.
- No number from the business appears in the code.
- `logs/agent-2.md` is filled in.
