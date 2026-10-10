# PesoProfit "Agentic Dynamic Markdown Pricing": what we deliver, by AI feature

The brief (`PesoProfit Agentic Dynamic Markdown Pricing.md`) promises an agentic layer that watches live signals, decides markdowns, keeps to commercial rules and pushes prices everywhere. In PesoWeb that layer is delivered by **four AI features**, each runnable from **Intelligent Hub, AI Control, Run now**, on a simulated world or on a real company (`Docs/real-use-guide.md`).

| Feature | Its job | Run now | Where its output appears |
|---|---|---|---|
| **AI Monitoring** | Watches the numbers and the books for what is out of the ordinary | Yes | My tasks, Alert rules, Overview |
| **AI Pricing** | Decides markdowns and list prices inside the owner's rules | Yes | Approval Center |
| **AI Product Loss Prevention** | Says what to count first, to find hidden shrink and unreported deliveries | Yes (new) | Count first, My tasks |
| **AI Replenish** | Says what to reorder, how much and when | Yes | Reorders, draft purchase orders |

## 1. The brief, claim by claim

| The brief says | Status | How, and where to see it |
|---|---|---|
| **Continuous live signal ingestion**: product expiry timelines | **Done** | Expiry batches and FEFO are PesoWeb's own; `expiry-risk` and `batches` feeds read them. AI Pricing marks down batches that are 1 to 3 days from expiry; AI Monitoring flags expired stock not written off |
| ...inventory positions and rate of sale at SKU and store level | **Done** | AI Pricing and AI Replenish compute a rate of sale per product per branch from the ledger; AI Replenish adds days of cover and a safety allowance |
| ...live competitor price monitoring at store level | **Partly** | A competitor-price table (fed by an agent or a person) is shown beside every proposal and caps price rises at 5% above the lowest rival. There is **no live scraping**; the demo feed is simulated |
| **Autonomous decisioning**: the agents decide and execute | **Done within rules; deliberately not for list prices** | The markdown agent decides on a bounded discount ladder and applies it itself when the company's autonomy is **Autonomous**; PesoWeb can still refuse. List-price changes always wait for a person (Approval Center) by design |
| ...applied throughout the trading day | **Done** | The markdown agent ticks hourly in the simulator and every 15 minutes in the customer story; the rate limit is "at most N changes per product per hour" |
| **Hard and soft margin thresholds** | **Done** | Policy: hard floor (never below cost plus x%), soft floor (below needs a person), deepest markdown, rate limit; enforced by PesoWeb on every change |
| **Store-level waste reduction targets** | **Partly** | A waste target per branch (share of cost of sales) is set and shown against actual waste. It does **not yet steer** the agent automatically |
| **Alignment with strategic trading priorities** | **Not built** | Not modelled (no category or campaign priorities) |
| **Push to ESL, e-commerce, picking systems** | **Partly** | PesoWeb's own POS and checkout always charge the current price. A generic webhook sends price changes and alerts to any https address once each. **No connector** for a particular electronic shelf label, e-commerce or picker product |
| **Impact: reduced shrink and waste** | **Shown in simulation** | Twin worlds, AI against no AI: ahead on 10 of 10 days, markdowns trimmed waste (`Docs/showcase-results.md`). Real effect needs real days with a control branch (AI Impact) |
| **Impact: protected margins** | **Done** | Margin floors are enforced; 25 real products were found priced under 5% above cost on the real company |
| **Impact: real-time agility** | **Partly** | Intra-day ticks and a one-minute Overview; no sub-minute event stream |

## 2. The four features

### AI Monitoring
- **Does:** checks the nine rules (expired stock, cash difference, selling below cost, shrinkage, too much stock, exceptions, proposals waiting...) and, on top, compares each branch with its own recent past (sales halved or doubled, one cash difference far above usual, a cashier short again and again, a burst of returns or deleted sales, shelf quantity that no longer matches the ledger).
- **Evidence:** 9 live checks; on the real company it found ₱3,600 of expired stock not written off and ledger differences on 488 products.
- **Limits:** needs about a week of sales history for the sales check; thresholds are fixed, not learned.

### AI Pricing
- **Does:** for stock close to expiry, the markdown that maximises expected profit on a bounded ladder (must beat "no markdown" by a margin); for list prices, the best bounded step under a learned or assumed price sensitivity, never below the margin floor, with a no-regret check and a rival-price cap.
- **Evidence:** the demand model on 2 years of real supermarket sales: price awareness lowers the forecast error by about 10 to 12% like for like (`Docs/real-data-demand-check.md`).
- **Limits:** a real company's price sensitivity is "assumed" until it has price variation; a company with no pricing policy has every proposal refused (set it first).

### AI Product Loss Prevention (new: now runnable)
- **Does:** PesoWeb's POS cannot see a short delivery or silent stock loss, because nothing is recorded. The AI spends a small counting budget where a loss would cost the most and is least likely to be explained by a record: stock delivered **without a receiving report** first, then high-value fast sellers. The list appears under **Count first** and in My tasks; a person counts on the shelf and corrects any difference on the Stock Adjustments screen. A product just counted or dismissed is not suggested again for 14 days.
- **Evidence:** 11 live checks; on the real company it listed 8 products to count first, led by BIOGESIC (390 on the shelf, ₱15,600 at cost, delivered with no receiving report).
- **Limits:** it never counts or changes stock itself; it says "count differs from system", never an accusation. A product with nothing on the shelf at a branch is left out. To link a received purchase to its receiving report it matches ledger rows to purchase lines by order and only where counts and quantities agree.

### AI Replenish
- **Does:** for every product at every branch, will the stock last until a delivery arrives? Reorder point = rate x lead time + a safety allowance for about a 90% service level; order up to cover; pack rounding; perishables capped at their shelf life. A person turns suggestions into **Pending** draft purchase orders; nothing is sent to a supplier.
- **Evidence:** covered by the Intelligent Hub live checks (reorders, draft purchase orders) and unit tests on the reorder maths.
- **Limits:** on the real company it correctly found nothing to reorder (the shelves hold far more than the sales rate needs); the staged demo scenario shows it working.

## 3. What is still not in the brief's picture

- Live competitor monitoring beyond a fed table.
- ESL, e-commerce and picking-system connectors.
- Waste targets that steer the agent; strategic trading priorities.
- Real measured profit effect on a real store.

These are stated in the submission as limits, not hidden.
