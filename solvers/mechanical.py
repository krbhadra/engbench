"""Mechanical grader: AABB fit + collision + clearance checks.

No CAD engine needed — axis-aligned bounding boxes are enough to catch
overlap and clearance violations, which is what these tasks test.
"""
from __future__ import annotations


def _box(position, size):
    x, y, z = position
    w, d, h = size
    return (x, y, z, x + w, y + d, z + h)


def _overlap(a, b):
    ax0, ay0, az0, ax1, ay1, az1 = a
    bx0, by0, bz0, bx1, by1, bz1 = b
    return ax0 < bx1 and ax1 > bx0 and ay0 < by1 and ay1 > by0 and az0 < bz1 and az1 > bz0


def _gap(a, b):
    """Shortest axis-aligned gap between two boxes; 0 or negative if overlapping."""
    ax0, ay0, az0, ax1, ay1, az1 = a
    bx0, by0, bz0, bx1, by1, bz1 = b
    dx = max(bx0 - ax1, ax0 - bx1, 0)
    dy = max(by0 - ay1, ay0 - by1, 0)
    dz = max(bz0 - az1, az0 - bz1, 0)
    if dx == 0 and dy == 0 and dz == 0:
        return 0.0
    return (dx ** 2 + dy ** 2 + dz ** 2) ** 0.5


def grade(task: dict, output: dict) -> dict:
    violations = []
    sizes = {c["id"]: c["size"] for c in task["components"]}
    placements = {p["id"]: p["position"] for p in output.get("placements", [])}

    missing = sizes.keys() - placements.keys()
    if missing:
        violations.append(f"missing placements for: {sorted(missing)}")
        return {"passed": False, "violations": violations}

    boxes = {cid: _box(placements[cid], sizes[cid]) for cid in sizes}
    ex, ey, ez = task["enclosure"]["size"]

    for cid, (x0, y0, z0, x1, y1, z1) in boxes.items():
        if x0 < 0 or y0 < 0 or z0 < 0 or x1 > ex or y1 > ey or z1 > ez:
            violations.append(f"{cid} exceeds enclosure bounds")

    ids = list(boxes)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            if _overlap(boxes[a], boxes[b]):
                violations.append(f"{a} overlaps {b}")

    for rule in task.get("min_clearance", []):
        a, b = rule["pair"]
        required = rule["distance"]
        actual = _gap(boxes[a], boxes[b])
        if actual < required:
            violations.append(
                f"{a}-{b} clearance {actual:.1f} < required {required}"
            )

    return {"passed": len(violations) == 0, "violations": violations}
