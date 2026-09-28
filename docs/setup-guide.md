# Setup guide

Written for someone who has never seen this repository. The demo runs fully
offline: no accounts, keys or internet needed after installing.

## Prerequisites

| Tool | Version | Check with |
|---|---|---|
| Python | 3.10 or newer | `python3 --version` |
| pip | comes with Python | `python3 -m pip --version` |
| A web browser | Chrome, Safari, Firefox or Edge | |

No database, Docker or Node.js needed.

## Install (once)

From the repository root:

```bash
cd src
```
```bash
python3 -m venv .venv
```
```bash
.venv/bin/pip install -r requirements.txt
```

On Windows, use `.venv\Scripts\pip` and `.venv\Scripts\python` in place of
`.venv/bin/pip` and `.venv/bin/python` throughout.

## Environment variables (optional)

The demo needs none. To change settings, copy the example file inside `src/`:

```bash
cp .env.example .env
```

| Variable | Default | Meaning |
|---|---|---|
| `LLM_MODE` | `mock` | `mock` = offline, saved AI answers. `bob` = IBM Bob via Bob Shell. `live` = IBM watsonx.ai |
| `BOB_API_KEY` | none | IBM Bob API key, Scope = Inference (bob mode only) |
| `BOB_TEAM_ID` | none | Only for Bob keys that are not Inference-scoped |
| `BOB_MAX_COST` | `2` | Spending cap per question, in Bobcoins |
| `BOB_BIN` | found on PATH | Path to the `bob` command, if not on PATH |
| `SEED_CASE` | `case` | Which case "Load demo case" opens: `case` (Aarav, has saved answers) or `case_2` (Kavya, needs `LLM_MODE=bob` or `live`) |
| `PORT` | `8000` | Port the web app listens on |
| `WATSONX_APIKEY` | none | IBM Cloud API key (live mode only) |
| `WATSONX_PROJECT_ID` | none | watsonx.ai project ID (live mode only) |
| `WATSONX_URL` | `https://us-south.ml.cloud.ibm.com` | watsonx.ai region URL |
| `WATSONX_MODEL` | `ibm/granite-3-3-8b-instruct` | Model ID |

`.env` is git-ignored. Never commit real keys.

## Run

Inside `src/`:

```bash
.venv/bin/python -m app
```

Wait for `Uvicorn running on http://127.0.0.1:8000`, then open
**http://127.0.0.1:8000** in a browser (a laptop-width window).

Stop it with **Ctrl + C**.

## Verify it's working

**In the browser (about 60 seconds):**
1. Home tab: click **1. Load demo case**. The Reports tab lists 18 reports.
2. Home tab: click **2. Analyse reports**. The Timeline shows a summary, a
   red **"Two reports disagree"** panel (UNRECONCILED), and 12 sightings.
3. Open the **Leads** tab: 3 ranked leads; the first cites C02-1, T07-1,
   T12-1, T10-1.
4. Home tab: click **3. Write documents**. The Documents tab shows the lead
   sheet, public appeal and case file, each with a Download button.
5. **Scoring** tab: the weights table and rules.

**Automated checks (inside `src/`):**

```bash
.venv/bin/python smoke_test.py
```
```bash
.venv/bin/python tests/test_scoring.py
```

Every line should end in `ok`. The first runs the whole pipeline through the
API; the second checks six scores worked out by hand.

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `address already in use` | Another copy is running on port 8000 | Stop it with Ctrl + C in its terminal, or run with a different port: `PORT=8001 .venv/bin/python -m app` |
| `No module named fastapi` | Ran the system Python instead of the virtual environment | Use `.venv/bin/python`, not `python` |
| `python3: command not found` | Python not installed | Install Python 3.10+ from python.org |
| `No such file or directory: ... prompts/...` | Started from the wrong folder, or files missing | Run from inside `src/`; check `src/prompts/` has 4 `.txt` files |
| Page looks unstyled or buttons do nothing | Browser kept an old copy of the page | Hard refresh: Cmd + Option + R (Safari), Cmd/Ctrl + Shift + R (Chrome) |
| A new case or tip shows "Needs manual entry" | Offline mode only has saved answers for the demo case | Expected. Set `LLM_MODE=bob` (IBM Bob) or `LLM_MODE=live` (watsonx.ai) |
| Bob mode: everything shows "Needs manual entry" | Bob Shell not installed, key missing or wrong scope | Check `bob --version`; check `BOB_API_KEY` in `src/.env`; for a non-Inference key set `BOB_TEAM_ID`; the terminal log shows Bob's error |
| Layout is stacked in one column | Window narrower than 1000 px | Widen the browser window |

## Run with IBM Bob as the AI

1. Install Bob Shell (official installer), then reopen the terminal:
   ```bash
   curl -fsSL https://bob.ibm.com/download/bobshell.sh | bash
   ```
2. Check it works: `bob --version`
3. In `src/.env` set `BOB_API_KEY=...` (create the key in the Bob web portal
   with Scope = Inference) and `LLM_MODE=bob`.
4. Start the app as usual. The top strip shows "Live mode: IBM Bob".
   Load demo case, Analyse, Write documents: the first run makes 37 Bob calls
   and takes several minutes; every answer is cached in
   `data/llm_cache.json`, so later runs are instant and cost nothing.
5. To present offline on Bob's answers, set `LLM_MODE=mock` again: saved Bob
   answers take priority over the reference answers.

Each call runs `bob run --format json` in an empty scratch folder with one
turn, MCP and subagents disabled, and a cost cap, so Bob can only answer the
question and cannot modify the project.

## Optional: answer the AI questions with Bob in the editor instead

```bash
.venv/bin/python scripts/bob.py
```

This writes the questions to `src/bob/questions/`. Ask Bob (in the editor)
to answer each file and save the JSON reply where the file says, then run the
script again. It takes four rounds (18, 17, 1, 1 questions). When it prints
"Done", restart the app. To restore the reference answers:

```bash
.venv/bin/python scripts/build_mock.py
```
