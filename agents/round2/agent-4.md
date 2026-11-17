# Agent 4, round 2

Read CONTRACTS section 11 first. Same paths as before. Add to `logs/agent-4.md`.

1. **No draft when Libeen wrote last** (11.9): do not call `draft`. Return `"draft": null, "checks": []`. The reply block shows "Esperando respuesta del cliente" and no buttons.
2. **Recorded and mock markers**: the header or chat column says "Respuesta grabada" when the extraction or draft has `recorded: true`, and "Modo simulado" for the mock, so nobody mistakes either for a live answer.
3. **Inbox on a cold cache**: do not block the page for two minutes. Load the list of chats first, then fill each row as its extraction arrives (one request per chat is fine). A row that is still loading says "Leyendo…".
4. **Draft call only when a chat is opened**, never for the inbox.
5. **`ask_for` and `client_reasons`**: no new block. In the ficha, mark the rows in `ask_for` with a small "se pide" tag, so the advisor sees what the reply is about to ask without reading it.
6. **Review line**: when `review` is `full`, say why in a few words, from the analysis (for example "Revisión: lectura completa · edad, petición especial").
7. The two new checks (`internal_terms`, `max_chars`) show in the warning like the others. Nothing to code if you render the list as is. Confirm it.

Tests: no draft call for a chat where Libeen wrote last, the inbox route does not call `draft`, markers pass through.

Done when `pytest tests/server` passes and the page works end to end in mock mode.
