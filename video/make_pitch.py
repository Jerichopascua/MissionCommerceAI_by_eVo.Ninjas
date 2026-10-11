"""Builds the hackathon pitch video: problem first (explained simply), the working product, how the AI works, the evidence,
the setup, and the AMD part. Reuses the captured screens in video/frames/ and the drawing helpers of make_video.py.

    python video/make_pitch.py                 full cut (about 6 minutes), writes video/MissionCommerce_Pitch_full.mp4
    python video/make_pitch.py --cut short     short cut (about 4 minutes),        writes video/MissionCommerce_Pitch_short.mp4
    python video/make_pitch.py --final         refuses to build unless results/amd-session.json is a real AMD run

The AMD scene is built only from results/amd-session.json (written by sim/scripts/amd_session_collect.py on the AMD server).
Without a real AMD run it is drawn as a visible DRAFT placeholder, never as a result."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_video as mv                                  # noqa: E402
from make_video import BG, BLUE, DARK, INK, MUTED, RED, W, H, font, wrap   # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
AMD_JSON = ROOT / "results" / "amd-session.json"
GREEN = (22, 163, 74)
ORANGE = (234, 88, 12)


def load_amd():
    try:
        d = json.loads(AMD_JSON.read_text(encoding="utf-8"))
        return d if d.get("amd") else None
    except (OSError, ValueError):
        return None


def header(d, title, step=None):
    d.rectangle((0, 0, W, 78), fill=(255, 255, 255))
    d.rectangle((0, 76, W, 79), fill=BLUE)
    if step:
        d.ellipse((30, 20, 78, 68), fill=BLUE)
        d.text((54 - d.textlength(str(step), font=font(26, True)) / 2, 26), str(step), font=font(26, True), fill=(255, 255, 255))
        d.text((100, 20), title, font=font(34, True), fill=INK)
    else:
        d.text((40, 20), title, font=font(34, True), fill=INK)


def numbers(path, kicker, title, items, foot=None, dark=False):
    """Big figures with a label each."""
    im = Image.new("RGB", (W, H), DARK if dark else BG)
    d = ImageDraw.Draw(im)
    ink, sub = ((255, 255, 255), (200, 220, 255)) if dark else (INK, MUTED)
    d.text((70, 60), kicker.upper(), font=font(24, True), fill=(184, 208, 248) if dark else BLUE)
    y = 98
    for l in wrap(d, title, font(50, True), W - 140):
        d.text((70, y), l, font=font(50, True), fill=ink)
        y += 62
    n = len(items)
    cw = (W - 140 - (n - 1) * 24) // n
    top = max(y + 30, 270)
    for i, (big, label, color) in enumerate(items):
        x = 70 + i * (cw + 24)
        d.rounded_rectangle((x, top, x + cw, top + 250), radius=22, fill=(255, 255, 255) if not dark else (30, 60, 130))
        size = 74
        while size > 36 and d.textlength(big, font=font(size, True)) > cw - 48:
            size -= 4                                   # a long figure shrinks to fit its card
        d.text((x + 24, top + 28 + (74 - size) // 2), big, font=font(size, True), fill=color if not dark else (255, 255, 255))
        yy = top + 135
        for l in wrap(d, label, font(27), cw - 48):
            d.text((x + 24, yy), l, font=font(27), fill=INK if not dark else (220, 232, 255))
            yy += 36
    if foot:
        yy = H - 120
        for l in wrap(d, foot, font(27), W - 140)[:3]:
            d.text((70, yy), l, font=font(27), fill=sub)
            yy += 36
    im.save(path)


def steps(path, kicker, title, rows, foot=None):
    """Numbered rows: (heading, text)."""
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((70, 44), kicker.upper(), font=font(24, True), fill=BLUE)
    d.text((70, 78), title, font=font(46, True), fill=INK)
    y = 150
    for i, (head, text) in enumerate(rows, 1):
        d.rounded_rectangle((70, y, W - 70, y + 114), radius=18, fill=(255, 255, 255))
        d.ellipse((92, y + 29, 148, y + 85), fill=BLUE)
        d.text((120 - d.textlength(str(i), font=font(30, True)) / 2, y + 39), str(i), font=font(30, True), fill=(255, 255, 255))
        d.text((172, y + 10), head, font=font(29, True), fill=INK)
        for j, l in enumerate(wrap(d, text, font(22), W - 280)[:2]):
            d.text((172, y + 48 + j * 27), l, font=font(22), fill=MUTED)
        y += 124
    if foot:
        d.rectangle((0, H - 70, W, H), fill=INK)
        d.text((70, H - 54), foot, font=font(26), fill=(255, 255, 255))
    im.save(path)


def flow(path, kicker, title, boxes, foot=None):
    """Boxes left to right: (heading, [lines], color)."""
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((70, 44), kicker.upper(), font=font(24, True), fill=BLUE)
    d.text((70, 78), title, font=font(46, True), fill=INK)
    n = len(boxes)
    gap = 56
    bw = (W - 140 - gap * (n - 1)) // n
    top = 190
    for i, (head, lines, color) in enumerate(boxes):
        x = 70 + i * (bw + gap)
        d.rounded_rectangle((x, top, x + bw, top + 370), radius=22, fill=(255, 255, 255), outline=color, width=5)
        d.rectangle((x + 5, top + 5, x + bw - 5, top + 78), fill=color)
        for j, l in enumerate(wrap(d, head, font(27, True), bw - 30)[:2]):
            d.text((x + 18, top + 12 + j * 32), l, font=font(27, True), fill=(255, 255, 255))
        yy = top + 98
        for l in lines:
            for k, w in enumerate(wrap(d, l, font(23), bw - 40)):
                d.text((x + 20, yy), ("- " if k == 0 else "  ") + w, font=font(23), fill=INK)
                yy += 30
            yy += 6
        if i < n - 1:
            ax = x + bw + 6
            d.polygon([(ax, top + 175), (ax + gap - 12, top + 175), (ax + gap - 12, top + 160), (ax + gap + 8, top + 190),
                       (ax + gap - 12, top + 220), (ax + gap - 12, top + 205), (ax, top + 205)], fill=BLUE)
    if foot:
        d.rectangle((0, H - 90, W, H), fill=INK)
        for j, l in enumerate(wrap(d, foot, font(26), W - 140)[:2]):
            d.text((70, H - 78 + j * 34), l, font=font(26), fill=(255, 255, 255))
    im.save(path)


def amd_scene(path, amd):
    """The AMD scene, from real session numbers only; a clearly marked draft without them."""
    im = Image.new("RGB", (W, H), (20, 24, 31))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 78), fill=(237, 28, 36))
    d.text((40, 18), "AMD Developer Cloud  ·  ROCm  ·  working product", font=font(34, True), fill=(255, 255, 255))
    if not amd:
        d.text((70, 150), "DRAFT: the AMD session has not been run yet", font=font(46, True), fill=(255, 255, 255))
        rows = ["This scene is built from results/amd-session.json,",
                "written by sim/scripts/amd_session_collect.py on the AMD server.",
                "", "Not filled with estimates, and not shown as a result until it is real.",
                "Planned: Oct 14 (three days of buffer before the Oct 18 deadline)."]
        y = 240
        for r in rows:
            d.text((70, y), r, font=font(29), fill=(190, 200, 215))
            y += 42
        d.rounded_rectangle((W - 330, H - 120, W - 40, H - 40), radius=14, fill=(220, 38, 38))
        d.text((W - 305, H - 100), "DRAFT - NOT FINAL", font=font(28, True), fill=(255, 255, 255))
        im.save(path)
        return
    hw, qs, li = amd["hardware"], amd["quicksim"], amd.get("insight_llm", {})
    g, c = qs.get("gpu", {}), qs.get("cpu", {})
    d.text((70, 110), f"{hw.get('device', 'AMD GPU')}  ·  ROCm/HIP {hw.get('hip')}  ·  PyTorch {hw.get('torch')}", font=font(30, True), fill=(255, 255, 255))
    cards = []
    if g.get("generation_s"):
        cards.append((f"{qs['individuals']:,} shoppers", f"{qs['days']} days generated in {g['generation_s']:.1f}s on the GPU"
                      + (f" ({qs['speedup_x']}x the CPU)" if qs.get("speedup_x") else ""), (255, 255, 255)))
    if hw.get("matmul_fp16_tflops"):
        cards.append((f"{hw['matmul_fp16_tflops']} TFLOPS", "fp16 matrix multiply, measured on the server", (255, 255, 255)))
    if li.get("tokens_per_s"):
        cards.append((f"{li['tokens_per_s']} tok/s", f"{li['model']} on vLLM rewords the AI's notes; "
                      f"{li['reworded_by_model']} of {li['notes']} accepted, the rest kept standard wording", (255, 255, 255)))
    cw = (W - 140 - 24 * max(0, len(cards) - 1)) // max(1, len(cards))
    for i, (big, label, col) in enumerate(cards):
        x = 70 + i * (cw + 24)
        d.rounded_rectangle((x, 190, x + cw, 440), radius=20, fill=(36, 42, 54))
        d.text((x + 22, 214), big, font=font(48, True), fill=col)
        yy = 296
        for l in wrap(d, label, font(25), cw - 44)[:5]:
            d.text((x + 22, yy), l, font=font(25), fill=(200, 210, 225))
            yy += 33
    smi = (hw.get("rocm_smi") or "").splitlines()[:6]
    d.rectangle((70, 470, W - 70, H - 50), fill=(8, 10, 14))
    for j, l in enumerate(["$ rocm-smi"] + smi):
        d.text((90, 486 + j * 30), l[:110], font=font(21), fill=(130, 230, 150))
    d.text((70, H - 38), f"Measured {amd['measured_at']} on {amd['host']}", font=font(20), fill=(150, 160, 175))
    im.save(path)


def amd_narration(amd, short=False):
    if not amd:
        return ("Draft placeholder. The A M D scene is filled from the real session numbers: the GPU and ROCm version, how fast the "
                "shopper simulation runs on the GPU compared with the CPU, and the language model that words the notes on the same GPU." if not short
                else "Draft placeholder: the A M D scene is filled from the real session numbers.")
    hw, qs, li = amd["hardware"], amd["quicksim"], amd.get("insight_llm", {})
    g = qs.get("gpu", {})
    if short:
        bits = [f"On the A M D Developer Cloud, an {hw.get('device', 'A M D GPU')} with ROCm."]
        if g.get("generation_s"):
            bits.append(f"PyTorch generates {qs['individuals']:,} shoppers in {g['generation_s']:.0f} seconds"
                        + (f", {qs['speedup_x']} times the CPU." if qs.get("speedup_x") else "."))
        if li.get("tokens_per_s"):
            bits.append(f"And vLLM serves {li['model']} to word the notes at {li['tokens_per_s']:.0f} tokens a second.")
        return " ".join(bits)
    parts = [f"On the A M D Developer Cloud we run an {hw.get('device', 'A M D GPU')} with ROCm. "]
    if g.get("generation_s"):
        parts.append(f"PyTorch on ROCm generates {qs['individuals']:,} shoppers over {qs['days']} days in {g['generation_s']:.0f} seconds"
                     + (f", {qs['speedup_x']} times faster than the CPU. " if qs.get("speedup_x") else ". "))
    if li.get("tokens_per_s"):
        parts.append(f"The same GPU serves {li['model']} with vLLM. It rewords the A I notes at {li['tokens_per_s']:.0f} tokens a second, "
                     f"and any note with an invented figure is thrown away before it is shown.")
    return "".join(parts)


def scenes(amd):
    """The pitch, in order. cuts: 'f' = in the full cut, 's' = in the short cut."""
    return [
        # ---- 1. the problem, simply
        dict(k="hook", sayp='A shop has thirty six packs of snacks that go bad in two days. It will sell eight. Twenty eight go in the bin, with the money.', cuts="fsp", kind="numbers", kicker="Imagine you run a small shop", title="Snacks that go bad in two days",
             items=[("36", "packs on the shelf", BLUE), ("8", "you will probably sell", GREEN), ("28", "end up in the bin, with your money", RED)],
             foot="And that is only one leak. A person cannot watch every date, every price and every shelf.",
             say="Imagine you run a small shop. You have thirty six packs of snacks, and they go bad in two days. You will probably sell eight. "
                 "The other twenty eight go in the bin, and so does your money. And that is only one leak in one shop."),
        dict(k="problem", cuts="fs", kind="card", kicker="The problem: Reinvent Commerce", title="Shops have the data, but not the decisions",
             lines=["Four everyday leaks: stock that expires, prices set by habit, shelves that run empty, cash and stock that quietly go missing.",
                    "The data to catch each one is already in the till. Nobody turns it into an action in time."],
             say="Shops already have the data. Four leaks cost them every day: stock that expires, prices set by habit, shelves that run empty, "
                 "and cash and stock that quietly go missing. The data to catch each one is already in the till. Nobody turns it into an action in time."),
        dict(k="idea", sayp='Mission Commerce A I is two parts. Sim dot Peso Web, a practice world that drives the real point of sale. And the Intelligent Hub, the A I inside it. The A I proposes, Peso Web enforces the rules, and a person decides.', cuts="fsp", kind="steps", kicker="Our answer: MissionCommerce AI", title="Practise first, then run live, and people decide",
             rows=[("Sim.PesoWeb: a practice world", "A seeded retail world drives the real PesoWeb POS and ERP, so the AI is tested before a real shop depends on it."),
                   ("The AI proposes", "Six AI features in the Intelligent Hub: pricing, loss prevention, replenish, missions, monitoring, insight."),
                   ("PesoWeb disposes", "Margin floors, approval lanes, on and off switches and an audit trail. The AI cannot override them."),
                   ("A person has the last word", "The owner approves; the AI never changes a price by itself.")],
             say="Our answer is Mission Commerce A I, in two parts. Sim dot Peso Web is a practice world: it drives the real Peso Web point of sale, "
                 "so the A I is tested before a real shop depends on it. The Intelligent Hub is the A I inside the real system. The A I proposes, "
                 "Peso Web enforces the rules, and a person has the last word."),
        # ---- 2. Sim.PesoWeb
        dict(k="simworld", cuts="f", kind="steps", kicker="Sim.PesoWeb: the practice world", title="A shop that never closes, with the answers known",
             rows=[("The real system under test", "Companies, branches, staff and a real 493-product catalog with expiry dates, all through PesoWeb's own API."),
                   ("Shoppers with memory", "Rule-based shoppers, real receipts, public basket data sets, and a few shoppers whose choices come from a language model."),
                   ("Incidents with known answers", "Cash shortages, hidden shrink and expiring batches are planted, so we can score what the AI caught and missed."),
                   ("Two identical shops", "One with the AI, one without, same shoppers and stock. An A/A check proves they are identical before we compare.")],
             say="Sim dot Peso Web is a shop that never closes, and where the answers are known. It runs a real catalog and real staff through Peso Web's "
                 "own A P I. Shoppers have memory and judgement. We plant incidents with known answers, so we can score what the A I caught and missed. "
                 "And we run two identical shops, one with the A I and one without."),
        dict(k="simresult", sayp='In two identical simulated shops, the one with the A I was ahead on ten of ten days, with about two hundred and thirty six pesos a day more margin. An A over A check proves the shops are identical.', cuts="fsp", kind="scene", step=1, title="Sim.PesoWeb: the shop with the AI against the same shop without",
             shots=[("20_sim_results.png", "desk")],
             bullets=["10 of 10 trial days ahead of the no-AI shop", "+236 pesos a day gross margin, units about flat", "The markdown agent adds +136 pesos a day net, waste 162 pesos a day lower",
                      "A/A check: same day, no AI, zero difference"],
             caption="Real catalog, identical twin shops, recorded run. Simulated shoppers: the shop and the AI's decisions are real.",
             say="Here is the result. The same shop twice, with the A I and without. The A I shop was ahead on ten of ten trial days, about two hundred "
                 "and thirty six pesos a day more gross margin, with units about flat. The markdown agent adds a further one hundred and thirty six "
                 "pesos a day, and cuts waste. An A over A check shows zero difference when the A I does nothing."),
        dict(k="simstory", cuts="f", kind="scene", step=2, title="Shoppers who think and learn", shots=[("21_sim_customer_story.png", "desk")],
             bullets=["40 customers with their own money, memory and friends", "Clearance cuts chicken waste from 926 to 424 pesos an evening",
                      "When shoppers learn when prices drop, it falls to 46", "The behaviour detector reads only purchase records"],
             caption="A neighbourhood story: what happens when customers learn the evening price drop.",
             say="Shoppers are not static. In this neighbourhood story, forty customers have their own money, memory and friends. Clearance cuts "
                 "the chicken thrown away from nine hundred and twenty six pesos an evening to four hundred and twenty four. When customers learn when "
                 "prices drop, it falls to forty six."),
        dict(k="siminc", cuts="f", kind="scene", step=3, title="Incidents with known answers: caught and missed", shots=[("22_sim_day_report.png", "desk")],
             bullets=["Branches, sales, cash variance, expiry at risk, open exceptions", "PesoWeb alone caught 3 of 5 planted incidents",
                      "Risk-ranked counts by the AI found the other 2", "Coverage rises with counting effort: 0.6, then 0.8, then 1.0"],
             caption="The day report by company and branch: what happened, and what the system found.",
             say="Each simulated day is reported by company and branch. We plant incidents with known answers. Peso Web alone caught three of five. "
                 "The A I's risk ranked stock counts found the other two. Coverage rises with the counting effort."),
        # ---- 3. the Intelligent Hub: the whole AI
        dict(k="hub", cuts="fs", kind="scene", step=4, title="The Intelligent Hub: one place for the whole shop", shots=[("30_hub_overview.png", "desk")],
             bullets=["By period, category and region: sales, margin, turnover, expiry at risk, exceptions", "My tasks by role; alerts follow rules the owner can edit",
                      "Same screens in the simulator and in the live shop"],
             caption="A simulated company with real history: numbers by branch and region, and what needs attention.",
             say="This is the Intelligent Hub inside Peso Web, on a simulated company with history. Sales, margin, stock turnover, expiry at risk and "
                 "exceptions by period, category and region, and tasks for each role."),
        dict(k="control", cuts="fs", kind="scene", step=5, title="Six AI features, each one switchable", shots=[("36_ai_control.png", "desk")],
             bullets=["Monitoring, Pricing, Loss Prevention, Replenish, Customer Mission, Insight", "On or off per company, and AI markdowns per branch",
                      "Run now, last run, and what it produced", "Enforced on the server: a switched-off feature is refused"],
             caption="AI Control: the owner decides which features run, and can switch any of them off at once.",
             say="Six A I features, and the owner controls each one. Monitoring, pricing, loss prevention, replenish, customer missions and insight. "
                 "Each can be switched off per company, and markdowns per branch. The switch is enforced on the server."),
        dict(k="pricing", cuts="f", kind="scene", step=6, title="AI Pricing: the owner decides in the Approval Center", shots=[("04_approval_center.png", "desk")],
             bullets=["Markdowns for short-dated stock, list-price advice from the shop's own sales", "Each proposal shows the reason, margin before and after, rival prices",
                      "Three approval lanes: store manager, pricing manager, owner", "Margin floors and a maximum discount can never be waived"],
             caption="Real company: the AI's proposals wait for a person, with the reason and the margin check.",
             say="A I Pricing proposes markdowns for short dated stock and list price changes learned from the shop's own sales. Every proposal waits in "
                 "the Approval Center with the reason and the margin before and after. Margin floors can never be waived."),
        dict(k="loss", cuts="fs", kind="scene", step=7, title="Loss Prevention: stock that will expire, and what to count first", shots=[("01_ai_sell_fast.png", "desk")],
             bullets=["Batches that will expire unsold, at today's rate of sale", "What it is worth at cost, and the discount that clears it",
                      "Count first: stock delivered with no receiving report, then fast sellers", "Never accuses anyone: only 'the count differs from the system'"],
             caption="Real company data: batches that will expire unsold, how much it costs, and the discount to clear them.",
             say="Loss Prevention finds two kinds of loss the point of sale cannot see. Batches that will expire unsold, with the discount that clears "
                 "them. And what to count first, where a shortage would cost the most. Real company data, never an accusation."),
        dict(k="replenish", cuts="f", kind="scene", step=8, title="Replenish: what to reorder, how much, by when", shots=[("32_hub_reorders.png", "desk")],
             bullets=["From each branch's rate of sale, stock on hand and lead time", "Reorder point with a 90% service level; pack rounding; perishables capped",
                      "Becomes a pending draft purchase order, stock untouched until received"],
             caption="AI Replenish: suggestions with the reasoning, and draft purchase orders for a person to confirm.",
             say="Replenish suggests what to reorder, how much, and by when, from each branch's rate of sale and lead time. A person confirms, and "
                 "it becomes a draft purchase order."),
        dict(k="missions", cuts="f", kind="scene", step=9, title="Customer Missions: why shoppers came", shots=[("33_hub_missions.png", "desk")],
             bullets=["Late night, morning grab-and-go, quick top-up, weekly restock", "From the shape of the basket and the time of day",
                      "Says what it means for stock and staffing", "An inference, labelled as one: it cannot see intent"],
             caption="AI Customer Mission: what shoppers were trying to get done, by branch.",
             say="Customer Missions works out what shoppers were trying to get done, from the shape of the basket and the time of day, and says what "
                 "that means for stock and staff. It is an inference, and it is labelled as one."),
        dict(k="impact", cuts="fs", kind="scene", step=10, title="AI Impact: the AI branch against the control branch", shots=[("34_hub_impact.png", "desk")],
             bullets=["Equal days before and after the AI started pricing", "Keep one branch with AI markdowns off and the Hub compares fairly",
                      "Difference in differences, with an explicit 'indicative, not proof'", "Needs several days: it says when there are too few"],
             caption="Before and after, and AI branches against a control branch, with the caveats stated.",
             say="A I Impact answers: did it work? It compares equal days before and after, and when the owner keeps one branch with the A I off, it "
                 "compares A I branches against that control. It states plainly that this is indicative, not proof."),
        dict(k="insight", sayp='A I Insight analyses how the A I is doing and what to improve: proposals expiring before anyone decides, people rejecting twenty three of a hundred and one, and no control branch. Each with a concrete change.', cuts="fsp", kind="scene", step=11, title="AI Insight: how the AI is doing, and what to improve", shots=[("38_hub_insight.png", "desk")],
             bullets=["Reads the results, the proposal outcomes, the approval queue and the settings", "Says what became of the proposals: applied, rejected by people, refused by a rule, expired",
                      "Suggests concrete changes: approvers, step size, a control branch, features never run", "Every figure checked against the data; a language model may only reword"],
             caption="A simulated company: 13 proposals expired, 23 of 101 rejected by people, and no control branch. Each with the advice.",
             say="A I Insight does not just explain. It analyses how the A I is doing, and what to improve in its setup. Here, thirteen proposals "
                 "expired before anyone decided, twenty three of a hundred and one were rejected by people, and there is no control branch. Each comes with "
                 "a concrete change. It is rules over the numbers, every figure is checked, and a language model may only reword it."),
        # ---- 4. one use case end to end: from the AI's finding to a customer's basket
        dict(k="rush", sayp="One click on Rush sale fills in the product, the discount and the last day. The register charges it at once and the shop's registered customers are told.", cuts="fsp", kind="scene", step=12, title="Use case: from an AI finding to a rush sale", shots=[("02_put_on_sale_prefilled.png", "desk")],
             bullets=["One click on Rush sale: product, discount and last day filled in", "The pricing rules still apply; the manager confirms",
                      "The register charges it at once; registered customers are told in their app"],
             caption="Real company: the AI's expiry finding becomes a rush sale in one click, and the shop's own customers are told.",
             say="Here is one use case end to end. The A I found stock that will expire. One click on Rush sale fills in the product, the discount "
                 "and the last day. The manager confirms, the register charges it at once, and the shop's registered customers are told."),
        dict(k="shopper", sayp='A first time customer registers on her phone with a name, a number and a password, sees the sale, and reserves.', cuts="fsp", kind="scene", step=13, title="The shopper: register, see the sale, reserve", shots=[("06_phone_register.png", "phone"), ("07_phone_welcome_sale.png", "phone"), ("11_phone_reference.png", "phone")],
             bullets=["A first-time customer registers on her phone: name, mobile number, password", "She sees the rush sale, and can install the app",
                      "She reserves and gets a reference number and a QR code"],
             caption="The customer app: installable, no app store, no email. Reserved at the sale price.",
             say="A first time customer opens the shop's web app on her phone. A name, a mobile number and a password, and she is a registered "
                 "customer. She sees the rush sale, installs the app, reserves the items, and gets a reference number and a Q R code."),
        dict(k="cashier", sayp='At the cashier the reference brings up her order at the sale prices, and the expiring batch becomes cash.', cuts="fsp", kind="scene", step=14, title="The cashier keys in the reference", shots=[("12_pos_online_order.png", "desk")],
             bullets=["Her name and reserved items appear, at the sale prices", "One click loads them into the normal sale",
                      "The batch that would have expired is now cash"],
             caption="The reference number brings up the customer and her items at the clearance prices.",
             say="At the cashier, the reference number brings up her name and her items at the clearance prices. One click loads them into the "
                 "normal sale. The batch that would have expired is now cash."),
        # ---- 5. how it is built, the evidence, the AMD part
        dict(k="predict", sayp="The prediction is statistics: the shop's own rate of sale, a price response model, and expiry order. A language model never decides.", cuts="fsp", kind="steps", kicker="How the AI works: not a language model", title="The prediction is statistics, and you can check it",
             rows=[("Rate of sale", "From the shop's own sales of the last 28 days, per product and branch."),
                   ("Price response", "A Poisson demand model: units follow the usual rate times (price / usual price) to a learned slope."),
                   ("First expired, first sold", "Units that expire sooner sell first, so the model knows what is left on the last day."),
                   ("A safe discount", "The optimizer picks the discount that cuts waste, inside the margin floor and the maximum discount.")],
             foot="A language model never decides. It may only reword a note, and a figure it invents is thrown away.",
             say="The prediction is not a language model. It is statistics you can check. The rate of sale comes from the shop's own sales. A "
                 "demand model learns how units respond to price. Units that expire first sell first, so we know what is left on the last day. "
                 "Then an optimizer picks a discount that is safe for the margin. A language model never decides."),
        dict(k="evidence", cuts="fs", kind="numbers", kicker="The effect, and its limits", title="Measured, and honest about it",
             items=[("10 of 10", "test days where the AI shop beat the identical shop without it", GREEN), ("+8%", "gross margin (simulated shoppers, A/A checked)", BLUE),
                    ("10 to 12%", "lower forecast error with price awareness, on 2 years of real supermarket sales", ORANGE)],
             foot="Limits we state: simulated shoppers in the twin test; against the best simple baseline the gain on real data is small; "
                  "the AI did not beat a sensible fixed rule in the smallest world.",
             say="Measured, and honest about it. In two identical simulated shops, the A I shop was ahead on ten of ten test days, with about eight "
                 "percent more gross margin. On two years of real supermarket sales, price awareness lowered forecast error by ten to twelve percent. "
                 "We state the limits: simulated shoppers, only a small gain over the best simple baseline, and in the smallest world the A I did not beat "
                 "a sensible fixed rule."),
        dict(k="setup", cuts="f", kind="flow", kicker="The setup and environment", title="What runs where",
             boxes=[("Sim.PesoWeb (Python)", ["Seeded world, shoppers, incidents", "Calls the real API", "Scoring, twin worlds"], ORANGE),
                    ("The shop system (PesoWeb)", ["ASP.NET Core API, SQL Server", "Angular screens: POS, Hub", "Guardrails, approvals, audit"], BLUE),
                    ("The AI layer (Python)", ["Demand model, optimizer", "Detectors, missions, replenish", "Insight: rules plus wording"], GREEN),
                    ("AMD Developer Cloud", ["Instinct GPU, ROCm", "PyTorch: Quick Sim", "vLLM: wording of notes"], (237, 28, 36))],
             foot="Tests: 311 shop-system, 190 AI, 240 simulator. Live checks on real data. Open source, MIT.",
             say="The simulator is Python and drives the real Peso Web A P I. Peso Web is an ASP dot NET A P I with SQL Server and Angular screens, "
                 "and it enforces the guardrails. The A I layer is Python and only talks to it through the A P I. And the A M D Developer Cloud runs the GPU parts."),
        dict(k="amd", cuts="fsp", kind="amd", say=amd_narration(amd), sayp=amd_narration(amd, short=True)),
        dict(k="concept3d", cuts="fs", kind="clip", clip="sim3d_concept.mp4",
             say="On the roadmap: a three D view of the simulated shop. This clip is a concept, built on mock data, with shoppers walking the "
                 "aisles. It will be replaced by detailed three D shops driven by the simulator's own days."),
        dict(k="close", sayp='Practise safely. Act on the data. People decide. Thank you.', cuts="fsp", kind="card", kicker="Reinvent Commerce", title="Practise safely. Act on the data. People decide.",
             lines=["Sim.PesoWeb tests the AI before a real shop depends on it.", "The Intelligent Hub finds the loss and says how to improve.",
                    "Next: SMS and other channels, online payment, more shops."],
             dark=True,
             say="Mission Commerce A I. Practise safely in Sim dot Peso Web, act on the data in the Intelligent Hub, and let people decide. Thank you."),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cut", choices=("full", "short", "pitch"), default="full")
    ap.add_argument("--final", action="store_true")
    args = ap.parse_args()
    amd = load_amd()
    if args.final and not amd:
        print("REFUSED: --final needs results/amd-session.json from a real AMD ROCm run (amd = true).")
        return 2
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    work = mv.WORK / ("pitch_" + args.cut)
    work.mkdir(parents=True, exist_ok=True)
    mv.FRAMES.mkdir(exist_ok=True)
    tag = {"full": "f", "short": "s", "pitch": "p"}[args.cut]
    chosen = [s for s in scenes(amd) if tag in s["cuts"]]
    imgs = []
    for i, s in enumerate(chosen):
        p = work / f"s{i:02d}.png"
        kind = s["kind"]
        if kind == "numbers":
            numbers(p, s["kicker"], s["title"], s["items"], s.get("foot"))
        elif kind == "card":
            mv.card(p, s["kicker"], s["title"], s["lines"], dark=s.get("dark", False))
        elif kind == "steps":
            steps(p, s["kicker"], s["title"], s["rows"], s.get("foot"))
        elif kind == "flow":
            flow(p, s["kicker"], s["title"], s["boxes"], s.get("foot"))
        elif kind == "amd":
            amd_scene(p, amd)
        elif kind == "clip":
            p = None
        else:
            mv.scene(p, s["step"], s["title"], s["shots"], s["bullets"], s["caption"])
        imgs.append(p)
    # the voice-over: Windows' built-in voice unless the narration files are replaced
    mv.WORK = work
    wavs = mv.tts([(s.get("sayp") or s["say"]) if args.cut == "pitch" else s["say"] for s in chosen])
    clips, total = [], 0.0
    for i, (img, wav) in enumerate(zip(imgs, wavs)):
        dur = mv.seconds(wav) + 0.9
        total += dur
        clip = work / f"c{i:02d}.mp4"
        if img is None:                                   # a recorded clip, looped to the length of the narration
            source = ["-stream_loop", "-1", "-i", str(Path(__file__).resolve().parent / chosen[i]["clip"])]
        else:
            source = ["-loop", "1", "-i", str(img)]
        subprocess.run([ff, "-y", "-loglevel", "error", *source, "-i", str(wav),
                        "-vf", f"scale={W}:{H},format=yuv420p,fade=t=in:st=0:d=0.35,fade=t=out:st={dur - 0.35:.2f}:d=0.35",
                        "-af", "apad", "-t", f"{dur:.2f}", "-r", "25", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                        "-c:a", "aac", "-b:a", "128k", str(clip)], check=True)
        clips.append(clip)
        print(f"{chosen[i]['k']:10} {dur:5.1f}s")
    listing = work / "list.txt"
    listing.write_text("\n".join(f"file '{c.as_posix()}'" for c in clips), encoding="utf-8")
    out = Path(__file__).resolve().parent / f"MissionCommerce_Pitch_{args.cut}.mp4"
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(out)], check=True)
    print(f"written {out.name}: {total / 60:.1f} min, {out.stat().st_size / 1e6:.1f} MB" + ("" if amd else "  (DRAFT: no real AMD run yet)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
