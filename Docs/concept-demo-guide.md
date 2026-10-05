# Concept demo: how to run it, how to prove it works, and what it means

The demo is one PesoWeb feature (stock with expiry dates, sold first-expiry-first-out, plus **markdown pricing with guardrails**) and one very simple AI agent task: *"this milk expires tomorrow and there is too much of it, so what should we do?"* It needs only the local PesoWeb server. No GPU, no LLM, no simulator.

Not clear what the data mean, how the AI thinks, or where it learns? Read `concept-demo-explained.md` (sample data before and after each feature, the AI's decision table, and an honest answer on learning).

Files: `demo/concept_demo.py`, `demo/README.md`. Last recorded run: 9 of 9 checks passed.

---

## Part 1. Run it, step by step

### Before you start (one time)

You need: Windows with SQL Server LocalDB, the .NET SDK, Python 3.10+ with `requests` and `pyyaml` (`pip install requests pyyaml`), and the PesoWeb worktree at `D:\git\Retailo_v1_mission` (branch `Retail_MissionCommerceAI`, already built).

If the dev database `PesoWeb_MissionDev` does not exist yet on your machine, create it once with the recipe in `pesoweb-additions/README.md`, section "Live verification environment" (restore the repo backup into LocalDB, record the two history rows, run `dotnet ef database update`). You can check it exists:

    SqlLocalDB start MSSQLLocalDB
    sqlcmd -S "(localdb)\MSSQLLocalDB" -E -C -Q "SELECT name FROM sys.databases"      # look for PesoWeb_MissionDev

### Step 1. Start the PesoWeb server

In PowerShell:

    cd D:\git\Retailo_v1_mission
    $env:ConnectionStrings__default = 'Server=(localdb)\MSSQLLocalDB;Database=PesoWeb_MissionDev;Trusted_Connection=True;TrustServerCertificate=True;MultipleActiveResultSets=true'
    dotnet run --project Retailo.csproj --no-build --no-launch-profile --urls http://localhost:5071

Leave this window open. It is ready when it prints that it is listening on `http://localhost:5071`. (If you changed PesoWeb code, stop the server and run `dotnet build Retailo.csproj` first; a running server locks the build output.)

Quick check from a second window: `curl -s -o NUL -w "%{http_code}" -X POST http://localhost:5071/api/Auth/Login -H "Content-Type: application/json" -d "{}"` prints an HTTP status number (any number, such as 400). Any answer at all means the server is alive; no answer means it is not.

### Step 2. Run the demo

In a second terminal:

    cd D:\git\AMD\hackathon_amd_act3\MissionCommerceAI_by_eVo.Ninjas
    python demo/concept_demo.py

It takes a few seconds. To use a different address: `set PESOWEB_URL=http://localhost:5099` first.

### Step 3. Read the output

You should see seven numbered steps and `Result: 9 of 9 checks passed.` The important lines:

    3. POS price: 100.00   (FEFO sells tomorrow's batch first)
    4. agent: 30% off Fresh Milk 1L ... Prediction: 20 units (15 to 26), about 1111 pesos wasted.
       PesoWeb answered HTTP 200 -> applied
    5. POS price: 70.00   (was 100.00)
    6. PesoWeb answered HTTP 422: EXCEEDS_MAX_DISCOUNT - Discount exceeds the maximum of 50.00%.
    7. price change #...: 100.0 -> 70.0 (Applied, OK), prediction p-1
       price change #...: 100.0 -> 20.0 (Rejected, EXCEEDS_MAX_DISCOUNT)

The exact batch numbers and ids differ every run (each run signs up a brand-new shop, so runs never interfere with each other). The discount the agent picks can vary slightly if the assumptions in the script change.

The script exits with code 0 only when every check passes (`echo %ERRORLEVEL%` in cmd, `$LASTEXITCODE` in PowerShell).

### If something goes wrong

| Symptom | Likely cause and fix |
|---|---|
| `unreachable after 3 tries` | The server is not running or is on another port. Redo Step 1, or set `PESOWEB_URL`. |
| `ModuleNotFoundError: requests` or `yaml` | `pip install requests pyyaml` |
| `Register ... 500` | The database lacks the signup constraint fix. Apply `scripts/20261005_widen_users_subscription_check.sql` (or run `dotnet ef database update`) on the dev database. |
| `404` on `/api/Pricing/...` or `/api/Expiry/...` | The server build is older than the Retail_MissionCommerceAI branch. Rebuild and restart. |
| Build error "file is locked" | Stop the running server before `dotnet build`. |

---

## Part 2. How to prove it is working

Do not take the agent's word for it. Each proof below checks something PesoWeb itself says, in a different way.

### Proof A. The built-in checks (30 seconds)

The script's nine `PASS/FAIL` lines compare the agent's claims with PesoWeb's replies: the price before and after comes from ringing up a real sale through the POS, the refusal comes from PesoWeb's HTTP status, and the audit rows come from PesoWeb's ledger. All nine must pass.

### Proof B. Look in the database yourself (independent of the script)

After a run, ask SQL Server directly:

    sqlcmd -S "(localdb)\MSSQLLocalDB" -E -C -W -d PesoWeb_MissionDev -Q "SELECT TOP 3 Id, PriceBefore, PriceAfter, Status, Source, GuardrailCode, PredictionRef FROM PriceChanges ORDER BY Id DESC; SELECT TOP 2 Id, BatchId, Price, IsActive FROM ActiveMarkdowns ORDER BY Id DESC;"

Expected (ids differ): the newest `PriceChanges` rows show one `Applied` row `100.00 -> 70.00` with `Source = Ai` and a `PredictionRef` like `p-1`, and one `Rejected` row `100.00 -> 20.00` with `GuardrailCode = EXCEEDS_MAX_DISCOUNT`. `ActiveMarkdowns` shows the 70.00 price active on the batch that expires tomorrow. These rows were written by PesoWeb's own code, not by the demo script.

### Proof C. Break it on purpose (a test that cannot fail proves nothing)

Switch the shop's autonomy to Off and the demo must stop working:

    copy demo\concept_demo.py demo\try_off.py
    # in demo\try_off.py change   "Autonomous"   to   "Off"   on the set_pricing_policy line
    python demo\try_off.py
    del demo\try_off.py

Expected: only about 3 of 9 checks pass; the agent's proposal is refused with `AUTONOMY_OFF`, the POS price stays at 100. We ran exactly this: 3 of 9 passed. This shows the guardrails belong to PesoWeb and the agent cannot talk its way past them. (You can also lower `max_discount` to 20 or raise `hard_floor` to 40 and watch the agent's choice shrink or get refused.)

### Proof D. The unit tests behind the agent

    cd ai && set PYTHONPATH=. && python -m unittest discover -s tests -t .       # 64 tests
    cd ..\sim && python -m unittest discover -s tests -t .                        # 81 tests

These cover the pricing maths (never below the hard floor, never above the maximum discount), the agent's behavior in Off, approval and refusal modes, and the prediction scoring.

### What this proves, and what it does not

| It proves | It does not prove |
|---|---|
| Expiry stock, FEFO selling and markdown prices work end to end in PesoWeb | That the agent's discount is the best possible one |
| An agent can act only inside the shop's rules, and PesoWeb enforces them | Real-store sales lift (the sales rate of 12 a day and the customers' price response are assumptions; the shop is brand new and has no history) |
| Every price change is recorded, with who made it and the prediction behind it | That the prediction is accurate (the measured accuracy is in `results/` and the dashboard: optimistic or pessimistic depending on the run) |

For measured results over many runs, see `results/proof-smoke.json` and the dashboard (`python -m http.server 8080` from the repo root, then open `/ui/dashboard/`). There the AI beats doing nothing on all five seeds but only ties a simple fixed rule, and that is reported as it is.

---

## Part 3. The simple explanation (for a 15-year-old)

**The shop problem.** Imagine you run a small shop and you bought 80 cartons of milk. Milk goes bad. Forty of them have a date on the carton that says *tomorrow*. If nobody buys them by tonight, you throw them in the bin, and the money you paid for them is gone. Shop owners hate that, and real shops lose a lot of money this way.

**What a smart shop does.** It puts the milk that goes bad first on sale. Selling it at 70 instead of 100 is much better than selling nothing, because more people will grab it. But there is a catch: if you cut the price too far, you lose money on every carton, and a sale that is too deep is as bad as the bin.

**What our little AI does.** It is like a shop helper that checks the dates every hour:

1. It looks at what is about to expire and how much is left.
2. It makes a guess: "if we leave the price alone, about 27 of those 40 cartons will end up in the bin. If we take 30% off, only about 19 will."
3. It writes that guess down **before** doing anything, so nobody can say later that it knew all along.
4. It asks the shop's computer system, PesoWeb, to change the price.

**The rules the AI cannot break.** The shop owner sets the rules first: "never sell for less than what I paid plus a little profit, and never more than 50% off." PesoWeb, not the AI, checks every request. If the AI asks for 80% off, PesoWeb says **no** and explains why. The AI can ask, but PesoWeb decides. That is the safety part, and it is the part we care about most: an AI you can trust only because it is not allowed to do something silly.

**How we know it works.** We do not just trust what the AI says. We check three things on the computer itself:

- Ring up a real sale: the price really went from 100 to 70.
- Ask for a silly price: it was really refused, and the price on the shelf did not change.
- Look at the shop's records: both tries are written down, with the reason.

And then we try to break it: we switch the AI's permission off, and the demo fails, which shows the test is real and the rules are really enforced.

**An honest warning.** In this small demo we told the AI how fast milk usually sells and how much cheaper prices attract people. That is a guess, not data from a real shop. So the demo proves the *idea works safely*. It does not yet prove how much money a real shop would save. That needs real shops, or many careful simulated runs, and those are in the dashboard.
