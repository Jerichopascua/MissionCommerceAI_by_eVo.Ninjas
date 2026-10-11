"""Records a short, clean clip of the 3D shop-simulation concept (ui/sim3d, mock data) into video/frames/sim3d/ and video/sim3d_concept.mp4.

The prototype's own simulation is stepped deterministically (a fixed number of simulated seconds per frame), so the clip is smooth whatever
the speed of this PC. It is labelled as a concept with mock data.

    python video/record_sim3d.py
"""
import asyncio
import base64
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp import Browser                                  # noqa: E402
import make_video as mv                                  # noqa: E402
from make_video import font, wrap, BLUE, INK, W, H       # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "sim3d_concept.mp4"
FRAMES = HERE / "frames" / "sim3d"
URL = (HERE.parent / "ui" / "sim3d" / "index.html").as_uri() + "?demo=1&speed=1&ff=40"
N = 160                      # frames at 10 per second: 16 seconds, as long as the narration
SIM_SECONDS_PER_FRAME = 1.5


def compose(shot: Image.Image, label: str, caption: str) -> Image.Image:
    im = Image.new("RGB", (W, H), (238, 244, 255))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 78), fill=(255, 255, 255))
    d.rectangle((0, 76, W, 79), fill=BLUE)
    d.text((40, 20), "Roadmap: a 3D view of the simulated shop", font=font(34, True), fill=INK)
    d.rounded_rectangle((W - 330, 18, W - 40, 62), radius=22, fill=(255, 237, 213))
    d.text((W - 312, 25), "CONCEPT \u00b7 MOCK DATA", font=font(24, True), fill=(194, 65, 12))
    ph = H - 79 - 92 - 20
    pw = int(shot.width * ph / shot.height)
    s = shot.resize((pw, ph), Image.LANCZOS)
    x = (W - pw) // 2
    d.rounded_rectangle((x - 5, 95, x + pw + 5, 95 + ph + 5), radius=10, fill=(22, 41, 77))
    im.paste(s, (x, 98))
    d.rectangle((0, H - 92, W, H), fill=INK)
    for i, l in enumerate(wrap(d, caption, font(27), W - 90)[:2]):
        d.text((45, H - 80 + i * 36), l, font=font(27), fill=(255, 255, 255))
    return im


async def main():
    FRAMES.mkdir(parents=True, exist_ok=True)
    for old in FRAMES.glob("*.png"):
        old.unlink()
    b = Browser(port=9446, profile=r"D:\tmp_chrome_sim3d_profile",
                extra_args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--enable-webgl"])
    await b.start()
    try:
        await b.viewport(1366, 768)
        await b.goto(URL, 6)
        await b.wait_for("#stage canvas", 40)
        await asyncio.sleep(3)
        await b.js("UI.running = false;")
        caption = "Concept: shoppers walking the aisles of a simulated store. It will be replaced by detailed 3D shops driven by the simulator's own days."
        for i in range(N):
            await b.js("(function(){for (var k=0;k<%d;k++) UI.engine.step(0.25); UI.tickUi(true);})()" % int(SIM_SECONDS_PER_FRAME * 4))
            await asyncio.sleep(0.15)
            r = await b.send("Page.captureScreenshot", format="png")
            raw = base64.b64decode(r["data"])
            (FRAMES / "raw.png").write_bytes(raw)
            shot = Image.open(FRAMES / "raw.png").convert("RGB")
            compose(shot, "CONCEPT", caption).save(FRAMES / f"f{i:04d}.png")
        print("frames:", N)
    finally:
        await b.close()
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ff, "-y", "-loglevel", "error", "-framerate", "10", "-i", str(FRAMES / "f%04d.png"), "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-crf", "20", str(OUT)], check=True)
    print("written", OUT, f"{OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    asyncio.run(main())
