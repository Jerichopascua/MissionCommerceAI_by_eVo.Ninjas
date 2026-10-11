"""AI Insight: plain-language explanations of what the AI did and why.

The facts come from PesoWeb (what the other AI features suggested and the numbers behind it). A fixed template always produces a
correct sentence from those facts. A language model may reword it more naturally, but only under three conditions:

  1. it is given nothing but the facts and the template sentence, and told to reword, never to add or decide;
  2. every number in its answer must be one of the numbers in the facts (a figure it made up makes the answer unusable);
  3. any failure, timeout or unusable answer falls back to the template, so output never depends on a model being available.

The model is never in a decision path: nothing here changes a price, an order or a stock level.
"""
import hashlib
import json
import re
from pathlib import Path

NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
MAX_WORDS = 70


def peso(value) -> str:
    return "₱{:,.0f}".format(float(value)) if abs(float(value) - round(float(value))) < 0.005 else "₱{:,.2f}".format(float(value))


def g(value, places: int = 1) -> str:
    text = f"{float(value):.{places}f}"
    if "." in text:                       # drop trailing zeros of a fraction only: 2.50 -> 2.5, but 30 stays 30
        text = text.rstrip("0").rstrip(".")
    return text


def when(days) -> str:
    d = int(round(float(days)))
    return "today" if d == 0 else "tomorrow" if d == 1 else f"in {d} days"


def _numbers(value, out: set):
    """Every number in a facts structure, as the figures a sentence might show (whole, one and two decimals)."""
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        v = float(value)
        for form in (round(v), round(v, 1), round(v, 2), abs(round(v)), abs(round(v, 1)), abs(round(v, 2))):
            out.add(float(form))
    elif isinstance(value, str):
        for m in NUMBER.findall(value):
            try:
                out.add(float(m.replace(",", "")))
            except ValueError:
                pass
    elif isinstance(value, dict):
        for v in value.values():
            _numbers(v, out)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _numbers(v, out)


def allowed_numbers(facts: dict) -> set:
    out = set()
    _numbers(facts, out)
    return out


def valid_wording(text: str, facts: dict, template_text: str = "") -> bool:
    """True when the wording only uses numbers that are in the facts (or in the template sentence built from them)."""
    if not text or not text.strip():
        return False
    if len(text.split()) > MAX_WORDS:
        return False
    allowed = allowed_numbers(facts)
    _numbers(template_text, allowed)
    for m in NUMBER.findall(text):
        try:
            v = float(m.replace(",", ""))
        except ValueError:
            return False
        if not any(abs(v - a) < 0.005 for a in allowed):
            return False
    return True


# ---- templates: one correct sentence per kind, from the facts alone ----------------------------------------------------------------

def template(kind: str, f: dict) -> tuple:
    """(headline, body)"""
    if kind == "SellFast":
        name = f["product"]
        if f.get("daysLeft") is not None and float(f["daysLeft"]) < 0:
            n = abs(int(round(float(f["daysLeft"]))))
            return (f"{name}: write off",
                    f"{g(f['unitsAtRisk'], 0)} unit(s) expired {n} day(s) ago and are still on the books, about {peso(f['valueAtRiskAtCost'])} at cost. "
                    f"They cannot be sold: write them off under Inventory.")
        body = (f"{g(f['batchQty'], 0)} units at {f['branch']} expire {when(f['daysLeft'])}. At about {g(f['ratePerDay'])} a day, "
                f"about {g(f['unitsAtRisk'], 0)} will be left, worth {peso(f['valueAtRiskAtCost'])} at cost.")
        if f.get("suggestedDiscountPct"):
            body += f" A {g(f['suggestedDiscountPct'], 0)}% rush sale at {peso(f['suggestedPrice'])} is expected to clear them."
        status = f.get("proposalStatus")
        if status == "Proposed":
            body += " The markdown is waiting for approval."
        elif status == "Applied":
            body += " The markdown is on."
        pct = f.get("suggestedDiscountPct")
        head = f"{name}: {g(pct, 0)}% rush sale suggested" if pct else f"{name}: may expire unsold"
        return head, body
    if kind == "Count":
        return (f"Count {f['product']} first",
                f"{f['branch']} shows {g(f['onHand'], 0)} on the shelf, about {peso(f['valueAtCost'])} at cost. {f.get('reason') or ''}".strip())
    if kind == "Replenish":
        return (f"Reorder {f['product']}",
                f"{f['branch']} has {g(f['onHand'], 0)} on hand and sells about {g(f['ratePerDay'])} a day, which is {g(f['daysOfCover'])} day(s) of cover. "
                f"Suggested order: {g(f['suggestedQty'], 0)} units, with a delivery lead time of {g(f['leadTimeDays'], 0)} days.")
    if kind == "Markdown":
        move = "down" if float(f["to"]) < float(f["from"]) else "up"
        body = (f"{f['name']} at {f['scope']}: price {move} from {peso(f['from'])} to {peso(f['to'])} ({g(abs(float(f['pct'])), 0)}%). "
                f"The margin goes from {g(f['marginNowPct'])}% to {g(f['marginAfterPct'])}%.")
        if f.get("reason"):
            body += " " + f["reason"]
        return f"{f['name']}: price {move} {g(abs(float(f['pct'])), 0)}%", body
    raise ValueError(f"unknown insight kind: {kind}")


SYSTEM = ("You reword notes for a store owner. Use only the facts and the sentence you are given. Write at most two short, plain sentences. "
          "Keep every number exactly as given. Never add a number, a reason or a recommendation that is not in the facts.")


def reword(kind: str, ref: str, headline: str, body: str, facts: dict, wording=None, cache_dir=None) -> dict:
    """One note from a sentence that is already correct. A model (`wording`, a callable (system, user) -> text) may reword it, and its answer
    is used only if every figure in it is in the facts or in the sentence it was given."""
    source = "template"
    if wording is not None:
        key = hashlib.sha256(json.dumps([kind, facts, body], sort_keys=True, default=str).encode()).hexdigest()[:24]
        cached = None
        path = Path(cache_dir) / f"{key}.json" if cache_dir else None
        if path and path.exists():
            try:
                cached = json.loads(path.read_text(encoding="utf-8")).get("text")
            except (OSError, ValueError):
                cached = None
        text = cached
        if text is None:
            try:
                text = wording(SYSTEM, json.dumps({"facts": facts, "sentence": body}, default=str))
            except Exception:
                text = None
            if text and path:
                try:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps({"text": text}), encoding="utf-8")
                except OSError:
                    pass
        if text and valid_wording(text.strip(), facts, body):
            body, source = text.strip(), "model"
    return {"kind": kind, "refKey": ref, "headline": headline, "body": body, "source": source}


def build(kind: str, ref: str, facts: dict, wording=None, cache_dir=None) -> dict:
    """One explanation: the standard sentence for what another AI feature suggested, optionally reworded."""
    headline, body = template(kind, facts)
    return reword(kind, ref, headline, body, facts, wording, cache_dir)
