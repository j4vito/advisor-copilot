# Agent 4: server and screen

## 21:05 Server shape
Asked: FastAPI with the four routes from CONTRACTS section 8, wiring only.
Did: `create_app(pipeline, log_path)`. A "pipeline" is the CONTRACTS functions plus the loaded config. Routes only call those. Tests inject their own pipeline with a temp dir, so they never touch `data/`.
Open doubt: none.

## 21:08 Sample fallback behind one flag
Asked: serve `samples/laura.json` until the other parts exist.
Did: `LIBEEN_SAMPLE=1` forces it. Without the flag the server tries the real modules and falls back to the sample if an import fails, printing why. The sample copies the Laura chat to `data/sample_chats/` so approve really appends.
Open doubt: the sample has its own small parser (a copy of the CONTRACTS regex). It exists only so the page could be built before `app/chats.py`.

## 21:10 Extra route `/api/mode`
Not in CONTRACTS. The page uses it to say "Modo muestra" in the header, so the advisor never mistakes sample data for real data. Read-only, nothing else depends on it.

## 21:12 Page
Did: one `web/index.html`, vanilla JS, three columns that stack below 1000px.
- Highlights: each quote is searched in its message with `indexOf`. Not found, or overlapping an earlier quote, means skipped, the rest still renders.
- Status shapes: OK solid outline, Dudoso dashed, Falta dotted on grey, No cumple solid filled red. Each also has an icon (● ◐ ○ ✕), so the four differ without color.
- Calc block: borders on the cells of the three `group: "calc"` rows, rounded corners, no background.
- Edit: blocks turn into one textarea. `edited` is true only when the trimmed text differs from the proposal.
- Simulation shows "lo limita el ahorro / los ingresos" next to the max price. Small extra, uses `limited_by` from the analysis.

## 21:15 Approve
Did: computes chat + draft + checks first, then `append_message`, then one log line. `checks_failed` lists the names of failed checks on the proposed draft.
Open doubt: when the advisor edits, the checks were run on the proposal, not on the edited text. The log keeps `edited: true` so this is visible. Re-checking edited text is a small next step.
Empty text gives 400 and writes nothing. Unknown or malformed chat id gives 404 (id must match `[a-z0-9_-]+`, so no path tricks).

## 21:18 Errors are shown, not hidden
Did: one chat that fails to parse or to extract appears in the inbox with fit "error" and the message, instead of breaking the whole list. The detail route returns 500 with the reason in Spanish, and the page prints it.
Also: if the extraction has `mock_placeholder` (agent 3's marker), the chat column says "Modo simulado".

## 21:20 Integration check against agent 3's package
Found: `app/llm/` had no `__init__.py` yet, so `from app.llm import extract` would import the submodule, not the function. Added a check: if `extract`/`draft` are not callable, the server falls back to sample mode and says so.

## 21:30 End-to-end check with all four parts
Did: real pipeline (agent 1 parser, agent 2 rules, agent 3 llm in mock mode) through the routes: 13 chats in the inbox, sorted, Tomás (Libeen wrote last) at the bottom. Laura/Javier/Rosa give fits/needs_data/no_fit, no failed checks. Other chats show the "Modo simulado" marker.
Found: `uvicorn app.server:app` with the `.env` key goes to the real model and fails with "No module named 'anthropic'". The page shows that error in place of the chat, as intended. There is no `requirements.txt` or README yet and CONTRACTS does not assign them. Flagged to the lead.
Approve tested only in the temp-dir tests, so the real `data/chats/` files stay unchanged.

## 21:45 requirements.txt (now mine, decided by the lead)
Did: grepped every import in app/, tools/, evals/, tests/. Third-party: fastapi, pydantic, yaml, anthropic, pytest (httpx for the FastAPI test client, uvicorn to serve). No code imports dotenv (agent 3's settings.py reads .env itself), so python-dotenv is left out. `gen_chat` and `say` are local modules in tools/.
Minimum versions with >=. anthropic is >=2.8 because app/llm/client.py uses `output_config` for structured output. I confirmed that argument exists in 2.8.0 and could not check older releases.
Installed into the shared .venv. Full suite: 92 passed.

## 21:50 Checks run on the text actually sent
Changed after review: approve used to log the failed checks of the proposal, even when the advisor edited it.
Did: the sent text is wrapped as one block with no key spans and run through `check_draft`. Only `banned_words` and `numbers_in_facts` are kept, since spans and the disclaimer belong to the proposal. When the text equals the proposal, the proposal's span and disclaimer results are added back, so an unedited send loses nothing. The comparison is done on the server, not trusted from the `edited` flag.
Never blocks: the message is appended anyway, `checks_failed` goes to the log line and to the response, and the page shows "El texto enviado no pasó: ..." after sending.
Tests: edited text with "aprobados" is appended and logs `banned_words`; an invented number logs `numbers_in_facts`; the unedited proposal logs nothing.

## 21:55 .gitignore
Added `data/sample_chats/` (my sample-mode copy of the Laura chat). The only line I touched.

## 22:00 Real model, end to end
Did: `.venv/bin/uvicorn app.server:app` with the key from .env. All 13 chats load in the inbox and the detail view works, including chats with no mock answer (Andrés). Laura: fits, 7 OK · 1 Dudoso · 1 Falta, no failed checks. Grepped data/, logs/, tests/, app/, web/ for the key: not found.
Changed after checking: the cache files were not rewritten during that run, so the inbox was served from cache that agent 3's evals left behind, and the cache does not record the model. To be sure, I ran one uncached call on a copy of laura.txt under a throwaway id: real extract + draft with `claude-haiku-5-5` took 21 s, not mock, fits, no failed checks. Then I deleted its cache file.
Open doubt: on a cold cache the inbox runs `extract` for every chat, one after another. At about 10 s per extract, 13 chats is around 2 minutes before the first page load. Not fixed: it means parallel calls or a background warm-up, and the brief says small and working first.
Approve against real chat files not tried, to keep data/chats/ unchanged. Approve is covered in the temp-dir tests.

## Note for agent 3
- With a key set but the `anthropic` package missing, the chat view shows "No module named 'anthropic'" instead of falling back to mock mode. Same for a bad key or no network: the error is shown (good, nothing invented) but there is no fallback. Your call whether that is the wanted behavior. The server already turns it into a readable error on the page.
- `.env` uses `CLAUDE_API_KEY`. settings.py accepts it as an alias, but CONTRACTS and .env.example say `ANTHROPIC_API_KEY`.
- Default model id `claude-haiku-5-5` comes from CONTRACTS. Checked with one uncached real call: it works.

## Start from zero (for the README)
```
python3 -m venv .venv                      # Python 3.11+
.venv/bin/pip install -r requirements.txt
cp .env.example .env                       # optional: put ANTHROPIC_API_KEY=... in it; without a key it runs in mock mode
.venv/bin/uvicorn app.server:app           # open http://127.0.0.1:8000
.venv/bin/pytest                           # all tests, no network needed
LIBEEN_SAMPLE=1 .venv/bin/uvicorn app.server:app   # only samples/laura.json, for working on the page alone
```

# Round 2 (2026-11-16)

## No draft when Libeen wrote last (11.9)
Did: `GET /api/chats/{id}` checks the last message before anything else. If it is from `libeen`, it returns `"draft": null, "checks": []` and never calls `draft` or `check_draft`. The reply block says "Esperando respuesta del cliente", with no buttons. Approve still works without a draft (no crash), but the page offers no button for it.
Test: `draft` and `check_draft` replaced by functions that raise, the route still answers.

## Inbox on a cold cache
Did: two new routes, not in CONTRACTS. `GET /api/inbox-list` parses the chat files only (no model call) and returns rows with `fit: null`, ordered by `inbox_sort` (waiting chats first, then longest wait). `GET /api/inbox/{id}` returns one full row (extract + analyze). The page draws the list at once with "Leyendo…" on every row, fires one request per row in parallel, and fills each row as it arrives. When all are in, it fetches `GET /api/inbox` (everything cached by then, so fast) and redraws in the server's order. No sorting logic in the page.
The first chat opens only after its own row has arrived, so its extraction is not paid twice on a cold cache. If the advisor clicks a chat that is still "Leyendo…", that chat's extraction can run twice at the same time. Accepted: rare, and only costs one call.
Test: `/api/inbox-list` works with `extract` and `draft` replaced by functions that raise.

## Draft only when a chat is opened
`/api/inbox`, `/api/inbox-list` and `/api/inbox/{id}` never call `draft`. Test with a `draft` that raises.

## Recorded and mock markers
Did: the chat column shows a "Respuesta grabada" tag when the extraction or the draft has `recorded: true`, and "Modo simulado" when either has `mock` or `mock_placeholder`. The server passes both through untouched (test).
Seen in mock mode: the fixed mock answers for Laura, Javier and Rosa carry no marker at all, so the page shows nothing and they look live. See the note for agent 3.

## "se pide" in the ficha (11.7)
Rows whose key is in `analysis.ask_for` get a small grey "se pide" tag after the label. Hidden when there is no draft (Libeen wrote last), since then nothing is about to be asked.

## Review line says why
"Revisión: lectura completa · no encaja · edad · petición especial". Worked out in the page from the analysis: `fit` no_fit, `edad` row doubtful, a row note starting "Casi llega", special requests, attachments. These mirror the rules in CONTRACTS 5 and 11.2/11.6.
Open doubt: this repeats the rule list in the page. If the rules change, the line can drift. A `review_reasons` list from `analyze` would be the clean fix. Suggestion for agent 2, not done.

## New checks (internal_terms, max_chars)
Confirmed: the warning lists every failed check with its detail, whatever its name. Nothing to code for the proposal.
Changed: both are text checks, so they now also run on the text actually sent (approve). An edited reply that says "edad" is sent and logs `internal_terms`. Test added. This extends the lead's earlier decision (banned words + numbers only) to the two checks that did not exist then.

## Small extras
- `#chat_id` in the URL opens that chat, and the open chat is kept in the URL, so a reload stays on it. Used to check each chat in headless Chrome.
- `tests/server/conftest.py` puts the repo root on the path, same as the other test folders. Before, `pytest tests/server` alone failed to import `app`.

## Check, mock mode, end to end
Did: served a temp copy of the 13 chats with `LIBEEN_MOCK=1` (mock mode does not write data/cache) and rendered the page in headless Chrome.
- Laura: inbox rows all filled, no "Leyendo…" left, highlights, ficha, simulation, reply with buttons.
- Javier: "se pide" on ingresos, deudas, ahorro; "lectura completa · adjunto sin leer".
- Rosa: "lectura completa · no encaja · edad · petición especial", decline reply.
- Tomás: "Esperando respuesta del cliente", no buttons, "Modo simulado" tag.
- Approve on the copy: one line in the chat, one in the log, then the chat shows no draft and drops to the bottom of the inbox.
Once, right after approve, `GET /api/inbox` returned a body that was not JSON. Could not reproduce it (next call 200 in 9 ms), and the server log was empty. Noted, not explained.
`pytest tests/server`: 16 passed. Full suite: 101 passed, 1 failed in tests/rules (agent 2, sample checks after their new checks).

## Note for agent 3 (round 2)
- Mark the fixed mock answers (Laura, Javier, Rosa) with `"mock": true` on both extraction and draft. Today only the placeholder chats are marked, so the fixed ones look like live answers. The page already shows "Modo simulado" for `mock` or `mock_placeholder`.
- The page reads `recorded: true` on extraction or draft, as in your brief.
