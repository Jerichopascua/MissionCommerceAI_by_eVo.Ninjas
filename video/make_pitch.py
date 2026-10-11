"""Builds the hackathon pitch video: problem first (explained simply), the working product, how the AI works, the evidence,
the setup, and the AMD part. Reuses the captured screens in video/frames/ and the drawing helpers of make_video.py.

    python video/make_pitch.py                 full cut (about 4.5 minutes), writes video/MissionCommerce_Pitch_full.mp4
    python video/make_pitch.py --cut short     3-minute cut,             writes video/MissionCommerce_Pitch_short.mp4
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


def amd_narration(amd):
    if not amd:
        return ("Draft placeholder. The A M D scene is filled from the real session numbers: the GPU and ROCm version, how fast the "
                "shopper simulation runs on the GPU compared with the CPU, and the language model that words the notes on the same GPU.")
    hw, qs, li = amd["hardware"], amd["quicksim"], amd.get("insight_llm", {})
    g = qs.get("gpu", {})
    parts = [f"On the A M D Developer Cloud we run an {hw.get('device', 'A M D GPU')} with ROCm. "]
    if g.get("generation_s"):
        parts.append(f"PyTorch on ROCm generates {qs['individuals']:,} shoppers over {qs['days']} days in {g['generation_s']:.0f} seconds"
                     + (f", {qs['speedup_x']} times faster than the CPU. " if qs.get("speedup_x") else ". "))
    if li.get("tokens_per_s"):
        parts.append(f"The same GPU serves {li['model']} with vLLM. It rewords the A I notes at {li['tokens_per_s']:.0f} tokens a second, "
                     f"and any note with an invented figure is thrown away before it is shown.")
    return "".join(parts)


# (key, tag set: "f" full cut, "s" short cut)
def scenes(amd):
    T = lambda *a: a
    return [
        dict(k="hook", cuts="fs", kind="numbers", kicker="Imagine you run a small shop", title="Snacks that go bad in two days",
             items=[("36", "packs on the shelf", BLUE), ("8", "you will probably sell", GREEN), ("28", "end up in the bin, with your money", RED)],
             foot="Every shop has this, every day. A person cannot watch every expiry date.",
             say="Imagine you run a small shop. You have thirty six packs of snacks, and they go bad in two days. You will probably sell eight. "
                 "The other twenty eight go in the bin, and so does your money. Every shop has this problem, every day."),
        dict(k="problem", cuts="fs", kind="card", kicker="The problem: Reinvent Commerce", title="Shops have the data, but not the decisions",
             lines=["Sales, stock, expiry dates and customers sit in different places, so nobody turns them into an action in time.",
                    "The challenge: turn customer and business data into a useful action that helps a business serve and keep its customers."],
             say="Shops already have the data: sales, stock, expiry dates and customers. But it sits in different places, so nobody turns it into a "
                 "decision in time. That is the Reinvent Commerce challenge: turn data into an action that helps the business and its customers."),
        dict(k="idea", cuts="fs", kind="steps", kicker="Our answer: MissionCommerce AI", title="From a date on a pack to a sale in a customer's hand",
             rows=[("It watches", "Every batch with an expiry date, against how fast it really sells."),
                   ("It suggests", "A rush sale at a price that is still safe for the shop's margin."),
                   ("It tells the shop's own customers", "Registered customers see it in their phone app and reserve it."),
                   ("A person decides", "The owner approves; the AI never changes a price by itself.")],
             say="Our answer is Mission Commerce A I. It watches every batch with an expiry date. It suggests a rush sale at a price that is still "
                 "safe for the shop. It tells the shop's own customers. And a person always has the last word."),
        dict(k="find", cuts="fs", kind="scene", step=1, title="The AI finds stock that will expire unsold", shots=[("01_ai_sell_fast.png", "desk")],
             bullets=["Each batch: units still unsold on the last day, at today's rate of sale", "What it is worth at cost, and the discount that clears it",
                      "Never below cost: the owner's pricing rules apply"],
             caption="Real company data: batches that will expire unsold, how much it costs, and the discount to clear them.",
             say="This is the real shop system. The A I has found batches that will expire unsold. For each one it shows how many units will be "
                 "left on the last day, what that is worth at cost, and the discount that would clear them, never below cost."),
        dict(k="decide", cuts="fs", kind="scene", step=2, title="One click: Rush sale, the owner decides", shots=[("02_put_on_sale_prefilled.png", "desk")],
             bullets=["Product, discount and last day are filled in from the AI", "The pricing rules still apply", "Tick: tell registered customers"],
             caption="Rush sale: filled in from the AI suggestion. The manager only confirms.",
             say="With one click on Rush sale, the product, the discount and the last day are filled in. The pricing rules still apply, and the "
                 "manager confirms, with a tick to tell the shop's registered customers."),
        dict(k="told", cuts="f", kind="scene", step=3, title="The register and the customers know at once", shots=[("03_put_on_sale_sent.png", "desk")],
             bullets=["The POS charges the sale price immediately", "A message reaches every registered customer's app", "SMS and other channels: next"],
             caption="Put on sale: the register charges the sale price and registered customers get the message.",
             say="The register charges the sale price at once, and the message reaches every registered customer in the app."),
        dict(k="register", cuts="fs", kind="scene", step=4, title="A first-time customer registers on her phone", shots=[("05_phone_login.png", "phone"), ("06_phone_register.png", "phone")],
             bullets=["The shop's web app opens in the phone's browser", "A name, a mobile number, a password: no email", "She is now a registered customer of the shop"],
             caption="First visit: name, mobile number, password. That is all it takes to become a registered customer.",
             say="A first time customer opens the shop's web app on her phone. A name, a mobile number and a password, and she is a registered "
                 "customer of the shop. No app store, no email."),
        dict(k="install", cuts="f", kind="scene", step=5, title="She sees the rush sale and installs the app", shots=[("07_phone_welcome_sale.png", "phone"), ("08_phone_install.png", "phone")],
             bullets=["The shop's message and the clearance items come first", "One tap installs it on the home screen", "She can change her phone and password, not her ID"],
             caption="The rush sale is the first thing she sees. One tap puts the app on her home screen.",
             say="She sees the rush sale straight away, and one tap puts the app on her home screen like any other app."),
        dict(k="reserve", cuts="fs", kind="scene", step=6, title="Reserve now, pay at the store", shots=[("09_phone_sale_added.png", "phone"), ("10_phone_basket.png", "phone"), ("11_phone_reference.png", "phone")],
             bullets=["She adds the clearance items and reserves", "A reference number and a QR code", "She rushes to the store: the stock sells before it expires"],
             caption="Reserved at the sale price: a reference number and a QR code for the store.",
             say="She adds the clearance items and reserves them. She gets a reference number and a Q R code, and she rushes to the store to pay."),
        dict(k="cashier", cuts="fs", kind="scene", step=7, title="The cashier keys in the reference", shots=[("12_pos_online_order.png", "desk")],
             bullets=["Her name and reserved items appear, at the sale prices", "One click loads them into the normal sale", "The batch that would have expired is now cash"],
             caption="The reference number brings up the customer and her items at the clearance prices.",
             say="At the cashier, the reference number brings up her name and her items at the clearance prices. One click loads them into the "
                 "normal sale. The batch that would have expired is now cash."),
        dict(k="predict", cuts="fs", kind="steps", kicker="How the AI works: not a language model", title="The prediction is statistics, and you can check it",
             rows=[("Rate of sale", "From the shop's own sales of the last 28 days, per product and branch."),
                   ("Price response", "A Poisson demand model: units follow the usual rate times (price / usual price) to a learned slope."),
                   ("First expired, first sold", "Units that expire sooner sell first, so the model knows what is left on the last day."),
                   ("A safe discount", "The optimizer picks the discount that cuts waste, inside the margin floor and the maximum discount.")],
             foot="A language model never decides. It may only reword a note, and a figure it invents is thrown away.",
             say="The prediction is not a language model. It is statistics you can check. The rate of sale comes from the shop's own sales. A "
                 "demand model learns how units respond to price. Units that expire first sell first, so we know what is left on the last day. "
                 "Then an optimizer picks a discount that is safe for the margin. A language model never decides."),
        dict(k="caps", cuts="f", kind="steps", kicker="What the AI does", title="Six capabilities, one rule: people decide",
             rows=[("Monitoring and Loss Prevention", "Unusual activity, what to count first, and stock that will expire unsold."),
                   ("Pricing", "Markdowns and list-price advice, every change through margin rules and approval."),
                   ("Replenish and Customer Missions", "What to reorder and why shoppers came; the shop plans stock and staff."),
                   ("Insight", "Plain-language notes; every figure is checked against the data.")],
             foot="Switchable per company and per branch. Every action is audited.",
             say="Behind this are six capabilities: monitoring, loss prevention, pricing, replenishment, customer missions and plain language "
                 "insight. Each can be switched off per company and per branch, and every action is audited."),
        dict(k="evidence", cuts="fs", kind="numbers", kicker="The effect, and its limits", title="Measured, and honest about it",
             items=[("10 of 10", "test days where the AI shop beat the identical shop without it", GREEN), ("+8%", "gross margin (simulated shoppers, A/A checked)", BLUE),
                    ("10 to 12%", "lower forecast error with price awareness, on 2 years of real supermarket sales", ORANGE)],
             foot="Limits we state: simulated shoppers in the twin test; against the best simple baseline the gain on real data is small.",
             say="Measured, and honest about it. In two identical simulated shops, the A I shop was ahead on ten of ten test days, with about eight "
                 "percent more gross margin. On two years of real supermarket sales, price awareness lowered forecast error by ten to twelve percent. "
                 "We also state the limits: simulated shoppers, and only a small gain over the best simple baseline."),
        dict(k="setup", cuts="f", kind="flow", kicker="The setup and environment", title="What runs where",
             boxes=[("The shop system (PesoWeb)", ["ASP.NET Core API", "Angular screens", "SQL Server", "POS, stock, expiry batches"], BLUE),
                    ("The AI layer", ["Python", "Demand model, optimizer", "Detectors, agent", "Never decides alone"], GREEN),
                    ("The customer app", ["Installable web app", "Register, reserve, QR", "Live prices and sales"], ORANGE),
                    ("AMD Developer Cloud", ["Instinct GPU, ROCm", "PyTorch: shopper simulation", "vLLM: wording of notes"], (237, 28, 36))],
             foot="Tests: 311 shop-system, 170 AI, 240 simulator. Live checks on the real company data. Open source, MIT.",
             say="The shop system is Peso Web: an ASP dot NET API, Angular screens and SQL Server. The A I layer is Python and talks to it through "
                 "the real A P I. The customer app is an installable web app. And the A M D Developer Cloud runs the GPU parts."),
        dict(k="amd", cuts="fs", kind="amd", say=amd_narration(amd)),
        dict(k="close", cuts="fs", kind="card", kicker="Reinvent Commerce", title="From a date on a pack to a sale in a customer's hand",
             lines=["The AI finds the loss. People decide. Customers get a deal.", "Next: SMS and other channels, online payment, more shops."],
             dark=True,
             say="Mission Commerce A I. The A I finds the loss, people decide, and customers get a deal. Thank you."),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cut", choices=("full", "short"), default="full")
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
    tag = "s" if args.cut == "short" else "f"
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
        else:
            mv.scene(p, s["step"], s["title"], s["shots"], s["bullets"], s["caption"])
        imgs.append(p)
    # the voice-over: Windows' built-in voice unless the narration files are replaced
    mv.WORK = work
    wavs = mv.tts([s["say"] for s in chosen])
    clips, total = [], 0.0
    for i, (img, wav) in enumerate(zip(imgs, wavs)):
        dur = mv.seconds(wav) + 0.9
        total += dur
        clip = work / f"c{i:02d}.mp4"
        subprocess.run([ff, "-y", "-loglevel", "error", "-loop", "1", "-i", str(img), "-i", str(wav),
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
