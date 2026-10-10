# How we added a "smart helper" to a shop system (the simple version)

*For anyone who has never worked with shop software. No computer science needed.*

---

## 1. The problem, in one story

Imagine Mang Tomas, who owns a small convenience store with two branches.

- His **milk** goes bad in 5 days. If he does not sell it in time, it goes in the trash and he loses money.
- He is not sure if he should charge ₱52 or ₱55 for a bottle of soda.
- Some shelves run empty on Friday because he forgot to reorder on Wednesday.
- Someone at the till is "short" in the cash every week, and he cannot tell if it is a mistake or something else.

His shop software, **PesoWeb**, already records everything: every sale, every delivery, every peso in the cash drawer, every product that is about to expire. But it just **stores** the information. It does not **tell him what to do**.

Our project fixes that. We added a **smart helper** (we call it *MissionCommerce AI*) that reads what PesoWeb already knows and says:

> "Mark this milk down 20% today, it will sell before it expires."
> "You will run out of instant coffee in 2 days. Order 36 packs."
> "This cashier's drawer has been short 4 times this week. Take a look."

And here is the most important rule of the whole project:

> **The helper only suggests. The shop owner (or PesoWeb's own safety rules) decides.**

---

## 2. The hackathon track we are solving: "Reinvent Commerce"

The AMD hackathon track says: *"Help a business understand its customers and take better action."*

That is exactly Mang Tomas's problem: understand what is happening in the shop, then **do something useful** about it. The track asks us to show:

| What the judges want | What we show |
|---|---|
| A real shop problem | Wasted food, wrong prices, empty shelves, cash that does not add up |
| A useful action | A price change, a reorder, an alert, each one with the reason |
| Suggestions that fit the shop | The helper learns from this shop's own sales |
| A measurable effect | More profit and less wasted food, tested against a copy of the shop without the helper |
| Explain how predictions are made | Every number comes from simple math you can check. A chatbot is **never** the thing making predictions |

---

## 3. What the helper can do (6 skills)

Think of six little helpers, each with one job. The owner can switch each one **on or off** in a screen called **AI Control**.

1. **AI Pricing** looks at food that is close to its expiry date and suggests a discount. It also suggests better normal prices.
2. **AI Replenish** says what to reorder and how much, so shelves do not run empty.
3. **AI Customer Mission** looks at what people buy and when, and guesses *why they came*: a quick top-up, a dinner run, the weekly big shop. It is only a guess, and we say so.
4. **AI Monitoring** watches for strange things: a day when sales dropped by half, cash that does not match, lots of returned sales.
5. **AI Product Loss Prevention** suggests which products to count first, to find stock that went missing.
6. **AI Insight** writes the reasons in plain language.

---

## 4. How we built it, step by step

Think of building a house: foundation first, then walls, then the roof, then the test.

### Step 1: Start with a real shop system
PesoWeb already had sales, purchases, stock with expiry dates, cash drawers and reports. We did not rebuild any of that.

### Step 2: Give the helper a window to look through
We added a set of read-only "windows" (called APIs) so the helper can see: sales, stock about to expire, cash drawer results, price changes, what shoppers bought together. The helper has its own login that can **read, but not change** the shop's money.

### Step 3: Build the safety fence BEFORE the helper
Before the helper could suggest anything, we built rules PesoWeb enforces on its own:
- never sell below a minimum profit (a "floor"),
- never discount more than a limit,
- never change one price too many times in an hour.

Even if the helper made a mistake, PesoWeb would say **no**. Every attempt is written in a log, so there is always a record.

### Step 4: The "boss approves" screen (Approval Center)
Normal price changes always wait for a human. We built a screen where a manager sees each suggestion with the **reason**, the profit before and after, what rival shops charge, and warnings. They press **Approve**, **Reject** or **Approve a different price**. Everything can be undone.

### Step 5: The on/off switches (AI Control)
The owner can turn each of the six skills on or off. When one is off, PesoWeb **refuses** anything it suggests, even if the helper program keeps running. There is also a **Run now** button.

### Step 6: Switches for each branch
The owner can say: *"At this branch the AI may mark prices down; at that one it may not."* A branch with the AI **off** becomes a "control branch" for fair tests, and every branch now shows a little **AI** or **Control** tag.

### Step 7: The Intelligent Hub (one place for everything)
A menu group called **Intelligent Hub** collects it all:
- **Overview**: sales, profit, waste and stock for each branch, refreshing every minute.
- **My tasks**: what is waiting for me.
- **Reorders**: what to order, with a button that makes a draft purchase order (nothing is sent to the supplier by itself).
- **Customer missions**, **Alert rules**, **AI Settings**.
- **AI Impact**: "did the AI really help?" (more below).

### Step 8: Teach the helper from the shop's own sales
The helper learns *how much sales change when the price changes*, using this shop's own history. When it knows little, it is careful and says "I am assuming, not sure". This is plain math, not a chatbot.

### Step 9: Test it on a pretend town (the simulator)
We cannot experiment on real customers. So we built a **simulator**: pretend shoppers walk into pretend shops that run on the real PesoWeb. We used the real product list and real prices of an actual store; only the shoppers are pretend.

We ran two copies of the same shop. In one copy the helper was on. In the other it was off. We first checked the two copies were **truly identical** (if not, the test is unfair), then compared them.

### Step 10: Measure whether it really helps (AI Impact)
Result of the careful test: the shop with the helper was ahead on **10 out of 10 test days**, roughly **8% more gross profit**, with a little less wasted food. That is a **modest** improvement, and we say it honestly: real shops have thin profit.

### Step 11: Save and reload the test town (snapshots)
Running tests changes the database. We added a **Test snapshots** screen: save the whole database under a name, and restore it later. It refuses to restore if the database design changed, so nothing breaks.

---

## 5. The technology, in plain words

| Part | What it is | Why |
|---|---|---|
| **PesoWeb** | The shop system: sales, stock, cash, reports. Built with .NET (the engine), a SQL Server database (the memory) and Angular (the screens) | It was already there |
| **Python** | The language the helper is written in | Good for math and for pretend shoppers |
| **Statistics (numpy)** | Counting and curve-fitting: "when the price goes up 10%, how many fewer do we sell?" | Checkable, honest, fast |
| **A language model, through an AI API** (Anthropic's Claude, or Qwen running on an AMD GPU) | A chatbot-style program | It only **writes the explanations** and can **play a few pretend shoppers** (they get a made-up person and a mission). **It never decides anything for the shop** |
| **PyTorch on AMD ROCm** | Lets the AMD graphics chip do the heavy work, like simulating 200,000 shoppers | Fast. The AMD GPU test is the last thing we will run |

**Important:** the chatbot is not needed for the helper to work. If it is switched off, or the internet is down, the helper still works, because the decisions come from math. Today the demo runs without it; it is an extra you can switch on.

---

### Choosing who the pretend shoppers are
Before any test starts, you **must choose** where the shoppers come from, and you can mix sources:
- **Pretend shoppers** made by our rules (always there).
- **A few chatbot shoppers** that think for themselves.
- **Real receipts** from a real store, or **public shopping data** (Instacart, Dunnhumby): real baskets get replayed in our shop.
- **Real answers** from shoppers at the till ("why did you come today?") to check the "customer mission" guesses.

The result always says which sources were used. We can also check our price predictions on real data and the report says plainly if they did not do better than simple guessing.

## 6. What it cannot do (we say it plainly)

- The pretend shoppers are **simulated**. Their reaction to price is our assumption. The shop's products and prices are real.
- The improvement is **modest**, not magic.
- Guessing *why* a customer came is only right about **6 times out of 10** on pretend shoppers.
- The rival-price numbers in the demo are **simulated**.
- It cannot send SMS messages, and it does not talk to electronic shelf labels yet.
- We have not yet run the AMD GPU test.

---

## 7. How to see it yourself in 2 minutes

1. Run `powershell -ExecutionPolicy Bypass -File ui\demo\start-demo.ps1` (from the project folder).
2. Open `http://127.0.0.1:4200` and log in as the demo shop owner.
3. In the left menu open **Intelligent Hub**, then click **Overview**, **My tasks**, **Approval Center**, **Reorders** and **AI Impact**.

For the full click-by-click tour with pictures see `Docs/demo/DEMO-GUIDE.md`.
