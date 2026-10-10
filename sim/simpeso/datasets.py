"""Customer data sets: where the shoppers of a test come from, chosen by the person who starts it (one, or a combination).

A test must name its customer data set(s); there is no silent default. Each data set says what it can be used for (its roles), whether its
files are present, and what it is. A combination is a weighted mix: for every simulated visit one source is picked by weight (seeded, so a run
repeats), and that source supplies the basket.

Roles:
  visits     supplies baskets (what a shopper puts in the basket), so it can drive a business-day run
  decisions  supplies the judgement of a few shoppers step by step (hero shoppers; the customer-story test only)
  demand     supplies price and units history, to fit and check the demand model (the validation test)
  missions   supplies real "why I came" answers, to check AI Customer Mission

Real data sets are files the user puts under sim/customer_data/<id>/ (that folder is git-ignored; licences and privacy are the user's to check).
"""
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(os.environ.get("CUSTOMER_DATA_DIR") or Path(__file__).resolve().parent.parent / "customer_data")
ROLES = ("visits", "decisions", "demand", "missions")


@dataclass(frozen=True)
class DatasetSpec:
    id: str
    name: str
    kind: str                 # simulated | real-store | public | survey | ai
    roles: tuple
    summary: str
    files: tuple = ()         # files that must exist under DATA_DIR/<id>/ (any one name in a group, separated by |)
    needs_env: tuple = ()     # at least one of these environment variables must be set
    where: str = ""           # shown when it is not available
    note: str = ""            # limits and licence reminders


REGISTRY = {d.id: d for d in [
    DatasetSpec("simulated-rules", "Simulated shoppers (rule-based)", "simulated", ("visits",),
                "Seeded pretend shoppers built from the archetype library; their price reaction is the simulator's own assumption. Always available.",
                note="Not real behaviour."),
    DatasetSpec("hero-llm", "Hero shoppers (AI API)", "ai", ("decisions",),
                "A few shoppers with a persona and a mission whose choices come from an AI API; the rest stay rule-based. Used by the customer-story test.",
                needs_env=("ANTHROPIC_API_KEY", "LLM_BASE_URL", "OPENAI_API_KEY"),
                where="Set ANTHROPIC_API_KEY, or LLM_BASE_URL and LLM_MODEL (see simpeso/llm_hero.py).",
                note="A model playing a person is still a simulation."),
    DatasetSpec("store-pos", "Real store sales (your own POS export)", "real-store", ("visits", "demand"),
                "Receipts of a real store. Baskets are replayed; the history also fits and checks the demand model.",
                files=("receipts.csv|sales.csv|pos.csv",),
                where="Put a CSV with receipt id, date/time, product and quantity (and price) in customer_data/store-pos/receipts.csv.",
                note="Personal data (names, phone numbers) must not be in it."),
    DatasetSpec("instacart", "Instacart Market Basket (public)", "public", ("visits",),
                "About 3 million grocery orders with hour of day and weekday; no prices. Baskets are replayed.",
                files=("orders.csv", "order_products__prior.csv"),
                where="Download the Instacart Market Basket Analysis files and put orders.csv and order_products__prior.csv in customer_data/instacart/.",
                note="US online grocery, not the Philippines. Check the licence before use."),
    DatasetSpec("dunnhumby", "Dunnhumby The Complete Journey (public)", "public", ("visits", "demand"),
                "About 2,500 households over two years with promotions and coupons. Baskets are replayed; prices and promotions fit the demand model.",
                files=("transaction_data.csv",),
                where="Download The Complete Journey and put transaction_data.csv in customer_data/dunnhumby/.",
                note="US supermarket. Check the licence before use."),
    DatasetSpec("m5", "M5 Walmart (public)", "public", ("demand",),
                "Daily unit sales with weekly sell prices for Walmart items. For checking the demand model, not for baskets.",
                files=("sales_train_validation.csv|sales_train_evaluation.csv", "sell_prices.csv", "calendar.csv"),
                where="Download the M5 Forecasting files into customer_data/m5/.", note="US. Check the licence before use."),
    DatasetSpec("favorita", "Corporacion Favorita (public)", "public", ("demand",),
                "Daily unit sales and an on-promotion flag for Ecuadorian grocery stores (no prices). For checking the demand model.",
                files=("train.csv",), where="Download the Favorita grocery sales files and put train.csv in customer_data/favorita/.",
                note="Ecuador. Check the licence before use."),
    DatasetSpec("till-survey", "Till question: why did you come today (real answers)", "survey", ("missions",),
                "One-tap answers collected from real shoppers at the till, used as ground truth for AI Customer Mission.",
                files=("answers.csv",), where="Collect receipt id, date/time and mission answers into customer_data/till-survey/answers.csv.",
                note="Needs the shoppers' consent; no personal data."),
]}


class SelectionError(Exception):
    pass


def folder(dataset_id: str) -> Path:
    return DATA_DIR / dataset_id


def _has(group: str, base: Path) -> bool:
    return any((base / name).is_file() for name in group.split("|"))


def status(spec: DatasetSpec) -> dict:
    """{'available': bool, 'missing': [...]} for one data set."""
    missing = []
    base = folder(spec.id)
    for group in spec.files:
        if not _has(group, base):
            missing.append(group)
    if spec.needs_env and not any(os.environ.get(v) for v in spec.needs_env):
        missing.append("one of " + ", ".join(spec.needs_env))
    return {"available": not missing, "missing": missing}


def catalog() -> list:
    out = []
    for spec in REGISTRY.values():
        s = status(spec)
        out.append({"id": spec.id, "name": spec.name, "kind": spec.kind, "roles": list(spec.roles), "summary": spec.summary,
                    "available": s["available"], "missing": s["missing"], "where": spec.where, "note": spec.note})
    return out


@dataclass
class Mix:
    """The chosen data sets with weights (normalised to 1) and what the test uses them for."""
    weights: dict = field(default_factory=dict)

    def ids(self) -> list:
        return list(self.weights)

    def with_role(self, role: str) -> dict:
        w = {i: x for i, x in self.weights.items() if role in REGISTRY[i].roles}
        total = sum(w.values())
        return {i: x / total for i, x in w.items()} if total > 0 else {}

    def summary(self) -> str:
        return ", ".join(f"{i} {w * 100:.0f}%" for i, w in self.weights.items())

    def as_dict(self) -> dict:
        return {"datasets": self.weights, "summary": self.summary()}


def parse(text: str) -> dict:
    """'store-pos:0.6,simulated-rules:0.4' or 'instacart,dunnhumby' (equal weights) -> {id: weight}, not yet normalised or checked."""
    out = {}
    for part in [p.strip() for p in (text or "").split(",") if p.strip()]:
        name, _, w = part.partition(":")
        name = name.strip()
        try:
            weight = float(w) if w else 1.0
        except ValueError:
            raise SelectionError(f"'{w}' is not a number (in '{part}')")
        if weight <= 0:
            raise SelectionError(f"the weight of '{name}' must be above 0")
        out[name] = out.get(name, 0.0) + weight
    return out


def build_mix(text: str, purpose: str, stub_llm: bool = False) -> Mix:
    """Check a selection for a purpose: 'visits' (a business-day run), 'story' (customer story: visits are not used, heroes are),
    'demand' (the validation test), 'missions' (the Customer Mission check). Raises SelectionError with a message a person can act on."""
    raw = parse(text)
    if not raw:
        raise SelectionError("no customer data set was chosen. A test must say which one(s) to use.")
    unknown = [i for i in raw if i not in REGISTRY]
    if unknown:
        raise SelectionError("unknown data set: " + ", ".join(unknown) + ". Known: " + ", ".join(REGISTRY))
    unavailable = []
    for i in raw:
        s = status(REGISTRY[i])
        if i == "hero-llm" and stub_llm:
            continue                                  # the offline stand-in needs no key
        if not s["available"]:
            unavailable.append(f"{i}: missing {', '.join(s['missing'])}. {REGISTRY[i].where}")
    if unavailable:
        raise SelectionError("not available:\n  " + "\n  ".join(unavailable))
    total = sum(raw.values())
    mix = Mix({i: w / total for i, w in raw.items()})
    if purpose == "visits":
        unusable = [i for i in raw if "visits" not in REGISTRY[i].roles]
        need = "visits"
    elif purpose == "story":
        unusable = [i for i in raw if i not in ("hero-llm", "simulated-rules")]
        need = "hero-llm and/or simulated-rules"
    else:
        need = {"demand": "demand", "missions": "missions"}[purpose]
        unusable = [i for i in raw if need not in REGISTRY[i].roles]
    if unusable:
        raise SelectionError(f"{', '.join(unusable)} cannot be used for this test. This test needs data sets with the role: {need}. "
                             + "; ".join(f"{i} is for {', '.join(REGISTRY[i].roles)}" for i in unusable))
    return mix


def menu_text() -> str:
    lines = ["Customer data sets (choose one, or several with weights, for example  store-pos:0.6,simulated-rules:0.4):", ""]
    for n, d in enumerate(catalog(), 1):
        mark = "available" if d["available"] else "NOT available"
        lines.append(f"  {n}. {d['id']:16s} [{mark}]  roles: {', '.join(d['roles'])}")
        lines.append(f"       {d['name']}. {d['summary']}")
        if not d["available"]:
            lines.append(f"       to use it: {d['where']}")
    return "\n".join(lines)


def choose(arg: str, purpose: str, stream_in=None, stream_out=None, stub_llm: bool = False) -> Mix:
    """The selection a test needs. If none was given and a person is at the keyboard, show the menu and ask; otherwise refuse (never a silent default)."""
    stream_in, stream_out = stream_in or sys.stdin, stream_out or sys.stdout
    if not arg:
        if not (hasattr(stream_in, "isatty") and stream_in.isatty()):
            raise SelectionError("no customer data set was chosen: add  --datasets <id[:weight],...>\n\n" + menu_text())
        print(menu_text(), file=stream_out)
        print("\nType the ids (or their numbers) separated by commas, with optional :weights.", file=stream_out)
        arg = stream_in.readline().strip()
        names = list(REGISTRY)
        parts = []
        for p in [x.strip() for x in arg.split(",") if x.strip()]:
            head, _, w = p.partition(":")
            if head.isdigit() and 1 <= int(head) <= len(names):
                head = names[int(head) - 1]
            parts.append(head + (":" + w if w else ""))
        arg = ",".join(parts)
    return build_mix(arg, purpose, stub_llm)


def record(run_dir: Path, mix: Mix, day=None, purpose: str = "visits") -> None:
    """Remember in the run's folder which data sets a test used, so the result can always say."""
    path = Path(run_dir) / "datasets.json"
    rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    rows.append({"day": day, "purpose": purpose, **mix.as_dict()})
    path.write_text(json.dumps(rows[-200:], indent=1), encoding="utf-8")


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="simpeso.datasets", description="List the customer data sets and whether their files are in place.")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    print(json.dumps(catalog(), indent=1) if args.json else menu_text())
    print(f"\nReal data files go under {DATA_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
