"""Builds the Rush Sale presentation video from the captured screens (video/frames) with a spoken voiceover.

    python video/make_video.py
Writes video/MissionCommerce_RushSale.mp4. Uses Windows' built-in voice for the narration and the ffmpeg that ships with imageio_ffmpeg.
"""
import json
import subprocess
import sys
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FRAMES = HERE / "frames"
WORK = Path(r"D:\tmp_video_build")
OUT = HERE / "MissionCommerce_RushSale.mp4"
W, H = 1280, 720
BG, INK, BLUE, DARK, MUTED, RED = (238, 244, 255), (22, 41, 77), (31, 107, 255), (0, 73, 207), (91, 107, 140), (220, 38, 38)
VOICE = "Microsoft Zira Desktop"


def font(size, bold=False):
    return ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf", size)


def wrap(draw, text, fnt, width):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=fnt) <= width:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def gradient():
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(238 - 20 * t), int(244 - 14 * t), 255))
    return im


def card(path, kicker, title, lines, dark=True):
    im = Image.new("RGB", (W, H), DARK if dark else BG)
    d = ImageDraw.Draw(im)
    if dark:
        for y in range(H):
            t = y / H
            d.line([(0, y), (W, y)], fill=(int(56 - 40 * t), int(128 - 60 * t), int(248 - 30 * t)))
        d.ellipse((W - 420, -180, W + 160, 400), fill=(60, 130, 248))
    ink = (255, 255, 255) if dark else INK
    d.text((90, 150), kicker.upper(), font=font(26, True), fill=(184, 208, 248) if dark else BLUE)
    y = 200
    for l in wrap(d, title, font(66, True), W - 220):
        d.text((90, y), l, font=font(66, True), fill=ink)
        y += 82
    y += 24
    for line in lines:
        for l in wrap(d, line, font(32), W - 220):
            d.text((90, y), l, font=font(32), fill=(220, 232, 255) if dark else MUTED)
            y += 44
        y += 8
    d.text((90, H - 70), "MissionCommerce AI  ·  Team Evo.Ninjas  ·  AMD Developer Hackathon, Reinvent Commerce", font=font(22), fill=(184, 208, 248) if dark else MUTED)
    im.save(path)


def scene(path, step, title, shots, bullets, caption):
    """shots: list of (frame file, kind) with kind 'desk' or 'phone'. A right-hand panel carries the bullets."""
    im = gradient()
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 78), fill=(255, 255, 255))
    d.rectangle((0, 76, W, 79), fill=BLUE)
    d.ellipse((30, 20, 78, 68), fill=BLUE)
    d.text((54 - d.textlength(str(step), font=font(26, True)) / 2, 26), str(step), font=font(26, True), fill=(255, 255, 255))
    d.text((100, 20), title, font=font(34, True), fill=INK)
    area_top, area_h = 96, 520
    phones = [s for s in shots if s[1] == "phone"]
    if phones:
        ph = area_h
        x = 40
        for f, _ in phones:
            s = Image.open(FRAMES / f).convert("RGB")
            s = s.resize((int(s.width * ph / s.height), ph), Image.LANCZOS)
            d.rounded_rectangle((x - 8, area_top - 8, x + s.width + 8, area_top + ph + 8), radius=26, fill=(22, 41, 77))
            im.paste(s, (x, area_top))
            x += s.width + 34
        panel_x = x + 10
    else:
        f, _ = shots[0]
        s = Image.open(FRAMES / f).convert("RGB")
        s = s.crop((0, 0, s.width, min(s.height, 800)))
        sw = 800
        s = s.resize((sw, int(s.height * sw / s.width)), Image.LANCZOS)
        d.rounded_rectangle((32, area_top - 4, 32 + sw + 8, area_top + s.height + 4), radius=10, fill=(22, 41, 77))
        im.paste(s, (36, area_top))
        panel_x = 36 + sw + 36
    # bullets
    y = area_top + 4
    for b in bullets:
        lines = wrap(d, b, font(25), W - panel_x - 36)
        d.ellipse((panel_x, y + 10, panel_x + 12, y + 22), fill=BLUE)
        for l in lines:
            d.text((panel_x + 28, y), l, font=font(25), fill=INK)
            y += 34
        y += 18
    # caption bar
    d.rectangle((0, H - 92, W, H), fill=INK)
    for i, l in enumerate(wrap(d, caption, font(27), W - 90)[:2]):
        d.text((45, H - 80 + i * 36), l, font=font(27), fill=(255, 255, 255))
    im.save(path)


SCENES = [
    dict(kind="card", kicker="MissionCommerce AI", title="Rush Sale",
         lines=["AI finds the stock that is about to expire, and turns it into cash, not loss.",
                "Promoted to the store's registered customers, bought on their phone, paid at the cashier."],
         say="Mission Commerce A I by Evo Ninjas. Rush Sale. Turning stock that is about to expire into cash, instead of loss."),
    dict(kind="card", kicker="The problem", title="Expiring stock is money thrown away",
         lines=["Milk, snacks, bread, medicine: every store has stock that expires before it sells.",
                "Nobody notices until the date has passed. Then it is a write-off."],
         say="Every store has stock that expires before it sells. Nobody notices until the date has passed, and then it is a write off."),
    dict(kind="scene", step=1, title="The AI watches every expiry date", shots=[("01_ai_sell_fast.png", "desk")],
         bullets=["For each batch: units still unsold on the last day at today's rate of sale",
                  "What that stock is worth at cost, and the discount that would clear it",
                  "Never below cost: the owner's pricing rules apply",
                  "Already expired stock is flagged to write off"],
         caption="AI Product Loss Prevention: which batches will expire unsold, how much it costs, and the discount to clear it.",
         say="Our A I watches every batch that has an expiry date. For each one it works out how many units will still be on the shelf on the last day, what that stock is worth at cost, and the discount that would clear it, without ever selling below cost. Here, batches are at risk, about four thousand pesos at cost."),
    dict(kind="scene", step=2, title="It proposes the rush sale, the owner decides", shots=[("04_approval_center.png", "desk")],
         bullets=["For batches near expiry the AI has already proposed the markdown",
                  "Each proposal shows the reason, the margin check and the profit at stake",
                  "The owner approves or rejects: the AI never changes a price by itself"],
         caption="The Approval Center: the AI's proposals wait for a person, with the reason and the margin check.",
         say="For the nearest batches the A I has already proposed the markdown. The owner stays in control. Every proposal waits in the Approval Center, with the reason, the margin check, and the profit at stake."),
    dict(kind="scene", step=3, title="One click: Rush sale", shots=[("02_put_on_sale_prefilled.png", "desk")],
         bullets=["Product, discount and last day are filled in from the AI suggestion",
                  "Tick \"Tell registered customers\"",
                  "SMS and other channels: coming soon"],
         caption="Rush sale: filled in from the AI suggestion. The manager only confirms.",
         say="With one click on Rush sale, the product, the discount and the last day are filled in from the A I suggestion. The manager confirms, and ticks, Tell registered customers."),
    dict(kind="scene", step=4, title="The store's registered customers are told", shots=[("03_put_on_sale_sent.png", "desk")],
         bullets=["The sale is live at the register at once: the POS charges the sale price",
                  "A message goes to every registered customer in the customer app",
                  "The log shows what was sent and to how many customers"],
         caption="Put on sale: the register charges the sale price, and registered customers get the message.",
         say="The sale is live at the register at once, and a message goes to every registered customer in the customer app. Text messages and other channels are coming soon."),
    dict(kind="scene", step=5, title="A first-time customer registers on the phone", shots=[("05_phone_login.png", "phone"), ("06_phone_register.png", "phone")],
         bullets=["Opens the store's web app on the phone: nothing to download first",
                  "New customer: name, mobile number, password. No email needed",
                  "She becomes a registered customer in the store's own records"],
         caption="First visit: a name, a mobile number and a password. That is all it takes to become a registered customer.",
         say="A first time customer opens the store's web app on her phone. No email is needed. A name, a mobile number and a password, and she is a registered customer in the store's own records."),
    dict(kind="scene", step=6, title="She sees the rush sale, and installs the app", shots=[("07_phone_welcome_sale.png", "phone"), ("08_phone_install.png", "phone")],
         bullets=["The store's rush sale messages are right at the top",
                  "Clearance items first, with the old price crossed out",
                  "Install it on the home screen from the browser: no app store",
                  "She can change her phone number and password, not her ID"],
         caption="The rush sale message and the clearance list are the first thing she sees. One tap installs the app.",
         say="She sees the store's rush sale message and the clearance items straight away. The app installs on the phone's home screen like any other app, from the browser, with no app store."),
    dict(kind="scene", step=7, title="Reserve now, pay at the store", shots=[("09_phone_sale_added.png", "phone"), ("10_phone_basket.png", "phone"), ("11_phone_reference.png", "phone")],
         bullets=["Add the clearance items, then reserve",
                  "A reference number and a QR code",
                  "She rushes to the store, so the stock is sold before it expires"],
         caption="Reserved at the sale price: she gets a reference number and a QR code to show at the store.",
         say="She adds the clearance items and reserves them. She gets a reference number and a QR code, and she rushes to the store to pay."),
    dict(kind="scene", step=8, title="At the cashier: key in the reference", shots=[("12_pos_online_order.png", "desk")],
         bullets=["The customer's name and her reserved items appear",
                  "At the clearance prices, with the normal price crossed out",
                  "One click loads them into the normal sale"],
         caption="The cashier keys in the reference number: the customer and the reserved items come up at the sale prices.",
         say="At the cashier, the reference number is keyed in. The customer's name and her reserved items appear, at the clearance prices. One click loads them into the normal point of sale."),
    dict(kind="scene", step=9, title="Rung up like any other sale", shots=[("13_pos_loaded.png", "desk")],
         bullets=["Customer and items are in the cart at the sale prices",
                  "The sale goes through the normal POS, stock and books",
                  "The batch that would have expired is now cash"],
         caption="The reserved items are in the cart at the clearance price, ready to pay.",
         say="The customer and the items are in the cart at the clearance prices. The cashier takes payment as usual, and the batch that would have expired is now cash."),
    dict(kind="card", kicker="What is next", title="More channels, online payment, more shoppers",
         lines=["Text message and other channels for the rush sale",
                "Pay online from the app, with the store's own payment methods",
                "Balances and due dates from the store's own books",
                "Same store system: AI that finds the loss, people who decide, customers who get a deal."],
         say="What is next: text messages and other channels, paying online from the app, and balances from the store's own books. Mission Commerce A I: the A I finds the loss, people decide, and customers get a deal."),
]


def tts(texts):
    WORK.mkdir(parents=True, exist_ok=True)
    data = [{"i": i, "text": t, "path": str(WORK / f"v{i:02d}.wav")} for i, t in enumerate(texts)]
    (WORK / "tts.json").write_text(json.dumps(data), encoding="utf-8")
    script = f"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice('{VOICE}')
$s.Rate = 0
$items = Get-Content -Raw -Encoding UTF8 '{WORK / "tts.json"}' | ConvertFrom-Json
foreach ($it in $items) {{
  $s.SetOutputToWaveFile($it.path)
  $s.Speak($it.text)
  $s.SetOutputToNull()
}}
"""
    (WORK / "tts.ps1").write_text(script, encoding="utf-8")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(WORK / "tts.ps1")], check=True)
    return [Path(d["path"]) for d in data]


def seconds(path):
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def main():
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    WORK.mkdir(parents=True, exist_ok=True)
    images = []
    for i, s in enumerate(SCENES):
        p = WORK / f"s{i:02d}.png"
        if s["kind"] == "card":
            card(p, s["kicker"], s["title"], s["lines"], dark=(i in (0, len(SCENES) - 1)))
        else:
            scene(p, s["step"], s["title"], s["shots"], s["bullets"], s["caption"])
        images.append(p)
    wavs = tts([s["say"] for s in SCENES])
    clips = []
    for i, (img, wav) in enumerate(zip(images, wavs)):
        dur = seconds(wav) + 1.0
        clip = WORK / f"c{i:02d}.mp4"
        subprocess.run([ff, "-y", "-loglevel", "error", "-loop", "1", "-i", str(img), "-i", str(wav),
                        "-vf", f"scale={W}:{H},format=yuv420p,fade=t=in:st=0:d=0.4,fade=t=out:st={dur - 0.4:.2f}:d=0.4",
                        "-af", "apad", "-t", f"{dur:.2f}", "-r", "25", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                        "-c:a", "aac", "-b:a", "128k", str(clip)], check=True)
        clips.append(clip)
        print(f"scene {i}: {dur:.1f}s")
    listing = WORK / "list.txt"
    listing.write_text("\n".join(f"file '{c.as_posix()}'" for c in clips), encoding="utf-8")
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(OUT)], check=True)
    print("written", OUT, f"{OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    sys.exit(main())
