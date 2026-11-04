import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import test from 'node:test';
import { review } from './docs/engine.mjs';

test('browser port matches Python for published fixtures and seeded scenarios', () => {
  const oracle = String.raw`
import json, random
from engine import calculate
from test_app import fixture

rng = random.Random(712)
inputs = [fixture(i) for i in range(4)]
for _ in range(256):
    horizon = rng.randint(2, 24)
    rows = []
    for i in range(rng.randint(1, 10)):
        release = rng.randrange(horizon)
        rows.append(dict(id=f"R{i}", release=release,
                         deadline=rng.randint(release + 1, horizon),
                         duration=rng.randint(1, 8)))
    inputs.append(dict(horizon=horizon, inspection=rng.randint(0, 2),
                       lateness=rng.randint(0, 2), requests=rows))
print(json.dumps([calculate(value) for value in inputs]))
`;
  const references = JSON.parse(execFileSync('python3', ['-B', '-c', oracle], {encoding: 'utf8'}));
  assert.equal(references.length, 260);
  for (const reference of references) {
    const actual = review(reference.input);
    assert.equal(actual.effective_buffer, reference.effective_buffer);
    const withoutMessage = ({ message, ...reason }) => reason;
    for (const [strategy, expected] of Object.entries(reference.strategies)) {
      const received = actual.strategies[strategy];
      assert.deepEqual(received.bookings, expected.bookings);
      assert.deepEqual(received.rejected, expected.rejected);
      assert.deepEqual(received.reasons.map(withoutMessage), expected.reasons.map(withoutMessage));
    }
  }
});
