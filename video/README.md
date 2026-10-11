# Rush Sale presentation video

`MissionCommerce_RushSale.mp4` (about 2.5 minutes, 1280x720, spoken voiceover) shows the story end to end with the real screens:
the AI finds batches that will expire unsold, proposes the rush sale, the manager puts it on sale and tells the registered customers,
a first-time customer registers on the phone (and can install the app), reserves the clearance items, and the cashier keys in the
reference to ring them up.

To make it again (PesoWeb on :5071 and :4200, `customer-app/SERVE.cmd` on :8090):

1. `python sim/scripts/rush_sale_demo_data.py` (once: batches with expiry dates, today's sales, the AI run; take a backup first)
2. `python video/record_scenes.py` (captures the real screens into `video/frames/`)
3. `python video/make_video.py` (cards, captions, voiceover with Windows' built-in voice, writes the mp4)

## The 3D shop concept clip (roadmap scene)

`python video/record_sim3d.py` records a short, clean clip of the 3D shop-simulation prototype (`ui/sim3d`, mock data) into
`video/sim3d_concept.mp4`, labelled "CONCEPT, MOCK DATA". `make_pitch.py` puts it in the roadmap scene of the short and full cuts. It is a
concept: the data is invented inside the prototype and it is not driven by the simulator yet.

## Cuts

`python video/make_pitch.py --cut pitch|short|full` (see `Docs/demo-video-plan.md`). The AMD scene stays a DRAFT until
`results/amd-session.json` is a real AMD run; `--final` refuses otherwise.
