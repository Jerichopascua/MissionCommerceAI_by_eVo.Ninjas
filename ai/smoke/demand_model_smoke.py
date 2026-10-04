"""Can we recover a hidden price response from sales? (core of the markdown proof, in miniature.)

The 'simulator' knows each SKU-branch pair's true price elasticity. The model sees only
units sold at the discounts that were tried, and must estimate the elasticity.
Model: units ~ Poisson(base * (1 - discount) ** -elasticity), fitted by gradient descent on the device.

PASS means the training pipeline works on this device and the estimator is sane. It says nothing
about real shoppers: the true elasticity here is our own assumption.
"""
import time

import torch

dev = "cuda" if torch.cuda.is_available() else "cpu"
PAIRS, DAYS = 5000, 14
LADDER = torch.tensor([0.0, 0.05, 0.10, 0.20, 0.30, 0.50], device=dev)


def main():
    torch.manual_seed(7)
    true_e = torch.rand(PAIRS, device=dev) * 1.7 + 0.8             # hidden elasticity 0.8 .. 2.5
    true_b = torch.exp(torch.randn(PAIRS, device=dev) * 0.5 + 2.0)  # hidden base units/day
    disc = LADDER[torch.randint(0, len(LADDER), (PAIRS, DAYS), device=dev)]
    x = -torch.log(1 - disc)                                        # log-price effect
    y = torch.poisson(true_b[:, None] * torch.exp(true_e[:, None] * x))

    log_b = torch.zeros(PAIRS, device=dev, requires_grad=True)
    e = torch.ones(PAIRS, device=dev, requires_grad=True)
    opt = torch.optim.Adam([log_b, e], lr=0.05)

    if dev == "cuda":
        torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(400):
        opt.zero_grad()
        log_lam = log_b[:, None] + e[:, None] * x
        # Poisson negative log-likelihood + shrinkage of each pair's elasticity toward the population mean.
        # 14 noisy days per pair is too little to fit each pair alone (unpooled correlation ~0.79); 0.1 is where
        # the improvement plateaus across seeds (~0.83). The real engine should pool across branches and categories.
        loss = (torch.exp(log_lam) - y * log_lam).mean() + 0.1 * ((e - e.mean()) ** 2).mean()
        loss.backward()
        opt.step()
    if dev == "cuda":
        torch.cuda.synchronize()
    dt = time.perf_counter() - t0

    mae = (e.detach() - true_e).abs().mean().item()
    corr = torch.corrcoef(torch.stack([e.detach(), true_e]))[0, 1].item()
    print(f"device={dev} pairs={PAIRS} days={DAYS} train_time={dt:.2f}s")
    print(f"elasticity MAE={mae:.3f}  correlation={corr:.3f}")
    ok = mae < 0.35 and corr > 0.8
    print("PASS" if ok else "CHECK: estimator is weaker than expected (see MAE/correlation)")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
