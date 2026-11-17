# Agent 4: server and screen

Read `CONTRACTS.md` first (all of it, mainly sections 1, 3, 5, 6, 8, 9 and 10). You own: `app/server.py`, `web/`, `tests/server/`.

## Goal

One page where the advisor reads less and only decides. Visual polish is not graded. Clarity is.

## Build

**Server** (FastAPI, the four routes in CONTRACTS section 8):
- It only wires things together: `parse_chat`, `extract`, `analyze`, `draft`, `check_draft`, `inbox_sort`. No business logic here.
- Until the other agents deliver, serve `samples/laura.json` behind the same routes so the page can be finished. Keep that fallback behind one flag.
- `approve` appends the message with `append_message` and writes the log line. This is the only way anything is "sent".

**Page** (`web/index.html`, vanilla JS, no build step), three columns:

1. **Inbox**. One row per chat: name, fit tag, the reasons in one line, waiting time. Order comes from the server.

2. **Chat**, read only. Each quote from the extraction is highlighted in the message, with the color and number of its field. If a quote cannot be found in the message, skip it without breaking the rest.

3. **Decision panel**, always the same blocks in the same order:
   - **Ficha**: the nine rows from `analysis.rows`. Columns: number badge, label, value, status, note. A missing value shows "Sin dato". Status sits in a fixed-width column so it can be scanned without reading. The four statuses must differ by more than color (shape, border or darkness).
   - The three rows with `group: "calc"` look like the others but share one thin, light outline, so the sum reads as one block. The result row shows "=" in place of a number badge. Keep it subtle: no heavy lines, no background.
   - A count line on top: "7 OK · 1 Dudoso · 1 Falta · 0 No cumple".
   - **Avisos**: always three rows (preguntas sin responder, adjuntos sin leer, peticiones especiales), "Ninguno" when empty.
   - **Simulación**: always the same four cells, "Sin dato" when there is no simulation.
   - **Respuesta propuesta**: the reply kind, a "Revisión: normal" or "Revisión: lectura completa" line, the blocks with their labels, and each `key_span` inside a rounded dotted box. Failed checks show as a warning above the buttons.
   - Buttons: "Aprobar y enviar" and "Editar texto". Editing turns the blocks into one text area. The approve call sends `edited: true` when the text changed.

After approve, reload the chat and the inbox.

Labels in Spanish: ok is "OK", doubtful is "Dudoso", missing is "Falta", fails is "No cumple".

Use real buttons and a real table, readable contrast, and let the columns stack on a narrow window.

## Do not build

Anything in CONTRACTS section 9.

## Done when

- `uvicorn app.server:app` starts and the page works end to end with the sample data.
- `pytest tests/server` covers the four routes, including that approve appends exactly one line to the chat file and one to the log.
- `logs/agent-4.md` is filled in.
