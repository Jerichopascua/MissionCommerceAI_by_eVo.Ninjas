"""AI Insight, second half: how the AI is doing, and what to improve in its setup.

`analyze(snapshot)` reads what PesoWeb holds about the AI (the switches, the branch settings, the pricing rules, the outcome of every price
proposal, the approval queue, the AI-branch-against-control comparison, the run history) and returns findings in two groups:

  Analysis  what happened, in numbers (the effect so far, what became of the proposals, AI against control)
  Improve   what to change in the setup, and why (a refused-too-often rule, proposals expiring unseen, no control branch, a feature never run)

Every finding is a deterministic rule over the numbers, with the figures it used kept in `facts`. Nothing here is a language model, and nothing
changes PesoWeb: it only says what it sees. A language model may later reword a finding (see insight.reword), and a figure it adds is thrown away.

Snapshot (all parts optional; a missing part just produces fewer findings):
    now          ISO time
    features     [{key, name, enabled, buildState, canRun, lastRun: {status, finishedAt, summary} | None}]
    branches     [{warehouseId, name, pricingEnabled, wasteTargetPct, salesTargetPerDay}]
    policy       {configured, autonomyMode, hardMarginFloorPct, maxDiscountPct, storeLaneMaxPct, ...}
    impact       the AI Impact payload (/api/ai/hub/impact)
    approvals    {summary: {waiting, oldestMinutes, approvedToday, autoApprovedToday, expiredJustNow}}
    changes      [{source, status, guardrailCode, discountPct, createdAt}]  (the price-change log)
    tasks        {act, approvals, alerts, reorders, counts, sellFast}
"""
import datetime as dt

MIN_PROPOSALS = 5                    # below this the shares are too noisy to talk about
REFUSAL_SHARE = 0.2                  # a rule that refuses at least this share of proposals is worth a look
STALE_RUN_DAYS = 7
OLD_QUEUE_MINUTES = 8 * 60

# How PesoWeb records what became of a price change (Status, GuardrailCode). A rule refusal is a Rejected change with any other code.
NOT_A_RULE = {"OK", "AUTO_APPROVED", "REJECTED_BY_USER", "PROPOSAL_EXPIRED"}
BY_PERSON = "REJECTED_BY_USER"
EXPIRED = "PROPOSAL_EXPIRED"

REFUSAL_ADVICE = {
    "BELOW_HARD_FLOOR": ("Check that unit costs are current: a stale cost makes a fair price look too low. If the costs are right, those batches "
                         "need a smaller discount, not a lower floor."),
    "EXCEEDS_MAX_DISCOUNT": ("If clearing short-dated stock matters more than margin on it, raise the maximum discount; otherwise nothing "
                             "is wrong, the rule did its job."),
    "NO_COST": "Enter the unit cost for these products. Without a cost the AI cannot tell a safe price from a loss, so it will not propose one.",
    "TOO_MANY_CHANGES": "The AI is being stopped from changing one product's price again and again. Raise the hourly limit only if that is intended.",
    "AUTONOMY_OFF": "Pricing autonomy is switched off, so every AI markdown is refused. Switch it to Approval or Autonomous to let it propose.",
}


def _f(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _g(value, places=1):
    text = f"{_f(value):.{places}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def _peso(v):
    return "₱{:,.0f}".format(_f(v))


def _signed(v, places=1):
    return ("+" if _f(v) >= 0 else "-") + _g(abs(_f(v)), places)


def _ai_changes(s):
    """The AI's own proposals in the price-change log (not the manual ones, and not an ended markdown)."""
    return [c for c in (s.get("changes") or []) if str(c.get("source", "")).lower() == "ai" and str(c.get("status", "")).lower() != "ended"]


def _code(c):
    return str(c.get("guardrailCode") or "").upper()


def _outcomes(changes):
    out = {"applied": 0, "waiting": 0, "byPerson": 0, "expired": 0, "byRule": 0}
    for c in changes:
        st, code = str(c.get("status") or "").lower(), _code(c)
        if code == BY_PERSON:
            out["byPerson"] += 1
        elif code == EXPIRED:
            out["expired"] += 1
        elif st in ("applied", "approved"):
            out["applied"] += 1
        elif st in ("pending", "proposed"):
            out["waiting"] += 1
        elif st in ("rejected", "refused") and code not in NOT_A_RULE:
            out["byRule"] += 1
    return out


def _note(kind, ref, headline, body, facts, severity):
    return {"kind": kind, "refKey": ref, "headline": headline, "body": body, "facts": facts, "severity": severity}


def _days_ago(iso, now):
    try:
        t = dt.datetime.fromisoformat(str(iso)[:19])
        return max(0, (now - t).days)
    except (TypeError, ValueError):
        return None


# ---- what happened ------------------------------------------------------------------------------------------------------------------

def effect_so_far(s):
    imp = s.get("impact") or {}
    if not imp.get("available"):
        return None
    after = (imp.get("after") or {}).get("metrics") or {}
    before = (imp.get("before") or {}).get("metrics") or {}
    n = int(imp.get("windowDays") or 0)
    if not n or not _f(after.get("sales")):
        return None
    ch = imp.get("change") or {}
    switch = str(imp.get("switchDate") or "")[:10]
    facts = {"days": n, "sales": after.get("sales"), "marginPct": after.get("marginPct"), "wastePct": after.get("wastePct"),
             "marginPerDay": ch.get("marginPerDay"), "aiPriceChanges": imp.get("aiPriceChanges")}
    if _f(before.get("sales")) <= 0:
        body = (f"Since the AI started pricing on {switch}, {n} days of sales are on record: {_peso(after['sales'])}, with a margin of "
                f"{_g(after.get('marginPct'))}%. There is no earlier period to compare with, so the effect of the AI cannot be separated yet.")
        return _note("Analysis", "analysis:effect", "Too early to measure the effect", body, facts, "Watch")
    facts.update(salesPct=ch.get("salesPct"), marginPts=ch.get("marginPts"), wastePts=ch.get("wastePts"))
    body = (f"Over {n} days after {switch} against the {n} days before: sales {_signed(ch.get('salesPct'))}%, margin rate "
            f"{_signed(ch.get('marginPts'))} points, waste rate {_signed(ch.get('wastePts'))} points; margin per day {_signed(ch.get('marginPerDay'), 0)} pesos "
            f"with {imp.get('aiPriceChanges', 0)} AI price changes applied. Indicative, not proof: the season and promotions also moved.")
    good = _f(ch.get("marginPerDay")) > 0
    return _note("Analysis", "analysis:effect", "The effect since the AI started pricing", body, facts, "Good" if good else "Watch")


def ai_vs_control(s):
    ctl = (s.get("impact") or {}).get("control") or {}
    if not ctl.get("available"):
        return None
    ai, co, d = ctl.get("ai") or {}, ctl.get("control") or {}, ctl.get("difference") or {}
    facts = {"aiBranches": ai.get("branches"), "controlBranches": co.get("branches"),
             "aiMarginPts": (ai.get("change") or {}).get("marginPts"), "controlMarginPts": (co.get("change") or {}).get("marginPts"),
             "aiWastePts": (ai.get("change") or {}).get("wastePts"), "controlWastePts": (co.get("change") or {}).get("wastePts"),
             "marginPts": d.get("marginPts"), "wastePts": d.get("wastePts"), "salesPts": d.get("salesPts")}
    body = (f"{ai.get('branches')} AI branch(es) against {co.get('branches')} control branch(es), the same days: the AI branches' margin moved "
            f"{_signed(facts['aiMarginPts'])} points and waste {_signed(facts['aiWastePts'])}, the control's {_signed(facts['controlMarginPts'])} and "
            f"{_signed(facts['controlWastePts'])}. Difference: margin {_signed(d.get('marginPts'))} points, waste {_signed(d.get('wastePts'))} points.")
    better = _f(d.get("marginPts")) > 0 or _f(d.get("wastePts")) < 0
    return _note("Analysis", "analysis:control", "AI branches against the control branch", body, facts, "Good" if better else "Watch")


def proposal_outcomes(s):
    ch = _ai_changes(s)
    n = len(ch)
    if n < MIN_PROPOSALS:
        return None
    o = _outcomes(ch)
    facts = {"proposals": n, "applied": o["applied"], "waiting": o["waiting"], "byPerson": o["byPerson"], "expired": o["expired"],
             "byRule": o["byRule"], "appliedPct": round(o["applied"] / n * 100)}
    body = (f"Of {n} price proposals the AI made, {o['applied']} were applied ({facts['appliedPct']}%), {o['waiting']} are waiting, "
            f"{o['byPerson']} were rejected by a person, {o['byRule']} were refused by a rule and {o['expired']} expired without a decision.")
    lost = o["byPerson"] + o["byRule"] + o["expired"]
    return _note("Analysis", "analysis:proposals", "What became of the AI's price proposals", body, facts, "Watch" if lost * 2 > n else "Good")


# ---- what to improve ----------------------------------------------------------------------------------------------------------------

def pricing_rules(s):
    p = s.get("policy") or {}
    if p and not p.get("configured", True):
        return _note("Improve", "improve:policy", "Set the pricing rules",
                     "No pricing rules are set, so the AI cannot make any price proposal. Set the hard margin floor and the maximum discount "
                     "in the Approval Center, Settings.", {}, "Act")
    if p and _f(p.get("hardMarginFloorPct"), 1) <= 0:
        return _note("Improve", "improve:floor", "The hard margin floor is 0%",
                     "A markdown may go all the way down to cost. A small floor (a few percent over cost) leaves something for handling and "
                     "loss; it costs little because the AI only goes that low when the batch would otherwise be thrown away.",
                     {"hardMarginFloorPct": p.get("hardMarginFloorPct")}, "Watch")
    return None


def refusals(s):
    ch = _ai_changes(s)
    n = len(ch)
    if n < MIN_PROPOSALS:
        return []
    p = s.get("policy") or {}
    by = {}
    for c in ch:
        code = _code(c)
        if code and code not in NOT_A_RULE and str(c.get("status") or "").lower() in ("rejected", "refused"):
            by[code] = by.get(code, 0) + 1
    out = []
    for code, k in sorted(by.items(), key=lambda kv: -kv[1]):
        if k / n < REFUSAL_SHARE and k < 5:
            continue
        advice = REFUSAL_ADVICE.get(code, "Look at the reason shown on each refused proposal in the Approval Center.")
        extra = ""
        if code == "BELOW_HARD_FLOOR":
            extra = f" (the floor is {_g(p.get('hardMarginFloorPct'))}% over cost)"
        if code == "EXCEEDS_MAX_DISCOUNT":
            extra = f" (the limit is {_g(p.get('maxDiscountPct'))}%)"
        facts = {"refused": k, "proposals": n, "sharePct": round(k / n * 100), "code": code,
                 "hardMarginFloorPct": p.get("hardMarginFloorPct"), "maxDiscountPct": p.get("maxDiscountPct")}
        out.append(_note("Improve", f"improve:refusal:{code}", f"{k} of {n} proposals refused: {code.replace('_', ' ').lower()}",
                         f"{k} of the AI's {n} price proposals ({facts['sharePct']}%) were refused by this rule{extra}. {advice}", facts, "Act"))
    return out[:2]


def person_rejections(s):
    ch = _ai_changes(s)
    n = len(ch)
    if n < MIN_PROPOSALS:
        return None
    o = _outcomes(ch)
    decided = o["applied"] + o["byPerson"]
    if not decided or o["byPerson"] / n < 0.15:
        return None
    facts = {"proposals": n, "byPerson": o["byPerson"], "applied": o["applied"], "sharePct": round(o["byPerson"] / n * 100)}
    body = (f"People rejected {o['byPerson']} of the AI's {n} proposals ({facts['sharePct']}%) and approved {o['applied']}. Look at what the rejected "
            f"ones have in common in the Approval Center: if they are mostly the larger moves, a smaller maximum step will get more of the AI's "
            f"proposals approved instead of rejected.")
    return _note("Improve", "improve:rejections", f"{o['byPerson']} of {n} proposals were rejected by people", body, facts, "Watch")


def stale_queue(s):
    sm = (s.get("approvals") or {}).get("summary") or {}
    expired_log = sum(1 for c in _ai_changes(s) if _code(c) == EXPIRED)
    waiting, expired, oldest = int(_f(sm.get("waiting"))), max(int(_f(sm.get("expiredJustNow"))), expired_log), _f(sm.get("oldestMinutes"))
    if expired <= 0 and not (waiting and oldest >= OLD_QUEUE_MINUTES):
        return None
    p = s.get("policy") or {}
    lane = _g(p.get("storeLaneMaxPct") or 5, 0)
    facts = {"waiting": waiting, "expired": expired, "oldestMinutes": oldest, "storeLaneMaxPct": p.get("storeLaneMaxPct")}
    body = (f"{expired} proposal(s) expired without a decision and {waiting} are waiting (the oldest {_g(oldest, 0)} minutes). A markdown loses value "
            f"every hour the stock sits. Name someone who looks at the Approval Center each day, or let the AI apply small steps on its own "
            f"(up to {lane}%) by setting the autonomy mode, so only the large changes wait for a person.")
    return _note("Improve", "improve:queue", "Proposals are expiring before anyone decides", body, facts, "Act")


def control_branch(s):
    imp = s.get("impact") or {}
    ctl = imp.get("control") or {}
    branches = s.get("branches") or []
    if ctl.get("available") or len(branches) < 2:
        return None
    ai_on = sum(1 for b in branches if b.get("pricingEnabled", True))
    if ai_on < len(branches):
        return None                      # a branch is already set aside; the comparison just has no days yet
    facts = {"branches": len(branches), "aiBranches": ai_on}
    body = (f"All {len(branches)} branches have AI markdowns on, so the AI cannot be compared with anything. Switch AI markdowns off at one "
            f"branch that is similar in size and mix, keep the others on, and after a few days the Hub shows a fair AI-against-control comparison.")
    return _note("Improve", "improve:control", "Set one branch aside as a control", body, facts, "Watch")


def feature_use(s, now):
    out = []
    for f in s.get("features") or []:
        name = f.get("name") or f.get("key")
        if f.get("buildState") not in (None, "Built") or not f.get("canRun", True):
            continue
        if not f.get("enabled", True):
            out.append(_note("Improve", f"improve:off:{f.get('key')}", f"{name} is switched off",
                             f"{name} is off for this company, so nothing from it appears in the Hub. Switch it on in AI Control if that is not intended.",
                             {}, "Watch"))
            continue
        last = f.get("lastRun") or None
        if not last:
            out.append(_note("Improve", f"improve:never:{f.get('key')}", f"{name} has never run",
                             f"{name} is on but has not produced anything yet. Press Run now in AI Control (the agent must be running).", {}, "Watch"))
            continue
        age = _days_ago(last.get("finishedAt") or last.get("requestedAt"), now)
        if age is not None and age >= STALE_RUN_DAYS:
            out.append(_note("Improve", f"improve:stale:{f.get('key')}", f"{name} last ran {age} days ago",
                             f"{name} last ran {age} days ago, so what it shows is stale. Run it again, or schedule the agent so it runs every day.",
                             {"daysAgo": age}, "Watch"))
    return out[:3]


def waste_targets(s):
    imp = s.get("impact") or {}
    targets = {b.get("warehouseId"): b for b in (s.get("branches") or [])}
    out = []
    for r in imp.get("branches") or []:
        t = targets.get(r.get("warehouseId")) or {}
        target, waste = t.get("wasteTargetPct"), ((r.get("after") or {}).get("wastePct"))
        if target is None or waste is None:
            continue
        if _f(waste) > _f(target):
            facts = {"wastePct": waste, "targetPct": target, "aiMarkdowns": r.get("aiMarkdowns")}
            tail = ("AI markdowns are off here." if not t.get("pricingEnabled", True)
                    else f"The AI applied {r.get('aiMarkdowns', 0)} markdown(s) there; check the hour before which it may not mark down, or the "
                         f"maximum discount.")
            out.append(_note("Improve", f"improve:waste:{r.get('warehouseId')}", f"{r.get('name')}: waste above target",
                             f"Waste at {r.get('name')} is {_g(waste)}% against a target of {_g(target)}%. {tail}", facts, "Watch"))
    return out[:2]


def too_early(s):
    imp = s.get("impact") or {}
    if imp.get("available"):
        n = int(imp.get("windowDays") or 0)
        if 0 < n < 7:
            return _note("Improve", "improve:window", "Wait for more days before judging",
                         f"Only {n} days have passed since the AI started pricing. Read the comparison after at least 14 days, so one good or bad week "
                         f"is not mistaken for the effect.", {"days": n}, "Watch")
        return None
    return _note("Improve", "improve:window", "No AI price change has been applied yet",
                 "The effect cannot be measured until the AI has applied a price change. Approve proposals in the Approval Center, or let AI "
                 "markdowns run, and come back after a few days.", {}, "Watch")


def analyze(s: dict) -> list:
    now = dt.datetime.fromisoformat(str(s.get("now") or dt.datetime.now().isoformat())[:19])
    notes = []
    for rule in (effect_so_far, ai_vs_control, proposal_outcomes):
        n = rule(s)
        if n:
            notes.append(n)
    improve = ([pricing_rules(s)] + refusals(s) + [stale_queue(s), person_rejections(s), control_branch(s)] + waste_targets(s)
               + feature_use(s, now) + [too_early(s)])
    order = {"Act": 0, "Watch": 1, "Good": 2}
    improve = sorted([n for n in improve if n], key=lambda n: order.get(n["severity"], 3))
    return notes + improve
