"""Live check of database snapshots against the local PesoWeb_MissionDev. It SAVES the database, changes it, RESTORES it and checks the change is gone,
then changes the database structure with a probe stored procedure and checks that a restore is now refused.

Start PesoWeb with the snapshot switches first (they are off in normal use):
    Snapshots__Enabled=true Snapshots__AllowedEmails=snapadmin@snap.test dotnet run --project Retailo.csproj --no-build --no-launch-profile --urls http://localhost:5071
Then:   python scripts/snapshot_check.py
Nothing else may use the database while it runs (a restore replaces everything saved since the snapshot)."""
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from simpeso.driver import DriverRefusal, PesoWebDriver      # noqa: E402

BASE = "http://localhost:5071"
SERVER, DATABASE = r"(localdb)\MSSQLLocalDB", "PesoWeb_MissionDev"
ADMIN, PASSWORD = "snapadmin@snap.test", "Snap!123456"
checks = []


def check(ok, what):
    checks.append(bool(ok))
    print(f"   [{'PASS' if ok else 'FAIL'}] {what}")


def sql(q):
    subprocess.run(["sqlcmd", "-S", SERVER, "-d", DATABASE, "-E", "-b", "-Q", "SET NOCOUNT ON; " + q], check=True, capture_output=True, text=True)


def main() -> int:
    run = "snap-" + uuid.uuid4().hex[:6]
    drv = PesoWebDriver(BASE, run)
    try:
        admin = drv.register("Snapshot Admin", "Snap", "Admin", ADMIN, PASSWORD)
    except Exception:                                   # already registered by an earlier run
        admin = drv.login(ADMIN, PASSWORD)

    def call(method, path, body=None, token=None):
        return drv._call(method, path, token or admin.token, json_body=body, raw=True)

    print("1. Who may use it")
    other = drv.register("Ordinary Shop", "Some", "Owner", f"{run}@snap.test", PASSWORD)
    st, _ = call("GET", "/api/snapshots", token=other.token)
    check(st == 403, "an ordinary company owner is refused")
    st, body = call("GET", "/api/snapshots")
    check(st == 200 and body["status"]["enabled"], "the allowed address can see the snapshots")
    check(body["status"]["hasInitial"] and any(s["kind"] == "Initial" and s["restorable"] for s in body["snapshots"]),
          f"an initial snapshot exists for the current structure ({body['status'].get('initialSnapshot')}) and can be restored")

    print("2. Save under a name")
    name = "check-" + uuid.uuid4().hex[:6]
    st, o = call("POST", "/api/snapshots", {"Name": name, "Note": "live check"})
    check(st == 200 and o["sizeBytes"] > 1_000_000, f"saved '{name}' ({o.get('sizeBytes', 0) // 1024 // 1024} MB)")
    st, _ = call("POST", "/api/snapshots", {"Name": name})
    check(st == 400, "the same name is not saved over")
    st, _ = call("POST", "/api/snapshots", {"Name": "../evil"})
    check(st == 400, "a name that tries to leave the folder is refused")

    print("3. Change the database, then restore")
    changed = drv.register("Added After Snapshot", "Late", "Owner", f"{run}.late@snap.test", PASSWORD)
    check(changed.token, "a company created after the snapshot exists")
    st, _ = call("POST", "/api/snapshots/restore", {"Name": name, "ConfirmText": "no"})
    check(st == 400, "a restore without typing RESTORE is refused")
    st, o = call("POST", "/api/snapshots/restore", {"Name": name, "ConfirmText": "RESTORE"})
    check(st == 200 and "safety copy" in o.get("message", ""), "restore: " + str(o.get("message")))
    try:
        drv.login(f"{run}.late@snap.test", PASSWORD)
        gone = False
    except Exception:
        gone = True
    check(gone, "the company created after the snapshot is gone")
    st, body = call("GET", "/api/snapshots")
    check(st == 200 and any(s["kind"] == "Safety" for s in body["snapshots"]), "the signed-in admin still works, and a safety snapshot of the state before the restore was kept")

    print("4. A change to the database structure blocks the restore")
    sql("EXEC('CREATE OR ALTER PROCEDURE dbo.zz_snapshot_probe AS SELECT 1')")
    try:
        st, body = call("GET", "/api/snapshots")
        mine = next(s for s in body["snapshots"] if s["name"] == name)
        check(body["status"]["hasInitial"] is False, "with a changed structure there is no initial snapshot for it yet")
        check(mine["restorable"] is False and "stored procedures" in mine["reason"], "the old snapshot is marked not restorable: " + mine["reason"][:80] + "...")
        st, o = call("POST", "/api/snapshots/restore", {"Name": name, "ConfirmText": "RESTORE"})
        check(st == 409 and "refused" in o.get("message", ""), "restoring it is refused with the reason")
        st, _ = call("GET", "/api/snapshots")
        check(st == 200, "and nothing was touched: PesoWeb still works")
    finally:
        sql("DROP PROCEDURE IF EXISTS dbo.zz_snapshot_probe;")
    st, body = call("GET", "/api/snapshots")
    check(next(s for s in body["snapshots"] if s["name"] == name)["restorable"], "after the structure is back the snapshot can be restored again")

    print("5. Tidy up")
    st, _ = call("DELETE", f"/api/snapshots/{name}")
    check(st == 200, "a saved snapshot can be deleted")
    initial = next(s for s in body["snapshots"] if s["kind"] == "Initial")
    st, _ = call("DELETE", f"/api/snapshots/{initial['name']}")
    check(st == 400, "an initial snapshot cannot be deleted from here")
    for s in body["snapshots"]:
        if s["kind"] == "Safety":
            call("DELETE", f"/api/snapshots/{s['name']}")

    print(f"\nResult: {sum(checks)} of {len(checks)} checks passed.")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
