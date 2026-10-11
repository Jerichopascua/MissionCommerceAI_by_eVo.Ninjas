# Sim.PesoWeb 3D customer simulation (prototype)

An animated, isometric 3D store (three.js): shoppers walk in, pick from coloured shelves and pay, with a clock, speed control (1x to 100x),
camera views, KPIs and an event log. The entry flow is Tenant, Branch, Scenario, Summary, then the 3D world.

**Status: a visual prototype. It is not connected to Sim.PesoWeb yet.**

- The data source says `LOCAL MOCK`: the tenants (ABC Grocery, Kopi Kita, Mabuhay), branches, scenarios and every number are invented
  inside `index.html`. It makes no API calls.
- It loads three.js from a CDN, so it needs an internet connection.
- `BRIEF.txt` is the design brief it was built from (the rule in it: do not invent the Sim.PesoWeb API).

Open: `ui/sim3d/index.html` in a browser (or `python -m http.server` at the repo root and open `/ui/sim3d/`).

**What connecting it would take:** replay a recorded simulated day (the action log and day report that `sim/` writes under `sim/runs/<world>/`)
as the scene's event stream, so the 3D shoppers are the simulator's own shoppers and the KPIs are PesoWeb's own numbers.
