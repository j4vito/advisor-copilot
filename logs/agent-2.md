# Agent 2: rules core (2026-11-15)

## 20:40 Setup
Asked: rules core in pure Python, PyYAML + pytest.
Did: system Python is 3.14.5 without pytest, so I made a venv at `.venv` and installed `pyyaml pytest` there. Created an empty `app/__init__.py` (did not exist). Run tests with `.venv/bin/python -m pytest tests/rules`.
Open doubt: Agent 1 may want the same venv; it is shared, nothing project-specific in it.

## 20:45 Config loader
Asked: `load_config` that fails at start on a missing or wrong key.
Did: `app/rules/config.py` checks required sections and keys, numeric types, positive ratios and the exact field order. A relative path that does not exist from the cwd falls back to the project root. Errors name the key (`qualification.min_savings`).
Open doubt: none.

## 20:50 Net income row
Asked: computed row with visible sum and range logic (CONTRACTS 5).
Did: low = income min − debts (unless `yes`), high = income max (− debts only when `no`). The display always shows the arithmetic on both ends (`3.800 − 250 = 3.550 €`); for a range `2.000 a 3.000 − 250 = 1.750 a 2.750 €`; with `yes`, `3.800 € (deudas ya descontadas)`. Note when `unknown` and debts > 0: `Si ya lo descontó: <income>. <Encaja igual | No llega igual | Sigue en duda | Cambia el resultado>`, the first wording forced by the Laura sample, the others mine. A doubtful `ingresos` or `deudas` raises an `ok` net income to `doubtful`.
Open doubt: the contract says debts missing gives `missing` even when `income_net_of_debts` is `yes`. I followed it literally, though with `yes` the debts arguably do not matter.

## 20:55 Notes, facts and reasons forced by the sample
Did: matched `laura.json` exactly. Things the sample decided for me:
- `ahorro` note "Marca el límite de precio" goes on the row that limits the simulation (ahorro for savings, net_income for income) only when that row has no other note.
- facts: `field.net_income` is the low end only (Laura's high end 3.800 is not a separate fact). No facts for compradores, edad or plazo weeks. For an income range I added `field.ingresos_min` / `field.ingresos_max`.
- reasons for `fits`: "Cumple ingresos y ahorro" then "Quiere mudarse <plazo text>". For `no_fit` and `needs_data` I wrote my own short reasons ("Ingresos por debajo del mínimo", "Falta saber deudas y ahorro"), plus "Edad: lo decide el asesor" when it applies.
- plazo display capitalises the first letter of the text ("Antes del verano").
Open doubt: none.

## 21:00 Simulation rounding
Did: all money math in `Decimal` from the config values as strings, so `floor_to_100` cannot fall one step short from float error. `monthly_payment` and `monthly_savings` are rounded half up to whole euros (contract does not say; floor gives the same Laura numbers). `monthly_savings` uses the unrounded payment. by_income is clamped at 0 when net income is negative.
Open doubt: rounding of the monthly numbers is my choice.

## 21:05 check_draft
Did: four checks in contract order. Banned words matched as whole words, case-insensitive. Numbers parsed Spanish style (dot thousands, comma decimal) from both the text and the fact strings, compared as values, so "unos 204.500 €" and "204.500 euros" pass and "250.000 €" fails. Offer disclaimer decided by `draft.reply_kind`. Details are short Spanish strings, empty when ok. `max_chars` is not checked (not one of the four).
Open doubt: a number like "1:12" or a date in a draft would be split and may fail `numbers_in_facts`; acceptable for now.

## 21:10 Tests
Did: 27 tests in `tests/rules`: Laura analysis and checks equal the sample, Rosa (three fails, age doubtful, decline, full review), Javier (net income missing, ask_info, full because of audio), income exactly at the minimum is ok, unknown number, banned word, bad key spans, disclaimer, config change (min income and savings ratio) changes the result, config errors, inbox order, formatter. All pass. Grepped `app/rules` for numeric literals: only structural ones and 12 months per year.
Open doubt: none.

# Round 2 (2026-11-16)

## 2026-11-16 Bugs from real data
Asked: marta7 failing row said "Marca el límite de precio", rosa failing row had no note, pablo got an offer on 2.100 to 2.500 €, carmen's gross income became a `missing` net row.
Did: a failing net income row always carries "Mínimo: 2.200 €" (from config). "Marca el límite de precio" only when `fit` is `fits`. `fits` now needs the low end of net income at or above the minimum, so pablo is `needs_data` and asks for `ingresos`. A doubtful `ingresos` with no value is kept as doubtful (before, my loader turned any null value into `missing`), and the net row is doubtful with `? − 0 = ` and "Falta el neto mensual". I checked this by running the cached real model output for the 13 chats through Agent 3's `finish()` and my `analyze`.
Open doubt: none.

## 2026-11-16 Near miss (11.2)
Did: a value below a minimum but within `near_miss_pct` is `doubtful`, note "Casi llega: mínimo X", `review` full. This covers savings, weeks and the high end of net income.
Open doubt: a near-miss savings value (Elena, 14.900 €) still gives `fits` and an offer with full review, because 11.1 only tightens income. A near-miss income gives `needs_data`, because 11.1 says the low end must reach the minimum, so the reply asks to confirm income. These two cases behave differently. I followed the text literally.

## 2026-11-16 Simulation, facts, age
Did: no simulation and no `sim.*` facts for `no_fit`. Any age above `advisor_review_age` sets `review` full. With `income_net_of_debts: yes`, debts no longer matter and the net row uses the income as is (my round 1 doubt, now changed as asked). Loose shapes from the model are tolerated: a bare number for `ingresos`, a bare string for `plazo`.
Open doubt: `needs_data` still gets a simulation when net income and savings have values (pablo). 11.5 only removes it for `no_fit`. The draft for `ask_info` could then see `sim.*` facts. One option is to show the simulation only when `fit` is `fits`.

## 2026-11-16 ask_for and client_reasons (11.7)
Did: `ask_for` takes missing fields, plus `ingresos` when net income is unclear or below the minimum, and `deudas`/`ahorro` when doubtful with no value. It drops `deudas` when the income is already net, follows `ask_priority`, removes `hidden_fields` and is cut to `max_questions`. It is only filled for `ask_info`. `client_reasons` has one entry per failing row, in table order, with numbers taken from facts. To make every number in a reason a fact, I add `field.net_income_max` (only when a net range fails) and `field.plazo_weeks` (only when plazo fails). Laura's facts are unchanged.
Open doubt: what "blocks the decision" means is my own reading. Missing non-money fields such as `empleo` are included (pablo asks `ingresos, empleo`).

## 2026-11-16 Checks 5 and 6, config
Did: `internal_terms` (whole word, case-insensitive) and `max_chars` (on the blocks joined by blank lines) added as checks 5 and 6. `load_config` validates `near_miss_pct` (0 to 1), `max_questions`, `ask_priority` and `hidden_fields` (must be known fields), `internal_terms` and `offer_facts` (lists of strings).
Open doubt: `samples/laura.json` `checks` lists only four. The coordinator said to take the closest reading: `check_draft` returns six, and the sample test asserts the first four equal the sample and the last two are ok. `offer_facts` is validated but not enforced by any check, because the brief asks for none.

## 2026-11-16 Tests
Did: 53 tests in `tests/rules` pass (new: pablo, carmen, elena, near-miss income and weeks, marta7, age 62 fits with full review, debts ignored with `yes`, `ask_for` order/cut/config, `client_reasons` only from failing rows and passing the number check, `edad` in a draft, too long draft, new config keys). `tests/llm tests/server`: 39 pass. Whole `tests/`: 128 pass. Public names and signatures unchanged; `ask_for` and `client_reasons` are new keys.
Open doubt: `data/expected/` for elena and pablo still has round 1 values (`no_fit` and `fits`). Agent 1 is updating them.
