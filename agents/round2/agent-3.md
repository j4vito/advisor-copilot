# Agent 3, round 2

Read CONTRACTS section 11 first. Same paths as before, plus one line in `.gitignore` (remove `data/cache/`). Add to `logs/agent-3.md`. Wait for agent 2's round 2 before the real model run.

What the real drafts got wrong (read from `data/cache/`):
- `rosa`: after saying no, it asked for her zone and debts, mentioned age, and used the "deudas sí cuentan" snippet that nobody asked about.
- `marta7`: "La edad también la revisa nuestro asesor". Age must never reach the client.
- `elena`: invented a deadline problem that is in no rule.
- `irene`: asked for eight things in one message.
- `laura`: stated 3.550 € as a fact when the row is doubtful, and the next step asked about jobs instead of proposing a call.
- Offers list every simulation number and read long.

Build:
1. **Draft input**: drop the rows in `draft.hidden_fields` before calling the model. Pass `ask_for`, `client_reasons` and `draft.offer_facts`. For an offer, pass only those facts plus the field facts.
2. **Draft prompt**: the rules in 11.8. Keep the prompt short and state each rule once.
3. **Recorded answers** (11.10): with no key, use the recorded real answer for that chat content when there is one, marked `recorded`. Ignore the model id and prompt hash for this lookup, match on the chat content. Then mock. Remove `data/cache/` from `.gitignore`.
4. **Warm-up**: `python -m app.llm.warm` runs extract and draft for every chat and prints progress. This is how the cache gets refreshed before committing.
5. **No draft** when the last message is from `libeen` (11.9): `draft` is not called by the server, but make `evals` respect `no_draft`.
6. **Evals**: check `must_not_contain` against the draft text (case-insensitive) and report it as its own line in the summary. Add a `max_chars` line.
7. **Missing package or bad key**: if `anthropic` cannot be imported, behave as if there were no key (recorded, then mock) and say so once on stderr. A failed API call still raises a clear error.

Then run the evals with the real key, twice, and write the honest result in the log: which cases fail and why you think so. Do not tune the prompt to one chat if the rule is unclear. Flag it.
