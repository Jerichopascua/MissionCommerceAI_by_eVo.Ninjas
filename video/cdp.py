"""A very small Chrome driver (DevTools protocol over a websocket) used to capture the real screens for the presentation video.
Headless Chrome, one tab, no extra packages beyond `websockets`."""
import asyncio
import base64
import json
import subprocess
import time
import urllib.request
from pathlib import Path

import websockets

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


class Browser:
    def __init__(self, port=9333, profile=r"D:/tmp_chrome_video_profile", extra_args=None):
        self.port, self.profile = port, profile
        self.extra_args = list(extra_args or [])
        self.proc = None
        self.ws = None
        self._id = 0

    async def start(self):
        self.proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", f"--remote-debugging-port={self.port}",
                                      f"--user-data-dir={self.profile}", "--no-first-run", "--hide-scrollbars",
                                      "--window-size=1366,900"] + self.extra_args + ["about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/list", timeout=2))
                page = next(t for t in tabs if t.get("type") == "page")
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("Chrome did not start")
        self.ws = await websockets.connect(page["webSocketDebuggerUrl"], max_size=64 * 1024 * 1024)
        await self.send("Page.enable")
        await self.send("Runtime.enable")

    async def send(self, method, **params):
        self._id += 1
        mid = self._id
        await self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    async def viewport(self, width, height, mobile=False, scale=1):
        await self.send("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=scale, mobile=mobile)

    async def goto(self, url, wait=2.0):
        await self.send("Page.navigate", url=url)
        await asyncio.sleep(wait)

    async def js(self, expression):
        r = await self.send("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in r:
            raise RuntimeError(str(r["exceptionDetails"])[:300])
        return r.get("result", {}).get("value")

    async def wait_for(self, selector, timeout=30):
        end = time.time() + timeout
        while time.time() < end:
            if await self.js(f"!!document.querySelector({json.dumps(selector)})"):
                return True
            await asyncio.sleep(0.5)
        raise TimeoutError(f"not found: {selector}")

    async def wait_text(self, text, timeout=30):
        end = time.time() + timeout
        while time.time() < end:
            if await self.js(f"document.body && document.body.innerText.includes({json.dumps(text)})"):
                return True
            await asyncio.sleep(0.5)
        raise TimeoutError(f"text not found: {text}")

    async def click(self, selector):
        await self.js(f"document.querySelector({json.dumps(selector)}).click()")

    async def click_text(self, text, tag="button,a"):
        ok = await self.js("""(function(t,tag){var els=[].slice.call(document.querySelectorAll(tag));
            var el=els.filter(function(e){return e.offsetParent!==null && (e.innerText||'').trim().indexOf(t)>=0;})[0];
            if(!el){return false;} el.click(); return true;})(%s,%s)""" % (json.dumps(text), json.dumps(tag)))
        if not ok:
            raise RuntimeError(f"nothing to click with text: {text}")

    async def fill(self, selector, value):
        await self.js("""(function(s,v){var e=document.querySelector(s); e.focus(); e.value=v;
            e.dispatchEvent(new Event('input',{bubbles:true})); e.dispatchEvent(new Event('change',{bubbles:true}));})(%s,%s)"""
                      % (json.dumps(selector), json.dumps(value)))

    async def shot(self, path, full=False):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        params = {"format": "png"}
        if full:
            m = await self.send("Page.getLayoutMetrics")
            size = m["cssContentSize"]
            params.update(captureBeyondViewport=True, clip={"x": 0, "y": 0, "width": size["width"], "height": size["height"], "scale": 1})
        r = await self.send("Page.captureScreenshot", **params)
        Path(path).write_bytes(base64.b64decode(r["data"]))

    async def close(self):
        try:
            if self.ws:
                await self.ws.close()
        finally:
            if self.proc:
                self.proc.terminate()
