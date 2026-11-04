"""Decision-time explanations around the immutable pre-event research model."""
import hashlib
import json
from pathlib import Path
import re
import sys

RESEARCH = Path(__file__).resolve().with_name("baseline")
sys.path.insert(0, str(RESEARCH))
from model import Request, fits, schedule, validate  # noqa: E402


def integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name}: {low}~{high} 사이의 정수를 입력하세요.")
    return value


def parse(payload):
    if not isinstance(payload, dict) or set(payload) != {"horizon", "inspection", "lateness", "requests"}:
        raise ValueError("대여 조건과 신청 목록 형식을 확인하세요.")
    horizon = integer(payload["horizon"], "운영 시간", 1, 48)
    inspection = integer(payload["inspection"], "점검 시간", 0, 48)
    lateness = integer(payload["lateness"], "반납 여유", 0, 48)
    items = payload["requests"]
    if not isinstance(items, list) or not 1 <= len(items) <= 30:
        raise ValueError("신청은 1~30건을 입력하세요.")
    requests = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {"id", "release", "deadline", "duration"}:
            raise ValueError("신청 항목 형식을 확인하세요.")
        if not isinstance(item["id"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,12}", item["id"]):
            raise ValueError("신청 표시는 12자 이하 영문·숫자·밑줄·하이픈을 사용하세요.")
        for key in ("release", "deadline", "duration"):
            integer(item[key], item["id"]+" "+key, 0 if key == "release" else 1, 48)
        requests.append(Request(**item))
    try:
        validate(requests, horizon, inspection+lateness)
    except ValueError as exc:
        raise ValueError("중복 신청 표시 또는 운영 시간 밖의 시작·마감 조건을 확인하세요.") from exc
    return requests, horizon, inspection, lateness


def explain(request, earlier, inspection, lateness):
    if request.duration > request.deadline-request.release:
        return {"code": "WINDOW_TOO_SHORT", "message": "요청 길이가 가능한 시간보다 깁니다.", "blocking_requests": []}
    slots = range(request.release, request.deadline-request.duration+1)
    zero_buffer_possible = any(fits(t, t+request.duration, earlier, 0) for t in slots)
    code = "BUFFER_CONFLICT" if zero_buffer_possible and inspection+lateness else "CAPACITY_CONFLICT"
    if code == "BUFFER_CONFLICT":
        message = "점검·반납 여유 시간을 확보할 수 없습니다." if lateness else "점검 시간을 확보할 수 없습니다."
    else:
        message = "앞선 신청과 겹치지 않는 대여 시간이 없습니다."
    blockers = sorted({b.id for t in slots for b in earlier
                       if not fits(t, t+request.duration, [b], inspection+lateness)})
    return {"code": code, "message": message, "blocking_requests": blockers}


def next_feasible_slot(request, bookings, horizon, buffer):
    """Find the earliest deadline extension without moving confirmed bookings."""
    first_late_start = max(request.release, request.deadline - request.duration + 1)
    for start in range(first_late_start, horizon - request.duration + 1):
        end = start + request.duration
        if fits(start, end, bookings, buffer):
            return {"start": start, "end": end, "deadline_extension": end - request.deadline}
    return None


def calculate(payload):
    requests, horizon, inspection, lateness = parse(payload)
    total_buffer = inspection+lateness
    strategies = {}
    for strategy in ("strict", "gap", "deadline"):
        bookings, rejected = schedule(requests, horizon, total_buffer, strategy)
        reasons = []
        if strategy == "gap":
            # Explain the decision when it occurred, not against later bookings.
            # Otherwise a later backfill could obscure the original buffer conflict.
            for index, request in enumerate(requests):
                if request.id in rejected:
                    before, _ = schedule(requests[:index], horizon, total_buffer, strategy)
                    reasons.append({
                        "id": request.id,
                        **explain(request, before, inspection, lateness),
                        "alternative": next_feasible_slot(request, bookings, horizon, total_buffer),
                    })
        strategies[strategy] = {
            "served": len(bookings), "rejected": rejected,
            "bookings": [{"id": b.id, "start": b.start, "end": b.end} for b in bookings],
            "reasons": reasons,
        }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return {"schema": "gapborrow-review/v2", "state": "LOCAL_RESEARCH_NOT_A_REAL_BOOKING",
            "pre_event_created": "2026-10-20", "input": payload,
            "input_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
            "effective_buffer": total_buffer, "strategies": strategies,
            "limitations": ["One device, fixed known integer windows.",
                            "Changing inputs computes a new plan; no real reservations are changed.",
                            "Lateness allowance is a chosen bound, not a measured probability or guarantee.",
                            "No field validation or general fairness/optimality claim."]}
