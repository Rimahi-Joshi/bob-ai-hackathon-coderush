# src/

All source code. Run everything from inside this folder (see
[../docs/setup-guide.md](../docs/setup-guide.md)).

```
src/
├── app/                  Python backend (FastAPI)
│   ├── __main__.py       python -m app  -> starts the server (reads .env if present)
│   ├── main.py           HTTP endpoints, serves the web page
│   ├── models.py         Data shapes: reports, sightings (Observation), Case
│   ├── pipeline.py       AI stages: read, compare, narrative + leads, documents
│   ├── scoring.py        Description match, credibility, priority (no AI); SCORING table
│   ├── timeline.py       Main trail, conflict forks, set-aside list (no AI)
│   ├── places.py         The 12 places and the travel-time matrix
│   └── store.py          Save / load a case as JSON
├── llm/
│   └── client.py         One AI interface: mock (offline) or IBM watsonx.ai; disk cache
├── prompts/              The four AI instructions, one .txt per task
├── static/               Web page: index.html, style.css, app.js (no framework)
├── data/
│   ├── seed/             Demo dataset: case.json (18 reports), places.json
│   ├── mock/             Saved AI answers (responses.json) + readable sources (authored/)
│   └── cases/            Cases saved while the app runs (git-ignored)
├── scripts/
│   ├── bob.py            Answer the AI questions with IBM Bob through files
│   └── build_mock.py     Rebuild saved answers from data/mock/authored/
├── tests/test_scoring.py Six scores worked out by hand
├── smoke_test.py         End-to-end check through the API
├── requirements.txt      fastapi, uvicorn, pydantic, httpx
└── .env.example          Every setting, with descriptions
```

**Where the AI is used and where it isn't:** the AI reads and compares text
and writes prose (`pipeline.py` + `prompts/`). Every number and every
conflict decision is plain Python (`scoring.py`, `timeline.py`).

**Replacing the dataset:** edit `data/seed/case.json` (and `places.json` if
the town changes), then regenerate the saved AI answers with IBM Bob
(`scripts/bob.py`) or live watsonx.ai. Details in
[../docs/dataset.md](../docs/dataset.md).
