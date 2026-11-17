# Advisor copilot

A first version of a tool that saves time for Libeen's sales advisors without taking decisions away from them.

## The problem

Every lead starts as a WhatsApp chat. Today an advisor reads each one, pulls out the data by hand (where, when, how many buyers, income, savings), checks it against the rules and writes a reply. This prototype does the reading, the checking and the first draft. The advisor only decides.

## The approach

One screen, three columns: the inbox, the chat, and a decision panel.

- **The model reads.** It turns a chat into eight fields, each with the exact quote it came from. The quote is highlighted in the chat, so the advisor sees where every number comes from. If a quote is not really in the chat, code drops it and marks the field as doubtful.
- **Rules decide.** Plain code compares the fields with the thresholds in `config/rules.yaml` (minimum income after debts, minimum savings, time needed to buy). It sets each field's status, runs the price simulation, and picks the reply type: offer, ask for more data, or decline. No model is involved, so the result is the same every time and can be tested.
- **The model writes.** It drafts the reply for the type the rules chose, using only numbers the rules produced. Code then checks the draft: no forbidden words such as "aprobado", no invented numbers.
- **The advisor approves.** Nothing is sent without a click. Every send is logged, including whether the advisor edited the text.

The panel always shows the same rows in the same order, so an advisor who knows the screen sees what is missing without reading. Income minus debts is shown as a visible sum, because it is a calculation, not something the client said.

**Left out on purpose:** a real WhatsApp connection (chats are text files), audio transcription, tone buttons, a second reply option, and correcting a field from the screen.

## Run it

Python 3.11+.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env                  # optional: add ANTHROPIC_API_KEY
.venv/bin/uvicorn app.server:app      # open http://127.0.0.1:8000
```

Without a key the app replays the real Claude Haiku answers recorded in `data/cache/` for all 20 chats, marked as recorded. A chat with no recorded answer falls back to a clearly marked mock. With a key it calls Claude Haiku live. `.venv/bin/python -m app.llm.warm` refreshes the recorded answers.

Simulate the client side of a chat:

```bash
.venv/bin/python tools/say.py laura cliente "Vale, ¿cuándo hablamos?"
.venv/bin/python tools/gen_chat.py --seed 12 --out data/chats   # a new random chat
```

## How I know it works

```bash
.venv/bin/pytest                          # unit tests, no network
.venv/bin/python -m evals.run --mock      # evals without the model
.venv/bin/python -m evals.run             # evals with the real model
```

`data/chats/` holds 20 invented chats: the three from the brief and 17 hard cases (gross yearly income, contradictory numbers, a client telling the assistant to approve him, savings and income just under the minimum, a client over 60, a chat where Libeen wrote last, a client who corrects a number, savings that are not cash, debts only in an attachment, a chat in Catalan, and more). Each has an expected result in `data/expected/`.

The evals caught real bugs. One: a client gave 34.000 € gross a year, the model stored it as monthly income, and the rules said she qualified. After round 2, with the real model, 18 of 20 chats pass, and fit, reply type and review are right for all 20. Every draft passes the checks, including no mention of age and no forbidden words. The two failures are open decisions, not model errors: Andrés's pension is not said to be net, and the model marks his income as doubtful; Víctor mentions a loan with no amount, and the contract does not say whether that makes income after debts missing or doubtful. Both are explained in `logs/agent-3.md`.

## How it was built

I worked with Claude in two stages.

1. **Design, in conversation.** Reading the brief and Libeen's site, looking at how US real estate and mortgage teams use AI for lead qualification, and iterating on mockups of the screen until the panel was right. The main decisions came from that: rules in config and not in the prompt, a fixed panel, quotes highlighted in the chat, numbers shown as visible sums.
2. **Code, by four agents in parallel.** I wrote a shared contract (`CONTRACTS.md`) with every data format, plus one brief per agent (`agents/`): conversations and test data, rules, model layer and evals, server and screen. Each agent kept a log of what it was asked, what it did and what it changed after review (`logs/`). I then read the real model output for every chat and wrote a second round of instructions (`agents/round2/`) for the problems the tests did not catch.

The logs are the honest record of what was accepted, corrected and why.

## Next rounds I had planned

The work stopped after round 2 for the conversations, the rules and the model layer. These were the next steps, in order:

1. **Screen, round 2** (`agents/round2/agent-4.md`, written but not run). No draft and no buttons when Libeen wrote last ("Esperando respuesta del cliente"). A visible "Respuesta grabada" or "Modo simulado" marker, so nobody mistakes a recorded answer for a live one. Load the inbox row by row ("Leyendo…") instead of blocking on a cold cache. Mark the rows the reply is about to ask for with a "se pide" tag, and say in a few words why a chat needs a full review.
2. **Settle the open contract questions** the agents flagged in their logs, then align rules and expected files:
   - A near miss on savings gets an offer with full review, but a near miss on income asks for data, because the offer rule only tightens income. I would make both "offer, full review, the advisor decides".
   - Clients who need more data still get a simulation, so a reply asking for income can see numbers built on an income below the minimum. I would only simulate when the client fits.
   - Debts mentioned but with no amount (Víctor) give a missing net income row; by analogy with gross income it should be doubtful.
   - Decide whether a reply asking for data asks for non-money fields (job, buyers) or only for what blocks the decision.
3. **Stronger draft checks.** Check that an offer only mentions the allowed simulation numbers (`draft.offer_facts`, validated but not enforced yet), that the reply is in Spanish when the client writes in another language (Jordi), and that times and dates such as "1:12" are not read as invented numbers. Add the two new checks to `samples/laura.json`. Fix what the checks miss today: replies that use the internal label "ingresos declarados" (a client-facing wording per field in config), and small slips mixing "tú" and "vosotros".
4. **More evals with the real model.** Run each chat several times to measure variance instead of two runs, and add every new failure from real use as a chat with its expected file before changing a prompt.

## With one more week

- Let the advisor correct a field on the screen and have the rules, simulation and draft update on their own.
- Measure how often drafts are sent without edits, per reply type. Types that are almost never edited are the first candidates for more automation.
- Transcribe audio messages.
- Calibrate the thresholds and the inbox order with the sales team.
