"""Pre-event synthetic research, 2026-10-20. Not a lending-system integration.

One device, fixed integer time slots, known request windows, no late returns.
Gap insertion preserves earlier accepted bookings; it is not globally optimal.
"""
from dataclasses import asdict, dataclass
from itertools import product
import argparse
import json
from pathlib import Path


@dataclass(frozen=True)
class Request:
    id: str
    release: int
    deadline: int
    duration: int


@dataclass(frozen=True)
class Booking:
    id: str
    start: int
    end: int


def validate(requests, horizon, turnaround):
    if type(horizon) is not int or horizon < 1:
        raise ValueError("horizon must be a positive integer")
    if type(turnaround) is not int or turnaround < 0:
        raise ValueError("turnaround must be a nonnegative integer")
    seen = set()
    for r in requests:
        if not isinstance(r.id, str) or not r.id.strip() or r.id in seen:
            raise ValueError("request IDs must be unique nonempty strings")
        seen.add(r.id)
        if any(type(v) is not int for v in (r.release, r.deadline, r.duration)):
            raise ValueError("request times must be integers, not booleans")
        if not 0 <= r.release < r.deadline <= horizon or r.duration < 1:
            raise ValueError("invalid request window or duration")


def fits(start, end, bookings, turnaround):
    return all(end + turnaround <= b.start or b.end + turnaround <= start
               for b in bookings)


def schedule(requests, horizon, turnaround=0, strategy="gap"):
    """Never move an accepted booking. 'strict' enforces head-of-line order.

    'deadline' is a comparator that changes queue priority; it offers no
    earlier-queue protection guarantee. Rejected requests get no reservation.
    """
    validate(requests, horizon, turnaround)
    if strategy not in {"strict", "gap", "deadline"}:
        raise ValueError("unknown strategy")
    ordered = list(requests)
    if strategy == "deadline":
        ordered.sort(key=lambda r: r.deadline)  # Stable queue-order tie break.
    bookings, rejected, cursor = [], [], 0
    for r in ordered:
        lower = max(r.release, cursor) if strategy == "strict" else r.release
        candidates = range(lower, r.deadline - r.duration + 1)
        start = next((t for t in candidates
                      if fits(t, t + r.duration, bookings, turnaround)), None)
        if start is None:
            rejected.append(r.id)
        else:
            bookings.append(Booking(r.id, start, start + r.duration))
            if strategy == "strict":
                cursor = start + r.duration + turnaround
    return bookings, rejected


def optimal_count(requests, horizon, turnaround=0):
    """Independent small-instance exhaustive cardinality upper bound.

    Does not protect queue order. Never use it to claim the greedy policy is
    optimal or equally fair. Limited to <=5 requests and <=12 slots.
    """
    validate(requests, horizon, turnaround)
    if len(requests) > 5 or horizon > 12:
        raise ValueError("oracle supports only small synthetic instances")
    choices = [[None] + list(range(r.release, r.deadline-r.duration+1))
               for r in requests]
    best = 0
    for placement in product(*choices):
        intervals = sorted((t, t+r.duration) for r, t in zip(requests, placement)
                           if t is not None)
        if len(intervals) <= best:
            continue
        if all(a[1] + turnaround <= b[0]
               for a, b in zip(intervals, intervals[1:])):
            best = len(intervals)
    return best


def evaluate_case(case):
    requests = [Request(**r) for r in case["requests"]]
    horizon, turnaround = case["horizon"], case["turnaround"]
    result = {"case": case["id"], "synthetic": True, "note": case["note"],
              "horizon": horizon, "turnaround": turnaround,
              "requests": case["requests"], "strategies": {}}
    for strategy in ("strict", "gap", "deadline"):
        bookings, rejected = schedule(requests, horizon, turnaround, strategy)
        result["strategies"][strategy] = {
            "served": len(bookings), "rejected": rejected,
            "bookings": [asdict(b) for b in bookings],
            "occupied_slots": sum(b.end-b.start for b in bookings),
        }
    result["unconstrained_cardinality_upper_bound"] = optimal_count(
        requests, horizon, turnaround)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path,
                        default=Path(__file__).with_name("cases.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text())
    report = {"status": "PRE_EVENT_SYNTHETIC_RESEARCH_NOT_FIELD_VALIDATION",
              "created_date": "2026-10-20", "results": [evaluate_case(c) for c in cases],
              "limitations": ["Fixed known windows; one device; integer slots",
                              "No real students, inventory, late returns or staff validation",
                              "No general optimality, fairness or real-impact claim"]}
    with args.output.open("x") as f:
        f.write(json.dumps(report, indent=2)+"\n")
    print(json.dumps({"output": str(args.output), "cases": len(cases),
                      "served": [{"case": r["case"], **{
                          k: v["served"] for k, v in r["strategies"].items()}}
                          for r in report["results"]]}))


if __name__ == "__main__":
    main()
