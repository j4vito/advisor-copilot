# Agent 1: conversations (2026-11-15)

## 21:03 Setup
Asked: standard library + pytest, Python 3.11+.
Did: system Python is 3.14.5 with no pytest. Created a venv at `.venv` and installed pytest there (did not touch the system Python). Run tests with `.venv/bin/python -m pytest tests/chats`. Created an empty `app/__init__.py` (it did not exist yet).
Open doubt: the README (not mine) should say how to create the venv.

## 21:05 Parser
Asked: `parse_chat(path)` and `append_message(path, sender, text)` from CONTRACTS section 3.
Did: the regex from the contract, used as is. Its `(.*)\]$` is greedy, so brackets inside a message and messages that end in `]` (like `[[audio 1:12]]`) work. The timestamp is also checked against `YYYY-MM-DDTHH:MM`. Bad lines raise `ChatFormatError` (a `ValueError`) with the file name and the 1-based line number. A blank line in the middle counts as a bad line; one trailing newline is fine. `append_message` turns real line breaks into `\n` and adds a newline first if the file does not end with one.
Contract reading: `Chat` is a dataclass (`chat.messages`). It also allows `chat["messages"]` and `to_dict()`, so other agents can use it either way. `ts` is kept as the original string. `index` is the 0-based line number.
Open doubt: a client who literally types backslash-n would get a line break. Accepted, it will not happen in the demo.

## 21:07 The three chats from the test
Did: typed `laura.txt` (same as `samples/laura.json`, a test checks this), `javier.txt` and `rosa.txt`, using the texts from the brief. I invented the timestamps.

## 21:08 Hard cases
Did: one trap per chat, all people and numbers invented:
carmen (gross annual income), pablo (2.500 total vs 1.200 + 900), marcos (prompt injection asking to be approved), elena (savings 14.900), diego (savings 15.100, income already net of a 200 € loan), nuria (`\n` and brackets inside messages; brackets are not attachments), tomas (Libeen wrote last), irene (only asks for information), andres (four buyers, mixed incomes, two ages above 60).

## 21:09 Expected results
Did: `data/expected/<chat_id>.json` with the shape of `expected` in the sample, plus a `_note` key that names the trap (same idea as `_about` in the sample). `fields` hold what the extraction should say (the model's status). `net_income_status`, `fit`, `reply_kind` and `review` come from applying CONTRACTS section 5 and `config/rules.yaml` by hand. A `value` is included only when it is unambiguous.
Open doubts (I picked the closest reading):
- carmen: 34.000 € gross a year has no single correct net monthly figure. Expected: `ingresos` doubtful with no value, `net_income_status` doubtful, so `needs_data` and `ask_info`. Section 5 does not say what the net row does when `ingresos` is doubtful but has no value. If agent 3 puts a gross/12 number in the value, the rules would say `fits`. That would be wrong, and this case is there to catch it.
- pablo: expected `ingresos` doubtful (ideally the range 2.100–2.500), so net straddles 2.200 and is doubtful. The rules still give `fits` and `offer`, because doubtful with a value counts. If the model keeps only 2.500, net would be `ok`.
- rosa: only the husband's age is given. I put `edad` as doubtful with no value. One could argue for `ok` with `[67]`.
- andres: the pension (900 €) is not said to be net. I still counted it in 3.900 with status ok.
- For chats with zero debts, `income_net_of_debts` is `unknown` unless the client says "después de deudas". It does not change the result.
- javier: `zona` "madrid o alrededores" is ok but has no value, because the exact string is a matter of taste.

## 21:10 Generator
Asked: `tools/gen_chat.py --seed N --out data/chats`, about 100 lines.
Did: picks a name, then picks each field with a 3 in 4 chance. It builds sentences from templates (with the verb in singular or plural) and splits them into two client messages, sometimes with an `[audio 0:45]`. It writes the chat and `<out>/../expected/<id>.json`. Rule values are read from `config/rules.yaml` with a small regex (no YAML library, to stay on the standard library). The expected answers apply section 5 in code (`net_status`). Chat id is name + seed, for example `marta7`. The output is about 120 lines.
Changed after review: the first ranges gave mostly `no_fit` (savings under 15.000). I narrowed income and savings. 30 seeds now give 6 fits, 12 needs_data and 12 no_fit. I also made the job sentence neutral ("Trabajo en un taller") because the old one mixed genders.
Kept in data: `marta7` (seed 7) as an example.

## 21:11 Say
Did: `tools/say.py <chat_id> <cliente|libeen> "<text>"` appends one message to an existing chat and prints it back as parsed. It exits with 2 on a bad sender and 1 on an unknown chat. Tried it on a copy of laura, which I then deleted.

## 21:12 Tests
Did: `tests/chats/test_chats.py` (31 tests): parsing, `\n`, brackets, empty message, bad lines with their line number, append then parse, append to a file with no trailing newline, every data chat parses and has a valid expected file, laura matches the sample, the generator is deterministic and 50 seeds parse, `net_status` against the section 5 cases, and say.py. A `conftest.py` puts the project root on `sys.path`.
Result: 31 passed.

# Round 2 (2026-11-16)

## 2026-11-16 Read round 2 brief and CONTRACTS section 11
Asked: update expected files to section 11, add `must_not_contain` and `no_draft`, update the generator, add two hard cases.
Did: re-read `config/rules.yaml` (new `near_miss_pct`, `max_chars` 600, draft keys). I did not change the text of any existing chat. Checked with sha1 before and after: all 13 files are byte-identical, so no cached answer in `data/cache/` goes stale. I did not touch `data/cache/`.

## 2026-11-16 Expected files rechecked against section 11
Did: worked through every chat by hand. Changes:
- pablo: `fits/offer` became `needs_data/ask_info` (11.1, the range 2.100–2.500 straddles the minimum).
- elena: savings 14.900 is at or above 15.000 × 0.97 = 14.550, so it is a near miss, doubtful rather than a fail (11.2). Net income 3.000 is clear, so `fits/offer`, with `review: full` because of the near miss. Added `must_not_contain: ["plazo"]`.
- andres: `empleo` became doubtful. Review became `full` (ages 68 and 66). Added `must_not_contain: ["edad"]`.
- rosa: `must_not_contain: ["zona", "deudas", "edad"]` (the brief's two words plus `edad`, since she is 67). The result is still `no_fit/decline/full`.
- marcos: `must_not_contain: ["aprobado"]`.
- tomas: `no_draft: true` (11.9).
- carmen: no change, still `doubtful` / `needs_data` (11.3 now agrees).
- laura, diego, nuria, irene, javier: no change. Laura still matches `samples/laura.json`.
Open doubt: for elena the brief only said to "work out" the result. Section 5 says doubtful savings with a value counts for `fits`, and 11.1 only adds the income condition, so I gave an offer with full review. A simulation based on 14.900 might look odd to the advisor, but 11.2 says the advisor decides.

## 2026-11-16 Generator
Did: `net_status` now returns `(status, near_miss, clear)`. A new `below()` returns ok, near or fails using `near_miss_pct` from the config. `fits` needs `clear` (the low end of net income at or above the minimum). A near miss on income, savings or weeks gives doubtful, not a fail, and sets `review: full`. Any age above `advisor_review_age` sets `review: full` and adds `must_not_contain: ["edad"]`. Rule values still come from `rules.yaml`.
Kept the order of the random draws unchanged, so `--seed 7` gives a byte-identical `marta7.txt`. I regenerated it: `no_fit/decline/full`, plus `must_not_contain: ["edad"]` (she is 62).
Open doubt: section 11.2 does not cover income in the near-miss band with debts unknown. I used doubtful plus full review, because the declared income is the best case.

## 2026-11-16 Two new hard cases
Did: `alberto` has 2.150 € net after debts (it says so), no debts, 20.000 € savings. 2.150 is at or above 2.134, so it is a near miss and the row is doubtful. The low end is below 2.200, so 11.1 rules out `fits`, and nothing fails, so the result is `needs_data/ask_info/full`. `ramon` is 63, 2.900 € net, no debts, 45.000 € savings: `fits/offer/full`, `must_not_contain: ["edad"]`.
Open doubt: for alberto, the contract's path from a near miss on income goes to `ask_info`, which asks for the income again even though he gave an exact figure. It is the literal reading of 11.1 plus 11.2. The coordinator may prefer `offer` with full review.

## 2026-11-16 Tests and cross-check
Did: the tests now cover `below()`, the new `net_status` cases (2.134 is near, 2.133 fails), that `near_miss_pct` is read from the config, and that age above 60 means full review and `must_not_contain` in generated chats. For every data chat they also check: age above 60 means full review and `edad` in `must_not_contain`, `no_draft` is set exactly when Libeen wrote last, and there are no unknown keys. Result: 36 passed.
Cross-check (read only, in scratch, nothing written): I fed a stand-in extraction built from each expected file into Agent 2's `analyze`. Nine chats match. Six differ, all in the round 2 rules Agent 2 is still adding: near miss (alberto, elena), age means full review (andres, ramon), and income doubtful with no value (carmen, pablo, where the stand-in had no value). To recheck once `app/rules` is finished.

# Round 3 (2026-11-17)

## 2026-11-17 Five new hard cases
Asked: five more chats, one trap each, not already covered by the 15 existing ones.
Did: chose five of the coordinator's suggestions. All people and data are invented.
- `jorge`: corrects his income later ("son 2.000, no 2.600"). The corrected value is unambiguous, so `ingresos` is ok at 2.000. Net 2.000 is below 2.134, so it fails rather than being a near miss. Result `no_fit/decline/full`, `must_not_contain: ["2.600"]` (a decline must not cite the old figure).
- `lucas`: savings that are not cash (5.000 in the bank, a 12.000 car to sell, parents who "will help"). `ahorro` is doubtful with no value, so the result is `needs_data/ask_info/normal`. `must_not_contain: ["17.000"]` catches a reply that adds the car to the cash.
- `sara`: declares 2.500, then says it is before 500 of debts. So `income_net_of_debts` is `no`, net is 2.000 and fails. Result `no_fit/decline/full`.
- `victor`: debts are only "algún préstamo" plus a `[documento]` attachment. `deudas` is doubtful with no value, the net row is doubtful, and the result is `needs_data/ask_info/full` (full because of the attachment).
- `jordi`: the client writes in Catalan. The data is clear: 4.100 net, no debts, 28.000 savings. Result `fits/offer/normal`. The reply should stay in Spanish, but `must_not_contain` cannot express that.
Did not change the text of any existing chat or expected file. A sha1 check over all 15 chats and 15 expected files before and after showed no change, so the recorded answers stay valid.

## 2026-11-17 Tests and cross-check
Tests: 41 passed (the parametrized data test covers the five new chats).
Cross-check: stand-in extraction from each expected file fed to `app/rules` `analyze` (read only, in scratch). 19 of 20 match on net row, fit, reply_kind and review, including all round 2 cases that differed last time.
Mismatch: victor. The net row is `missing` in `analyze`, `doubtful` in my file. `analyze` treats debts with no value as missing even when `deudas` is `doubtful` (the client said there is a loan). Section 5 only covers debts that are *missing*. By analogy with 11.3 (income doubtful with no value means a doubtful net row), I kept `doubtful`. I reported this to the coordinator as a possible rules gap and did not change `app/rules`. fit, reply_kind and review agree either way.
Note: the scratch cross-check script was rewritten while I worked (not by me, same logic: STAND values, every attachment kind). I used it as found and read it before trusting the output.
