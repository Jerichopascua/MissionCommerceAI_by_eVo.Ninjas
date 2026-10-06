"""Live check that PesoWeb itself (no hub page open, no agent running) opens alerts and pushes them, and price changes, to a webhook.

Start PesoWeb with the test switches first (never in normal use):
    Hub__AllowLocalWebhooks=true Hub__BackgroundMinutes=1 dotnet run --project Retailo.csproj --no-build --no-launch-profile --urls http://localhost:5071
Then:
    python scripts/hub_background_check.py
It listens on 127.0.0.1:9099, sets that as a company's webhook, creates a breach and a price change by calling only business endpoints,
and waits (up to about 3 minutes) for the background check to deliver them."""
import json
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from simpeso.driver import PesoWebDriver            # noqa: E402
from simpeso.verticals import ProductSpec           # noqa: E402

BASE = "http://localhost:5071"
PORT = 9099
received = []
checks = []


class Hook(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8")
        try:
            received.append(json.loads(body))
        except ValueError:
            received.append({"raw": body})
        self.send_response(200)
        self.end_headers()

    def log_message(self, *a):
        pass


def check(ok, what):
    checks.append(bool(ok))
    print(f"   [{'PASS' if ok else 'FAIL'}] {what}")


def wait_for(pred, seconds):
    end = time.time() + seconds
    while time.time() < end:
        if pred():
            return True
        time.sleep(5)
    return False


def main() -> int:
    server = HTTPServer(("127.0.0.1", PORT), Hook)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    run = "hb-" + uuid.uuid4().hex[:6]
    drv = PesoWebDriver(BASE, run)
    a = drv.register("Hub Background Store", "Demo", "Owner", f"{run}@hb.test", "Hub!123456")
    wh = a.warehouse_id
    basics = drv.setup_basics(a)
    cat = drv.add_category(a, "Grocery")
    pid = drv.add_product(a, ProductSpec("HB-1", "Test item", "Grocery", 60, 100, False), cat, basics)
    drv.set_pricing_policy(a, "Autonomous", hard_floor=5, soft_floor=10, max_discount=50, max_changes_per_hour=10)

    st, o = drv._call("PUT", "/api/ai/channel", a.token, json_body={"WebhookUrl": f"http://127.0.0.1:{PORT}/hook", "SendAlerts": True, "SendPriceChanges": True}, raw=True)
    if st != 200:
        print("The local webhook was refused: start PesoWeb with Hub__AllowLocalWebhooks=true (see the top of this file).")
        return 2
    st, _ = drv._call("POST", "/api/ai/channel/test", a.token, raw=True)
    check(st == 200 and any(m.get("type") == "Test" for m in received), "the test message reaches the listener over real HTTP")

    # the rule is saved first (this runs one check); the breach is created afterwards, with no hub call, so only the background check can notice it
    drv._call("PUT", "/api/ai/hub/rules/ApprovalsWaiting", a.token, json_body={"enabled": True, "threshold": 0, "role": "Pricing manager", "severity": "Act", "notifyEmail": False})
    received.clear()
    st, body = drv._call("POST", "/api/Pricing/ListPrice", a.token, json_body={"WarehouseId": wh, "ProductId": pid, "NewPrice": 103, "Source": "Ai", "Confidence": "learned"}, raw=True)
    change_id = body.get("priceChangeId")
    print("   waiting for PesoWeb's own background check (up to 3 minutes)...")
    got = wait_for(lambda: any(m.get("type") == "AlertOpened" for m in received), 180)
    check(got, "PesoWeb opened the alert and pushed it to the webhook by itself")
    alert = next((m for m in received if m.get("type") == "AlertOpened"), {})
    check("waiting for a decision" in alert.get("text", "") and alert.get("role") == "Pricing manager", "the message says what happened and who is responsible")

    st, _ = drv._call("POST", "/api/Pricing/ApproveListPrice", a.token, json_body={"PriceChangeId": change_id}, raw=True)
    check(st == 200, "a person approves the price change")
    got = wait_for(lambda: any(m.get("type") == "PriceChanged" for m in received), 180)
    check(got, "the price change is pushed to the webhook by the background check, once")
    time.sleep(70)
    check(sum(1 for m in received if m.get("type") == "PriceChanged") == 1, "it is not sent a second time")
    server.shutdown()

    print(f"\nResult: {sum(checks)} of {len(checks)} checks passed.")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
