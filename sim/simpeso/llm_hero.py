"""Hero shoppers: a few simulated shoppers whose judgement comes from a language model through an AI API.

Most simulated shoppers decide with a transparent rule-based model (customers.py), which scales to thousands. A hero shopper has a persona
(who they are) and a mission (what they came for), and an LLM chooses what they do at each step: buy some, ask the cashier, wait, or leave.
Their memory and beliefs are still kept by the same Customer object, so the LLM sees the diary and the belief the program holds for them.

The LLM is only ever a simulated person. It is not part of the shop's AI: it never sees PesoWeb data, prices other than the shelf price in front
of the shopper, or the AI's decisions; it only receives the synthetic persona and what a shopper could see in the shop. Every answer is validated
(action, quantity, stock, what the shopper could afford); anything else falls back to the rule-based decision, so a failed call never stops a run.
Answers are cached on disk, so the same run replays identically and costs nothing the second time.

Provider (environment variables; the key is never written to a file or printed):
  ANTHROPIC_API_KEY (+ optional LLM_MODEL, default claude-haiku-4-5-20251001)   Anthropic Messages API
  LLM_BASE_URL (+ LLM_MODEL, optional LLM_API_KEY)                                any OpenAI-compatible server: vLLM on the AMD GPU, or a hosted one
  OPENAI_API_KEY (+ LLM_MODEL, optional LLM_BASE_URL)                             OpenAI-compatible hosted API
  LLM_PROVIDER=anthropic|openai forces the choice."""
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from . import customers as cu

ACTIONS = ("buy", "ask", "wait", "leave")
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
RUNS = Path(__file__).resolve().parent.parent / "runs"
MAX_QTY = 6
AFFORD_SLACK = 1.15           # a hero may stretch a little beyond the rule-based willingness to pay, not far


class LlmError(Exception):
    pass


class LlmBudgetExceeded(LlmError):
    pass


def parse_json_object(text: str) -> dict:
    """The first JSON object in the text (models sometimes wrap it in a code fence or add a sentence)."""
    if not text:
        raise LlmError("empty answer")
    cleaned = re.sub(r"```(?:json)?", "", text)
    start = cleaned.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(cleaned)):
            if cleaned[i] == "{":
                depth += 1
            elif cleaned[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        value = json.loads(cleaned[start:i + 1])
                        if isinstance(value, dict):
                            return value
                    except ValueError:
                        pass
                    break
        start = cleaned.find("{", start + 1)
    raise LlmError("no JSON object in the answer")


class LlmClient:
    """One call per decision, a disk cache, and a hard cap on the number of real calls."""

    def __init__(self, provider: str, model: str, base_url: str = None, api_key: str = None, timeout: float = 30.0,
                 cache_path=None, max_calls: int = 300, transport=None):
        if provider not in ("anthropic", "openai"):
            raise LlmError("provider must be anthropic or openai")
        self.provider, self.model, self.base_url, self.timeout = provider, model, (base_url or "").rstrip("/"), timeout
        self._key = api_key
        self.max_calls, self.transport = max_calls, transport
        self.calls = self.cached = self.failures = 0
        self.cache_path = Path(cache_path) if cache_path else None
        self._cache = {}
        if self.cache_path and self.cache_path.exists():
            for line in self.cache_path.read_text(encoding="utf-8").splitlines():
                try:
                    row = json.loads(line)
                    self._cache[row["k"]] = row["v"]
                except (ValueError, KeyError):
                    continue

    def __repr__(self):
        return f"LlmClient({self.provider}, {self.model}, calls={self.calls}, cached={self.cached})"       # never shows the key

    @classmethod
    def from_env(cls, cache_path=None, max_calls: int = 300):
        env = os.environ
        provider = (env.get("LLM_PROVIDER") or "").lower()
        if not provider:
            provider = "anthropic" if env.get("ANTHROPIC_API_KEY") else ("openai" if (env.get("LLM_BASE_URL") or env.get("OPENAI_API_KEY")) else "")
        if provider == "anthropic":
            if not env.get("ANTHROPIC_API_KEY"):
                raise LlmError("ANTHROPIC_API_KEY is not set")
            return cls("anthropic", env.get("LLM_MODEL") or DEFAULT_ANTHROPIC_MODEL, env.get("LLM_BASE_URL") or "https://api.anthropic.com",
                       env["ANTHROPIC_API_KEY"], cache_path=cache_path, max_calls=max_calls)
        if provider == "openai":
            if not env.get("LLM_MODEL"):
                raise LlmError("LLM_MODEL is not set (the model name the server serves)")
            return cls("openai", env["LLM_MODEL"], env.get("LLM_BASE_URL") or "https://api.openai.com",
                       env.get("LLM_API_KEY") or env.get("OPENAI_API_KEY"), cache_path=cache_path, max_calls=max_calls)
        raise LlmError("no AI API is configured: set ANTHROPIC_API_KEY, or LLM_BASE_URL and LLM_MODEL (see simpeso/llm_hero.py)")

    # ---- the two wire formats ------------------------------------------------------------------------------
    def build_request(self, system: str, user: str):
        if self.provider == "anthropic":
            return (self.base_url + "/v1/messages",
                    {"x-api-key": self._key or "", "anthropic-version": "2023-06-01", "content-type": "application/json"},
                    {"model": self.model, "max_tokens": 200, "temperature": 0, "system": system, "messages": [{"role": "user", "content": user}]})
        headers = {"content-type": "application/json"}
        if self._key:
            headers["authorization"] = "Bearer " + self._key
        return (self.base_url + "/v1/chat/completions", headers,
                {"model": self.model, "max_tokens": 200, "temperature": 0,
                 "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})

    def _extract(self, body: dict) -> str:
        if self.provider == "anthropic":
            return "".join(b.get("text", "") for b in body.get("content", []) if b.get("type") == "text")
        return body["choices"][0]["message"]["content"]

    def _send(self, system: str, user: str) -> str:
        url, headers, payload = self.build_request(system, user)
        if self.transport is not None:
            return self.transport(url, headers, payload)
        import requests
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        except requests.RequestException as e:
            raise LlmError(type(e).__name__) from None             # the message could carry the URL; not the key, but keep it short
        if r.status_code != 200:
            raise LlmError(f"the AI API answered {r.status_code}")
        try:
            return self._extract(r.json())
        except (ValueError, KeyError, IndexError) as e:
            raise LlmError("unexpected answer shape") from e

    def complete_json(self, system: str, user: str) -> dict:
        key = hashlib.sha256(f"{self.provider}|{self.model}|{system}|{user}".encode("utf-8")).hexdigest()
        if key in self._cache:
            self.cached += 1
            return parse_json_object(self._cache[key])
        if self.calls >= self.max_calls:
            raise LlmBudgetExceeded(f"{self.max_calls} calls used")
        self.calls += 1
        try:
            text = self._send(system, user)
        except LlmError:
            self.failures += 1
            raise
        value = parse_json_object(text)                              # only a usable answer is cached
        self._cache[key] = text
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with self.cache_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"k": key, "v": text}) + "\n")
        return value


# ---- personas -------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class HeroSpec:
    persona: str      # who they are (synthetic)
    mission: str      # what they came for tonight


BUILT_IN = [
    HeroSpec("Jun, 34, delivery rider, rents a room in Quezon City, sends money home every month; skips lunch to save.",
             "Wants a hot meal for tonight that costs as little as possible and is happy to wait for a discount."),
    HeroSpec("Mrs. Reyes, 58, retired teacher, lives with her grandchildren; careful with money but not poor.",
             "Needs dinner for four tonight and does not want to hang around the shop."),
    HeroSpec("Lea, 22, call-centre agent on a night shift, buys on her way to work.",
             "Wants something quick before her shift; the price matters less than the time."),
    HeroSpec("Ben, 45, jeepney driver, bargain hunter who knows the neighbourhood shops well.",
             "Looks for the evening markdowns and tells his friends when he finds one."),
]


def load_personas(path, count: int, seed: int = 1) -> list:
    """From a JSONL file of synthetic personas (for example a sample of NVIDIA Nemotron-Personas): each line an object with a text field
    (persona, or professional_persona, or text) and optionally occupation, age, city and mission. Picks `count` reproducibly."""
    import random
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        text = row.get("persona") or row.get("professional_persona") or row.get("text")
        if not text:
            bits = [str(row[k]) for k in ("age", "occupation", "city") if row.get(k)]
            text = ", ".join(bits)
        if text:
            rows.append(HeroSpec(str(text)[:400], str(row.get("mission") or "Doing the usual evening shop; looking for something to eat tonight.")[:200]))
    random.Random(seed).shuffle(rows)
    return rows[:count]


# ---- the hero ---------------------------------------------------------------------------------------------------------
SYSTEM = ("You are role-playing ONE shopper standing in a small neighbourhood shop. Stay in character and decide like that person would. "
          "Choose exactly one action: buy (say how many), ask (ask the cashier when the price usually drops), wait (stay a while for the price to drop) or leave. "
          "You only know what is in your notes; you know nothing about how the shop sets prices. "
          'Reply with JSON only, no other text: {"action": "buy|ask|wait|leave", "qty": <whole number, 0 unless buying>, "reason": "<one short sentence in the first person>"}')


def _money_text(stress: float) -> str:
    return ("money is very tight right now" if stress >= 0.65 else "money is a little tight" if stress >= 0.3 else "money is comfortable")


def _belief_text(c) -> str:
    if c.cut_hour is None:
        return "You have never noticed the price drop."
    how = "quite sure" if c.conf >= 0.7 else "fairly sure" if c.conf >= 0.4 else "only guessing"
    return f"You believe the price usually drops around {cu.clock(c.cut_hour)} ({how})."


def build_prompt(c, obs) -> str:
    notes = [f"- day {d}, {cu.clock(h)}: {t}" for d, h, t in c.diary[-6:]] or ["- (nothing yet)"]
    cheaper = "cheaper than usual" if obs.shelf_price < 0.95 * obs.list_price else "the usual price"
    return "\n".join([
        f"Who you are: {c.hero.persona}",
        f"What you came for tonight: {c.hero.mission}",
        f"Your situation: {_money_text(c.traits.budget_stress)}.",
        f"It is {cu.clock(obs.hour)}. The shop closes at {cu.clock(cu.CLOSE)}.",
        f"On the shelf: cooked chicken at {obs.shelf_price:.0f} pesos each ({cheaper}; the usual price is {obs.list_price:.0f}). {obs.stock_left} left.",
        _belief_text(c),
        "You already asked the cashier tonight." if c.asked else "You have not asked the cashier tonight.",
        "Your notes:", *notes,
        f"You may buy at most {min(MAX_QTY, obs.stock_left)}."])


class HeroCustomer(cu.Customer):
    """A Customer whose decide() is made by the language model; everything else (memory, beliefs, learning) is inherited."""

    def decide(self, obs, rnd):
        if obs.stock_left <= 0:
            return "leave", 0
        self.hero_calls += 1
        try:
            answer = self.llm.complete_json(SYSTEM, build_prompt(self, obs))
            action = str(answer.get("action", "")).strip().lower()
            qty = int(answer.get("qty") or 0)
            reason = str(answer.get("reason") or "").strip()[:160]
            if action not in ACTIONS:
                raise LlmError("unknown action")
            if action == "buy":
                if not 1 <= qty <= min(MAX_QTY, obs.stock_left):
                    raise LlmError("quantity out of range")
                if obs.shelf_price > self.wtp * AFFORD_SLACK:
                    raise LlmError("cannot afford it")
            else:
                qty = 0
            if action == "ask" and self.asked:
                raise LlmError("already asked")
        except (LlmError, ValueError, TypeError):
            self.hero_fallbacks += 1
            return cu.Customer.decide(self, obs, rnd)       # the rule-based decision stands in
        if reason:
            self.note(obs.hour, f"(thinking) {reason}")
        return action, qty


def stub_transport(url, headers, payload):
    """An offline stand-in for the AI API, so the hero path can be tried and tested without a key: a plausible, deterministic shopper."""
    text = payload["messages"][-1]["content"]
    if "cheaper than usual" in text:
        return json.dumps({"action": "buy", "qty": 2, "reason": "It is cheaper now, so I will take two."})
    if "You have not asked the cashier tonight." in text and "never noticed" in text:
        return json.dumps({"action": "ask", "qty": 0, "reason": "I want to know when the price goes down."})
    if "You believe the price usually drops" in text:
        return json.dumps({"action": "wait", "qty": 0, "reason": "It should drop soon, I will wait."})
    return json.dumps({"action": "leave", "qty": 0, "reason": "Too expensive for me tonight."})


def make_hero(customer, spec: HeroSpec, llm):
    """Turn an existing Customer into a hero in place, so friends lists keep pointing at the same object."""
    customer.__class__ = HeroCustomer
    customer.hero, customer.llm, customer.hero_calls, customer.hero_fallbacks = spec, llm, 0, 0
    return customer


def add_heroes(people: list, specs: list, llm) -> list:
    """Replace the first len(specs) customers after Marco (customer 0) with heroes. Returns the heroes."""
    heroes = []
    for i, spec in enumerate(specs[: max(0, len(people) - 1)]):
        heroes.append(make_hero(people[1 + i], spec, llm))
    return heroes


def summary(heroes: list, llm) -> dict:
    return {"heroes": len(heroes), "decisions": sum(h.hero_calls for h in heroes), "fell_back_to_rules": sum(h.hero_fallbacks for h in heroes),
            "api_calls": getattr(llm, "calls", 0), "answered_from_cache": getattr(llm, "cached", 0), "api_failures": getattr(llm, "failures", 0)}
