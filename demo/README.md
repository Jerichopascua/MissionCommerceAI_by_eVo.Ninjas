# Concept demo (local only)

One PesoWeb feature (FEFO expiry stock plus guardrailed markdown pricing) and one very simple agent task, against your local PesoWeb server. No GPU, LLM or simulator needed.

    # 1. start PesoWeb on the dev database (see pesoweb-additions/README.md), default http://localhost:5071
    # 2. run
    python demo/concept_demo.py            # needs: pip install requests pyyaml

It signs up a fresh shop, stocks 40 units of milk expiring tomorrow and 40 expiring in 20 days, lets the owner set margin guardrails, then runs the agent. It prints what the POS charges before and after, shows PesoWeb refusing an 80%-off request with a reason code, and shows both attempts in PesoWeb's price-change ledger. It exits 0 only if all 9 checks pass.

Last run: 9 of 9 passed (agent chose 30% off, POS price 100 to 70, 80% off refused as `EXCEEDS_MAX_DISCOUNT`).

Limits: the daily sales rate (12) and the price response are assumptions because the shop has no sales history. This proves the mechanism and the guardrails, not a real-store lift. For multi-seed measured results see `results/` and the dashboard.
