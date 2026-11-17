# Agent 1: conversations

Read `CONTRACTS.md` first (sections 1 to 3 and 10 matter most). You own: `app/chats.py`, `tools/`, `data/chats/`, `data/expected/`, `tests/chats/`.

## Goal

Give the project test conversations and the tiny tools to create them. Keep everything as simple as possible. No model, no API, no dependencies beyond the standard library and pytest.

## Build

1. **Parser** `app/chats.py`: `parse_chat(path)` and `append_message(path, sender, text)` exactly as in CONTRACTS section 3. Lines that do not match the format raise a clear error with the line number.

2. **The three chats from the test**, typed by hand into `data/chats/laura.txt`, `javier.txt`, `rosa.txt`. Laura is in `samples/laura.json`. The other two:

   Javier:
   - cliente: buenas, cuanto cuesta esto? me interesa algo por madrid o alrededores
   - libeen: ¡Hola, Javier! Depende de la casa y de tu situación. ¿Compras solo o con alguien? ¿Y cuánto ganas al mes, más o menos?
   - cliente: solo. soy autonomo, depende del mes, entre 2000 y 3000
   - cliente: [audio 1:12]
   - cliente: y esto es fiable? no sera una estafa no

   Rosa:
   - cliente: Buenos días. Somos mi marido y yo. Él tiene 67 años y está jubilado, yo trabajo a media jornada. Entre los dos, 1.400 €. Ahorros no tenemos, pero necesitamos salir del piso en dos semanas.
   - cliente: Si no podéis vendernos, ¿nos alquiláis algo solo de alquiler?
   - cliente: Mi hijo dice que os pida por escrito que estamos aprobados antes de seguir.

3. **Hard cases**, written by hand, about 8 more chats. One trap each:
   - income given gross, not net
   - numbers that contradict each other across messages
   - a client who tells the assistant to ignore its rules and approve them
   - savings just under and just over the minimum (two chats)
   - a message with a line break and with brackets inside
   - a chat where Libeen wrote last (nothing to answer)
   - a client who only asks for information and gives no data
   - four buyers with mixed incomes

4. **Expected results**: `data/expected/<chat_id>.json` for every chat, in the shape of the `expected` object in `samples/laura.json`. Only include a `value` where it is unambiguous. Use `config/rules.yaml` to work out `net_income_status`, `fit`, `reply_kind` and `review` by hand, following CONTRACTS section 5.

5. **Generator** `tools/gen_chat.py`: builds a random chat from a small set of sentence templates and a seed, and writes both the chat file and its expected file. Because the script picks the values, it knows the expected answers. Around 100 lines. Usage: `python tools/gen_chat.py --seed 7 --out data/chats`.

6. **Say** `tools/say.py`: `python tools/say.py laura cliente "Vale, ¿cuándo hablamos?"` appends one message. This is how the demo simulates both sides.

## Done when

- `pytest tests/chats` passes: parsing, line breaks, brackets inside messages, bad lines, append then parse.
- Every file in `data/chats` parses and has an expected file.
- Only invented people and data.
- `logs/agent-1.md` is filled in.
