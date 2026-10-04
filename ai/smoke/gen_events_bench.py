"""GPU event-generation benchmark for the Quick Sim aggregated lane.

Synthetic customers visit shops at their own rates; each visit becomes a transaction event
(hour, SKU, quantity, amount). This only measures raw generation throughput on the device.
It is not the full simulator, and it does not claim anything about retail accuracy.

Env: CUSTOMERS (default 2,000,000 on GPU / 200,000 on CPU), DAYS (default 30).
"""
import os
import time

import torch

dev = "cuda" if torch.cuda.is_available() else "cpu"
CUSTOMERS = int(os.environ.get("CUSTOMERS", 2_000_000 if dev == "cuda" else 200_000))
DAYS = int(os.environ.get("DAYS", 30))
SKUS = 400


def sync():
    if dev == "cuda":
        torch.cuda.synchronize()


def main():
    torch.manual_seed(20271)
    rate = torch.rand(CUSTOMERS, device=dev) * 0.6 + 0.1          # visits per day per customer
    base_price = torch.rand(SKUS, device=dev) * 200 + 10
    sku_weight = torch.softmax(torch.randn(SKUS, device=dev), 0)
    events = 0
    revenue = torch.zeros((), device=dev)

    sync()
    t0 = time.perf_counter()
    for _ in range(DAYS):
        visits = torch.poisson(rate)
        total = int(visits.sum().item())
        hour = torch.randint(6, 23, (total,), device=dev)         # kept so the work is not optimised away
        sku = torch.multinomial(sku_weight, total, replacement=True)
        qty = torch.randint(1, 6, (total,), device=dev).float()
        price = base_price[sku] * (1 + 0.05 * torch.randn(total, device=dev))
        revenue += (qty * price).sum() + hour.sum() * 0
        events += total
    sync()
    dt = time.perf_counter() - t0
    print(f"device={dev} customers={CUSTOMERS:,} days={DAYS} events={events:,} "
          f"time={dt:.2f}s  ~{events / dt:,.0f} events/s  (revenue checksum {revenue.item():,.0f})")


if __name__ == "__main__":
    main()
