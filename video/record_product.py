"""Captures the whole-product screens for the pitch video into video/frames/ (the Sim.PesoWeb results, and the Intelligent Hub with all
six AI features, AI Impact, and AI Insight on a simulated company that has real history).

Needs PesoWeb (API :5071, screens :4200), `python -m http.server 8080` at the repo root for the Sim.PesoWeb dashboard, and the notes made
by `python sim/scripts/insight_check.py <owner email> <password>` for that company.

    python video/record_product.py
"""
import asyncio
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp import Browser                                  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FRAMES = Path(__file__).resolve().parent / "frames"
PESOWEB = "http://127.0.0.1:4200"
DASH = "http://127.0.0.1:8080/ui/dashboard"


def owner():
    text = io.open(ROOT / "sim" / "runs" / "CREDENTIALS.txt", encoding="utf-8", errors="replace").read()
    m = re.search(r"c1 OWNER tenant \d+: (owner\.c1\.s21\.real2@simworld\.test) / (\S+)", text)
    if not m:
        raise SystemExit("the simulated company's login is not in sim/runs/CREDENTIALS.txt")
    return m.group(1), m.group(2)


async def login(b, email, password):
    await b.goto("about:blank", 1)
    await b.js("1")
    await b.goto(f"{PESOWEB}/#/auth/login", 4)
    await b.js("localStorage.clear(); sessionStorage.clear();")
    await b.goto(f"{PESOWEB}/#/auth/login", 5)
    await b.wait_for("#email", 60)
    await b.fill("#email", email)
    await b.fill("#password", password)
    await b.click("#frm button[type=submit]")
    await asyncio.sleep(6)


async def scroll_to_text(b, text, top=70):
    await b.js("""(function(t,top){var els=[].slice.call(document.querySelectorAll('h5,h6,h4'));
        var el=els.filter(function(e){return (e.innerText||'').indexOf(t)>=0;})[0];
        if(el){var r=el.getBoundingClientRect(); window.scrollTo(0, window.scrollY + r.top - top);}})(%r,%d)""" % (text, top))
    await asyncio.sleep(1)


async def main():
    email, password = owner()
    b = Browser(port=9444, profile=r"D:\tmp_chrome_video_profile2")
    await b.start()
    try:
        # ---- Sim.PesoWeb: the recorded comparison of two identical shops, with and without the AI
        await b.viewport(1366, 900)
        await b.goto(f"{DASH}/index.html", 4)
        await b.wait_text("Sim.PesoWeb results", 30)
        await asyncio.sleep(1.5)
        await b.shot(FRAMES / "20_sim_results.png")
        await scroll_to_text(b, "Customer story", 20)
        await b.shot(FRAMES / "21_sim_customer_story.png")
        await b.goto(f"{DASH}/day.html", 4)
        await asyncio.sleep(2)
        await b.shot(FRAMES / "22_sim_day_report.png")
        print("sim dashboard ok")

        # ---- the Intelligent Hub of a simulated company with real history
        await login(b, email, password)
        for name, route, wait, scroll in (
            ("30_hub_overview", "/#/ai/hub?tab=overview", "Intelligence Hub", None),
            ("31_hub_tasks", "/#/ai/hub?tab=tasks", "My tasks", None),
            ("32_hub_reorders", "/#/ai/hub?tab=reorders", "Reorders", None),
            ("33_hub_missions", "/#/ai/hub?tab=missions", "shoppers", None),
            ("34_hub_impact", "/#/ai/hub?tab=impact", "What changed", None),
            ("35_hub_settings", "/#/ai/hub?tab=settings", "AI features", None),
            ("36_ai_control", "/#/ai/control", "AI Control", None),
            ("37_approval_center", "/#/pricing/approvals", "Approval Center", None),
        ):
            await b.goto(f"{PESOWEB}{route}", 3)
            try:
                await b.wait_text(wait, 40)
            except TimeoutError:
                print("  (text not found, capturing anyway):", name)
            await asyncio.sleep(2.5)
            await b.shot(FRAMES / f"{name}.png")
            print(name, "ok")

        # ---- AI Insight: what the AI achieved, and what to improve in its setup
        await b.goto(f"{PESOWEB}/#/ai/hub?tab=overview", 3)
        await b.wait_text("AI Insight", 40)
        await asyncio.sleep(2)
        await scroll_to_text(b, "AI Insight: how the AI is doing")
        await b.shot(FRAMES / "38_hub_insight.png")
        await scroll_to_text(b, "What the AI achieved", 60)
        await b.shot(FRAMES / "39_hub_insight_results.png")
        print("insight ok")
    finally:
        await b.close()


if __name__ == "__main__":
    asyncio.run(main())
