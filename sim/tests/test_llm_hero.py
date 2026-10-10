import json
import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from simpeso import customers as cu, llm_hero as lh, story
from tests.test_customers_story import FakeShop, person


R = random.Random(11)


def client(answers, **kw):
    """A client whose 'AI API' is a list of canned answers (strings), one per real call."""
    seen = []
    queue = list(answers)

    def transport(url, headers, payload):
        seen.append((url, headers, payload))
        return queue.pop(0) if queue else json.dumps({"action": "leave", "qty": 0, "reason": "x"})

    c = lh.LlmClient("openai", "m", "http://api.test", "secret-key", transport=transport, **kw)
    c.seen = seen
    return c


def hero(llm, **traits):
    c = person(**traits)
    lh.make_hero(c, lh.HeroSpec("Jun, 34, rider.", "Wants a cheap hot meal."), llm)
    c.start_night(0, __import__("random").Random(1), 250.0)
    return c


def obs(price=125.0, stock=10, hour=20.5):
    return cu.Observation(hour=hour, shelf_price=price, list_price=250.0, stock_left=stock)


class ParseTests(unittest.TestCase):
    def test_json_is_found_in_fences_and_chatter(self):
        self.assertEqual(lh.parse_json_object('```json\n{"action": "buy", "qty": 2}\n```')["qty"], 2)
        self.assertEqual(lh.parse_json_object('Sure! {"action": "wait", "qty": 0, "reason": "soon"} Hope that helps.')["action"], "wait")
        self.assertEqual(lh.parse_json_object('{"a": {"b": 1}}')["a"]["b"], 1)

    def test_no_json_is_an_error(self):
        for bad in ("", "no braces", "{broken", "[1, 2]"):
            with self.assertRaises(lh.LlmError):
                lh.parse_json_object(bad)


class ClientTests(unittest.TestCase):
    def test_anthropic_and_openai_wire_formats(self):
        a = lh.LlmClient("anthropic", "claude-x", "https://api.anthropic.com", "k")
        url, headers, body = a.build_request("sys", "usr")
        self.assertEqual(url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(headers["x-api-key"], "k")
        self.assertEqual(body["system"], "sys")
        self.assertEqual(body["messages"], [{"role": "user", "content": "usr"}])
        o = lh.LlmClient("openai", "qwen", "http://host:8000/", None)
        url, headers, body = o.build_request("sys", "usr")
        self.assertEqual(url, "http://host:8000/v1/chat/completions")
        self.assertNotIn("authorization", headers)                 # a local vLLM server needs no key
        self.assertEqual(body["messages"][0], {"role": "system", "content": "sys"})
        self.assertEqual(body["temperature"], 0)

    def test_the_key_never_appears_in_the_repr(self):
        self.assertNotIn("secret-key", repr(client([])))

    def test_answers_are_cached_on_disk_and_replayed_for_free(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "cache.jsonl"
            c1 = client([json.dumps({"action": "wait", "qty": 0, "reason": "r"})], cache_path=path)
            self.assertEqual(c1.complete_json("s", "u")["action"], "wait")
            self.assertEqual(c1.calls, 1)
            c2 = client([], cache_path=path)                       # a new run, same question
            self.assertEqual(c2.complete_json("s", "u")["action"], "wait")
            self.assertEqual((c2.calls, c2.cached), (0, 1))

    def test_an_unusable_answer_is_not_cached_and_the_budget_is_a_hard_stop(self):
        c = client(["not json", json.dumps({"action": "leave", "qty": 0})], max_calls=2)
        with self.assertRaises(lh.LlmError):
            c.complete_json("s", "u")
        c.complete_json("s", "u")
        with self.assertRaises(lh.LlmBudgetExceeded):
            c.complete_json("s", "other")

    def test_from_env_picks_the_provider_and_refuses_when_nothing_is_set(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}, clear=True):
            self.assertEqual(lh.LlmClient.from_env().provider, "anthropic")
        with mock.patch.dict(os.environ, {"LLM_BASE_URL": "http://host:8000", "LLM_MODEL": "Qwen/Qwen2.5-7B-Instruct"}, clear=True):
            c = lh.LlmClient.from_env()
            self.assertEqual((c.provider, c.model), ("openai", "Qwen/Qwen2.5-7B-Instruct"))
        with mock.patch.dict(os.environ, {"LLM_BASE_URL": "http://host:8000"}, clear=True):
            with self.assertRaises(lh.LlmError):
                lh.LlmClient.from_env()                             # no model name
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(lh.LlmError):
                lh.LlmClient.from_env()


class HeroTests(unittest.TestCase):
    def test_a_valid_answer_drives_the_decision_and_the_reason_goes_in_the_diary(self):
        h = hero(client([json.dumps({"action": "buy", "qty": 2, "reason": "It is half price, I will take two."})]))
        self.assertEqual(h.decide(obs(), R), ("buy", 2))
        self.assertTrue(any("(thinking) It is half price" in t for _, _, t in h.diary))
        self.assertEqual(h.hero_fallbacks, 0)

    def test_the_prompt_carries_the_persona_the_shelf_and_the_belief_and_nothing_else(self):
        llm = client([json.dumps({"action": "leave", "qty": 0})])
        h = hero(llm)
        h.cut_hour, h.conf = 20.5, 0.8
        h.decide(obs(price=250.0, hour=19.0), R)
        user = llm.seen[0][2]["messages"][1]["content"]
        for expected in ("Jun, 34, rider.", "Wants a cheap hot meal.", "250 pesos", "10 left", "usually drops around 20:30", "quite sure"):
            self.assertIn(expected, user)
        self.assertNotIn("secret-key", json.dumps(llm.seen[0][2]))

    def test_a_bad_answer_falls_back_to_the_rules_and_is_counted(self):
        for bad in ("not json", json.dumps({"action": "dance"}), json.dumps({"action": "buy", "qty": 99}), json.dumps({"action": "buy", "qty": 0}),
                    json.dumps({"action": "buy", "qty": "x"})):
            h = hero(client([bad]), stress=0.0, thrift=0.0)
            action, _ = h.decide(obs(), R)
            self.assertIn(action, ("buy", "ask", "wait", "leave"))
            self.assertEqual(h.hero_fallbacks, 1, bad)

    def test_it_cannot_buy_what_it_cannot_afford_or_what_is_not_there(self):
        h = hero(client([json.dumps({"action": "buy", "qty": 1})]), stress=0.9)
        h.wtp = 100.0
        self.assertNotEqual(h.decide(obs(price=250.0), R)[0], "buy")      # rules say it cannot pay 250
        self.assertEqual(h.hero_fallbacks, 1)
        h2 = hero(client([json.dumps({"action": "buy", "qty": 3})]), stress=0.0)
        action, qty = h2.decide(obs(stock=2), R)
        self.assertLessEqual(qty, 2)                                          # never more than the stock
        self.assertEqual(h2.decide(obs(stock=0), R), ("leave", 0))

    def test_asking_twice_is_not_allowed(self):
        h = hero(client([json.dumps({"action": "ask", "qty": 0})]))
        h.asked = True
        h.decide(obs(price=250.0), R)
        self.assertEqual(h.hero_fallbacks, 1)

    def test_a_dead_api_never_stops_a_night(self):
        def boom(url, headers, payload):
            raise lh.LlmError("down")
        llm = lh.LlmClient("openai", "m", "http://api.test", None, transport=boom)
        people = cu.build_population(5, size=10)
        heroes = lh.add_heroes(people, lh.BUILT_IN[:3], llm)
        for day in range(10):
            night = story.run_night(people, FakeShop(cut=20.5), day, 5)
            self.assertIn("events", night)
        self.assertEqual(len(heroes), 3)
        self.assertGreater(sum(x.hero_fallbacks for x in heroes), 0)
        self.assertEqual(sum(x.hero_fallbacks for x in heroes), sum(x.hero_calls for x in heroes))

    def test_the_offline_stub_runs_a_whole_night_with_heroes(self):
        llm = lh.LlmClient("openai", "stub", "http://stub", transport=lh.stub_transport, max_calls=10 ** 6)
        people = cu.build_population(7, size=12)
        heroes = lh.add_heroes(people, lh.BUILT_IN, llm)
        for day in range(3):
            story.run_night(people, FakeShop(cut=20.5), day, 7)
        s = lh.summary(heroes, llm)
        self.assertEqual(s["heroes"], 4)
        self.assertGreater(s["decisions"], 0)
        self.assertEqual(s["fell_back_to_rules"], 0)

    def test_heroes_keep_their_place_in_the_friend_circles_and_marco_stays_rule_based(self):
        people = cu.build_population(3, size=20)
        before = [id(p) for p in people]
        lh.add_heroes(people, lh.BUILT_IN[:2], client([]))
        self.assertEqual(before, [id(p) for p in people])
        self.assertNotIsInstance(people[0], lh.HeroCustomer)
        self.assertIsInstance(people[1], lh.HeroCustomer)
        friend_ids = {id(f) for p in people for f in p.friends}
        self.assertTrue(set(before) >= friend_ids)


class PersonaFileTests(unittest.TestCase):
    def test_personas_load_reproducibly_from_jsonl(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "p.jsonl"
            rows = [{"persona": f"Person {i}, a shopper."} for i in range(8)] + [{"age": 30, "occupation": "nurse", "city": "Cebu", "mission": "night snack"}, {"bad": 1}]
            path.write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n", encoding="utf-8")
            a = lh.load_personas(path, 4, seed=2)
            self.assertEqual(a, lh.load_personas(path, 4, seed=2))
            self.assertEqual(len(a), 4)
            everyone = lh.load_personas(path, 99, seed=1)
            self.assertEqual(len(everyone), 9)
            self.assertTrue(any(h.persona == "30, nurse, Cebu" and h.mission == "night snack" for h in everyone))


if __name__ == "__main__":
    unittest.main()
