"""A simulated competitor price feed.

Real competitor prices come from a person entering them, a file, or a price-monitoring service. In the simulation there is no outside
world, so this makes up a believable set: three rivals whose prices sit around ours, each product's rival price a fixed random draw
(seeded, so the same world always has the same rivals). This is the simulator's own assumption, labelled as a feed, and the AI sees it
only through PesoWeb's competitor-price endpoint, exactly as it would see a real one."""
from . import rng

COMPETITORS = ("Metro Mart", "Value Grocers", "Corner Store")
SPREAD = 0.06            # typical gap between a rival's price and ours (one standard deviation)
LOW, HIGH = 0.85, 1.20   # no rival is more than 15% below or 20% above


def _tick(price: float) -> float:
    return 0.5 if price < 50 else 1.0


def prices_for(seed: int, product_id: int, our_price: float, competitors=COMPETITORS) -> list:
    out = []
    t = _tick(our_price)
    for c in competitors:
        r = rng.derive(seed, "competitor", c, product_id)
        mult = min(HIGH, max(LOW, r.gauss(1.0, SPREAD)))
        price = max(t, round(round(our_price * mult / t) * t, 2))
        out.append({"ProductId": int(product_id), "Competitor": c, "Price": price})
    return out


def feed(seed: int, products: list, competitors=COMPETITORS) -> list:
    """products: dicts with id and price. Returns the rows to post to /api/ai/competitor-prices."""
    items = []
    for p in products:
        if p.get("price") and p["price"] > 0:
            items += prices_for(seed, p["id"], float(p["price"]), competitors)
    return items
