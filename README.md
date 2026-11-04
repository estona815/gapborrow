# GapBorrow · event prototype

GapBorrow compares booking policies for one shared device. It uses synthetic requests and does not make reservations. Start it with `python3 app.py`, then open the printed loopback URL.

## New work on November 5, 2026

A rejected request now shows the earliest later-deadline slot that can fit around the final protected-gap schedule. The suggested slot retains the requested duration and all existing buffers. The displayed extension is the number of slots by which the original deadline would have to move. If no slot fits within the operating horizon, the app says so.

The rejection explanation still uses bookings known at decision time. The alternative uses the final plan so it cannot collide with a later accepted request. Suggestions for multiple rejected requests are evaluated independently and can compete for the same slot. They do not reserve a slot.

The October 20 research model, examples, and previous reference outputs are included in `baseline/`. The original staff-review interface and explanation logic were also pre-event work. OpenAI Codex assisted development and verification. All cases are synthetic. The software does not demonstrate field impact or participant understanding.

Run `python3 -m unittest -v` to check the baseline schedule, HTTP routes, rejection explanation, and alternative-slot calculation.

## English browser demo

The `docs/` directory contains a static English interface and a browser port of the scheduling engine. Try the [GitHub Pages demo](https://estona815.github.io/gapborrow/) or serve the directory locally with `python3 -m http.server 8878 --bind 127.0.0.1 --directory docs`. Calculations stay in the browser.

Watch the [75-second captioned walkthrough](https://github.com/estona815/gapborrow/releases/tag/stemergent-2026-demo), or try this example in the live demo:

1. Select **Fully booked horizon**. At 4 slots, the protected-gap policy has no alternative for the rejected request.
2. Increase **Operating horizon** to 12 and select **Compare policies**. The accepted bookings remain in place. The rejected request gets slots 4–6 as a possible alternative, requiring a two-slot deadline extension.
3. Select **Download report** to inspect the exact inputs, schedules, and alternative in JSON. The alternative is for individual review and does not reserve a slot.

Run `node --test browser-parity.test.mjs` with Python 3 available. This compares all three strategies, rejection reason codes, blocking requests and alternative slots against the Python implementation over 260 synthetic inputs.
