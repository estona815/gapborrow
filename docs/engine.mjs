// Browser port of baseline/model.py and engine.py. The Python version remains
// the reference for verifying allocations and the event-period alternatives.
const strategies = ['strict', 'gap', 'deadline'];
const bounded = (n, min, max) => Number.isInteger(n) && min <= n && n <= max;
const fits = (start, end, bookings, buffer) =>
  bookings.every(b => end + buffer <= b.start || b.end + buffer <= start);

function firstFit(request, lower, endBy, bookings, buffer) {
  for (let start = lower; start + request.duration <= endBy; start++) {
    if (fits(start, start + request.duration, bookings, buffer)) {
      return { id: request.id, start, end: start + request.duration };
    }
  }
  return null;
}

function schedule(requests, buffer, strategy) {
  const ordered = strategy === 'deadline'
    ? [...requests].sort((a, b) => a.deadline - b.deadline) : requests;
  const bookings = [], rejected = [], decisions = new Map();
  let cursor = 0;
  for (const r of ordered) {
    const lower = strategy === 'strict' ? Math.max(r.release, cursor) : r.release;
    const booking = firstFit(r, lower, r.deadline, bookings, buffer);
    if (booking) {
      bookings.push(booking);
      if (strategy === 'strict') cursor = booking.end + buffer;
    } else {
      rejected.push(r.id);
      if (strategy === 'gap') decisions.set(r.id, [...bookings]);
    }
  }
  return { bookings, rejected, decisions };
}

function explain(r, earlier, buffer) {
  if (r.duration > r.deadline - r.release) {
    return { code: 'WINDOW_TOO_SHORT', message: 'The requested duration exceeds the available window.', blocking_requests: [] };
  }
  const bufferConflict = buffer > 0 && firstFit(r, r.release, r.deadline, earlier, 0);
  const blockers = earlier.filter(b => {
    for (let t = r.release; t + r.duration <= r.deadline; t++) {
      if (!fits(t, t + r.duration, [b], buffer)) return true;
    }
    return false;
  });
  return {
    code: bufferConflict ? 'BUFFER_CONFLICT' : 'CAPACITY_CONFLICT',
    message: bufferConflict ? 'There is no slot with the required turnaround buffer.' : 'No slot fits around bookings accepted at the time.',
    blocking_requests: blockers.map(b => b.id).sort(),
  };
}

export function review(input) {
  const { horizon, inspection, lateness, requests } = input;
  if (!bounded(horizon, 1, 48) || !bounded(inspection, 0, 48) ||
      !bounded(lateness, 0, 48) || !Array.isArray(requests) ||
      !bounded(requests.length, 1, 30)) {
    throw new Error('Use a horizon of 1–48 slots, buffers of 0–48 slots, and 1–30 requests.');
  }
  const ids = new Set();
  for (const r of requests) {
    if (typeof r.id !== 'string' || !/^[A-Za-z0-9_-]{1,12}$/.test(r.id) ||
        ids.has(r.id) || !bounded(r.release, 0, horizon - 1) ||
        !bounded(r.deadline, r.release + 1, horizon) || !bounded(r.duration, 1, 48)) {
      throw new Error('Use unique request labels and valid integer times within the operating horizon.');
    }
    ids.add(r.id);
  }
  const buffer = inspection + lateness;
  const output = {};
  for (const strategy of strategies) {
    const { bookings, rejected, decisions } = schedule(requests, buffer, strategy);
    const reasons = strategy === 'gap' ? requests.filter(r => decisions.has(r.id)).map(r => {
      const firstLateStart = Math.max(r.release, r.deadline - r.duration + 1);
      const slot = firstFit(r, firstLateStart, horizon, bookings, buffer);
      const alternative = slot ? {
        start: slot.start, end: slot.end, deadline_extension: slot.end - r.deadline,
      } : null;
      return { id: r.id, ...explain(r, decisions.get(r.id), buffer), alternative };
    }) : [];
    output[strategy] = { served: bookings.length, rejected, bookings, reasons };
  }
  return {
    schema: 'gapborrow-browser-review/v1', input, effective_buffer: buffer, strategies: output,
    limitations: ['One device with integer time slots.', 'Independent alternatives are not reservations.'],
  };
}
