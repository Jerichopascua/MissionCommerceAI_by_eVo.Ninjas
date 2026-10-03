# Sim.PesoWeb UI prototype

A clickable, animated design mock of the Sim.PesoWeb control panel. **All numbers are illustrative.** A "Prototype · illustrative data" badge is always shown in the header. Use this for design review and storyboarding. The final demo video must be recorded from the real app with real run numbers.

The production UI will be an Angular app in PesoWeb's stack (Angular 16, Bootstrap 5.3, ApexCharts) and shares PesoWeb's UI kit, so the Sim and the live system look the same. The environment switcher (Sim World / Live) is already in the sidebar for that reason.

## Open it
Open `index.html` in Chrome (no build step, no network needed).

| URL | What you get |
|---|---|
| `index.html` | Control Center, animated |
| `index.html#live` | Day-to-Day Live (clock ticks, transactions stream, an incident is injected around 11:40 sim time) |
| `index.html#quick` | Quick Sim fast-forward with the AMD compute panel |
| `index.html#scenario` | Scenario Builder (click Generate to watch the AI draft the YAML) |
| `index.html#caught` | Caught vs Missed (click any row to open the Investigator) |
| `index.html#missions` | Mission detection and Week 0 vs Week 3 |
| add `?theme=dark` | Dark ninja theme (matches the slide deck) |
| add `?freeze` | Jump animations to a representative moment (used for the PNGs) |
| add `?freeze&drawer` (on `#caught`) | Investigator already open |
| add `?title` | Title card overlay ("Fast-forward a retail world.") |

`screens/*.png` are frozen renders of each screen.

## Design notes
- Light app shell, PesoWeb-blue primary, like the reference "eGov Agent" demo. Dark theme for presentation.
- Investigator shows live steps with checkmarks while it works, then an evidence card.
- Cash findings are worded "unexplained cash variance", never theft.
- Shoppers follow habits: the live feed picks who shops by hour and by branch vertical (night-shift staff only appear late, motorcycle parts only at the motorcycle branch).
