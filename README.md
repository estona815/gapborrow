# GapBorrow · event prototype

GapBorrow compares booking policies for one shared device. It uses synthetic requests and does not make reservations. Start it with `python3 app.py`, then open the printed loopback URL.

## New work on November 5, 2026

A rejected request now shows the earliest later-deadline slot that can fit around the final protected-gap schedule. The suggested slot retains the requested duration and all existing buffers. The displayed extension is the number of slots by which the original deadline would have to move. If no slot fits within the operating horizon, the app says so.

The rejection explanation still uses bookings known at decision time. The alternative uses the final plan so it cannot collide with a later accepted request. Suggestions for multiple rejected requests are evaluated independently and can compete for the same slot. They do not reserve a slot.

The October 20 research model, examples, and previous reference outputs are included in `baseline/`. The original staff-review interface and explanation logic were also pre-event work. OpenAI Codex assisted development and verification. All cases are synthetic. The software does not demonstrate field impact or participant understanding.

Run `python3 -m unittest -v` to check the baseline schedule, HTTP routes, rejection explanation, and alternative-slot calculation.
