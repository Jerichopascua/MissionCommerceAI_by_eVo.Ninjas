"""Make two "twin" worlds comparable before a trial day.

Worlds that lived through different histories (price tests, more simulated days) end up with different stock on the shelf, and a
product that is sold out cannot sell. That alone can look like a 20% difference between "AI" and "no AI". So before each trial day:
  * top_up_stock: every product at every branch is brought up to the same level in both worlds;
  * align_rates: the short-dated lots are sized from the same sales rates in both worlds (the base world's rates, matched by
    branch and product code), so both receive identical lots.
Check any pair of worlds with scripts/aa_check.py (same day, no AI, no price change) before trusting a comparison."""
import datetime as dt
import subprocess

DEFAULT_LEVEL = 60
CHUNK = 120


def on_hand(drv, owner, warehouse_id) -> dict:
    out = {}
    for b in drv.all_batches(owner, warehouse_id):
        out[b["productId"]] = out.get(b["productId"], 0.0) + float(b["qtyOnHand"])
    return out


def top_up_stock(ctx, hooks, level: int = DEFAULT_LEVEL, tag: str = "top", today: dt.date = None) -> int:
    """Receive stock so each product at each branch has at least `level` units. Returns the number of lines received."""
    today = today or dt.date.today()
    drv, total = ctx.driver, 0
    for ckey, bkey, wh in hooks.live_branches():
        owner = ctx.owner(ckey)
        cs = ctx.state["companies"][ckey]
        have = on_hand(drv, owner, wh)
        lines = []
        for p in ctx.cmap[ckey].catalog:
            pid = cs["products"][p.code]
            need = level - have.get(pid, 0.0)
            if need < 1:
                continue
            line = {"product_id": pid, "unit_cost": p.cost, "quantity": int(need)}
            if p.expiry:                      # a perishable product's ordinary stock keeps well beyond the trial lots
                line["batch_no"] = f"{tag}-{wh}-{p.code}"
                line["expiry_date"] = (today + dt.timedelta(days=60)).isoformat()
                line["manufacturing_date"] = (today - dt.timedelta(days=1)).isoformat()
            lines.append(line)
        for i in range(0, len(lines), CHUNK):          # one purchase form is limited to 1,024 fields
            drv.receive_stock(owner, wh, cs["suppliers"][0], lines[i:i + CHUNK], today.isoformat())
        total += len(lines)
    return total


def rate_by_branch_code(hooks) -> dict:
    """(branch key, product code) -> units per day, from the hooks' learned rates."""
    out = {}
    for ckey, bkey, wh in hooks.live_branches():
        for pid, info in hooks._catalog.items():
            if info["company"] == ckey and (wh, pid) in hooks.rates:
                out[(bkey, info["code"])] = hooks.rates[(wh, pid)]
    return out


def align_rates(src_hooks, dst_hooks) -> int:
    """Give dst_hooks the same sales rates as src_hooks (matched by branch and product code). Returns the number set."""
    src = rate_by_branch_code(src_hooks)
    new, n = {}, 0
    for ckey, bkey, wh in dst_hooks.live_branches():
        for pid, info in dst_hooks._catalog.items():
            if info["company"] == ckey and (bkey, info["code"]) in src:
                new[(wh, pid)] = src[(bkey, info["code"])]
                n += 1
    dst_hooks.rates = new
    return n


def clear_leftover_lots(ctx, hooks, server: str = r"(localdb)\MSSQLLocalDB", database: str = "PesoWeb_MissionDev") -> int:
    """Test-bench housekeeping, done straight in the throwaway SQL database (PesoWeb has no API to remove a batch): zero out the unsold
    trial lots of earlier days. They carry the same expiry date as today's lots, so the POS would sell them first and distort the
    waste of today's lots, differently in each world. Only batches named lot-% in this world's companies are touched."""
    tenants = sorted({ctx.owner(ck).tenant_id for ck, _, _ in hooks.live_branches()})
    sql = f"SET NOCOUNT ON; UPDATE ProductBatches SET QtyOnHand = 0 WHERE BatchNo LIKE 'lot-%' AND QtyOnHand > 0 AND TenantID IN ({','.join(str(int(x)) for x in tenants)}); SELECT @@ROWCOUNT"
    out = subprocess.run(["sqlcmd", "-S", server, "-d", database, "-E", "-h", "-1", "-W", "-Q", sql], capture_output=True, text=True, check=True)
    return int(out.stdout.strip().splitlines()[-1])
