# Agent 2, round 2

Read CONTRACTS section 11 first. Same paths as before. Add to `logs/agent-2.md`.

Bugs found with real data:
- `marta7`: net income 1.800 € fails but its note says "Marca el límite de precio". `rosa`: the failing net income row has no note. Fix per 11.4.
- `pablo`: offered on a net income of 2.100 to 2.500 €. Fix per 11.1.
- `carmen`: gross income ends as a `missing` net row. Fix per 11.3.

Build:
1. 11.1 to 11.6 in `analyze`. The near miss applies to income, savings and weeks.
2. `ask_for` and `client_reasons` (11.7). `samples/laura.json` already has both as empty lists, so the sample test tells you the shape.
3. `facts`: no `sim.*` facts when there is no simulation.
4. `check_draft`: a fifth check `internal_terms` (11.6), whole word, case-insensitive. Also check `max_chars` as a sixth check named `max_chars`.
5. `load_config`: validate the new keys (`near_miss_pct`, `max_questions`, `ask_priority`, `hidden_fields`, `internal_terms`, `offer_facts`).
6. Your log said debts missing gives `missing` even when `income_net_of_debts` is `yes`. Change it: with `yes`, debts do not matter and the net row uses the income as is.

Tests to add: Pablo, Carmen, Elena (near miss), an age of 62 with a good income (fits, review full), a draft that says "edad", `ask_for` order and cut, `client_reasons` only from failing rows.

Done when `pytest tests/rules` passes, including the sample test.
