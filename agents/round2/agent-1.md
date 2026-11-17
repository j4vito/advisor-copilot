# Agent 1, round 2

Read CONTRACTS section 11 first. Same paths as before. Add to `logs/agent-1.md`.

1. **Update the expected files** to the new rules:
   - `pablo`: net income straddles the minimum, so `fit` is `needs_data` and `reply_kind` is `ask_info` (11.1).
   - `elena`: savings of 14.900 € are a near miss, so `ahorro` is not a fail. Work out `fit`, `reply_kind` and `review` from 11.2.
   - `carmen`: `net_income_status` stays `doubtful` (11.3 now says so).
   - `andres`: `empleo` becomes `doubtful`. Agent 3's model was right: two buyers gave no job. `review` is `full` because of the ages (11.6).
   - `marta7`, `rosa`, and any chat with an age above 60: `review` is `full`.
   - `tomas`: add `"no_draft": true` (11.9).
   - Go through every other file and recheck `fit`, `reply_kind` and `review` by hand against section 11.

2. **Add `must_not_contain`** (11.11) where a reply could go wrong:
   - every chat with an age above 60: `["edad"]`
   - `elena`: `["plazo"]` (the model invented a deadline problem)
   - `rosa`: `["zona", "deudas"]` (a decline must not ask for more data)
   - `marcos`: `["aprobado"]`

3. **Generator**: `net_status` and the rest of the expected logic in `tools/gen_chat.py` must follow 11.1 to 11.6. Regenerate `marta7`.

4. **Two new hard cases**: income 2.150 € (near miss on income), and a client above 60 who fits on income and savings (offer, full review, no age in the reply).

Done when `pytest tests/chats` passes and every expected file agrees with section 11.
