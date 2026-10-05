"""A simulated approver: a virtual store manager working the Approval Center queue.

In a simulation nobody is at the screen, so this stands in for the person. It reads the same queue a real approver sees and
decides from the same evidence (lane, learned or assumed, low-risk flag, margin, top seller), with a seeded temperament.
Every decision goes through the normal approve / reject endpoints, so the audit log, guardrails and undo behave exactly as
they would for a real person. The decisions are the simulator's assumption about people, not a measurement of them.
"""
from dataclasses import dataclass

from . import rng


@dataclass
class ApproverStyle:
    approve_rate_learned: float = 0.9     # chance to approve a change backed by learned evidence
    approve_rate_assumed: float = 0.4     # chance to approve a change that only rests on an assumption
    approve_rate_rule: float = 0.97       # a margin fix (price raised to the margin price) is a rule, not a guess: nearly always approved
    owner_lane_rate: float = 0.7          # extra caution for owner-lane changes
    trim_big_moves: bool = True           # approve a big raise at a smaller step instead of rejecting it
    max_delay_minutes: int = 120          # the longest a change waits before someone looks (virtual minutes)


def decide(item: dict, style: ApproverStyle, rand) -> dict:
    """item is one entry of GET /api/Pricing/Approvals. Returns {action, new_price, reason, delay_minutes}."""
    delay = int(rand.random() * style.max_delay_minutes)
    if item.get("belowSoftFloor") and float(item.get("pct") or 0) <= 0:       # a cut into the soft band is refused; a raise toward the floor is not
        return {"action": "reject", "reason": "below the soft margin floor", "delay_minutes": delay}
    if item.get("lowRisk"):
        return {"action": "approve", "reason": "low risk", "delay_minutes": delay}
    if item.get("confidence") == "rule":
        if rand.random() < style.approve_rate_rule:
            return {"action": "approve", "reason": "fixes a price below the margin price", "delay_minutes": delay}   # never trimmed: half a fix is still below the floor
        return {"action": "reject", "reason": "left for later", "delay_minutes": delay}
    learned = item.get("confidence") == "learned"
    rate = style.approve_rate_learned if learned else style.approve_rate_assumed
    if item.get("lane") == "Owner":
        rate *= style.owner_lane_rate
    if rand.random() >= rate:
        return {"action": "reject", "reason": "not convinced by the evidence" if not learned else "too much change at once", "delay_minutes": delay}
    pct = float(item.get("pct") or 0)
    if style.trim_big_moves and pct > 8 and item.get("type") == "Price":
        frm, to = float(item["from"]), float(item["to"])
        return {"action": "edit", "new_price": round(frm + (to - frm) * 0.5, 2), "reason": "approved half the step", "delay_minutes": delay}
    return {"action": "approve", "reason": "looks fine", "delay_minutes": delay}


def work_queue(drv, acct, seed: int, style: ApproverStyle = None, round_no: int = 0) -> dict:
    """Decide everything waiting for this account. Returns counts and the decisions (for the run log)."""
    style = style or ApproverStyle()
    queue = drv._call("GET", "/api/Pricing/Approvals", acct.token)
    out = {"seen": len(queue["items"]), "approved": 0, "edited": 0, "rejected": 0, "stale": 0, "failed": 0, "decisions": []}
    for item in queue["items"]:
        if not item.get("canApprove"):
            continue
        rand = rng.derive(seed, "approver", item["id"], round_no)
        d = decide(item, style, rand)
        is_md = item["type"] == "Markdown"
        if d["action"] == "reject":
            path, body = ("/api/Pricing/Reject" if is_md else "/api/Pricing/RejectListPrice"), {"PriceChangeId": item["id"], "Reason": f"simulated approver: {d['reason']}"}
        else:
            path, body = ("/api/Pricing/Approve" if is_md else "/api/Pricing/ApproveListPrice"), {"PriceChangeId": item["id"]}
            if d["action"] == "edit":
                body["NewPrice"] = d["new_price"]
        status, resp = drv._call("POST", path, acct.token, json_body=body, raw=True)
        ok = status == 200
        stale = not ok and (resp or {}).get("code") == "PRICE_CHANGED_SINCE"     # the price moved since it was proposed: the server closes it
        key = {"approve": "approved", "edit": "edited", "reject": "rejected"}[d["action"]] if ok else ("stale" if stale else "failed")
        out[key] += 1
        out["decisions"].append({"id": item["id"], "name": item["name"], **d, "ok": ok, "status": status, "code": (resp or {}).get("code")})
    return out
