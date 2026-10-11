# Rush Sale presentation video

`MissionCommerce_RushSale.mp4` (about 2.5 minutes, 1280x720, spoken voiceover) shows the story end to end with the real screens:
the AI finds batches that will expire unsold, proposes the rush sale, the manager puts it on sale and tells the registered customers,
a first-time customer registers on the phone (and can install the app), reserves the clearance items, and the cashier keys in the
reference to ring them up.

To make it again (PesoWeb on :5071 and :4200, `customer-app/SERVE.cmd` on :8090):

1. `python sim/scripts/rush_sale_demo_data.py` (once: batches with expiry dates, today's sales, the AI run; take a backup first)
2. `python video/record_scenes.py` (captures the real screens into `video/frames/`)
3. `python video/make_video.py` (cards, captions, voiceover with Windows' built-in voice, writes the mp4)
