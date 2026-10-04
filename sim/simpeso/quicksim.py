"""Quick Sim: the aggregated lane. Persistent individuals are rows of a tensor; a day is a few vectorised draws
(who visits, when, what, how many, at the price in force), so a month for hundreds of thousands to millions of people
generates in seconds on a GPU. It does NOT go through PesoWeb and is labelled aggregated everywhere it is shown.
The same models that run on the real-API lane then run over the result: a price-aware demand forecast against a
seasonal-naive baseline, and a residual anomaly detector scored against the anomalies the scenario planted.

    python -m simpeso.quicksim --individuals 200000 --days 28 --device auto --out ../results/quicksim.json

Same seed gives the same result on the same device (a CPU run and a GPU run draw different random streams)."""
import argparse
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import torch

from . import behavior

HOURS = 18


def pick_device(name: str) -> torch.device:
    if name == "auto":
        name = "cuda" if torch.cuda.is_available() else "cpu"      # ROCm builds of torch report as cuda
    return torch.device(name)


def _sync(dev):
    if dev.type == "cuda":
        torch.cuda.synchronize()


def simulate(individuals: int, days: int, branches: int, skus: int, seed: int, dev: torch.device,
             promo_share: float = 0.08) -> dict:
    g = torch.Generator(device=dev if dev.type == "cuda" else "cpu").manual_seed(seed)
    arr = behavior.population_arrays()
    rate_a = torch.tensor(arr["visits_per_week"] / 7.0, dtype=torch.float32, device=dev)
    hour_w = torch.tensor(arr["hour_weights"], dtype=torch.float32, device=dev)
    basket_a = torch.tensor(arr["basket"], dtype=torch.float32, device=dev)
    resp_a = torch.tensor(arr["response"], dtype=torch.float32, device=dev)
    wk_a = torch.tensor(arr["weekend_shopper"], device=dev)
    A = rate_a.shape[0]

    arch = torch.multinomial(rate_a / rate_a.sum(), individuals, replacement=True, generator=g)       # who they are
    home = torch.randint(0, branches, (individuals,), device=dev, generator=g)                       # where they shop
    jitter = 0.8 + 0.4 * torch.rand(individuals, device=dev, generator=g)
    rate_i = rate_a[arch] * jitter
    weekend_i = wk_a[arch]
    resp_i = resp_a[arch]
    sku_w = torch.softmax(torch.randn(A, skus, device=dev, generator=g) * 1.2, dim=1)
    price = torch.tensor(np.round(np.random.default_rng(seed).uniform(15, 220, skus), 2), dtype=torch.float32, device=dev)

    # planted promos: the scenario's price calendar, the thing a forecast has to learn from
    ratio = torch.ones(days, branches, skus, device=dev)
    promo = torch.rand(days, branches, skus, device=dev, generator=g) < promo_share
    ratio = torch.where(promo, 0.6 + 0.3 * torch.rand(days, branches, skus, device=dev, generator=g), ratio)

    daily = torch.zeros(days, branches, skus, device=dev)
    events = 0
    revenue = torch.zeros((), device=dev)
    _sync(dev)
    t0 = time.perf_counter()
    for d in range(days):
        weekend = d % 7 in (5, 6)
        p = rate_i * torch.where(weekend_i, 3.0 if weekend else 0.25, 0.85 if weekend else 1.0)
        visits = torch.poisson(p.clamp(max=3.0), generator=g)
        who = torch.repeat_interleave(torch.arange(individuals, device=dev), visits.long())
        if who.numel() == 0:
            continue
        a = arch[who]
        hour = torch.multinomial(hour_w[a], 1, generator=g).squeeze(1)                                # when
        sku = torch.multinomial(sku_w[a], 1, generator=g).squeeze(1)                                  # what
        b = home[who]
        r = ratio[d, b, sku]
        lam = (basket_a[a] / 3.0).clamp(min=0.5) * r.pow(-resp_i[who])                                # price-aware quantity
        units = torch.poisson(lam, generator=g)
        keep = units > 0
        b, sku, units, hour = b[keep], sku[keep], units[keep], hour[keep]
        daily[d].view(-1).index_add_(0, b * skus + sku, units)
        revenue += (units * price[sku] * ratio[d, b, sku]).sum() + hour.sum() * 0
        events += int(units.numel())
    _sync(dev)
    wall = time.perf_counter() - t0
    return {"daily": daily.cpu().numpy(), "ratio": ratio.cpu().numpy(), "events": events, "wall_s": wall,
            "revenue": float(revenue.item())}


def plant_anomalies(daily: np.ndarray, test_from: int, count: int, seed: int) -> list:
    rng = np.random.default_rng(seed + 7)
    d, b, s = daily.shape
    truth, used = [], set()
    while len(truth) < count:
        cell = (int(rng.integers(test_from, d)), int(rng.integers(0, b)), int(rng.integers(0, s)))
        if cell in used or daily[cell] < 40:
            continue
        used.add(cell)
        factor = float(rng.choice([3.0, 0.2]))
        daily[cell] = np.round(daily[cell] * factor)
        truth.append({"day": cell[0], "branch": cell[1], "sku": cell[2], "factor": factor})
    return truth


def forecast(daily: np.ndarray, ratio: np.ndarray, test_from: int):
    """Returns (model prediction, seasonal-naive prediction, fitted price slope, dispersion) for the test days.
    Dispersion is the training Pearson residual variance: a mixed population is more spread out than Poisson, and
    the anomaly threshold has to know that or it flags ordinary cells."""
    d, b, s = daily.shape
    train, ratios = daily[:test_from], ratio[:test_from]
    wd = np.arange(d) % 7
    base = np.ones((7, b, s))
    for k in range(7):
        sel = train[wd[:test_from] == k]
        rsel = ratios[wd[:test_from] == k]
        clean = np.where(rsel > 0.995, sel, np.nan)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            m = np.nanmean(clean, axis=0)
        base[k] = np.where(np.isnan(m), sel.mean(axis=0), m)
    base = np.maximum(base, 0.05)
    # one pooled log-price slope by Newton's method on the Poisson likelihood of the training days
    x = np.log(ratios)
    mu0 = base[wd[:test_from]]
    beta = -1.0
    for _ in range(40):
        mu = mu0 * np.exp(beta * x)
        g = (x * (train - mu)).sum()
        h = -(x * x * mu).sum()
        step = g / h if h else 0
        beta -= step
        if abs(step) < 1e-9:
            break
    fitted = mu0 * np.exp(beta * x)
    phi = max(1.0, float(np.mean((train - fitted) ** 2 / (fitted + 1.0))))
    pred = base[wd[test_from:]] * np.exp(beta * np.log(ratio[test_from:]))
    naive = daily[test_from - 7:d - 7].copy()
    return pred, naive, float(beta), phi


def wape(pred, actual) -> float:
    return float(np.abs(pred - actual).sum() / max(1.0, np.abs(actual).sum()))


def detect(actual, pred, phi=1.0, z=4.0):
    return np.abs(actual - pred) / np.sqrt(phi * (pred + 1.0)) > z


def run(individuals=200_000, days=28, branches=20, skus=60, seed=1, device="auto", anomalies=12) -> dict:
    dev = pick_device(device)
    sim = simulate(individuals, days, branches, skus, seed, dev)
    daily, ratio = sim["daily"], sim["ratio"]
    test_from = days - 7
    clean_actual = daily[test_from:].copy()
    t1 = time.perf_counter()
    truth = plant_anomalies(daily, test_from, anomalies, seed)
    pred, naive, beta, phi = forecast(daily, ratio, test_from)
    actual = daily[test_from:]
    flags = detect(actual, pred, phi)
    naive_flags = detect(actual, naive, phi)
    cells = {(t["day"] - test_from, t["branch"], t["sku"]) for t in truth}

    def pr(fl):
        hit = sum(1 for c in cells if fl[c])
        flagged = int(fl.sum())
        return {"flagged": flagged, "found": hit, "precision": hit / flagged if flagged else 0.0, "recall": hit / len(cells)}

    model_s = time.perf_counter() - t1
    return {"mode": "aggregated (not through PesoWeb)", "device": str(dev), "gpu": torch.cuda.get_device_name(0) if dev.type == "cuda" else None,
            "individuals": individuals, "days": days, "branches": branches, "skus": skus, "seed": seed,
            "events": sim["events"], "generation_s": round(sim["wall_s"], 3),
            "events_per_s": round(sim["events"] / sim["wall_s"]), "virtual_days_per_s": round(days / sim["wall_s"], 2),
            "revenue_checksum": round(sim["revenue"]), "model_and_detection_s": round(model_s, 3),
            "forecast": {"price_slope": round(beta, 3), "dispersion": round(phi, 2), "model_wape": round(wape(pred, clean_actual), 4),
                         "naive_wape": round(wape(naive, clean_actual), 4)},
            "anomalies": {"planted": len(truth), "model_detector": pr(flags), "naive_detector": pr(naive_flags)}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="simpeso.quicksim")
    ap.add_argument("--individuals", type=int, default=200_000)
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--branches", type=int, default=20)
    ap.add_argument("--skus", type=int, default=60)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    result = run(args.individuals, args.days, args.branches, args.skus, args.seed, args.device)
    text = json.dumps(result, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
