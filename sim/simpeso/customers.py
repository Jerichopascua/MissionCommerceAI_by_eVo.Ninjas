"""Customer actors: people with their own situation, memory and judgement.

Each customer has traits (how tight money is, how hard they hunt for bargains, how patient, how sociable), a memory of
what they saw, a belief about WHEN the shop cuts prices and how sure they are, friends, and a diary in plain words.
Every evening they decide, in 15-minute steps, whether to buy now, ask the cashier, wait, or leave. They learn from what
they see, what the cashier says and what friends tell them. Nothing here is told to them in advance: a customer who
has never seen a price cut shops at their habit hour at full price.

How "judgement" works today (honest): a transparent rule-based utility model with small bounded noise, so every decision
can be explained and tested. The decide() interface is the place where an LLM could supply the judgement for a few hero
customers; that is not built. Shoppers with adaptive=False never learn (the old statistical behavior), which is what
lets us measure what learning customers change."""
from dataclasses import dataclass, field

from . import rng

OPEN, CLOSE = 17.0, 22.0
STEP = 0.25
MAX_WAIT_HOURS = 2.5


def clock(h: float) -> str:
    return f"{int(h):02d}:{int(round((h - int(h)) * 60)):02d}"


@dataclass(frozen=True)
class Traits:
    budget_stress: float      # 0 comfortable .. 1 money is very tight
    thrift: float             # how hard they hunt for bargains
    patience: float           # 0..1, of the longest wait they will tolerate
    sociability: float        # chance they tell friends about a bargain
    need_p: float             # chance they want the product on a given evening
    habit_hour: float         # when they shop with no information
    max_buy: int              # most units they would take at a bargain price


@dataclass
class Observation:
    hour: float
    shelf_price: float
    list_price: float
    stock_left: int


class Customer:
    def __init__(self, cid: str, name: str, traits: Traits, adaptive: bool = True, friends=()):
        self.id, self.name, self.traits, self.adaptive = cid, name, traits, adaptive
        self.friends = list(friends)
        self.cut_hour = None              # belief: when the price usually drops
        self.conf = 0.0                   # how sure they are of it (0..1)
        self.early_bonus = 0.0            # hours earlier to arrive after missing out
        self.diary = []                   # (day, hour, text)
        self.history = []                 # (day, arrival, bought_qty, price)
        self.state, self.wants, self.wtp, self.arrival, self.asked = "idle", False, 0.0, None, False
        self.last_price, self.day = None, 0

    # ---- the evening -------------------------------------------------------------------------------------
    def note(self, hour: float, text: str) -> None:
        if (self.day, text) not in {(d, t) for d, _, t in self.diary}:      # no repeated lines in one evening
            self.diary.append((self.day, hour, text))

    def start_night(self, day: int, rnd, list_price: float) -> None:
        t = self.traits
        self.day, self.state, self.asked, self.last_price = day, "idle", False, None
        self.wants = rnd.random() < t.need_p
        self.wtp = list_price * (1.08 - 0.5 * t.budget_stress) * rnd.uniform(0.92, 1.08)
        self.arrival = self.plan_arrival(rnd) if self.wants else None

    def plan_arrival(self, rnd) -> float:
        t = self.traits
        if self.adaptive and self.cut_hour is not None and self.conf > 0.25 and t.thrift >= 0.5:
            margin = 0.5 + (1 - self.conf) * 1.5 + self.early_bonus
            arrive = self.cut_hour - min(margin, t.patience * MAX_WAIT_HOURS)
        else:
            arrive = t.habit_hour + rnd.uniform(-0.5, 0.5)
        return min(CLOSE - 0.25, max(OPEN, round(arrive * 4) / 4))

    def decide(self, obs: Observation, rnd):
        """Returns ("buy", qty) | ("ask", 0) | ("wait", 0) | ("leave", 0)."""
        t = self.traits
        if obs.stock_left <= 0:
            return "leave", 0
        full_price = obs.shelf_price > 0.95 * obs.list_price
        if (self.adaptive and full_price and t.thrift >= 0.6 and self.cut_hour is not None and self.conf >= 0.5
                and -0.25 <= self.cut_hour - obs.hour <= t.patience * MAX_WAIT_HOURS):
            return "wait", 0                        # a bargain hunter who trusts the cut waits even if they could pay
        if obs.shelf_price <= self.wtp:
            bargain = obs.shelf_price <= 0.6 * obs.list_price
            qty = 1 if not bargain else 1 + int(round(t.thrift * (t.max_buy - 1) + rnd.uniform(-0.3, 0.3)))
            return "buy", max(1, min(qty, t.max_buy, obs.stock_left))
        if not self.adaptive:
            return "leave", 0
        if not self.asked and self.conf < 0.7 and t.thrift >= 0.4:
            return "ask", 0
        if self.cut_hour is not None and self.conf >= 0.3:
            until = self.cut_hour - obs.hour
            if -0.25 <= until <= t.patience * MAX_WAIT_HOURS:
                return "wait", 0
            if until < -0.75:
                self.conf *= 0.5                    # it is well past the usual time and nothing changed: doubt the belief
                self.note(obs.hour, "the price did not drop when I expected; I trust my guess less now")
        return "leave", 0

    # ---- learning ----------------------------------------------------------------------------------------
    def saw_cut(self, hour: float, exact: bool) -> None:
        self.note(hour, f"saw the price drop{' right when it happened' if exact else ' (already cut when I got there)'} at about {clock(hour)}")
        if not self.adaptive:
            return
        if self.cut_hour is None:
            self.cut_hour, self.conf = hour, 0.4 if exact else 0.3
        else:
            self.cut_hour = 0.6 * self.cut_hour + 0.4 * hour
            self.conf = min(1.0, self.conf + (0.25 if exact else 0.1))

    def told(self, hour, source: str, at: float = None) -> None:
        at = at if at is not None else (self.diary[-1][1] if self.diary else OPEN)
        if hour is None:
            self.note(at, f"{source}: it depends, no fixed time")
            if source == "cashier":
                self.asked = True
            return
        self.note(at, f"{source} says the price usually drops around {clock(hour)}")
        if source == "cashier":
            self.asked = True
        if not self.adaptive:
            return
        if source == "cashier":
            self.cut_hour, self.conf = hour, max(self.conf, 0.6)
        elif self.conf < 0.5:
            self.cut_hour, self.conf = hour, max(self.conf, 0.4)

    def missed_out(self, hour: float) -> None:
        self.note(hour, "everything was gone; next time I come earlier")
        if self.adaptive:
            self.early_bonus = min(1.0, self.early_bonus + 0.25)


def build_population(seed: int, size: int = 40, adaptive: bool = True, hero_adaptive=None) -> list:
    """A neighbourhood: some people comfortable, some squeezed, friends clustered by situation. Customer 0 is Marco,
    who recently lost his job and shops late hoping for cheap food."""
    rnd = rng.derive(seed, "population")
    first = ["Marco", "Ana", "Jun", "Lea", "Rico", "Mia", "Paolo", "Gina", "Ben", "Tess", "Carlo", "Nina", "Dan", "Ella", "Rey", "Joy"]
    people = []
    for i in range(size):
        if i == 0:
            t = Traits(0.9, 0.9, 0.8, 0.8, 0.6, 21.0, 3)
            name = "Marco"
        else:
            kind = rnd.choices(["tight", "medium", "comfortable"], weights=[0.25, 0.35, 0.40])[0]
            stress = {"tight": rnd.uniform(0.65, 0.95), "medium": rnd.uniform(0.3, 0.6), "comfortable": rnd.uniform(0.0, 0.2)}[kind]
            thrift = min(1.0, 0.25 + stress * 0.7 + rnd.uniform(-0.1, 0.1))
            if kind == "comfortable" and rnd.random() < 0.35:
                thrift = rnd.uniform(0.6, 0.9)          # can afford full price but loves a bargain: times the visit to the cut
            t = Traits(stress, thrift, rnd.uniform(0.3, 0.9), rnd.uniform(0.2, 0.9),
                       rnd.uniform(0.2, 0.45), rnd.choice([18.0, 18.5, 19.0, 19.5, 20.0]) if kind != "tight" else rnd.choice([19.0, 20.0, 21.0]),
                       rnd.choice([1, 2, 3]))
            name = f"{rnd.choice(first)} {chr(65 + i % 26)}."
        ad = adaptive if (i != 0 or hero_adaptive is None) else hero_adaptive
        people.append(Customer(f"cust-{i:02d}", name, t, ad))
    by_tight = sorted(range(size), key=lambda i: people[i].traits.budget_stress)
    for pos, i in enumerate(by_tight):                      # friends are people in a similar situation
        near = [by_tight[j] for j in range(max(0, pos - 3), min(size, pos + 4)) if by_tight[j] != i]
        people[i].friends = [people[j] for j in rnd.sample(near, min(3, len(near)))]
    # make sure Marco's circle is people who are squeezed too
    tight = [p for p in people[1:] if p.traits.budget_stress > 0.65]
    people[0].friends = tight[:4]
    return people
