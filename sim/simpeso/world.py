"""World planner: turns seed + profile into a concrete corporate group (central group, companies = tenants, owners,
branches = warehouses, staff, catalogs, suppliers, expansion events). Pure and deterministic; the driver builds it
through the real PesoWeb API. Plan 5 can replace the rule-based business plan with an LLM plan that fits the same
schema, because every number is validated against the tier limits here."""
from dataclasses import dataclass, field, asdict

from . import archetypes, rng, verticals as vt

# SubscriptionTierLimits seed for Business (Subscription = 3); verified in pesoweb-additions/README.md.
BUSINESS_TIER = {"subscription": 3, "branches": 5, "users": 10, "products": 50000, "sales_per_day": 50000}

PROFILES = {
    "smoke":   {"branches": 2, "staff_per_branch": 2, "catalog_cap": 8,  "traffic_scale": 0.02, "regular_pool": 25},
    "starter": {"branches": 4, "staff_per_branch": 2, "catalog_cap": 30, "traffic_scale": 0.05, "regular_pool": 120},
}

COMPANIES = [   # fixed corporate group: five subsidiaries, one vertical each
    ("c1", "Evo Quick Mart", "convenience"),
    ("c2", "Evo Fresh and Pharma", "grocery_pharmacy"),
    ("c3", "Evo Moto Parts", "motorcycle_parts"),
    ("c4", "Evo General Trading", "mixed"),
    ("c5", "Evo Sports Hub", "sports"),
]
OWNER_FOR = {"convenience": "franchise_convenience_chain", "grocery_pharmacy": "supermarket_operator",
             "motorcycle_parts": "rider_parts_mechanic", "mixed": "general_trader", "sports": "sports_hobbyist"}

FIRST = ["Jerome", "Maricel", "Rafael", "Liza", "Dante", "Cheryl", "Noel", "Aileen", "Benjie", "Marites", "Carlo", "Jenny",
         "Arnold", "Rowena", "Paolo", "Grace", "Elmer", "Katrina", "Ramon", "Joy", "Migs", "Tess", "Allan", "Bea"]
LAST = ["Santos", "Reyes", "Cruz", "Bautista", "Ocampo", "Garcia", "Mendoza", "Torres", "Villanueva", "Castillo",
        "Aquino", "Ramos", "Dizon", "Navarro", "Salazar", "Domingo", "Pascual", "Flores", "Lim", "Tan"]
AREAS = [("Quezon City", "residential"), ("Makati", "office district"), ("Pasig", "mixed use"), ("Taguig", "condo cluster"),
         ("Manila", "terminal"), ("Mandaluyong", "office district"), ("Marikina", "residential"), ("Caloocan", "market area"),
         ("Paranaque", "residential"), ("Cebu City", "school belt"), ("Davao City", "mixed use"), ("Las Pinas", "residential")]
STAFF_ROLES = ["Cashier", "Cashier", "Stockkeeper", "Manager"]


@dataclass
class StaffPlan:
    key: str
    name: str
    role: str
    username: str
    email: str
    password: str
    speed: float
    accuracy: float
    reliability: float


@dataclass
class BranchPlan:
    key: str
    name: str
    city: str
    location_type: str
    vertical: str
    txns_per_day: int
    opens_day: int = 0
    opens_hour: int = 0
    staff: list = field(default_factory=list)


@dataclass
class SupplierPlan:
    name: str
    lead_time_days: int


@dataclass
class OwnerPlan:
    name: str
    email: str
    password: str
    archetype: str
    traits: dict


@dataclass
class CompanyPlan:
    key: str
    name: str
    vertical: str
    owner: OwnerPlan
    tier: int
    branches: list
    catalog: list
    suppliers: list
    expiry_reason: str = ""


@dataclass
class WorldPlan:
    seed: int
    profile: str
    group_name: str
    companies: list
    expansions: list
    decisions: list
    settings: dict


def _name(rnd) -> str:
    return f"{rnd.choice(FIRST)} {rnd.choice(LAST)}"


def _password(rnd) -> str:
    return "Sim!" + "".join(rnd.choice("abcdefghjkmnpqrstuvwxyz23456789") for _ in range(8))


def plan_group(seed: int, profile: str = "starter") -> WorldPlan:
    settings = dict(PROFILES[profile])
    verts = vt.load_all()
    owner_lib = {o.id: o for o in archetypes.owner_archetypes()}
    companies, decisions, expansions = [], [], []
    pending = {}   # company key -> (will_expand, areas, owner archetype)
    for ckey, cname, vname in COMPANIES:
        v = verts[vname]
        r = rng.derive(seed, "company", ckey)
        oa = owner_lib[OWNER_FOR[vname]]
        owner = OwnerPlan(_name(r), f"owner.{ckey}.s{seed}@simworld.test", _password(r), oa.id,
                          {"capital": oa.capital, "ambition": oa.ambition, "risk": oa.risk,
                           "patience": round(r.uniform(0.3, 1.0), 2)})
        # business plan: how many branches the owner wants, clamped to the tier cap with room for one expansion
        want = min(oa.ambition, settings["branches"]) if profile == "starter" else settings["branches"]
        will_expand = r.random() < oa.expansion_chance
        cap = BUSINESS_TIER["branches"]
        initial = min(want, cap - (1 if will_expand else 0))
        if initial < want:
            decisions.append(f"{ckey}: initial branches {want} -> {initial} to keep one expansion slot under the Business cap of {cap}")
        branches = []
        areas = rng_sample(r, AREAS, cap)
        for i in range(initial):
            branches.append(_branch(r, ckey, cname, v, areas[i], i + 1, 0, 0))
        companies.append(CompanyPlan(ckey, cname, vname, owner, BUSINESS_TIER["subscription"], branches, [], [],
                                     "" if v.expiry else f"{vname} stock does not expire (spare parts and gear)"))
        pending[ckey] = (will_expand, areas, oa)
    # at least one expansion so a branch always opens mid-run: the company with the highest expansion chance
    if not any(p[0] for p in pending.values()):
        best = max(companies, key=lambda c: pending[c.key][2].expansion_chance)
        pending[best.key] = (True,) + pending[best.key][1:]
        decisions.append(f"{best.key}: expansion forced so every run exercises a mid-run branch opening")
        if len(best.branches) >= BUSINESS_TIER["branches"]:
            best.branches.pop()
    for c in companies:
        will_expand, areas, oa = pending[c.key]
        r = rng.derive(seed, "expansion", c.key)
        if will_expand and len(c.branches) < BUSINESS_TIER["branches"]:
            nb = _branch(r, c.key, c.name, verts[c.vertical], areas[len(c.branches)], len(c.branches) + 1, 0, r.randint(11, 15))
            c.branches.append(nb)
            expansions.append({"company": c.key, "branch": nb.key, "day": 0, "hour": nb.opens_hour})
        _staff_and_catalog(c, verts[c.vertical], seed, settings, oa, decisions)
        c.suppliers = [SupplierPlan(f"{c.name} Supplier {n + 1}", rng.derive(seed, "supplier", c.key, n).randint(1, 4))
                       for n in range(2)]
    return WorldPlan(seed, profile, "Evo Retail Holdings", companies, expansions, decisions, settings)


def rng_sample(r, pool, k):
    items = list(pool)
    r.shuffle(items)
    return items[:k]


def _branch(r, ckey, cname, v, area, n, day, hour) -> BranchPlan:
    city, loc = area
    lo, hi = v.txns_per_day
    return BranchPlan(f"{ckey}-b{n}", f"{cname} {city} {n}", city, loc, v.name, r.randint(lo, hi), day, hour)


def _staff_and_catalog(c: CompanyPlan, v: vt.Vertical, seed: int, settings: dict, oa, decisions: list) -> None:
    users_cap = BUSINESS_TIER["users"] - 1       # one seat is the owner
    per = settings["staff_per_branch"]
    wanted = per * len(c.branches)
    if wanted > users_cap:
        decisions.append(f"{c.key}: staff {wanted} -> {users_cap} to fit the Business user limit of {BUSINESS_TIER['users']} (owner included)")
    remaining = users_cap
    for b in c.branches:
        n = min(per, remaining) if b.opens_hour == 0 else min(max(1, per - 1), remaining)
        n = max(n, 0)
        remaining -= n
        for s in range(n):
            r = rng.derive(seed, "staff", b.key, s)
            role = "Cashier" if s == 0 else STAFF_ROLES[(s + 1) % len(STAFF_ROLES)]
            b.staff.append(StaffPlan(f"{b.key}-s{s + 1}", _name(r), role, f"{b.key.replace('-', '')}s{s + 1}x{seed}",
                                     f"{b.key}.s{s + 1}.s{seed}@simworld.test", _password(r),
                                     round(r.uniform(0.6, 1.0), 2), round(r.uniform(0.85, 1.0), 3),
                                     round(r.uniform(0.8, 1.0), 2)))
    size = round(oa.catalog_share * v.catalog_size[1])
    size = max(v.catalog_size[0], size)
    size = min(size, settings["catalog_cap"], BUSINESS_TIER["products"])
    c.catalog = vt.build_catalog(v, rng.derive(seed, "catalog", c.key), size)


def to_dict(plan: WorldPlan) -> dict:
    return asdict(plan)


def plan_hash(plan: WorldPlan) -> str:
    return rng.stable_hash(to_dict(plan))
