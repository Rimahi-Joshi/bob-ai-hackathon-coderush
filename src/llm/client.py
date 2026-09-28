import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import httpx

log = logging.getLogger("llm")

ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = ROOT / "data" / "llm_cache.json"
MOCK_PATH = ROOT / "data" / "mock" / "responses.json"


class LLMError(Exception):
    pass


def cache_key(task: str, user: str) -> str:
    # Keyed on task name + user payload, not the system prompt text, so that
    # tweaking wording in prompts/*.txt does not throw away a known-good cache
    # the night before the demo. Delete the cache file to force regeneration.
    return hashlib.sha256(f"{task}\n{user}".encode()).hexdigest()[:24]


class DiskCache:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        try:
            self.data = json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            self.data = {}

    def get(self, key):
        return self.data.get(key)

    def put(self, key, value):
        with self.lock:
            self.data[key] = value
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, indent=1, ensure_ascii=False))
            tmp.replace(self.path)


def parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise LLMError("no JSON object in model output")
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        raise LLMError(f"bad JSON from model: {e}") from e


class WatsonxClient:
    """Live client for watsonx.ai chat completions.

    complete() returns the parsed JSON object from the model. Anything served
    from the disk cache comes back without a network call, so a warm cache
    makes the demo independent of conference wifi.
    """

    def __init__(self):
        self.api_key = os.environ.get("WATSONX_APIKEY", "")
        self.project_id = os.environ.get("WATSONX_PROJECT_ID", "")
        self.url = os.environ.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com").rstrip("/")
        self.model = os.environ.get("WATSONX_MODEL", "ibm/granite-3-3-8b-instruct")
        self.cache = DiskCache(CACHE_PATH)
        self._token = None
        self._token_exp = 0

    def token(self):
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        r = httpx.post(
            "https://iam.cloud.ibm.com/identity/token",
            data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": self.api_key},
            timeout=20,
        )
        r.raise_for_status()
        body = r.json()
        self._token = body["access_token"]
        self._token_exp = body.get("expiration", time.time() + 3000)
        return self._token

    def complete(self, system: str, user: str, schema: str, task: str = "") -> dict:
        key = cache_key(task or schema, user)
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        if not self.api_key or not self.project_id:
            raise LLMError("WATSONX_APIKEY / WATSONX_PROJECT_ID not set and no cached response")
        payload = {
            "model_id": self.model,
            "project_id": self.project_id,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": 3000,
            "temperature": 0,
        }
        try:
            r = httpx.post(
                f"{self.url}/ml/v1/text/chat?version=2024-10-08",
                headers={"Authorization": f"Bearer {self.token()}"},
                json=payload,
                timeout=90,
            )
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError) as e:
            raise LLMError(f"watsonx call failed: {e}") from e
        out = parse_json(text)
        self.cache.put(key, out)
        return out


class MockClient:
    """Serves saved answers offline.

    Answers from a real run (Bob or watsonx, in data/llm_cache.json) come
    first; the hand-written reference answers in data/mock/responses.json
    fill any gaps. Lookup is by the same key as the live clients.
    """

    def __init__(self):
        self.canned = DiskCache(MOCK_PATH)
        self.cache = DiskCache(CACHE_PATH)

    def complete(self, system: str, user: str, schema: str, task: str = "") -> dict:
        key = cache_key(task or schema, user)
        hit = self.cache.get(key) or self.canned.get(key)
        if hit is None:
            raise LLMError(f"mock mode: no canned response for {task or schema} ({key})")
        return hit


def _bob_answer(stdout: str) -> dict:
    """Pull the model's JSON reply out of `bob run --format json` output.

    The session JSON wraps the reply in fields we don't control, so walk it and
    take the last text that parses as a JSON object; plain-text output is
    parsed directly.
    """
    try:
        session = json.loads(stdout)
    except json.JSONDecodeError:
        return parse_json(stdout)
    texts = []

    def walk(v):
        if isinstance(v, str):
            texts.append(v)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(session)
    for t in reversed(texts):
        try:
            return parse_json(t)
        except LLMError:
            continue
    raise LLMError("no JSON answer found in Bob output")


class BobClient:
    """IBM Bob through Bob Shell (`bob run`), the documented way to call Bob
    from a script. Needs the `bob` command installed and BOB_API_KEY set.

    `bob run` is an agent with tools pre-approved, so every call runs in an
    empty scratch folder with MCP and subagents off and a single turn: Bob can
    answer but cannot touch the project. Answers are cached like watsonx ones,
    so each question costs Bob credits only once.
    """

    def __init__(self):
        self.cache = DiskCache(CACHE_PATH)
        self.bin = os.environ.get("BOB_BIN") or shutil.which("bob") or os.path.expanduser("~/.local/bin/bob")
        self.team = os.environ.get("BOB_TEAM_ID", "")
        self.max_cost = os.environ.get("BOB_MAX_COST", "2")
        self.workdir = tempfile.mkdtemp(prefix="trace-bob-")

    def complete(self, system: str, user: str, schema: str, task: str = "") -> dict:
        key = cache_key(task or schema, user)
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        if not os.environ.get("BOB_API_KEY"):
            raise LLMError("BOB_API_KEY not set and no cached response")
        if not os.path.exists(self.bin):
            raise LLMError("Bob Shell not installed (no `bob` command) and no cached response")
        prompt = f"{system}\n\n---\nINPUT:\n{user}\n\nReply with only the JSON object. Do not use any tools."
        cmd = [self.bin, "run", "--format", "json", "--max-turns", "1", "--max-cost", self.max_cost,
               "--disable-mcp", "--disable-subagents", "--accept-license", "--trust", "--workspace", self.workdir]
        if self.team:
            cmd += ["--team-id", self.team]
        try:
            r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=300, cwd=self.workdir)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise LLMError(f"bob run failed: {e}") from e
        if r.returncode != 0:
            raise LLMError(f"bob run exited {r.returncode}: {(r.stderr or r.stdout)[-400:]}")
        out = _bob_answer(r.stdout)
        self.cache.put(key, out)
        return out


_client = None


def get_client():
    global _client
    if _client is None:
        mode = os.environ.get("LLM_MODE", "mock").lower()
        _client = {"live": WatsonxClient, "bob": BobClient}.get(mode, MockClient)()
        log.info("LLM mode: %s", mode)
    return _client
