# Approval Center: design

Status: proposal with a clickable mock (`ui/prototype/approvals.html`, mock data only). Not built in PesoWeb yet. The back end it needs partly exists: guarded list-price proposals, approve and reject, and the ledger (see `price-advisor-and-price-test.md`, section 5).

## 1. The idea

One inbox for every change that needs a person, so nobody hunts through screens. The AI proposes, PesoWeb checks the rules, a person decides, and everything is logged. Today the things that wait for a person are list-price changes, markdowns that need approval (below the soft floor, or approval mode), and in future other exceptions that need a decision.

## 2. Who should approve (routing by risk, not by one fixed person)

| Lane | Who | Goes here when |
|---|---|---|
| Store manager | branch or store manager | the move is 5% or less, the price stays above the soft margin floor, the product is not a top seller, the sensitivity is learned from sales, and (for a markdown) it is a short-dated lot |
| Pricing manager | category or pricing manager (the owner in a small shop) | a move over 5%, or a top seller, or below the soft floor, or the sensitivity is only assumed |
| Owner | tenant owner or finance | a move over 8% on a top seller or below the soft floor, any bulk change (many products at once, or a total effect above a set peso amount), anything that touches the margin policy itself |

Rules for every lane:
- **The AI is never an approver.** It can only propose.
- **No self-approval:** a person cannot approve their own manual proposal.
- **A one-tenant Lite shop** has only an owner, so everything goes to the owner.
- **Proposals expire:** a stale proposal is closed rather than approved late. A markdown on a lot that expires tonight carries a visible time limit.
- **The central company** does not approve a subsidiary's prices. It sees the totals (group overview) and can audit.
- Routing thresholds belong in the tenant's pricing policy, not in code. (Today the 15% increase cap is a constant in code.)

## 3. The screen

Layout: a queue on the left, evidence for the selected item on the right, counters on top.

- **Counters:** waiting, oldest waiting, profit at stake per day (the conservative figure), approved today, auto-approved.
- **Queue:** grouped by lane. Each row shows the product, scope (all branches or one), old to new price and the percentage, how long it has waited, and chips: `learned` or `assumed` sensitivity, `top seller`, `below soft floor`, `low risk`, `time limit`.
- **Detail panel:** a plain-words reason, margin now and after, how fast it sells, the sensitivity with its range, the expected profit per day and the conservative figure, and a rule checklist (above the margin price, move within the limit, hourly limit, soft floor, evidence quality). It states what is missing: for a raise on a thin-margin staple, "no competitor price feed, check rivals first".
- **Actions:** Approve, Reject (a reason is required, with common reasons as quick picks), Approve with a different price (a slider limited to the allowed range), Ask for a price test first (sends the item to the price-test queue).
- **Bulk:** "Approve all low-risk (n)" covers only items that pass every check and move the price by 5% or less, and it shows the count and the total effect before it acts.
- **Safety nets:** an undo that restores the previous price through the same checks and is itself logged; a decision log of who decided what and when.
- **Speed:** keyboard (`j` and `k` to move, `a` to approve, `r` to reject).
- **Phones:** one column of cards for store managers, with a badge, and a daily digest instead of constant pings.

## 4. Real shop versus simulation

Real shop: nothing changes until a person approves. That stays the default and cannot be switched off by the AI.

Simulation needs to run without waiting for a person, without throwing away the approval step, so two separate mechanisms are proposed:
1. **Auto-approve within limits (a tenant policy setting, off by default).** Changes that are small, learned, and above the soft floor are approved automatically and logged as `auto` with the rule that allowed them. Everything else still waits in the queue. This is also the "trust ladder" for a real shop: it can be switched on later, tenant by tenant, once the owner trusts the AI.
2. **A simulated approver** (a virtual store manager used only in simulation) that works through the queue with a configurable delay and approve rate, so the simulation exercises the real human step and measures how long approvals take and what gets rejected.

Simulation tenants turn the setting on; real tenants keep it off. Every approval records who or what decided, so a report can always separate human approvals from automatic ones.

## 5. Build plan (not started)

| Part | Work |
|---|---|
| Policy | add list-price approval settings (auto-approve on or off, the size limit, the increase cap, lane thresholds, expiry time) with a migration |
| Queue API | one endpoint that lists everything waiting across list-price changes and markdowns, with lane, evidence and rule checks; bulk approve; undo |
| Permissions | permissions per lane (store, pricing, owner) granted like the existing pricing permissions |
| Screen | an Approval Center page in the web app (Angular), following the mock |
| Simulator | the simulated approver and a setting that turns auto-approve on for simulation tenants |
| Tests | rules, lanes, no self-approval, expiry, undo, bulk limits |

## 6. Open decisions

- The lane thresholds (5% and 8%, what counts as a top seller, the bulk peso limit).
- Whether auto-approve should ever apply to a raise, or only to decreases and markdown-like moves.
- Who the real approvers are for the target customers (a mini-mart owner, a branch manager, a head office pricing team).
